import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

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
from app.services.repository_readiness import RepositoryReadinessService
from app.schemas.recommendation import RecommendationInputSnapshotResponse


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
        """
        # 1. Load changed files sorted by file_path
        changed_files_db = (
            db.query(PullRequestChangedFile)
            .filter(PullRequestChangedFile.pull_request_id == pull_request_id)
            .order_by(PullRequestChangedFile.file_path.asc())
            .all()
        )
        changed_files = [
            {
                "file_path": f.file_path,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions
            }
            for f in changed_files_db
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
                "suite_name": tc.suite_name,
                "test_name": tc.test_name,
                "framework_name": tc.framework_name
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

        # 13. Load structured acceptance criteria
        acceptance_criteria_snapshot = []
        ac_rows = (
            db.query(AcceptanceCriterion)
            .filter(
                AcceptanceCriterion.repository_id == repository_id,
                AcceptanceCriterion.pull_request_id == pull_request_id
            )
            .order_by(AcceptanceCriterion.created_at.asc())
            .all()
        )
        for ac in ac_rows:
            acceptance_criteria_snapshot.append({
                "id": str(ac.id),
                "text": ac.text,
                "normalized_key": ac.normalized_key,
                "criterion_type": ac.criterion_type,
                "source": ac.source,
                "confidence": ac.confidence,
                "evidence_excerpt": ac.evidence_excerpt,
                "created_at": ac.created_at.isoformat() if ac.created_at else None,
            })

        # 14. Collect overall evidence counts
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
        }

        # 15. Compute deterministic SHA-256 hash of the content state
        # Excludes generated_at and input_snapshot_hash
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
            "fragility_patterns": fragility_patterns,
            "behaviors": behaviors_snapshot,
            "journeys": journeys_snapshot,
            "behavior_evidences": behavior_evidences_snapshot,
            "journey_mappings": journey_mappings_snapshot,
            "business_intent_override": business_intent_override,
            "acceptance_criteria": acceptance_criteria_snapshot,
        }

        serialized = json.dumps(content_state, sort_keys=True, default=str)
        input_snapshot_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        # 16. Build and return schema response
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
            fragility_patterns=fragility_patterns,
            behaviors=behaviors_snapshot,
            journeys=journeys_snapshot,
            behavior_evidences=behavior_evidences_snapshot,
            journey_mappings=journey_mappings_snapshot,
            behavior_confidence_summary=behavior_confidence_summary,
            journey_summary=journey_summary,
            business_intent_override=business_intent_override,
            acceptance_criteria=acceptance_criteria_snapshot,
            generated_at=generated_at,
            input_snapshot_hash=input_snapshot_hash
        )
