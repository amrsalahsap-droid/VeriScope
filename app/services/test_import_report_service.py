import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.test_result import TestCase, TestRun, TestResult
from app.models.test_import_report import TestImportQualityReport
from app.services.requirement_test_alignment_gate import RequirementTestAlignmentGate
from app.schemas.test_import_report import (
    TestImportQualityReportResponse,
    ImportQualityConflictExample
)

logger = logging.getLogger(__name__)

class TestImportQualityReportService:
    @classmethod
    def generate_and_persist_report(
        cls,
        db: Session,
        import_id: str,
        repository_id: uuid.UUID,
        pull_request_id: Optional[uuid.UUID] = None,
        test_run: Optional[TestRun] = None,
        test_cases: Optional[List[TestCase]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates test metadata quality against PR Acceptance Criteria,
        generates the Import Quality Report payload, persists it to DB, and returns it.
        """
        # Fetch PR Acceptance Criteria
        acs: List[AcceptanceCriterion] = []
        if pull_request_id:
            acs = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.pull_request_id == pull_request_id,
                AcceptanceCriterion.status != "REJECTED"
            ).all()

        # Fetch TestCases if not provided
        if test_cases is None:
            if test_run:
                # Get test cases linked to test results in this run
                results = db.query(TestResult).filter(TestResult.test_run_id == test_run.id).all()
                tc_ids = {r.test_case_id for r in results if r.test_case_id}
                test_cases = db.query(TestCase).filter(TestCase.id.in_(tc_ids)).all() if tc_ids else []
            else:
                test_cases = db.query(TestCase).filter(
                    TestCase.repository_id == repository_id,
                    TestCase.is_active == True
                ).all()

        # Run Requirement/Test Alignment Gate
        gate = RequirementTestAlignmentGate()
        summary = gate.evaluate_all_tests(test_cases or [], acs or [])

        # Counts
        tests_total = test_run.total_tests if test_run else len(test_cases or [])
        tests_passed = test_run.passed_tests if test_run else len([t for t in (test_cases or []) if getattr(t, "status", "").lower() == "passed"])
        tests_failed = test_run.failed_tests if test_run else len([t for t in (test_cases or []) if getattr(t, "status", "").lower() == "failed"])
        tests_skipped = test_run.skipped_tests if test_run else len([t for t in (test_cases or []) if getattr(t, "status", "").lower() == "skipped"])

        tests_with_ref = summary.tests_with_declared_ac_ref
        verified_cnt = summary.verified_mappings
        suggested_strong_cnt = summary.suggested_strong
        suggested_weak_cnt = summary.suggested_weak
        # summary.conflicted is the legacy conflict counter; true declared-vs-
        # semantic conflicts are now reported via metadata_conflict_semantic_match
        # under the 7-state model, so both must be included here.
        conflicted_cnt = summary.conflicted + summary.metadata_conflict_semantic_match
        ambiguous_cnt = summary.ambiguous
        unresolved_cnt = summary.unresolved

        # Determine metadata_quality_status
        if conflicted_cnt > 0:
            if (conflicted_cnt / max(tests_with_ref, 1)) >= 0.3 or (verified_cnt + suggested_strong_cnt) == 0:
                quality_status = "FAIL"
            else:
                quality_status = "PARTIAL"
        elif ambiguous_cnt > 0 or unresolved_cnt > 0 or suggested_weak_cnt > 0:
            quality_status = "PARTIAL"
        else:
            quality_status = "PASS"

        # Determine mapping_confidence_impact
        if quality_status == "FAIL" or conflicted_cnt > 0:
            confidence_impact = "HIGH"
        elif quality_status == "PARTIAL" or ambiguous_cnt > 0 or unresolved_cnt > 0:
            confidence_impact = "MEDIUM"
        elif tests_with_ref < tests_total and tests_total > 0:
            confidence_impact = "LOW"
        else:
            confidence_impact = "NONE"

        # Build warnings
        warnings: List[str] = []
        if conflicted_cnt > 0:
            warnings.append(
                "Some test cases declare AC references that conflict with the uploaded Acceptance Criteria definitions. "
                "These mappings require review and will not count as confirmed coverage."
            )
        if unresolved_cnt > 0:
            warnings.append("Some test cases reference AC IDs that were not found in the uploaded Acceptance Criteria list.")
        if ambiguous_cnt > 0:
            warnings.append("Some declared AC references match multiple Acceptance Criteria definitions ambiguously.")
        if tests_with_ref == 0 and tests_total > 0:
            warnings.append("No external AC references (e.g. AC-01) were found in test case names or metadata.")

        # Build conflict/warning examples (up to top 5)
        examples: List[Dict[str, Any]] = []
        ac_by_ref = {str(getattr(ac, "ac_id", getattr(ac, "id", ""))).upper(): ac for ac in acs}
        ac_by_id = {str(ac.id): ac for ac in acs}

        for res in summary.alignment_results:
            if len(examples) >= 5:
                break

            status_upper = res.review_status.upper()
            if status_upper in ("CONFLICTED", "AMBIGUOUS", "UNRESOLVED") or res.conflict_detected:
                dec_ref = res.declared_ac_ref or ""
                dec_ac_text = res.declared_ac_text or ""

                sem_ref = res.semantic_best_match_ac_ref or ""
                sem_text = res.semantic_best_match_ac_text or ""

                examples.append({
                    "test_name": res.test_name,
                    "declared_ac_ref": dec_ref,
                    "declared_ac_text": dec_ac_text,
                    "semantic_best_match_ref": str(sem_ref),
                    "semantic_best_match_text": sem_text,
                    "status": "CONFLICTED" if res.conflict_detected else status_upper,
                    "recommended_action": "Review and resolve mapping"
                })

        report_dict = {
            "import_id": str(import_id),
            "tests_total": tests_total,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "tests_skipped": tests_skipped,
            "tests_with_declared_ac_refs": tests_with_ref,
            "verified_mappings": verified_cnt,
            "suggested_strong": suggested_strong_cnt,
            "suggested_weak": suggested_weak_cnt,
            "conflicted_refs": conflicted_cnt,
            "ambiguous_refs": ambiguous_cnt,
            "unresolved_refs": unresolved_cnt,
            "metadata_quality_status": quality_status,
            "mapping_confidence_impact": confidence_impact,
            "warnings": warnings,
            "examples": examples
        }

        # Upsert report in database
        try:
            existing = db.query(TestImportQualityReport).filter(
                TestImportQualityReport.import_id == str(import_id)
            ).first()

            if existing:
                existing.metadata_quality_status = quality_status
                existing.mapping_confidence_impact = confidence_impact
                existing.report_json = report_dict
                existing.updated_at = datetime.utcnow()
            else:
                report_rec = TestImportQualityReport(
                    id=uuid.uuid4(),
                    import_id=str(import_id),
                    repository_id=repository_id,
                    pull_request_id=pull_request_id,
                    metadata_quality_status=quality_status,
                    mapping_confidence_impact=confidence_impact,
                    report_json=report_dict,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(report_rec)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to persist TestImportQualityReport for import_id={import_id}: {str(e)}")
            db.rollback()

        return report_dict

    @classmethod
    def get_report_by_import_id(cls, db: Session, import_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a persisted report by import ID."""
        rec = db.query(TestImportQualityReport).filter(
            TestImportQualityReport.import_id == str(import_id)
        ).first()
        return rec.report_json if rec else None

    @classmethod
    def get_latest_report(cls, db: Session, repository_id: uuid.UUID, pull_request_id: Optional[uuid.UUID] = None) -> Optional[Dict[str, Any]]:
        """Retrieves the latest persisted report for a repository / PR."""
        query = db.query(TestImportQualityReport).filter(
            TestImportQualityReport.repository_id == repository_id
        )
        if pull_request_id:
            query = query.filter(TestImportQualityReport.pull_request_id == pull_request_id)
        
        rec = query.order_by(TestImportQualityReport.created_at.desc()).first()
        return rec.report_json if rec else None
