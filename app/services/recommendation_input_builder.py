import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestRun, TestResult, TestCase
from app.models.coverage import CoverageReport, CoverageFileEntry
from app.models.fragility_pattern import FragilityPattern
from app.models.user import Workspace
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.behavior_evidence import BehaviorEvidence
from app.models.journey_behavior import JourneyBehavior
from app.models.business_intent import BusinessIntentOverride
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.requirement_package import RequirementPackage
from app.models.requirement_group import RequirementGroup
from app.services.repository_readiness import RepositoryReadinessService
from app.services.ac_test_mapping_service import ACTestMappingService
from app.schemas.recommendation import RecommendationInputSnapshotResponse

logger = logging.getLogger("veriscope.recommendation_input_builder")


def _safe_message(exc: Exception, max_len: int = 200) -> str:
    """Return a safe, single-line, truncated string from an exception."""
    msg = str(exc).replace("\r", " ").replace("\n", " ") if str(exc) else type(exc).__name__
    return msg[:max_len]


_SOURCE_FILE_EXCLUDES = (".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".lock")
_TEST_FILE_SUFFIXES = ("_test.py", "test.py", ".spec.ts", ".test.ts", ".test.js", ".spec.js")


def _build_readiness_input_summary_for_snapshot(
    db: Session,
    repository_id: UUID,
    pull_request_id: UUID,
    pr: Optional[PullRequest],
    latest_coverage: Optional[CoverageReport],
    changed_files: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return the normalized readiness input summary consumed by recommendation pages.

    Uses the same authoritative sources as the readiness cards:
    - ACTestMappingService for AC mapping summary
    - Granular TestResult rows for current PR test counts
    - CoverageReport.commit_sha vs PR head SHA for coverage currency
    - Changed files vs CoverageFileEntry paths for changed-file coverage
    """
    mapping_res = ACTestMappingService().build_mappings_for_pr(
        db=db,
        repository_id=repository_id,
        pull_request_id=pull_request_id,
    )
    ms = mapping_res.get("mapping_summary") or {}

    user_confirmed = int(ms.get("user_confirmed", 0) or 0)
    auto_trusted = (
        int(ms.get("evidence_verified_aligned", 0) or 0)
        + int(ms.get("metadata_conflict_semantic_match", 0) or 0)
        + int(ms.get("suggested", 0) or 0)
    )

    latest_run = db.query(TestRun).filter(
        TestRun.repository_id == repository_id,
        TestRun.pull_request_id == pull_request_id,
    ).order_by(TestRun.created_at.desc()).first()

    total = passed = failed = skipped = 0
    if latest_run:
        base_q = db.query(func.count(TestResult.id)).filter(
            TestResult.test_run_id == latest_run.id
        )
        total = base_q.scalar() or 0
        passed = base_q.filter(
            func.lower(TestResult.status).in_(["passed", "success"])
        ).scalar() or 0
        failed = base_q.filter(
            func.lower(TestResult.status).in_(["failed", "failure", "error"])
        ).scalar() or 0
        skipped = base_q.filter(
            func.lower(TestResult.status).in_(["skipped", "skip"])
        ).scalar() or 0

    coverage_current = False
    coverage_sha_mismatch = False
    if latest_coverage and pr:
        coverage_current = bool(latest_coverage.commit_sha == pr.head_commit_sha)
        coverage_sha_mismatch = bool(
            latest_coverage.commit_sha and latest_coverage.commit_sha != pr.head_commit_sha
        )

    source_changed = []
    test_changed = []
    for f in changed_files:
        path = f.get("file_path") or f.get("path") or ""
        lower = path.lower()
        if lower.endswith(_SOURCE_FILE_EXCLUDES):
            continue
        if any(lower.endswith(suffix) for suffix in _TEST_FILE_SUFFIXES) or "test" in lower:
            test_changed.append(path)
        else:
            source_changed.append(path)

    covered_paths: set = set()
    if latest_coverage:
        entries = db.query(CoverageFileEntry).filter(
            CoverageFileEntry.coverage_report_id == latest_coverage.id
        ).all()
        for entry in entries:
            fp = getattr(entry, "file_path", None)
            if fp:
                covered_paths.add(fp)

    changed_source_total = len(source_changed)
    changed_source_covered = sum(1 for p in source_changed if p in covered_paths)
    changed_test_total = len(test_changed)

    overall_pct = 0.0
    if latest_coverage and latest_coverage.line_coverage_ratio is not None:
        overall_pct = round(float(latest_coverage.line_coverage_ratio) * 100, 1)

    return {
        "repository_id": str(repository_id),
        "pull_request_id": str(pull_request_id),
        "pr_head_sha": pr.head_commit_sha if pr else None,
        "accepted_acs": int(ms.get("total_acs", 0) or 0),
        "trusted_ac_mappings": user_confirmed + auto_trusted,
        "auto_trusted_ac_mappings": auto_trusted,
        "user_confirmed_ac_mappings": user_confirmed,
        "review_required_ac_mappings": (
            int(ms.get("partial_support", 0) or 0)
            + int(ms.get("no_candidate", 0) or 0)
            + int(ms.get("rejected", 0) or 0)
        ),
        "metadata_conflicts": int(ms.get("metadata_conflict_semantic_match", 0) or 0),
        "partial_support": int(ms.get("partial_support", 0) or 0),
        "no_candidate": int(ms.get("no_candidate", 0) or 0),
        "current_pr_tests_total": total,
        "current_pr_tests_passed": passed,
        "current_pr_tests_failed": failed,
        "current_pr_tests_skipped": skipped,
        "coverage_is_current": coverage_current,
        "coverage_sha_mismatch": coverage_sha_mismatch,
        "changed_source_files_total": changed_source_total,
        "changed_source_files_covered": changed_source_covered,
        "changed_test_files_total": changed_test_total,
        "overall_coverage_percent": overall_pct,
    }


class RecommendationInputBuilderError(Exception):
    """Raised when a stage inside RecommendationInputBuilder fails."""

    def __init__(
        self,
        *,
        request_id: str,
        stage: str,
        original_error: Optional[Exception] = None,
        message: str = "",
    ):
        self.request_id = request_id
        self.stage = stage
        self.original_error = original_error
        self.message = _safe_message(Exception(message) if message else Exception("unknown"))
        super().__init__(
            f"RecommendationInputBuilder failed at stage '{stage}' "
            f"(request_id={request_id}): {self.message}"
        )


def _log_stage(
    *,
    request_id: str,
    stage: str,
    started: bool,
    completed: bool,
    repository_id: Optional[UUID] = None,
    pull_request_id: Optional[UUID] = None,
    records_loaded: int = 0,
    error_type: Optional[str] = None,
    error_message: str = "",
    extra: Optional[Dict[str, Any]] = None,
):
    payload = {
        "request_id": request_id,
        "stage": stage,
        "started": started,
        "completed": completed,
        "repository_id": str(repository_id) if repository_id else None,
        "pull_request_id": str(pull_request_id) if pull_request_id else None,
        "records_loaded": records_loaded,
        "error_type": error_type,
        "error_message": error_message,
    }
    if extra:
        payload.update(extra)
    if completed and not error_type:
        logger.info(json.dumps({"event": "recommendation_input_builder_stage", **payload}))
    elif completed and error_type:
        logger.error(json.dumps({"event": "recommendation_input_builder_stage_failed", **payload}))
    else:
        logger.info(json.dumps({"event": "recommendation_input_builder_stage_started", **payload}))


class RecommendationInputBuilder:
    @classmethod
    def build_snapshot(
        cls,
        db: Session,
        repository_id: UUID,
        pull_request_id: UUID,
        workspace: Workspace
    ) -> RecommendationInputSnapshotResponse:
        """
        Deterministically gathers repository + PR evidence (changed files, test runs/results,
        coverage reports/file entries, readiness, fragility patterns) and generates
        an immutable snapshot with a deterministic SHA-256 hash.

        This method is read-only. It explicitly disables autoflush so that any dirty
        pending state passed in from the caller is not flushed during the read phase.
        """
        request_id = str(uuid.uuid4())
        _log_stage(
            request_id=request_id,
            stage="build_recommendation_input",
            started=True,
            completed=False,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
        )

        try:
            # Read-only phase: prevent autoflush of any caller-pending state.
            with db.no_autoflush:
                return cls._build_snapshot_core(
                    request_id=request_id,
                    db=db,
                    repository_id=repository_id,
                    pull_request_id=pull_request_id,
                    workspace=workspace,
                )
        except SQLAlchemyError as exc:
            _log_stage(
                request_id=request_id,
                stage="build_recommendation_input",
                started=True,
                completed=True,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                error_type=type(exc).__name__,
                error_message=_safe_message(exc),
                extra={"sqlalchemy_exception": repr(exc)},
            )
            logger.exception(
                f"RecommendationInputBuilder first SQLAlchemy error "
                f"(request_id={request_id}): {exc}"
            )
            raise RecommendationInputBuilderError(
                request_id=request_id,
                stage="build_recommendation_input",
                original_error=exc,
                message=_safe_message(exc),
            ) from exc

    @classmethod
    def _build_snapshot_core(
        cls,
        request_id: str,
        db: Session,
        repository_id: UUID,
        pull_request_id: UUID,
        workspace: Workspace
    ) -> RecommendationInputSnapshotResponse:
        """Core read-only snapshot construction with per-stage logging."""

        def log(stage: str, started: bool = False, completed: bool = False, records: int = 0, error: Optional[str] = None):
            _log_stage(
                request_id=request_id,
                stage=stage,
                started=started,
                completed=completed,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                records_loaded=records,
                error_type=type(error).__name__ if error else None,
                error_message=error or "",
            )

        log("load_repository", started=True)
        # 1. Load path-backed changed-file evidence for this PR.
        log("load_pull_request", started=True)
        pr_record = db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
        log("load_pull_request", completed=True, records=1 if pr_record else 0)

        log("load_changed_files", started=True)
        from app.services.input_readiness_v2_service import InputReadinessV2Service
        changed_files_evidence = InputReadinessV2Service.get_changed_files_evidence(db, pr_record) if pr_record else {
            "changed_file_paths_available": False,
            "changed_files_source": None,
            "changed_files": [],
        }
        changed_files = [
            {
                "file_path": changed_file["path"],
                "status": changed_file["status"],
                "additions": changed_file["additions"],
                "deletions": changed_file["deletions"],
            }
            for changed_file in changed_files_evidence["changed_files"]
        ]

        # 2. Load authoritative test inventory sorted by stable identity
        test_cases = (
            db.query(TestCase)
            .filter(TestCase.repository_id == repository_id)
            .order_by(TestCase.stable_identity.asc())
            .all()
        )
        test_inventory = [
            {
                "stable_identity": tc.stable_identity,
                "canonical_identity_hash": tc.canonical_identity_hash,
                "dedupe_key": tc.dedupe_key,
                "suite_name": tc.suite_name,
                "test_name": tc.test_name,
                "raw_test_name": tc.raw_test_name,
                "normalized_test_name": tc.normalized_test_name,
                "framework_name": tc.framework_name,
                "framework_version": tc.framework_version,
                "test_type": tc.test_type,
                "automation_status": tc.automation_status,
                "source": tc.source,
                "source_metadata_json": tc.source_metadata_json,
                "file_path": tc.file_path,
                "module_or_area": tc.module_or_area,
                "owner": tc.owner,
                "tags": tc.tags,
                "is_active": tc.is_active,
                "last_seen_at": tc.last_seen_at.isoformat() if tc.last_seen_at else None,
                "last_seen_commit_sha": tc.last_seen_commit_sha,
                "inventory_snapshot_sha": tc.inventory_snapshot_sha,
                "confidence": tc.confidence,
            }
            for tc in test_cases
        ]

        # 3. Load latest CoverageReport and its file entries
        latest_coverage = (
            db.query(CoverageReport)
            .filter(CoverageReport.repository_id == repository_id)
            .order_by(CoverageReport.created_at.desc())
            .first()
        )

        coverage_files = []
        coverage_confidence = "MISSING"
        if latest_coverage:
            coverage_confidence = latest_coverage.coverage_confidence or "UNKNOWN"
            coverage_entries = (
                db.query(CoverageFileEntry)
                .filter(CoverageFileEntry.coverage_report_id == latest_coverage.id)
                .order_by(CoverageFileEntry.file_path.asc())
                .all()
            )
            coverage_files = [
                {
                    "file_path": entry.file_path,
                    "total_lines": entry.total_lines,
                    "line_coverage_ratio": entry.line_coverage_ratio,
                    "covered_lines": entry.covered_lines or [],
                    "uncovered_lines": entry.uncovered_lines or []
                }
                for entry in coverage_entries
            ]

        # 4. Load latest test run to get test counts/stats
        latest_test_run = (
            db.query(TestRun)
            .filter(TestRun.repository_id == repository_id)
            .order_by(TestRun.created_at.desc())
            .first()
        )

        # 5. Compute repository readiness
        readiness_svc = RepositoryReadinessService(db)
        readiness = readiness_svc.calculate_readiness(repository_id, workspace.id)

        # 5a. Compute normalized readiness input summary for the recommendation page.
        # This uses the same authoritative sources as the readiness cards.
        readiness_input_summary = _build_readiness_input_summary_for_snapshot(
            db=db,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            pr=pr_record,
            latest_coverage=latest_coverage,
            changed_files=changed_files,
        )

        # 6. Load active fragility patterns sorted by id
        fragility_patterns_db = (
            db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.status == "ACTIVE"
            )
            .order_by(FragilityPattern.id.asc())
            .all()
        )
        fragility_patterns = [
            {
                "pattern_id": str(p.id),
                "risk_level": p.risk_level,
                "confidence_score": 1.0 if p.confidence_level == "HIGH" else (0.6 if p.confidence_level == "MODERATE" else 0.3),
                "context": p.context or {}
            }
            for p in fragility_patterns_db
        ]

        # 7. Load discovered behaviors (repository-scoped, deterministic ordering)
        behaviors_db = (
            db.query(Behavior)
            .filter(
                Behavior.repository_id == repository_id,
                Behavior.is_deleted == False,
            )
            .order_by(Behavior.name.asc())
            .all()
        )
        behaviors_snapshot = [
            {
                "behavior_id": str(b.id),
                "name": b.name,
                "slug": b.slug,
                "confidence": b.confidence,
                "risk_level": b.risk_level,
                "journey_id": str(b.journey_id) if b.journey_id else None,
                "discovery_source": b.discovery_source,
            }
            for b in behaviors_db
        ]

        # 8. Load discovered journeys (repository-scoped, deterministic ordering)
        journeys_db = (
            db.query(Journey)
            .filter(
                Journey.repository_id == repository_id,
                Journey.is_deleted == False,
            )
            .order_by(Journey.name.asc())
            .all()
        )
        journeys_snapshot = [
            {
                "journey_id": str(j.id),
                "name": j.name,
                "slug": j.slug,
                "risk_level": j.risk_level,
            }
            for j in journeys_db
        ]

        # 9. Load behavior evidences (repository-scoped via behaviors)
        behavior_ids = [b.id for b in behaviors_db]
        behavior_evidences_db = []
        if behavior_ids:
            behavior_evidences_db = (
                db.query(BehaviorEvidence)
                .filter(BehaviorEvidence.behavior_id.in_(behavior_ids))
                .order_by(BehaviorEvidence.behavior_id.asc())
                .all()
            )
        behavior_evidences_snapshot = [
            {
                "behavior_id": str(ev.behavior_id),
                "evidence_type": ev.evidence_type,
                "source_path": ev.source_path,
                "confidence": ev.confidence,
                "excerpt": ev.excerpt[:200] if ev.excerpt else None,
            }
            for ev in behavior_evidences_db
        ]

        # 10. Load journey-behavior mappings
        journey_ids = [j.id for j in journeys_db]
        journey_mappings_db = []
        if journey_ids:
            journey_mappings_db = (
                db.query(JourneyBehavior)
                .filter(JourneyBehavior.journey_id.in_(journey_ids))
                .order_by(JourneyBehavior.journey_id.asc(), JourneyBehavior.behavior_id.asc())
                .all()
            )
        journey_mappings_snapshot = [
            {
                "journey_id": str(jb.journey_id),
                "behavior_id": str(jb.behavior_id),
                "relationship_type": jb.relationship_type,
                "confidence": jb.confidence,
            }
            for jb in journey_mappings_db
        ]

        # 11. Build confidence and journey summaries
        behavior_confidence_summary = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for b in behaviors_db:
            conf = (b.confidence or "MEDIUM").upper()
            if conf in behavior_confidence_summary:
                behavior_confidence_summary[conf] += 1
            else:
                behavior_confidence_summary["MEDIUM"] += 1

        journey_summary = {
            "total_journeys": len(journeys_db),
            "total_behaviors": len(behaviors_db),
            "total_evidences": len(behavior_evidences_db),
            "total_mappings": len(journey_mappings_db),
            "by_risk_level": {},
        }
        for j in journeys_db:
            rl = (j.risk_level or "MEDIUM").upper()
            journey_summary["by_risk_level"][rl] = journey_summary["by_risk_level"].get(rl, 0) + 1

        # 12. Load business intent override (manual AC paste)
        business_intent_override = None
        bio_override = (
            db.query(BusinessIntentOverride)
            .filter(
                BusinessIntentOverride.repository_id == repository_id,
                BusinessIntentOverride.pull_request_id == pull_request_id,
                BusinessIntentOverride.is_active == True
            )
            .order_by(BusinessIntentOverride.created_at.desc())
            .first()
        )
        if bio_override:
            business_intent_override = {
                "id": str(bio_override.id),
                "source": bio_override.source,
                "business_change_summary": bio_override.business_change_summary,
                "affected_users_journeys": bio_override.affected_users_journeys,
                "risk_notes": bio_override.risk_notes,
                "testing_notes": bio_override.testing_notes,
                "acceptance_criteria": bio_override.acceptance_criteria,
                "extracted_scenarios": bio_override.extracted_scenarios,
                "mapped_behaviors": bio_override.mapped_behaviors,
                "extraction_confidence": bio_override.extraction_confidence,
                "created_at": bio_override.created_at.isoformat() if bio_override.created_at else None,
            }

        # 13. Load structured requirement package (Input 2)
        requirement_package_snapshot = None
        requirement_groups_snapshot = []
        requirement_package = (
            db.query(RequirementPackage)
            .filter(
                RequirementPackage.repository_id == repository_id,
                RequirementPackage.pull_request_id == pull_request_id
            )
            .first()
        )
        if requirement_package:
            requirement_package_snapshot = {
                "id": str(requirement_package.id),
                "repository_id": str(requirement_package.repository_id),
                "pull_request_id": str(requirement_package.pull_request_id),
                "source_type": requirement_package.source_type,
                "source_id": requirement_package.source_id,
                "package_version": requirement_package.package_version,
                "status": requirement_package.status,
                "business_change_summary": requirement_package.business_change_summary,
                "affected_journeys": requirement_package.affected_journeys,
                "risk_notes": requirement_package.risk_notes,
                "invalid_test_data_examples": requirement_package.invalid_test_data_examples,
                "valid_test_data_examples": requirement_package.valid_test_data_examples,
                "security_notes": requirement_package.security_notes,
                "integration_notes": requirement_package.integration_notes,
                "out_of_scope_notes": requirement_package.out_of_scope_notes,
                "created_at": requirement_package.created_at.isoformat() if requirement_package.created_at else None,
            }

            # Load requirement groups for this package
            groups_db = (
                db.query(RequirementGroup)
                .filter(RequirementGroup.requirement_package_id == requirement_package.id)
                .order_by(RequirementGroup.group_number.asc())
                .all()
            )
            for grp in groups_db:
                requirement_groups_snapshot.append({
                    "id": str(grp.id),
                    "requirement_package_id": str(grp.requirement_package_id),
                    "group_number": grp.group_number,
                    "group_type": grp.group_type,
                    "stable_group_key": grp.stable_group_key,
                    "title": grp.title,
                    "description": grp.description,
                    "business_flow": grp.business_flow,
                    "priority": grp.priority,
                    "risk_level": grp.risk_level,
                    "source_type": grp.source_type,
                    "status": grp.status,
                })

        # 14. Load structured acceptance criteria (with stable_ac_key)
        acceptance_criteria_snapshot = []
        ac_rows = (
            db.query(AcceptanceCriterion)
            .filter(
                AcceptanceCriterion.repository_id == repository_id,
                AcceptanceCriterion.pull_request_id == pull_request_id,
                AcceptanceCriterion.status.in_(["ACCEPTED", "NEEDS_REVIEW"])
            )
            .order_by(AcceptanceCriterion.created_at.asc())
            .all()
        )
        for ac in ac_rows:
            acceptance_criteria_snapshot.append({
                "id": str(ac.id),
                "text": ac.text,
                "normalized_key": ac.normalized_key,
                "stable_ac_key": ac.stable_ac_key,
                "criterion_type": ac.criterion_type,
                "source": ac.source,
                "confidence": ac.confidence,
                "evidence_excerpt": ac.evidence_excerpt,
                "requirement_group_id": str(ac.requirement_group_id) if ac.requirement_group_id else None,
                "created_at": ac.created_at.isoformat() if ac.created_at else None,
            })

        # 15. Collect overall evidence counts
        test_runs_count = db.query(func.count(TestRun.id)).filter(TestRun.repository_id == repository_id).scalar() or 0
        coverage_reports_count = db.query(func.count(CoverageReport.id)).filter(CoverageReport.repository_id == repository_id).scalar() or 0

        evidence_counts = {
            "changed_files_count": len(changed_files),
            "test_cases_count": len(test_inventory),
            "test_runs_count": test_runs_count,
            "coverage_reports_count": coverage_reports_count,
            "active_fragility_patterns_count": len(fragility_patterns),
            "behaviors_count": len(behaviors_snapshot),
            "journeys_count": len(journeys_snapshot),
            "behavior_evidences_count": len(behavior_evidences_snapshot),
            "journey_mappings_count": len(journey_mappings_snapshot),
            "acceptance_criteria_count": len(acceptance_criteria_snapshot),
            "requirement_package_exists": int(requirement_package_snapshot is not None),
            "requirement_groups_count": len(requirement_groups_snapshot),
        }

        # 16. Compute deterministic SHA-256 hash of the content state
        # Excludes generated_at and input_snapshot_hash
        # Get business_behavior_mappings
        # Get business_behavior_mappings
        from app.models.business_behavior_mapping import BusinessBehaviorMapping
        mappings_db = db.query(BusinessBehaviorMapping).join(Behavior).filter(
            Behavior.repository_id == repository_id
        ).all()
        business_behavior_mappings_snapshot = []
        for m in mappings_db:
            business_behavior_mappings_snapshot.append({
                "id": str(m.id) if m.id else None,
                "repository_id": str(repository_id),
                "requirement_group_id": str(m.acceptance_criterion.requirement_group_id) if (m.acceptance_criterion and m.acceptance_criterion.requirement_group_id) else None,
                "acceptance_criterion_id": str(m.acceptance_criterion_id) if m.acceptance_criterion_id else None,
                "behavior_id": str(m.behavior_id),
                "behavior_scenario_id": str(m.behavior_scenario_id) if m.behavior_scenario_id else None,
                "pull_request_id": str(m.pull_request_id) if m.pull_request_id else None,
                "match_confidence": float(m.match_confidence) if m.match_confidence is not None else 0.5,
                "matched_terms": m.matched_terms,
                "reason": m.reason,
                "is_candidate_missing_scenario": m.is_candidate_missing_scenario,
            })

        # Get behavior_scenario_coverages
        from app.models.behavior_scenario_coverage import BehaviorScenarioCoverage
        coverages_db = db.query(BehaviorScenarioCoverage).filter(
            BehaviorScenarioCoverage.repository_id == repository_id
        ).all()
        behavior_scenario_coverages_snapshot = []
        for c in coverages_db:
            behavior_scenario_coverages_snapshot.append({
                "id": str(c.id) if c.id else None,
                "repository_id": str(c.repository_id),
                "behavior_id": str(c.behavior_id),
                "behavior_scenario_id": str(c.behavior_scenario_id),
                "recommendation_run_id": str(c.recommendation_run_id) if c.recommendation_run_id else None,
                "coverage_status": c.coverage_status,
                "current_pr_execution_status": c.current_pr_execution_status,
                "confidence": c.confidence,
                "reason": c.reason,
                "existing_tests": c.existing_tests,
                "suggested_scenarios": c.suggested_scenarios,
                "coverage_files": c.coverage_files,
            })

        # Derive changed_file_behavior_mappings from behavior evidence paths vs changed files
        changed_file_paths_set = {cf["file_path"].lower() for cf in changed_files}
        changed_file_behavior_mappings_snapshot = []
        for ev in behavior_evidences_db:
            if ev.source_path and ev.source_path.lower() in changed_file_paths_set:
                # Find the corresponding behavior
                beh = next((b for b in behaviors_db if b.id == ev.behavior_id), None)
                if beh:
                    changed_file_behavior_mappings_snapshot.append({
                        "file_path": ev.source_path,
                        "behavior_id": str(beh.id),
                        "behavior_name": beh.name,
                        "behavior_slug": beh.slug,
                        "impact_level": beh.risk_level or "MEDIUM",
                        "confidence": ev.confidence or "MEDIUM",
                        "evidence_type": ev.evidence_type,
                    })

        # Resolve PR head commit SHA from the same evidence-bound PR record.
        behavior_map_source_commit_sha = pr_record.head_commit_sha if pr_record else None
        behavior_map_generated_at = datetime.utcnow().isoformat()

        # Derive behavior_context_status from readiness
        behavior_context_status = "READY" if (
            changed_files_evidence["changed_file_paths_available"]
            and behaviors_snapshot
            and business_behavior_mappings_snapshot
        ) else ("PARTIAL" if behaviors_snapshot else "NOT_READY")

        # Unmapped product files: changed files with no behavior evidence coverage
        covered_file_paths = {m["file_path"].lower() for m in changed_file_behavior_mappings_snapshot}
        unmapped_product_files = [
            cf["file_path"] for cf in changed_files
            if cf["file_path"].lower() not in covered_file_paths
            and not cf["file_path"].endswith((".md", ".lock", ".json", ".yaml", ".yml", ".txt", ".toml"))
        ]

        # Unmapped requirement groups: groups with no BBM for any of their ACs
        mapped_ac_ids = {m["acceptance_criterion_id"] for m in business_behavior_mappings_snapshot if m.get("acceptance_criterion_id")}
        unmapped_requirement_groups = []
        for grp_snap in requirement_groups_snapshot:
            grp_ac_ids = [
                ac["id"] for ac in acceptance_criteria_snapshot
                if ac.get("requirement_group_id") == grp_snap["id"]
            ]
            if grp_ac_ids and not any(ac_id in mapped_ac_ids for ac_id in grp_ac_ids):
                unmapped_requirement_groups.append(grp_snap["title"])

        content_state = {
            "repository_id": str(repository_id),
            "pull_request_id": str(pull_request_id),
            "changed_files": changed_files,
            "test_inventory": test_inventory,
            "coverage_files": coverage_files,
            "evidence_counts": evidence_counts,
            "coverage_confidence": coverage_confidence,
            "readiness_state": readiness.readiness_state,
            "readiness_reasons": readiness.readiness_reasons or [],
            "readiness_input_summary": readiness_input_summary,
            "fragility_patterns": fragility_patterns,
            "behaviors": behaviors_snapshot,
            "journeys": journeys_snapshot,
            "behavior_evidences": behavior_evidences_snapshot,
            "journey_mappings": journey_mappings_snapshot,
            "business_intent_override": business_intent_override,
            "requirement_package": requirement_package_snapshot,
            "requirement_groups": requirement_groups_snapshot,
            "acceptance_criteria": acceptance_criteria_snapshot,
            "stable_ac_keys": [ac.get("stable_ac_key") for ac in acceptance_criteria_snapshot if ac.get("stable_ac_key")],
            "business_behavior_mappings": business_behavior_mappings_snapshot,
            "behavior_scenario_coverages": behavior_scenario_coverages_snapshot,
            "changed_file_behavior_mappings": changed_file_behavior_mappings_snapshot,
            "changed_file_paths_available": changed_files_evidence["changed_file_paths_available"],
            "changed_files_source": changed_files_evidence["changed_files_source"],
            "behavior_map_source_commit_sha": behavior_map_source_commit_sha,
            "behavior_map_generated_at": behavior_map_generated_at,
            "behavior_context_status": behavior_context_status,
            "unmapped_product_files": unmapped_product_files,
            "unmapped_requirement_groups": unmapped_requirement_groups,
        }

        serialized = json.dumps(content_state, sort_keys=True, default=str)
        input_snapshot_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        # 17. Build and return schema response
        generated_at = datetime.utcnow()

        return RecommendationInputSnapshotResponse(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            changed_files=changed_files,
            test_inventory=test_inventory,
            coverage_files=coverage_files,
            evidence_counts=evidence_counts,
            coverage_confidence=coverage_confidence,
            readiness_state=readiness.readiness_state,
            readiness_reasons=readiness.readiness_reasons or [],
            readiness_input_summary=readiness_input_summary,
            fragility_patterns=fragility_patterns,
            behaviors=behaviors_snapshot,
            journeys=journeys_snapshot,
            behavior_evidences=behavior_evidences_snapshot,
            journey_mappings=journey_mappings_snapshot,
            behavior_confidence_summary=behavior_confidence_summary,
            journey_summary=journey_summary,
            business_intent_override=business_intent_override,
            requirement_package=requirement_package_snapshot,
            requirement_groups=requirement_groups_snapshot,
            acceptance_criteria=acceptance_criteria_snapshot,
            stable_ac_keys=[ac.get("stable_ac_key") for ac in acceptance_criteria_snapshot if ac.get("stable_ac_key")],
            business_behavior_mappings=business_behavior_mappings_snapshot,
            behavior_scenario_coverages=behavior_scenario_coverages_snapshot,
            changed_file_behavior_mappings=changed_file_behavior_mappings_snapshot,
            changed_file_paths_available=changed_files_evidence["changed_file_paths_available"],
            changed_files_source=changed_files_evidence["changed_files_source"],
            behavior_map_source_commit_sha=behavior_map_source_commit_sha,
            behavior_map_generated_at=behavior_map_generated_at,
            behavior_context_status=behavior_context_status,
            unmapped_product_files=unmapped_product_files,
            unmapped_requirement_groups=unmapped_requirement_groups,
            generated_at=generated_at,
            input_snapshot_hash=input_snapshot_hash
        )
