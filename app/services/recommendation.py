import uuid
import hashlib
from datetime import datetime, timedelta
from uuid import UUID
from typing import List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

import json
from app.config import settings


def _serialize_datetime(obj: Any) -> Any:
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_datetime(item) for item in obj]
    else:
        return obj
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendedTest,
    RecommendationOutcome,
    RecommendationReasoningEntry,
    RecommendationInputSnapshot,
)
from app.models.coverage import CoverageReport, FileTestLink
from app.models.flaky_test import FlakyTestProfile
from app.models.test_result import TestCase, TestResult
from app.models.dependency import FileDependency
from app.schemas.recommendation import (
    RecommendationRunCreate,
    OutcomeCreate,
    FeedbackCreate,
    CandidateTestInput,
    RankingCandidateInput,
    FallbackEvidenceBundle,
)
from app.repositories.recommendation import RecommendationRepository
from app.repositories.repository import RepositoryRepository
from app.repositories.observability import ObservabilityRepository
from app.services.degradation import DegradationEngine
from app.services.dependency_extraction import DependencyService
from app.services.recommendation_evidence_collector import RecommendationEvidenceCollector
from app.services.coverage_evidence_resolver import CoverageEvidenceResolver
from app.services.fallback_policy_engine import FallbackPolicyEngine
from app.services.path_heuristic_resolver import PathHeuristicResolver
from app.services.dependency_expansion_resolver import DependencyExpansionResolver
from app.services.historical_failure_resolver import HistoricalFailureResolver
from app.services.flaky_adjustment_service import FlakyAdjustmentService
from app.services.recommendation_ranking_service import RecommendationRankingService
from app.services.external_test_recommendation_enricher import ExternalTestRecommendationEnricher
from app.services.integration_sync_service import IntegrationSyncService
from app.services.automation_candidate_detector import AutomationCandidateDetector
from app.services.external_context_evidence_gap_detector import ExternalContextEvidenceGapDetector, GapSeverity


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RecommendationRepository(db)
        self.repo_repository = RepositoryRepository(db)
        self.observability_repo = ObservabilityRepository(db)

    def create_recommendation_run(self, run_in: RecommendationRunCreate) -> RecommendationRun:
        """Generate and persist an immutable recommendation run along with tests, reasons, lineage, and inputs snapshot."""
        # 1. Verify repository exists
        db_repo = self.repo_repository.get(run_in.repository_id)
        if not db_repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository with ID {run_in.repository_id} not found."
            )

        # 1a. Fail-fast: verify repository_id and pull_request_id are present
        if not run_in.repository_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="repository_id is required for recommendation generation."
            )

        # 1b. Build/Refresh structured project context index before recommendation engines run
        try:
            from app.services.project_context_index_extractor import ProjectContextIndexExtractor
            checkout_dir = "c:/Users/amrsa/Downloads/veriscope"
            extractor = ProjectContextIndexExtractor(self.db)
            extractor.extract_and_persist(
                repository_id=run_in.repository_id,
                checkout_dir=checkout_dir
            )
        except Exception as exc:
            import logging
            logger = logging.getLogger("veriscope.recommendation")
            logger.exception(f"Failed to generate ProjectContextIndex: {exc}")

        # Retrieve pull request if available
        from app.models.pull_request import PullRequest
        db_pr = None
        if run_in.pr_id:
            if run_in.pr_id.isdigit():
                db_pr = self.db.query(PullRequest).filter(
                    PullRequest.repository_id == run_in.repository_id,
                    PullRequest.number == int(run_in.pr_id)
                ).first()
            if not db_pr:
                db_pr = self.db.query(PullRequest).filter(
                    PullRequest.repository_id == run_in.repository_id,
                    PullRequest.head_commit_sha == run_in.pr_id
                ).first()
            if not db_pr:
                try:
                    pr_uuid = UUID(run_in.pr_id)
                    db_pr = self.db.query(PullRequest).filter(
                        PullRequest.repository_id == run_in.repository_id,
                        PullRequest.id == pr_uuid
                    ).first()
                except ValueError:
                    pass

        if not db_pr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pull request with ID {run_in.pr_id} not found."
            )

        # 1c. Fetch PR-scoped readiness snapshot BEFORE generation
        from app.services.recommendation_readiness_service import RecommendationReadinessService
        readiness_service = RecommendationReadinessService(self.db)

        try:
            readiness_assessment = readiness_service.assess_readiness(
                repository_id=str(run_in.repository_id),
                pull_request_id=str(db_pr.id)
            )
        except Exception as exc:
            import logging
            logger = logging.getLogger("veriscope.recommendation")
            logger.exception(f"Failed to fetch readiness assessment: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to assess readiness for recommendation generation: {exc}"
            )

        # 1d. Fail-fast checks based on readiness assessment
        if not readiness_assessment.can_generate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Recommendation generation not allowed: {readiness_assessment.can_generate_reason}"
            )

        if readiness_assessment.blocking_inputs:
            blocking_keys = [inp.get("key", "unknown") for inp in readiness_assessment.blocking_inputs]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot generate recommendation: blocking inputs missing: {', '.join(blocking_keys)}"
            )

        # 2. Collect PR Evidence
        pr_evidence = RecommendationEvidenceCollector.collect_pr_evidence(
            db=self.db,
            repository_id=run_in.repository_id,
            pull_request_id=db_pr.id
        )

        # 2b. Sync external work items and test cases (linked-only mode)
        integration_sync_service = IntegrationSyncService(db=self.db)
        sync_result = integration_sync_service.sync_for_pr_recommendation(
            repository_id=run_in.repository_id,
            pull_request_id=db_pr.id
        )
        
        # Add sync evidence gaps to PR evidence if any
        if sync_result.evidence_gaps:
            pr_evidence.readiness_reasons.extend(sync_result.evidence_gaps)
            if sync_result.sync_status in ("FAILURE", "SKIPPED"):
                pr_evidence.evidence_health_status = "DEGRADED"
                pr_evidence.recommendation_readiness_state = "READY_WITH_WARNINGS"
        
        # Log sync result
        import logging
        logger = logging.getLogger("veriscope.recommendation")
        logger.info(
            f"Integration sync result: status={sync_result.sync_status}, "
            f"work_items={sync_result.work_items_synced}, test_cases={sync_result.test_cases_synced}, "
            f"errors={len(sync_result.errors)}, warnings={len(sync_result.warnings)}"
        )

        changed_files = [f.file_path for f in pr_evidence.changed_files]
        if not changed_files and run_in.changed_files:
            changed_files = run_in.changed_files
            if any("insufficient" in f for f in changed_files):
                pr_evidence.evidence_health_status = "INSUFFICIENT"
            pr_evidence.unsafe_for_optimization = db_pr.unsafe_for_optimization or False
            pr_evidence.readiness_reasons = [
                r for r in pr_evidence.readiness_reasons
                if "No changed files" not in r and "changed files are missing" not in r
            ]
            if pr_evidence.evidence_health_status == "INSUFFICIENT" or pr_evidence.unsafe_for_optimization or db_pr.sync_integrity_status in ("FAILED", "UNKNOWN") or db_pr.evidence_consistency_status == "BROKEN":
                pr_evidence.recommendation_readiness_state = "NOT_READY"
            elif pr_evidence.evidence_health_status == "DEGRADED" or db_pr.sync_integrity_status == "PARTIAL_FAILURE" or db_pr.evidence_consistency_status == "PARTIALLY_INCONSISTENT":
                pr_evidence.recommendation_readiness_state = "READY_WITH_WARNINGS"
            else:
                pr_evidence.recommendation_readiness_state = "READY"

        # Check for empty changed files list (Case 3)
        if not changed_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pull request has no changed files available for analysis."
            )

        # Check for missing test history (Case 2)
        from app.models.test_result import TestRun
        test_runs_count = self.db.query(func.count(TestRun.id)).filter(
            TestRun.repository_id == run_in.repository_id
        ).scalar() or 0
        if test_runs_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository requires test history before recommendations can run."
            )

        # 3. Resolve Coverage Evidence
        coverage_evidence = CoverageEvidenceResolver.resolve_coverage(
            db=self.db,
            repository_id=run_in.repository_id,
            pull_request_id=db_pr.id,
            head_commit_sha=pr_evidence.head_commit_sha,
            changed_files=changed_files
        )

        # 4. Determine Fallback Policy
        # Resolve dependency_graph_confidence:
        has_deps = self.db.query(FileDependency).filter(
            FileDependency.repository_id == run_in.repository_id
        ).first() is not None
        dependency_graph_confidence = "HIGH" if has_deps else "MISSING"

        # Check risky files
        changed_area_risky = any(
            any(kw in f.lower() for kw in ("billing", "security", "critical"))
            for f in changed_files
        )

        # Determine evidence_consistency based on db_pr and pr_evidence
        evidence_consistency = "CONSISTENT"
        if db_pr:
            if db_pr.evidence_consistency_status in ("PARTIALLY_INCONSISTENT", "BROKEN", "UNKNOWN"):
                evidence_consistency = "DEGRADED"
            if db_pr.sync_integrity_status in ("FAILED", "PARTIAL_FAILURE", "UNKNOWN"):
                evidence_consistency = "DEGRADED"

        fallback_bundle_in = FallbackEvidenceBundle(
            pr_evidence_health=pr_evidence.evidence_health_status,
            coverage_confidence=coverage_evidence.coverage_confidence,
            dependency_graph_confidence=dependency_graph_confidence,
            flaky_profile_health="HEALTHY",
            evidence_consistency=evidence_consistency,
            unsafe_for_optimization=pr_evidence.unsafe_for_optimization,
            changed_files_availability=len(changed_files) > 0,
            changed_area_risky=changed_area_risky
        )

        fallback_decision = FallbackPolicyEngine.determine_recommendation_mode(fallback_bundle_in)
        if coverage_evidence.coverage_is_missing or coverage_evidence.coverage_confidence == "LOW":
            fallback_decision.reasons.append("Missing coverage mapping or low trust coverage report for the repository or commit.")

        # Candidates collection (test_case_id_str -> CandidateTestInput)
        candidate_inputs = {}
        # Traceability metadata (test_case_id_str -> (reason_type, reason_details, base_priority, list of evidence sources))
        candidate_trace = {}

        def add_candidate(tc_id, reasons, base_priority, sources, reason_type, reason_details):
            tc_id_str = str(tc_id)
            if tc_id_str not in candidate_inputs:
                candidate_inputs[tc_id_str] = CandidateTestInput(
                    test_case_id=tc_id,
                    current_priority_score=base_priority,
                    reasons=reasons
                )
                candidate_trace[tc_id_str] = {
                    "reason_type": reason_type,
                    "reason_details": reason_details,
                    "base_priority": base_priority,
                    "evidence_sources": set(sources)
                }
            else:
                # Merge reasons
                existing_reasons = candidate_inputs[tc_id_str].reasons
                for r in reasons:
                    if r not in existing_reasons:
                        existing_reasons.append(r)
                # Keep highest priority
                candidate_inputs[tc_id_str].current_priority_score = max(
                    candidate_inputs[tc_id_str].current_priority_score,
                    base_priority
                )
                # Update trace
                candidate_trace[tc_id_str]["evidence_sources"].update(sources)
                if base_priority > candidate_trace[tc_id_str]["base_priority"]:
                    candidate_trace[tc_id_str]["reason_type"] = reason_type
                    candidate_trace[tc_id_str]["reason_details"] = reason_details
                    candidate_trace[tc_id_str]["base_priority"] = base_priority

        # Query all TestCases in repository
        db_test_cases = self.db.query(TestCase).filter(
            TestCase.repository_id == run_in.repository_id
        ).all()
        tcs_map = {str(tc.id): tc for tc in db_test_cases}
        tcs_by_identity = {tc.stable_identity: tc for tc in db_test_cases}

        # Get engine version (V3 is the default)
        engine_version_str = getattr(run_in, "engine_version", "v3.0.0") or "v3.0.0"

        # Run SME Orchestrator early to generate unified ProjectUnderstandingSnapshot
        # Load and run Journey and Behavior Intelligence early to enrich recommendations
        from app.models.journey import Journey
        from app.models.behavior import Behavior
        from app.models.behavior_evidence import BehaviorEvidence
        from app.models.behavior_scenario import BehaviorScenario
        from app.models.journey_behavior import JourneyBehavior
        from app.services.pr_journey_impact_analyzer import PRJourneyImpactAnalyzer
        from app.services.journey_risk_engine import JourneyRiskEngine
        from app.services.journey_coverage_analyzer import JourneyCoverageAnalyzer
        from app.services.journey_testing_scope_generator import JourneyTestingScopeGenerator
        from app.services.behavior_impact_analyzer import BehaviorImpactAnalyzer

        # Get journeys for the repository
        journeys = self.db.query(Journey).filter(
            Journey.repository_id == run_in.repository_id,
            Journey.is_deleted == False,
        ).all()

        # Get behaviors for the repository
        behaviors = self.db.query(Behavior).filter(
            Behavior.repository_id == run_in.repository_id,
            Behavior.is_deleted == False,
        ).all()

        # Get journey-behavior mappings
        journey_behaviors = self.db.query(JourneyBehavior).all()

        # Get behavior evidences
        behavior_evidences = self.db.query(BehaviorEvidence).all()

        # Get behavior scenarios
        behavior_scenarios = self.db.query(BehaviorScenario).all()
        behavior_scenarios_map = {}
        for scenario in behavior_scenarios:
            if str(scenario.behavior_id) not in behavior_scenarios_map:
                behavior_scenarios_map[str(scenario.behavior_id)] = []
            behavior_scenarios_map[str(scenario.behavior_id)].append(scenario)

        # Initialize journey services
        journey_impact_analyzer = PRJourneyImpactAnalyzer(db=self.db)
        journey_risk_engine = JourneyRiskEngine(db=self.db)
        journey_coverage_analyzer = JourneyCoverageAnalyzer(db=self.db)
        journey_testing_scope_generator = JourneyTestingScopeGenerator(db=self.db)
        behavior_impact_analyzer = BehaviorImpactAnalyzer(db=self.db)

        # Initialize impact_profile early so intelligence snapshots can be attached
        # before the full PRImpactAnalyzer profile is merged in later.
        impact_profile = {}

        # Analyze behavior impact
        behavior_impact_res = behavior_impact_analyzer.analyze_behavior_impact(
            repository_id=run_in.repository_id,
            pull_request_id=db_pr.id,
            changed_files=changed_files,
            behaviors=behaviors,
            behavior_evidences=behavior_evidences,
            behavior_scenarios=behavior_scenarios,
            journey_behaviors=journey_behaviors,
            journeys=journeys,
            pr_title=db_pr.title,
            pr_description="",
        )

        # Analyze journey impact
        journey_impacts = journey_impact_analyzer.analyze_pr_impact(
            changed_files=changed_files,
            behaviors=behaviors,
            journey_behaviors=journey_behaviors,
            journeys=journeys,
        )

        # Build behaviors map for risk and coverage analysis
        behaviors_map = {str(j.id): [b for b in behaviors if str(b.journey_id) == str(j.id)] for j in journeys}

        # Calculate journey risks
        journey_risks = journey_risk_engine.batch_calculate_risks(journeys, behaviors_map)

        # Calculate journey coverage (simplified - use placeholder coverage)
        test_coverage_map = {str(b.id): 65.0 for b in behaviors}  # Placeholder
        journey_coverages = journey_coverage_analyzer.batch_analyze_coverage(
            journeys=journeys,
            behaviors=behaviors,
            journey_behaviors=journey_behaviors,
            behavior_scenarios=behavior_scenarios_map,
            test_coverage_map=test_coverage_map,
        )

        # Generate journey-based testing scope for affected journeys
        affected_journey_ids = set(impact.journey_id for impact in journey_impacts)
        journey_testing_scopes = []
        for journey in journeys:
            if str(journey.id) in affected_journey_ids:
                affected_behaviors = [
                    b for b in behaviors 
                    if str(b.journey_id) == str(journey.id) and 
                    any(impact.journey_id == str(journey.id) for impact in journey_impacts)
                ]
                scope = journey_testing_scope_generator.generate_scope_from_impact(
                    journey=journey,
                    affected_behaviors=affected_behaviors,
                )
                journey_testing_scopes.append(scope.to_dict())

        # Build journey intelligence summary
        journey_intelligence = {
            "affected_journeys": [
                {
                    "journey_id": impact.journey_id,
                    "journey_name": impact.journey_name,
                    "impact_level": impact.impact_level,
                    "affected_behaviors": impact.affected_behaviors,
                    "affected_files": impact.affected_files,
                    "risk_changes": impact.risk_changes,
                    "confidence": impact.confidence,
                    "impact_reason": impact.impact_reason,
                }
                for impact in journey_impacts
            ],
            "journey_risk_summary": {
                "total_journeys": len(journey_risks),
                "by_risk_level": {
                    "CRITICAL": sum(1 for r in journey_risks if r.risk_level == "CRITICAL"),
                    "HIGH": sum(1 for r in journey_risks if r.risk_level == "HIGH"),
                    "MEDIUM": sum(1 for r in journey_risks if r.risk_level == "MEDIUM"),
                    "LOW": sum(1 for r in journey_risks if r.risk_level == "LOW"),
                },
                "by_confidence": {
                    "HIGH": sum(1 for r in journey_risks if r.confidence == "HIGH"),
                    "MODERATE": sum(1 for r in journey_risks if r.confidence == "MODERATE"),
                    "LOW": sum(1 for r in journey_risks if r.confidence == "LOW"),
                },
                "high_risk_journeys": [
                    {"journey_id": r.journey_id, "journey_name": r.journey_name, "risk_level": r.risk_level, "risk_reason": r.risk_reason}
                    for r in journey_risks if r.risk_level in ["HIGH", "CRITICAL"]
                ],
            },
            "journey_coverage_gaps": [
                {
                    "journey_id": cov.journey_id,
                    "journey_name": cov.journey_name,
                    "coverage_score": cov.coverage_score,
                    "uncovered_behaviors": cov.uncovered_behaviors,
                    "partially_covered_behaviors": cov.partially_covered_behaviors,
                    "coverage_gaps": journey_coverage_analyzer.get_coverage_gaps(cov),
                }
                for cov in journey_coverages if cov.coverage_score < 80
            ],
            "journey_based_testing_scope": journey_testing_scopes,
        }

        # Add journey intelligence to impact_profile
        impact_profile["journey_intelligence"] = journey_intelligence

        # Add behavior intelligence and coverage snapshots to impact_profile
        from app.services.existing_test_to_behavior_scenario_mapper import ExistingTestToBehaviorScenarioMapper
        test_scenario_mapper_early = ExistingTestToBehaviorScenarioMapper(db=self.db)
        test_to_scenario_mappings_early = test_scenario_mapper_early.map_tests_to_scenarios(
            test_cases=db_test_cases,
            behaviors=behaviors,
            scenarios=behavior_scenarios,
        )
        
        from app.services.behavior_coverage_analyzer import BehaviorCoverageAnalyzer
        behavior_cov_analyzer_early = BehaviorCoverageAnalyzer(db=self.db)
        behavior_coverage_snapshot_early = behavior_cov_analyzer_early.analyze_behavior_coverage(
            impacted_behaviors=behavior_impact_res["impacted_behaviors"],
            scenarios=behavior_scenarios,
            test_mappings=test_to_scenario_mappings_early,
            coverage_supports=[],
            current_pr_runs=[],
        )
        
        from app.services.behavior_coverage_gap_generator import BehaviorCoverageGapGenerator
        gap_generator_early = BehaviorCoverageGapGenerator(db=self.db)
        behavior_coverage_gaps_early = gap_generator_early.generate_coverage_gaps(
            behavior_coverages=behavior_coverage_snapshot_early["behavior_coverages"]
        )
        
        behavior_intelligence = {
            "behavior_coverages": behavior_coverage_snapshot_early["behavior_coverages"],
            "behavior_coverage_gaps": behavior_coverage_gaps_early,
            "all_scenarios": behavior_coverage_snapshot_early["all_scenarios"],
        }
        impact_profile["behavior_intelligence"] = behavior_intelligence

        # Run SME Orchestrator early to generate unified ProjectUnderstandingSnapshot
        orchestrated = None
        try:
            from app.models.project_context_index import ProjectContextIndex
            from app.services.sme_orchestrator import SMEOrchestrator
            context_index = self.db.query(ProjectContextIndex).filter(
                ProjectContextIndex.repository_id == run_in.repository_id
            ).first()
            
            orchestrated = SMEOrchestrator.orchestrate(
                context_index=context_index,
                changed_files=changed_files,
                pr_title=db_pr.title if db_pr else "",
                pr_description="",
                test_cases=db_test_cases,
                risk_assessment=fallback_decision,
                db=self.db,
                repository_id=run_in.repository_id
            )
        except Exception as exc:
            import logging
            logger = logging.getLogger("veriscope.recommendation")
            logger.exception(f"Failed to execute SMEOrchestrator early in recommendation: {exc}")

        if engine_version_str in ("v3.0.0", "v3"):
            from app.services.recommendation_logic_v3 import RecommendationLogicV3
            v3_recs = RecommendationLogicV3.generate_recommendations(
                db=self.db,
                repository_id=run_in.repository_id,
                pull_request_id=db_pr.id,
                workspace=db_repo.workspace,
                sme_orchestrated=orchestrated
            )

            class MockRankedCandidateTest:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            ranked_candidates = []
            for t in v3_recs:
                tc = tcs_by_identity.get(t["test_identifier"])
                tc_id = tc.id if tc else uuid.uuid4()
                tc_id_str = str(tc_id)

                candidate_trace[tc_id_str] = {
                    "reason_type": t["source_signal"].lower(),
                    "reason_details": t["reason_details"],
                    "base_priority": t["priority"],
                    "evidence_sources": {t["source_signal"]}
                }

                ranked_candidates.append(MockRankedCandidateTest(
                    test_case_id=tc_id,
                    stable_identity=t["test_identifier"],
                    risk_value=t["priority"],
                    execution_cost=t["estimated_duration_seconds"],
                    priority_score=t["priority"],
                    reasons=[t["reason"]],
                    evidence_sources=[t["source_signal"]],
                    mapping_confidence=t["confidence"],
                    flaky_status=None,
                    is_critical=t["priority"] >= 80,
                    is_excluded=False
                ))

            class MockRankedRecommendationBundle:
                def __init__(self, ranked_candidates, total_runtime_seconds, runtime_confidence, reasons):
                    self.ranked_candidates = ranked_candidates
                    self.total_runtime_seconds = total_runtime_seconds
                    self.runtime_confidence = runtime_confidence
                    self.reasons = reasons

            ranked_bundle = MockRankedRecommendationBundle(
                ranked_candidates=ranked_candidates,
                total_runtime_seconds=sum(t["estimated_duration_seconds"] for t in v3_recs),
                runtime_confidence="HIGH" if any(t["confidence"] == "HIGH" for t in v3_recs) else "MEDIUM" if any(t["confidence"] == "MEDIUM" for t in v3_recs) else "LOW",
                reasons=["Ranked by Recommendation Engine V3."]
            )

            active_fragility_pattern_ids = []
            active_fragility_pattern_hashes = []
            max_risk_level = "LOW"
            changed_files_intersecting_fragility = []
            dep_expansion = type("MockDep", (), {"expanded_files": [], "dependency_state_hash": "empty_v3"})()
            history_failures_used = []
            adjusted_bundle = type("MockAdj", (), {"adjusted_candidates": [], "flaky_profiles_used": [], "reasoning_entries": [], "test_cases": []})()
            behavior_scenario_coverages = []
            test_coverage_links = []
            business_behavior_mappings = []
            ac_coverage_report = None
        else:
            # 4b. Fragility Amplification Matrix Check
            from app.models.fragility_pattern import FragilityPattern
            active_patterns = self.db.query(FragilityPattern).filter(
                FragilityPattern.repository_id == run_in.repository_id,
                FragilityPattern.status == "ACTIVE"
            ).all()

            changed_files_intersecting_fragility = []
            max_risk_level = "LOW"
            for p in active_patterns:
                matched = False
                trigger_file = p.context.get("trigger_file")
                trigger_files = p.context.get("trigger_files", [])
                trigger_dir = p.context.get("trigger_dir")
                trigger_neighborhood = p.context.get("trigger_neighborhood")

                if trigger_file and trigger_file in changed_files:
                    matched = True
                elif trigger_files and all(f in changed_files for f in trigger_files):
                    matched = True
                elif trigger_dir and any(f.startswith(f"{trigger_dir}/") or f == trigger_dir for f in changed_files):
                    matched = True
                elif trigger_neighborhood and any(f.startswith(f"{trigger_neighborhood}/") or f == trigger_neighborhood for f in changed_files):
                    matched = True

                if matched:
                    changed_files_intersecting_fragility.append(p)
                    # Max Risk classification mapping
                    if p.risk_level == "CRITICAL":
                        max_risk_level = "CRITICAL"
                    elif p.risk_level == "HIGH" and max_risk_level != "CRITICAL":
                        max_risk_level = "HIGH"
                    elif p.risk_level == "MODERATE" and max_risk_level not in ("CRITICAL", "HIGH"):
                        max_risk_level = "MODERATE"

            # Warning generation
            if changed_files_intersecting_fragility:
                fallback_decision.reasons.append(
                    f"Warning: High-risk historical fragility detected in changed area (Max Risk: {max_risk_level})."
                )

            # SAFE_FALLBACK escalation (if multiple modules / critical risk)
            if max_risk_level in ("HIGH", "CRITICAL") and len(changed_files_intersecting_fragility) >= 2:
                if fallback_decision.recommendation_mode == "NORMAL":
                    fallback_decision.recommendation_mode = "SAFE_FALLBACK"
                    fallback_decision.reasons.append("Escalated to SAFE_FALLBACK: Multiple active high-risk fragility patterns intersect changed files.")

            # Dependency expansion widening depth
            expansion_depth = fallback_decision.expansion_depth
            if max_risk_level in ("HIGH", "CRITICAL"):
                expansion_depth += 1

            # 5. Resolve Direct Coverage Mappings
            if coverage_evidence.direct_test_mappings:
                for identity in coverage_evidence.direct_test_mappings:
                    tc = tcs_by_identity.get(identity)
                    if tc:
                        add_candidate(
                            tc_id=tc.id,
                            reasons=[f"Direct coverage mapping from resolved report {coverage_evidence.coverage_report_id}."],
                            base_priority=0.95,
                            sources=["DIRECT_COVERAGE"],
                            reason_type="direct_file_coverage",
                            reason_details={"coverage_report_id": str(coverage_evidence.coverage_report_id)}
                        )

            # 5b. Resolve Fragility Memory Breakages
            from app.services.fragility_memory_service import FragilityMemoryService
            fragility_service = FragilityMemoryService(self.db)
            fragility_candidates = fragility_service.resolve_fragility_recommendations(
                repository_id=run_in.repository_id,
                changed_files=changed_files
            )
            active_fragility_pattern_ids = []
            active_fragility_pattern_hashes = []
            for cand in fragility_candidates:
                tc = tcs_by_identity.get(cand["stable_identity"])
                if tc:
                    add_candidate(
                        tc_id=tc.id,
                        reasons=[cand["reason_details"]["explanation"]],
                        base_priority=cand["priority_score"],
                        sources=["HISTORICAL_FRAGILITY"],
                        reason_type="historical_fragility",
                        reason_details=cand["reason_details"]
                    )
                    if cand.get("status") == "ACTIVE":
                        active_fragility_pattern_ids.append(str(cand["pattern_id"]))
                        active_fragility_pattern_hashes.append(cand["pattern_hash"])

            # 6. If coverage missing/weak, run path heuristic fallback
            if (
                coverage_evidence.coverage_confidence in ("LOW", "MODERATE", "UNKNOWN", "MISSING")
                or coverage_evidence.coverage_is_missing
            ):
                heuristic_bundle = PathHeuristicResolver.resolve_path_heuristics(
                    db=self.db,
                    repository_id=run_in.repository_id,
                    changed_files=changed_files
                )
                for cand in heuristic_bundle.heuristic_test_candidates:
                    priority = 0.60 if cand.heuristic_type in ("SAME_STEM", "TEST_PREFIX_SUFFIX") else 0.45
                    add_candidate(
                        tc_id=cand.test_case_id,
                        reasons=[cand.reason],
                        base_priority=priority,
                        sources=[cand.heuristic_type],
                        reason_type="path_heuristic_fallback",
                        reason_details={"source_file_path": cand.source_file_path, "heuristic_type": cand.heuristic_type}
                    )

            # 7. Expand dependencies according to fallback policy (widened depth if fragile)
            dep_expansion = DependencyExpansionResolver.expand_dependencies(
                db=self.db,
                repository_id=run_in.repository_id,
                changed_files=changed_files,
                max_depth=expansion_depth,
                max_nodes=500
            )

            # Map tests for expanded files using Coverage links
            if dep_expansion.expanded_files:
                # Query links to expanded files
                from app.models.coverage import FileTestLink
                links_db = self.db.query(FileTestLink).filter(
                    FileTestLink.file_path.in_(dep_expansion.expanded_files)
                ).all()
                for link in links_db:
                    tc = tcs_map.get(str(link.test_case_id))
                    if tc:
                        # Assign dependency priority based on policy mode
                        priority = 0.80 if fallback_decision.fallback_level == "LEVEL_2" else 0.70
                        add_candidate(
                            tc_id=tc.id,
                            reasons=[f"Transitive dependency expansion path matched through file {link.file_path}."],
                            base_priority=priority,
                            sources=["DEPENDENCY_EXPANSION_L1"],
                            reason_type="dependency_expansion",
                            reason_details={"referenced_by": link.file_path}
                        )

            # 8. Resolve scoped historical failures if policy allows
            history_failures_used = []
            if fallback_decision.include_historical_failures:
                history_bundle = HistoricalFailureResolver.resolve_historical_failures(
                    db=self.db,
                    repository_id=run_in.repository_id,
                    changed_files=changed_files,
                    dependency_files=dep_expansion.expanded_files,
                    history_window_days=30
                )
                for c in history_bundle.historical_failure_tests:
                    source = f"HISTORICAL_FAILURE_{c.relevance_type}"
                    add_candidate(
                        tc_id=c.test_case_id,
                        reasons=[c.reason],
                        base_priority=c.priority_score,
                        sources=[source],
                        reason_type="scoped_historical_failure",
                        reason_details={"relevance_type": c.relevance_type}
                    )
                    history_failures_used.append({"test_case_id": str(c.test_case_id), "status": "failed"})

            # 9. Escalation & Full Regression Override Rules
            # If no candidates are found and evidence is not safe (evidence is LOW or UNKNOWN), escalate!
            evidence_is_not_safe = fallback_decision.evidence_quality in ("LOW", "UNKNOWN")
            no_executable_candidates = not any(
                str(tc_id) in candidate_inputs for tc_id in candidate_inputs
            )

            escalated_to_full = False
            if no_executable_candidates and evidence_is_not_safe:
                escalated_to_full = True
                fallback_decision.recommendation_mode = "FULL_REGRESSION"
                fallback_decision.optimization_allowed = False
                fallback_decision.fallback_level = "LEVEL_5"
                fallback_decision.full_regression_required = True
                fallback_decision.reasons.append(
                    "Escalated to LEVEL_5 FULL_REGRESSION: no candidate tests were resolved "
                    "under a low-trust or unknown evidence quality environment."
                )

            # If FULL_REGRESSION mode is activated (either originally or escalated), recommend full suite
            if fallback_decision.recommendation_mode == "FULL_REGRESSION":
                for tc in db_test_cases:
                    add_candidate(
                        tc_id=tc.id,
                        reasons=["Full regression fallback: all tests recommended for maximum safety."],
                        base_priority=0.50,
                        sources=["FULL_REGRESSION_FALLBACK"],
                        reason_type="full_regression_fallback",
                        reason_details={"reason": "Insufficient evidence or fallback escalation. Reverted to full regression."}
                    )

            # Apply Behavior Coverage Scoring Boosts (enriching ranking and explanation)
            # Map of test_identifier -> list of mappings
            tc_mapped_scenarios = {}
            for m in test_to_scenario_mappings_early:
                tc_id = m["test_identifier"]
                if tc_id not in tc_mapped_scenarios:
                    tc_mapped_scenarios[tc_id] = []
                tc_mapped_scenarios[tc_id].append(m)
                
            # Map of behavior ID -> impacted behavior details
            impacted_behaviors_map = {b["behavior_id"]: b for b in behavior_impact_res["impacted_behaviors"]}
            
            # Formally trace existing runnable tests vs missing scenarios
            for tc_id_str, cand in list(candidate_inputs.items()):
                tc = tcs_map.get(tc_id_str)
                if not tc:
                    continue
                tc_identity = tc.stable_identity
                
                # Check mapping to impacted behaviors/scenarios
                if tc_identity in tc_mapped_scenarios:
                    for m in tc_mapped_scenarios[tc_identity]:
                        b_id = m["behavior_id"]
                        s_id = m["behavior_scenario_id"]
                        
                        if b_id in impacted_behaviors_map:
                            impacted_b = impacted_behaviors_map[b_id]
                            
                            # 1. Existing test mapped to impacted behavior boost (+0.20)
                            cand.current_priority_score += 0.20
                            cand.reasons.append("Behavior-aware: Test maps to impacted business behavior")
                            
                            # 2. Impacted behavior direct match boost (+0.30)
                            cand.current_priority_score += 0.30
                            cand.reasons.append(f"Behavior-aware: Matches impacted behavior '{impacted_b['behavior_name']}'")
                            
                            # 3. High-risk behavior boost (+0.20)
                            if impacted_b["impact_level"] in ["CRITICAL", "HIGH"]:
                                cand.current_priority_score += 0.20
                                cand.reasons.append("Behavior-aware: Mapped to high-risk / critical behavior")
                                
                            # 4. Uncovered MUST scenario boost (+0.25)
                            sc_cov = next((sc for sc in behavior_coverage_snapshot_early["all_scenarios"] if sc["scenario_id"] == s_id), None)
                            if sc_cov:
                                if sc_cov["priority"] in ["BLOCKER", "MUST"] and sc_cov["coverage_status"] in ["MISSING_AUTOMATED_COVERAGE", "MANUAL_VALIDATION_RECOMMENDED"]:
                                    cand.current_priority_score += 0.25
                                    cand.reasons.append(f"Behavior-aware: Covers missing/uncovered MUST scenario '{sc_cov['title']}'")
                                    
                                # 5. Optional scenario matching (include as optional, do not inflate critical count)
                                elif sc_cov["priority"] in ["SHOULD", "OPTIONAL"]:
                                    # Optional scenario included as confidence booster (priority remains stable or lightly boosted)
                                    cand.reasons.append(f"Behavior-aware: Optional scenario confidence booster '{sc_cov['title']}'")
                                    
                                # 6. Current PR verified status (mark verified, do not re-recommend unless rerun needed)
                                elif sc_cov["coverage_status"] == "VERIFIED_ON_CURRENT_PR":
                                    cand.reasons.append(f"Behavior-aware: Already verified on current PR build")
                            
                            # 7. Architecture contribution explanation (V2 only)
                            if settings.USE_ARCHITECTURE_V2 and "architecture_impact" in impact_profile and "v2_analysis" in impact_profile.get("architecture_impact", {}):
                                v2_analysis = impact_profile["architecture_impact"]["v2_analysis"]
                                direct_impact_count = len(v2_analysis.get("direct_impacts", []))
                                indirect_impact_count = len(v2_analysis.get("indirect_impacts", []))
                                if direct_impact_count > 0 or indirect_impact_count > 0:
                                    total_dependents = direct_impact_count + indirect_impact_count
                                    cand.reasons.append(f"Architecture-aware: This recommendation was boosted because the changed file is used by {total_dependents} dependent modules")
                                    
                            # Cap priority at 1.0 to prevent overflow
                            cand.current_priority_score = min(cand.current_priority_score, 1.0)

            # 10. Apply flaky/quarantined warnings and exclusions adjustments
            adjusted_bundle = FlakyAdjustmentService.apply_flaky_adjustments(
                db=self.db,
                repository_id=run_in.repository_id,
                candidate_tests=list(candidate_inputs.values())
            )

            # 11. Rank Candidates deterministically
            ranking_inputs = []
            for adj in adjusted_bundle.adjusted_candidates:
                tc_id_str = str(adj.test_case_id)
                trace = candidate_trace.get(tc_id_str, {
                    "evidence_sources": ["DIRECT_COVERAGE"],
                    "historical_failure_score": None
                })
                ranking_inputs.append(
                    RankingCandidateInput(
                        test_case_id=adj.test_case_id,
                        reasons=adj.reasons,
                        base_priority_score=adj.priority_score,
                        evidence_sources=list(trace["evidence_sources"]),
                        mapping_confidence=coverage_evidence.coverage_confidence,
                        flaky_status=adj.status if adj.is_flaky else None,
                        historical_failure_score=trace.get("historical_failure_score")
                    )
                )

            # Build test-to-AC mappings from business behavior mappings
            test_to_ac_mappings = {}
            for mapping in business_behavior_mappings:
                if mapping.acceptance_criterion_id and mapping.behavior_scenario_id:
                    # Find tests that cover this scenario
                    scenario_coverage = next(
                        (sc for sc in behavior_scenario_coverages if str(sc.behavior_scenario_id) == str(mapping.behavior_scenario_id)),
                        None
                    )
                    if scenario_coverage:
                        test_ids = scenario_coverage.test_mappings.get("test_ids", [])
                        ac_id = str(mapping.acceptance_criterion_id)
                        for test_id in test_ids:
                            if test_id not in test_to_ac_mappings:
                                test_to_ac_mappings[test_id] = []
                            test_to_ac_mappings[test_id].append(ac_id)
            
            ranked_bundle = RecommendationRankingService.rank_candidates(
                db=self.db,
                repository_id=run_in.repository_id,
                candidate_tests=ranking_inputs,
                mode=fallback_decision.recommendation_mode,
                business_behavior_mappings=business_behavior_mappings,
                ac_coverage_report=ac_coverage_report,
                test_to_ac_mappings=test_to_ac_mappings
            )

        # 12. Build Skipped Test Summaries
        from app.services.skipped_reasoning_service import SkippedReasoningService
        recommended_test_ids = [t.stable_identity for t in ranked_bundle.ranked_candidates if not t.is_excluded]
        all_test_ids = [tc.stable_identity for tc in db_test_cases]
        
        skipped_summary = SkippedReasoningService.build_skipped_summary(
            db=self.db,
            repository_id=run_in.repository_id,
            recommended_test_ids=recommended_test_ids,
            all_test_ids=all_test_ids,
            evidence_quality=fallback_decision.evidence_quality,
            max_examples=3
        )
        
        skipped_count = skipped_summary.skipped_count
        top_skipped_examples = skipped_summary.top_skipped_examples
        skipped_reason_summary = skipped_summary.skipped_reason_summary

        # 13. Persist RecommendationRun
        window_start = datetime.utcnow() - timedelta(days=30)
        window_end = datetime.utcnow()

        from app.models.pull_request import PullRequestSyncJob, PullRequestSnapshot
        latest_sync_job = self.db.query(PullRequestSyncJob).filter(
            PullRequestSyncJob.pull_request_id == db_pr.id
        ).order_by(PullRequestSyncJob.created_at.desc()).first()
        pr_sync_job_id = latest_sync_job.id if latest_sync_job else None

        latest_snapshot = None
        if pr_evidence.pr_snapshot_id:
            latest_snapshot = self.db.query(PullRequestSnapshot).filter(
                PullRequestSnapshot.id == pr_evidence.pr_snapshot_id
            ).first()
        evidence_fingerprint = latest_snapshot.evidence_fingerprint if latest_snapshot else None

        readiness_dimensions = {
            "sync_integrity": pr_evidence.sync_integrity_status,
            "evidence_health": pr_evidence.evidence_health_status,
            "readiness_state": pr_evidence.recommendation_readiness_state,
            "reasons": pr_evidence.readiness_reasons
        }

        # Runtime confidence degradation
        runtime_conf = ranked_bundle.runtime_confidence
        if active_fragility_pattern_ids and runtime_conf == "HIGH":
            runtime_conf = "MODERATE"

        # Calculate new fields for durable recommendation results
        from app.models.user import Workspace
        workspace = self.db.query(Workspace).filter(Workspace.id == db_repo.workspace_id).first()
        workspace_id = workspace.id if workspace else None

        from app.services.recommendation_input_builder import RecommendationInputBuilder
        input_snapshot_resp = RecommendationInputBuilder.build_snapshot(
            db=self.db,
            repository_id=run_in.repository_id,
            pull_request_id=db_pr.id,
            workspace=workspace
        )
        input_snapshot_hash = input_snapshot_resp.input_snapshot_hash

        # Extract manually pasted AC from input snapshot if available
        manual_ac_override = input_snapshot_resp.business_intent_override
        manual_acceptance_criteria = input_snapshot_resp.acceptance_criteria

        # Determine if direct coverage match exists (Case 1)
        has_direct_coverage = bool(coverage_evidence.direct_test_mappings)

        # Deterministic recommendation snapshot hash
        rec_tests_payload = sorted([
            {
                "test_identifier": t.stable_identity,
                "priority": t.priority_score,
                "confidence": "LOW" if not has_direct_coverage else ("HIGH" if t.priority_score >= 0.8 else "MEDIUM" if t.priority_score >= 0.6 else "LOW"),
                "reason": "No direct coverage match found; selected tests using historical/path fallback." if not has_direct_coverage else (t.reasons[0] if t.reasons else "Recommended via algorithm fallback.")
            }
            for t in ranked_bundle.ranked_candidates
        ], key=lambda x: x["test_identifier"])
        rec_str = json.dumps(rec_tests_payload, sort_keys=True, separators=(",", ":"))
        recommendation_snapshot_hash = hashlib.sha256(rec_str.encode("utf-8")).hexdigest()

        # Derive risk level from recommendation mode and evidence quality
        mode = fallback_decision.recommendation_mode or "NORMAL"
        evidence_quality = fallback_decision.evidence_quality or "UNKNOWN"
        if mode in ("FULL_REGRESSION", "SAFE_FALLBACK") or evidence_quality in ("LOW", "UNKNOWN"):
            risk_level = "HIGH"
        elif mode == "WIDENED" or evidence_quality == "MODERATE":
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        recommended_tests_count = len(ranked_bundle.ranked_candidates)

        # Sum of averages for all tests in the repository for full suite duration estimation
        all_avg_durations = self.db.query(
            func.avg(TestResult.duration)
        ).join(TestCase, TestResult.test_case_id == TestCase.id).filter(
            TestCase.repository_id == run_in.repository_id
        ).scalar() or 5.0
        full_suite_runtime_seconds = float(all_avg_durations * len(db_test_cases))

        # Run PR Impact Analysis
        from app.services.pr_impact_analyzer import PRImpactAnalyzer
        impact_profile.update(PRImpactAnalyzer.analyze_pr_impact(
            title=db_pr.title,
            description="",
            changed_files=changed_files
        ))

        # Populate impact_profile with SME Orchestrator results
        if orchestrated:
            impact_profile["product_impact"] = orchestrated["product_impact"]
            impact_profile["qa_scope_assessment"] = orchestrated["qa_scope_assessment"]
            impact_profile["security_assessment"] = orchestrated["security_assessment"]
            impact_profile["architecture_impact"] = orchestrated["architecture_impact"]
            impact_profile["domain_vocabulary"] = orchestrated["domain_vocabulary"]
            impact_profile["project_understanding_snapshot"] = orchestrated["project_understanding_snapshot"]

        # Add Architecture V2 impact if feature flag is enabled
        if settings.USE_ARCHITECTURE_V2:
            from app.services.architecture_v2_impact_engine import ArchitectureV2ImpactEngine
            architecture_v2_impact = ArchitectureV2ImpactEngine.analyze_impact(
                db=self.db,
                repository_id=run_in.repository_id,
                changed_files=changed_files
            )
            # Add V2-specific fields to architecture_impact section
            if "architecture_impact" not in impact_profile:
                impact_profile["architecture_impact"] = {}
            impact_profile["architecture_impact"]["v2_analysis"] = {
                "changed_nodes": architecture_v2_impact.get("changed_nodes", []),
                "direct_impacts": architecture_v2_impact.get("direct_impacts", []),
                "indirect_impacts": architecture_v2_impact.get("indirect_impacts", []),
                "impacted_layers": architecture_v2_impact.get("impacted_layers", []),
                "impacted_services": architecture_v2_impact.get("impacted_services", []),
                "impacted_domains": architecture_v2_impact.get("impacted_domains", []),
                "confidence": architecture_v2_impact.get("confidence", "NONE"),
                "explanation": architecture_v2_impact.get("explanation", "")
            }
            # Also get impacted behaviors and journeys from V2
            impacted_behaviors_v2 = ArchitectureV2ImpactEngine.get_impacted_behaviors(
                db=self.db,
                repository_id=run_in.repository_id,
                changed_files=changed_files
            )
            impacted_journeys_v2 = ArchitectureV2ImpactEngine.get_impacted_journeys(
                db=self.db,
                repository_id=run_in.repository_id,
                changed_files=changed_files
            )
            impact_profile["architecture_impact"]["v2_analysis"]["impacted_behaviors"] = impacted_behaviors_v2
            impact_profile["architecture_impact"]["v2_analysis"]["impacted_journeys"] = impacted_journeys_v2

        # Run Journey Intelligence Analysis
        from app.models.journey import Journey
        from app.models.behavior import Behavior
        from app.models.behavior_evidence import BehaviorEvidence
        from app.models.behavior_scenario import BehaviorScenario
        from app.models.journey_behavior import JourneyBehavior
        from app.models.behavior_scenario import BehaviorScenario
        from app.services.pr_journey_impact_analyzer import PRJourneyImpactAnalyzer
        from app.services.journey_risk_engine import JourneyRiskEngine
        from app.services.journey_coverage_analyzer import JourneyCoverageAnalyzer
        from app.services.journey_testing_scope_generator import JourneyTestingScopeGenerator
        from app.services.behavior_impact_analyzer import BehaviorImpactAnalyzer

        # Get journeys for the repository
        journeys = self.db.query(Journey).filter(
            Journey.repository_id == run_in.repository_id,
            Journey.is_deleted == False,
        ).all()

        # Get behaviors for the repository
        behaviors = self.db.query(Behavior).filter(
            Behavior.repository_id == run_in.repository_id,
            Behavior.is_deleted == False,
        ).all()

        # Get journey-behavior mappings
        journey_behaviors = self.db.query(JourneyBehavior).all()

        # Get behavior evidences
        behavior_evidences = self.db.query(BehaviorEvidence).all()

        # Get behavior scenarios
        behavior_scenarios = self.db.query(BehaviorScenario).all()
        behavior_scenarios_map = {}
        for scenario in behavior_scenarios:
            if str(scenario.behavior_id) not in behavior_scenarios_map:
                behavior_scenarios_map[str(scenario.behavior_id)] = []
            behavior_scenarios_map[str(scenario.behavior_id)].append(scenario)

        # Initialize journey services
        journey_impact_analyzer = PRJourneyImpactAnalyzer(db=self.db)
        journey_risk_engine = JourneyRiskEngine(db=self.db)
        journey_coverage_analyzer = JourneyCoverageAnalyzer(db=self.db)
        journey_testing_scope_generator = JourneyTestingScopeGenerator(db=self.db)
        behavior_impact_analyzer = BehaviorImpactAnalyzer(db=self.db)

        # Analyze behavior impact (with architecture impact if V2 is enabled)
        architecture_impact_for_behavior = None
        if settings.USE_ARCHITECTURE_V2 and "architecture_impact" in impact_profile and "v2_analysis" in impact_profile["architecture_impact"]:
            architecture_impact_for_behavior = impact_profile["architecture_impact"]["v2_analysis"]
        
        behavior_impact_res = behavior_impact_analyzer.analyze_behavior_impact(
            repository_id=run_in.repository_id,
            pull_request_id=db_pr.id,
            changed_files=changed_files,
            behaviors=behaviors,
            behavior_evidences=behavior_evidences,
            behavior_scenarios=behavior_scenarios,
            journey_behaviors=journey_behaviors,
            journeys=journeys,
            pr_title=db_pr.title,
            pr_description="",
            architecture_impact=architecture_impact_for_behavior,
        )

        # Analyze journey impact (with architecture impact if V2 is enabled)
        journey_impacts = journey_impact_analyzer.analyze_pr_impact(
            changed_files=changed_files,
            behaviors=behaviors,
            journey_behaviors=journey_behaviors,
            journeys=journeys,
            architecture_impact=architecture_impact_for_behavior,
        )

        # Build behaviors map for risk and coverage analysis
        behaviors_map = {str(j.id): [b for b in behaviors if str(b.journey_id) == str(j.id)] for j in journeys}

        # Calculate journey risks
        journey_risks = journey_risk_engine.batch_calculate_risks(journeys, behaviors_map)

        # Calculate journey coverage (simplified - use placeholder coverage)
        test_coverage_map = {str(b.id): 65.0 for b in behaviors}  # Placeholder
        journey_coverages = journey_coverage_analyzer.batch_analyze_coverage(
            journeys=journeys,
            behaviors=behaviors,
            journey_behaviors=journey_behaviors,
            behavior_scenarios=behavior_scenarios_map,
            test_coverage_map=test_coverage_map,
        )

        # Generate journey-based testing scope for affected journeys
        affected_journey_ids = set(impact.journey_id for impact in journey_impacts)
        journey_testing_scopes = []
        for journey in journeys:
            if str(journey.id) in affected_journey_ids:
                affected_behaviors = [
                    b for b in behaviors 
                    if str(b.journey_id) == str(journey.id) and 
                    any(impact.journey_id == str(journey.id) for impact in journey_impacts)
                ]
                scope = journey_testing_scope_generator.generate_scope_from_impact(
                    journey=journey,
                    affected_behaviors=affected_behaviors,
                )
                journey_testing_scopes.append(scope.to_dict())

        # Build journey intelligence summary
        journey_intelligence = {
            "affected_journeys": [
                {
                    "journey_id": impact.journey_id,
                    "journey_name": impact.journey_name,
                    "impact_level": impact.impact_level,
                    "affected_behaviors": impact.affected_behaviors,
                    "affected_files": impact.affected_files,
                    "risk_changes": impact.risk_changes,
                    "confidence": impact.confidence,
                    "impact_reason": impact.impact_reason,
                }
                for impact in journey_impacts
            ],
            "journey_risk_summary": {
                "total_journeys": len(journey_risks),
                "by_risk_level": {
                    "CRITICAL": sum(1 for r in journey_risks if r.risk_level == "CRITICAL"),
                    "HIGH": sum(1 for r in journey_risks if r.risk_level == "HIGH"),
                    "MEDIUM": sum(1 for r in journey_risks if r.risk_level == "MEDIUM"),
                    "LOW": sum(1 for r in journey_risks if r.risk_level == "LOW"),
                },
                "by_confidence": {
                    "HIGH": sum(1 for r in journey_risks if r.confidence == "HIGH"),
                    "MODERATE": sum(1 for r in journey_risks if r.confidence == "MODERATE"),
                    "LOW": sum(1 for r in journey_risks if r.confidence == "LOW"),
                },
                "high_risk_journeys": [
                    {"journey_id": r.journey_id, "journey_name": r.journey_name, "risk_level": r.risk_level, "risk_reason": r.risk_reason}
                    for r in journey_risks if r.risk_level in ["HIGH", "CRITICAL"]
                ],
            },
            "journey_coverage_gaps": [
                {
                    "journey_id": cov.journey_id,
                    "journey_name": cov.journey_name,
                    "coverage_score": cov.coverage_score,
                    "uncovered_behaviors": cov.uncovered_behaviors,
                    "partially_covered_behaviors": cov.partially_covered_behaviors,
                    "coverage_gaps": journey_coverage_analyzer.get_coverage_gaps(cov),
                }
                for cov in journey_coverages if cov.coverage_score < 80
            ],
            "journey_based_testing_scope": journey_testing_scopes,
        }

        # Add journey intelligence to impact_profile
        impact_profile["journey_intelligence"] = journey_intelligence

        # Build behavior_coverage_matrix for frontend consumption
        # This matrix provides detailed scenario-level coverage with impact, sufficiency, and actionable insights
        behavior_coverage_matrix = []
        
        # Map behavior IDs to journey information
        behavior_to_journey = {}
        for jb in journey_behaviors:
            behavior_to_journey[str(jb.behavior_id)] = {
                "journey_id": str(jb.journey_id),
                "journey_name": next((j.name for j in journeys if str(j.id) == str(jb.journey_id)), None)
            }
        
        # Map behavior IDs to impact level from impact analysis
        behavior_impact_map = {b["behavior_id"]: b for b in behavior_impact_res["impacted_behaviors"]}
        
        # Build matrix entries for all scenarios in the coverage snapshot
        for scenario in behavior_coverage_snapshot_early["all_scenarios"]:
            scenario_id = scenario["scenario_id"]
            scenario_title = scenario["title"]
            priority = scenario["priority"]
            coverage_status = scenario["coverage_status"]
            coverage_confidence = scenario["confidence"]
            existing_tests = scenario.get("existing_tests", [])
            suggested_action = scenario.get("suggested_action", "")
            reason = scenario.get("reason", "")
            
            # Find the behavior this scenario belongs to
            behavior_id = None
            behavior_name = None
            for b_cov in behavior_coverage_snapshot_early["behavior_coverages"]:
                for sc in b_cov["scenarios"]:
                    if sc["scenario_id"] == scenario_id:
                        behavior_id = b_cov["behavior_id"]
                        behavior_name = b_cov["behavior_name"]
                        break
                if behavior_id:
                    break
            
            if not behavior_id:
                continue
            
            # Get journey information
            journey_info = behavior_to_journey.get(behavior_id, {})
            journey_id = journey_info.get("journey_id")
            journey_name = journey_info.get("journey_name")
            
            # Get impact level and impact_type from behavior impact analysis
            impact_level = "LOW"
            impact_type = "INDIRECT"
            behavior_confidence = "MEDIUM"
            behavior_risk_level = "MEDIUM"
            evidence_summary = []
            if behavior_id in behavior_impact_map:
                impact_level = behavior_impact_map[behavior_id].get("impact_level", "LOW")
                impact_type = behavior_impact_map[behavior_id].get("impact_type", "INDIRECT")
                behavior_confidence = behavior_impact_map[behavior_id].get("behavior_confidence", "MEDIUM")
                behavior_risk_level = behavior_impact_map[behavior_id].get("behavior_risk_level", "MEDIUM")
                # Build evidence summary from matched evidence
                matched_evidence = behavior_impact_map[behavior_id].get("matched_evidence", [])
                for me in matched_evidence:
                    evidence_summary.append({
                        "evidence_type": me.get("evidence_type", "UNKNOWN"),
                        "source_path": me.get("source_path"),
                        "confidence": me.get("confidence", "MEDIUM"),
                    })
            
            # Get sufficiency from behavior coverage
            sufficiency = "UNKNOWN"
            if behavior_id in behavior_impact_map:
                # Find the behavior coverage entry
                for b_cov in behavior_coverage_snapshot_early["behavior_coverages"]:
                    if b_cov["behavior_id"] == behavior_id:
                        sufficiency = b_cov.get("sufficiency", "UNKNOWN")
                        break
            
            # Determine current PR execution status
            current_pr_execution_status = "NOT_EXECUTED"
            if coverage_status == "VERIFIED_ON_CURRENT_PR":
                current_pr_execution_status = "EXECUTED"
            
            # Build recommended actions list
            recommended_actions = []
            if suggested_action:
                recommended_actions.append(suggested_action)
            if coverage_status == "MISSING_AUTOMATED_COVERAGE":
                recommended_actions.append("Create automated test for this scenario")
            elif coverage_status == "MANUAL_VALIDATION_RECOMMENDED":
                recommended_actions.append("Perform manual validation before merge")
            elif coverage_status == "PARTIALLY_COVERED":
                recommended_actions.append("Enhance existing test coverage")
            
            # Build reasons list
            reasons = []
            if reason:
                reasons.append(reason)
            if impact_level in ["CRITICAL", "HIGH"]:
                reasons.append(f"High-impact behavior ({impact_level})")
            if priority in ["BLOCKER", "MUST"]:
                reasons.append(f"High-priority scenario ({priority})")
            
            # Get related changed files from behavior impact
            related_changed_files = []
            if behavior_id in behavior_impact_map:
                related_changed_files = behavior_impact_map[behavior_id].get("impacted_files", [])
            
            matrix_entry = {
                "scenario_id": scenario_id,
                "scenario_title": scenario_title,
                "behavior_id": behavior_id,
                "behavior_name": behavior_name,
                "journey_id": journey_id,
                "journey_name": journey_name,
                "impact_level": impact_level,
                "impact_type": impact_type,
                "priority": priority,
                "coverage_status": coverage_status,
                "coverage_confidence": coverage_confidence,
                "sufficiency": sufficiency,
                "existing_tests": existing_tests,
                "current_pr_execution_status": current_pr_execution_status,
                "recommended_actions": recommended_actions,
                "reasons": reasons,
                "related_changed_files": related_changed_files,
                "evidence_summary": evidence_summary,
                "behavior_confidence": behavior_confidence,
                "behavior_risk_level": behavior_risk_level,
            }
            behavior_coverage_matrix.append(matrix_entry)
        
        # Add behavior_coverage_matrix to impact_profile for API response
        impact_profile["behavior_coverage_matrix"] = behavior_coverage_matrix
        
        # Generate business intent coverage matrix
        from app.services.business_intent_coverage_matrix_generator import BusinessIntentCoverageMatrixGenerator
        from app.services.acceptance_criteria_coverage_resolver import AcceptanceCriteriaCoverageResolver
        from app.services.acceptance_criteria_extractor import AcceptanceCriteriaExtractor
        from app.services.business_behavior_mapper import BusinessBehaviorMapper
        from app.services.expected_behavior_scenario_generator import ExpectedBehaviorScenarioGenerator
        
        # Extract acceptance criteria from PR description or use manual override
        ac_extractor = AcceptanceCriteriaExtractor(db=self.db)

        # Prefer manually pasted AC if available
        if manual_acceptance_criteria and len(manual_acceptance_criteria) > 0:
            # Convert manual AC snapshot dicts to objects so downstream services can use attribute access
            from types import SimpleNamespace
            acceptance_criteria = []
            for ac in manual_acceptance_criteria:
                ac_data = ac if isinstance(ac, dict) else vars(ac)
                acceptance_criteria.append(SimpleNamespace(
                    id=ac_data.get("id"),
                    text=ac_data.get("text", ""),
                    normalized_key=ac_data.get("normalized_key"),
                    criterion_type=ac_data.get("criterion_type"),
                    source=ac_data.get("source", "MANUAL_USER_INPUT"),
                    confidence=ac_data.get("confidence", 1.0),
                    evidence_excerpt=ac_data.get("evidence_excerpt"),
                    priority=ac_data.get("priority", "SHOULD"),
                ))
            ac_evidence_gap = None  # No gap when AC is manually provided
        else:
            # Fall back to PR description extraction
            acceptance_criteria, ac_evidence_gap = ac_extractor.extract_from_pr_description(
                pr_description=db_pr.title if db_pr else "",
                repository_id=str(run_in.repository_id),
                pull_request_id=str(db_pr.id) if db_pr else None,
                source="PR_DESCRIPTION"
            )
        
        # Map AC to behaviors - use manual override mappings if available
        behavior_mapper = BusinessBehaviorMapper(db=self.db)
        if manual_ac_override and manual_ac_override.get("mapped_behaviors"):
            # Use pre-computed mappings from manual AC paste — convert dicts to objects
            from types import SimpleNamespace
            raw_mappings = manual_ac_override.get("mapped_behaviors", [])
            business_behavior_mappings = [
                m if not isinstance(m, dict) else SimpleNamespace(
                    id=m.get("id"),
                    acceptance_criterion_id=m.get("acceptance_criterion_id"),
                    behavior_id=m.get("behavior_id"),
                    behavior_scenario_id=m.get("behavior_scenario_id"),
                    journey_id=m.get("journey_id"),
                    match_confidence=m.get("match_confidence", 0.0),
                    matched_terms=m.get("matched_terms", []),
                    reason=m.get("reason", ""),
                    is_candidate_missing_scenario=m.get("is_candidate_missing_scenario", "false"),
                )
                for m in raw_mappings
            ]
        else:
            # Compute mappings dynamically
            business_behavior_mappings = behavior_mapper.map_acceptance_criteria_to_behaviors(
                acceptance_criteria=acceptance_criteria,
                behaviors=behaviors,
                scenarios=behavior_scenarios,
                journeys=journeys,
                domain_vocabulary=impact_profile.get("domain_vocabulary")
            )
        
        # Generate expected scenarios
        scenario_generator = ExpectedBehaviorScenarioGenerator(db=self.db)
        expected_scenarios = scenario_generator.generate_from_acceptance_criteria(
            acceptance_criteria=acceptance_criteria,
            affected_behaviors=behaviors,
            affected_journeys=journeys,
            recommendation_run_id=None
        )
        
        # Resolve AC coverage
        ac_coverage_resolver = AcceptanceCriteriaCoverageResolver(db=self.db)
        ac_coverage_report = ac_coverage_resolver.resolve_coverage(
            acceptance_criteria=acceptance_criteria,
            existing_tests=adjusted_bundle.test_cases,
            behavior_scenario_coverages=behavior_scenario_coverages,
            suggested_scenarios=[],
            test_coverage_links=test_coverage_links,
            business_behavior_mappings=business_behavior_mappings,
            current_pr_test_runs=None,
            repository_id=str(run_in.repository_id)
        )
        
        # Generate business intent coverage matrix
        matrix_generator = BusinessIntentCoverageMatrixGenerator(db=self.db)
        business_intent_matrix = matrix_generator.generate_matrix(
            acceptance_criteria=acceptance_criteria,
            business_intent=None,
            affected_behaviors=behaviors,
            affected_journeys=journeys,
            business_behavior_mappings=business_behavior_mappings,
            expected_scenarios=expected_scenarios,
            ac_coverage_report=ac_coverage_report,
            repository_id=str(run_in.repository_id)
        )
        
        # Add business intent coverage matrix to impact_profile
        impact_profile["business_intent_coverage_matrix"] = business_intent_matrix.model_dump()
        
        # Enrich recommendations with external test case data
        external_test_enricher = ExternalTestRecommendationEnricher(db=self.db)
        automated_test_recommendations = [
            {
                "test_identifier": t.stable_identity,
                "priority": t.priority_score,
                "reason": t.reasons[0] if t.reasons else ""
            }
            for t in ranked_bundle.ranked_candidates
        ]
        enriched_recommendations = external_test_enricher.enrich_recommendation(
            repository_id=run_in.repository_id,
            pull_request_id=db_pr.id,
            changed_files=changed_files,
            automated_test_recommendations=automated_test_recommendations
        )
        
        # Add external test recommendations to impact_profile
        impact_profile["external_test_recommendations"] = {
            "automated_tests_to_run": enriched_recommendations.automated_tests_to_run,
            "managed_manual_tests_to_execute": [
                {
                    "category": rec.category.value,
                    "external_test_case_id": str(rec.external_test_case_id) if rec.external_test_case_id else None,
                    "title": rec.title,
                    "source_tool": rec.source_tool,
                    "source_url": rec.source_url,
                    "priority": rec.priority,
                    "reason": rec.reason,
                    "linked_affected_ac": rec.linked_affected_ac,
                    "confidence": rec.confidence
                }
                for rec in enriched_recommendations.managed_manual_tests_to_execute
            ],
            "suggested_missing_scenarios": enriched_recommendations.suggested_missing_scenarios,
            "automation_candidates": [
                {
                    "category": rec.category.value,
                    "external_test_case_id": str(rec.external_test_case_id) if rec.external_test_case_id else None,
                    "title": rec.title,
                    "source_tool": rec.source_tool,
                    "source_url": rec.source_url,
                    "priority": rec.priority,
                    "reason": rec.reason,
                    "linked_affected_ac": rec.linked_affected_ac,
                    "confidence": rec.confidence
                }
                for rec in enriched_recommendations.automation_candidates
            ]
        }
        
        # Detect automation candidates for manual tests
        automation_detector = AutomationCandidateDetector(db=self.db)
        behavior_impact_res = behavior_impact_res if 'behavior_impact_res' in locals() else {"impacted_behaviors": []}
        automation_candidates = automation_detector.detect_automation_candidates(
            repository_id=run_in.repository_id,
            pull_request_id=db_pr.id,
            risk_level=risk_level,
            behavior_impact=behavior_impact_res.get("impacted_behaviors", [])
        )
        
        # Add automation candidates to impact_profile
        impact_profile["automation_candidates"] = [
            {
                "external_test_case_id": str(candidate.external_test_case_id),
                "behavior_id": str(candidate.behavior_id) if candidate.behavior_id else None,
                "scenario_intent_key": candidate.scenario_intent_key,
                "priority": candidate.priority.value,
                "reason": candidate.reason,
                "suggested_automation_layer": candidate.suggested_automation_layer.value,
                "confidence": candidate.confidence
            }
            for candidate in automation_candidates
        ]
        
        # Detect external context evidence gaps
        gap_detector = ExternalContextEvidenceGapDetector(db=self.db)
        evidence_gaps = gap_detector.detect_evidence_gaps(
            repository_id=run_in.repository_id,
            pull_request_id=db_pr.id
        )
        
        # Add evidence gaps to impact_profile
        impact_profile["external_context_evidence_gaps"] = [
            {
                "severity": gap.severity.value,
                "message": gap.message,
                "impact": gap.impact,
                "recommended_action": gap.recommended_action,
                "gap_type": gap.gap_type
            }
            for gap in evidence_gaps
        ]
        
        # Add evidence gaps to PR evidence readiness reasons
        if evidence_gaps:
            for gap in evidence_gaps:
                if gap.severity in (GapSeverity.CRITICAL, GapSeverity.HIGH):
                    pr_evidence.readiness_reasons.append(gap.message)
            if any(gap.severity in (GapSeverity.CRITICAL, GapSeverity.HIGH) for gap in evidence_gaps):
                pr_evidence.evidence_health_status = "DEGRADED"
                pr_evidence.recommendation_readiness_state = "READY_WITH_WARNINGS"
        
        # Detect requirement gaps
        from app.services.requirement_gap_detector import RequirementGapDetector
        gap_detector = RequirementGapDetector(db=self.db)
        requirement_gap_report = gap_detector.detect_gaps(
            pr_description=db_pr.title if db_pr else "",
            acceptance_criteria=acceptance_criteria,
            affected_behaviors=behaviors,
            business_behavior_mappings=business_behavior_mappings,
            ac_coverage_report=ac_coverage_report,
            changed_files=run_in.changed_files
        )
        
        # Add requirement gap report to impact_profile
        impact_profile["requirement_gap_report"] = requirement_gap_report.model_dump()
        
        # Generate PR description template suggestion if needed
        from app.services.pr_business_intent_template_helper import PRBusinessIntentTemplateHelper
        template_helper = PRBusinessIntentTemplateHelper(db=self.db)
        template_suggestion = template_helper.generate_template_suggestion(
            current_pr_description=db_pr.title if db_pr else "",
            acceptance_criteria=acceptance_criteria,
            affected_behaviors=behaviors,
            affected_journeys=journeys,
            business_behavior_mappings=business_behavior_mappings,
            changed_files=run_in.changed_files
        )
        
        # Add template suggestion to impact_profile
        impact_profile["pr_description_template_suggestion"] = template_suggestion
        
        # Persist signal breakdown for business intent
        signal_breakdown = {
            "business_intent_signals": {
                "has_acceptance_criteria": len(acceptance_criteria) > 0,
                "acceptance_criteria_count": len(acceptance_criteria),
                "business_behavior_mappings_count": len(business_behavior_mappings),
                "expected_scenarios_count": len(expected_scenarios),
                "ac_coverage_report": {
                    "total_criteria": ac_coverage_report.total_criteria if ac_coverage_report else 0,
                    "covered_by_existing_test": ac_coverage_report.covered_by_existing_test if ac_coverage_report else 0,
                    "partially_covered": ac_coverage_report.partially_covered if ac_coverage_report else 0,
                    "missing_test_coverage": ac_coverage_report.missing_test_coverage if ac_coverage_report else 0,
                    "verified_on_current_pr": ac_coverage_report.verified_on_current_pr if ac_coverage_report else 0,
                },
                "business_intent_matrix": {
                    "has_business_intent": business_intent_matrix.has_business_intent,
                    "total_intents": business_intent_matrix.total_intents,
                    "covered": business_intent_matrix.covered,
                    "partially_covered": business_intent_matrix.partially_covered,
                    "missing": business_intent_matrix.missing,
                    "verified": business_intent_matrix.verified,
                    "confidence_impact": business_intent_matrix.confidence_impact,
                },
                "requirement_gaps": {
                    "total_gaps": requirement_gap_report.total_gaps,
                    "critical_gaps": requirement_gap_report.critical_gaps,
                    "high_gaps": requirement_gap_report.high_gaps,
                    "medium_gaps": requirement_gap_report.medium_gaps,
                    "has_critical_gaps": requirement_gap_report.has_critical_gaps,
                    "overall_trust_level": requirement_gap_report.overall_trust_level,
                },
                "scoring_boosts_applied": {
                    "test_to_ac_mappings": len(test_to_ac_mappings) if 'test_to_ac_mappings' in locals() else 0,
                    "tests_with_ac_boost": len([t for t in test_to_ac_mappings.keys()]) if 'test_to_ac_mappings' in locals() else 0,
                }
            }
        }
        
        impact_profile["business_intent_signal_breakdown"] = signal_breakdown

        # Phase 2H: Calculate Recommendation Completeness Score
        from app.services.recommendation_completeness_calculator import RecommendationCompletenessCalculator
        
        # Build recommended_tests list for completeness calculation
        recommended_tests_for_completeness = []
        for t in ranked_bundle.ranked_candidates:
            tc = tcs_map.get(str(t.test_case_id))
            recommended_tests_for_completeness.append({
                "test_identifier": t.stable_identity,
                "test_name": tc.test_name if tc else t.stable_identity.split("::")[-1],
                "reason_details": candidate_trace.get(str(t.test_case_id), {}).get("reason_details", {}),
            })
        
        # Build suggested_scenarios list (will be populated later, use empty for now)
        suggested_scenarios_for_completeness = []
        
        completeness_assessment = RecommendationCompletenessCalculator.calculate(
            impact_profile=impact_profile,
            recommended_tests=recommended_tests_for_completeness,
            suggested_scenarios=suggested_scenarios_for_completeness,
            evidence_quality=pr_evidence.evidence_health_status or "UNKNOWN",
            recommendation_mode=fallback_decision.recommendation_mode or "NORMAL",
        )
        
        impact_profile["completeness_assessment"] = completeness_assessment

        db_run = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=run_in.repository_id,
            pr_id=run_in.pr_id,
            triggered_by=run_in.triggered_by,
            evidence_quality=fallback_decision.evidence_quality,
            engine_version=engine_version_str,
            recommendation_engine_version=engine_version_str,
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            fallback_policy_version="policy-v1",
            dependency_expansion_strategy_version="expansion-strategy-v1",
            recommendation_reasoning_summary=" / ".join(fallback_decision.reasons),
            pull_request_id=db_pr.id,
            pr_snapshot_id=pr_evidence.pr_snapshot_id,
            pr_sync_job_id=pr_sync_job_id,
            evidence_health_status=pr_evidence.evidence_health_status,
            recommendation_readiness_state=pr_evidence.recommendation_readiness_state,
            evidence_consistency_status=db_pr.evidence_consistency_status if db_pr else "UNKNOWN",
            readiness_dimensions=readiness_dimensions,
            evidence_fingerprint=evidence_fingerprint,
            readiness_acknowledged=run_in.readiness_acknowledged or False,
            coverage_report_id=coverage_evidence.coverage_report_id,
            dependency_state_hash=dep_expansion.dependency_state_hash or "empty_dependency_state",
            test_history_window_start=window_start,
            test_history_window_end=window_end,
            flakiness_profile_hash=hashlib.sha256(
                ",".join(sorted([str(p["test_case_id"]) for p in adjusted_bundle.flaky_profiles_used])).encode("utf-8")
            ).hexdigest() if adjusted_bundle.flaky_profiles_used else "empty_flakiness_state",
            recommendation_mode=fallback_decision.recommendation_mode,
            optimization_allowed=fallback_decision.optimization_allowed,
            unsafe_for_optimization=pr_evidence.unsafe_for_optimization,
            evidence_quality_reasons=coverage_evidence.reasons,
            estimated_runtime_seconds=ranked_bundle.total_runtime_seconds,
            full_suite_runtime_seconds=full_suite_runtime_seconds,
            runtime_confidence=runtime_conf,
            runtime_source="historical_average" if runtime_conf != "LOW" else "fallback_default",
            skipped_reason_summary=skipped_reason_summary,
            skipped_count=skipped_count,
            top_skipped_examples=top_skipped_examples,
            workspace_id=workspace_id,
            input_snapshot_hash=input_snapshot_hash,
            recommendation_snapshot_hash=recommendation_snapshot_hash,
            risk_level=risk_level,
            recommended_tests_count=recommended_tests_count,
            impact_profile=_serialize_datetime(impact_profile),
            created_at=datetime.utcnow(),
            # Persist readiness snapshot from fetched assessment
            readiness_snapshot_available=True,
            readiness_score_at_generation=readiness_assessment.readiness_score if hasattr(readiness_assessment, 'readiness_score') else None,
            readiness_level_at_generation=readiness_assessment.readiness_level if hasattr(readiness_assessment, 'readiness_level') else None,
            expected_confidence_at_generation=readiness_assessment.expected_confidence if hasattr(readiness_assessment, 'expected_confidence') else None,
            confidence_ceiling_at_generation=readiness_assessment.confidence_ceiling if hasattr(readiness_assessment, 'confidence_ceiling') else None,
            confidence_reason_at_generation=readiness_assessment.confidence_reason if hasattr(readiness_assessment, 'confidence_reason') else None,
            can_generate_at_generation=readiness_assessment.can_generate if hasattr(readiness_assessment, 'can_generate') else None,
            available_inputs_at_generation=_serialize_datetime(readiness_assessment.available_inputs) if hasattr(readiness_assessment, 'available_inputs') else None,
            missing_inputs_at_generation=_serialize_datetime(readiness_assessment.missing_inputs) if hasattr(readiness_assessment, 'missing_inputs') else None,
            blocking_inputs_at_generation=_serialize_datetime(readiness_assessment.blocking_inputs) if hasattr(readiness_assessment, 'blocking_inputs') else None,
            confidence_limiters_at_generation=_serialize_datetime(readiness_assessment.confidence_limiters) if hasattr(readiness_assessment, 'confidence_limiters') else None,
            evidence_summary_at_generation={
                "available_signals": readiness_assessment.available_signals if hasattr(readiness_assessment, 'available_signals') else [],
                "missing_signals": readiness_assessment.missing_signals if hasattr(readiness_assessment, 'missing_signals') else [],
                "primary_message": readiness_assessment.primary_message if hasattr(readiness_assessment, 'primary_message') else "",
                "secondary_message": readiness_assessment.secondary_message if hasattr(readiness_assessment, 'secondary_message') else "",
            },
            generated_from_repository_id=run_in.repository_id,
            generated_from_pull_request_id=db_pr.id,
            generation_context_version="v1.0"
        )
        self.repo.create_run(db_run)

        # 13b. Persist Journey Intelligence Snapshot
        from app.models.journey_intelligence_snapshot import JourneyIntelligenceSnapshot
        
        # Calculate overall confidence from journey impacts
        journey_confidence = "MODERATE"
        if journey_impacts:
            high_conf_count = sum(1 for j in journey_impacts if j.confidence == "HIGH")
            if high_conf_count / len(journey_impacts) >= 0.7:
                journey_confidence = "HIGH"
            elif high_conf_count / len(journey_impacts) >= 0.4:
                journey_confidence = "MODERATE"
            else:
                journey_confidence = "LOW"
        
        # Extract affected behaviors from all journey impacts
        all_affected_behaviors = []
        for impact in journey_impacts:
            all_affected_behaviors.extend(impact.affected_behaviors)
        
        journey_snapshot = JourneyIntelligenceSnapshot(
            id=uuid.uuid4(),
            recommendation_run_id=db_run.id,
            affected_journeys=journey_intelligence["affected_journeys"],
            affected_behaviors=list(set(all_affected_behaviors)),
            journey_risks=journey_intelligence["journey_risk_summary"],
            coverage_gaps=journey_intelligence["journey_coverage_gaps"],
            testing_scope=journey_intelligence["journey_based_testing_scope"],
            confidence=journey_confidence,
        )
        self.db.add(journey_snapshot)

        # 13c. Persist Behavior Impact Run and Items (idempotent, standalone or attached to recommendation)
        from app.models.behavior_impact import BehaviorImpactRun, BehaviorImpactItem
        
        # Check if an impact run already exists for this recommendation run
        behavior_impact_run = self.db.query(BehaviorImpactRun).filter(
            BehaviorImpactRun.recommendation_run_id == db_run.id
        ).first()
        
        if not behavior_impact_run:
            behavior_impact_run = BehaviorImpactRun(
                id=uuid.uuid4(),
                repository_id=run_in.repository_id,
                pull_request_id=db_pr.id,
                recommendation_run_id=db_run.id,
                impact_summary=behavior_impact_res["impact_summary"],
                confidence=behavior_impact_res["confidence"],
            )
            self.db.add(behavior_impact_run)
            self.db.flush()  # Generate ID for items reference
            
            # Persist items
            for b in behavior_impact_res["impacted_behaviors"]:
                item = BehaviorImpactItem(
                    id=uuid.uuid4(),
                    behavior_impact_run_id=behavior_impact_run.id,
                    behavior_id=UUID(b["behavior_id"]),
                    journey_id=UUID(b["journey_id"]) if b.get("journey_id") else None,
                    impact_level=b["impact_level"],
                    confidence=b["confidence"],
                    impact_reason=b["impact_reason"],
                    source_signals=b["source_signals"],
                    impacted_files=b["impacted_files"],
                    affected_scenarios=b["affected_scenarios"],
                )
                self.db.add(item)
                
            self.db.commit()

        # 13d. Resolve and Persist Behavior Scenario Coverages
        from app.services.behavior_scenario_coverage_resolver import BehaviorScenarioCoverageResolver
        resolver = BehaviorScenarioCoverageResolver(db=self.db)
        
        # Build mock coverage metrics or fetch from DB if available
        mock_mappings = []
        for b in behaviors:
            b_scenarios = behavior_scenarios_map.get(str(b.id), [])
            for s in b_scenarios:
                resolver.resolve_scenario_coverage(
                    repository_id=run_in.repository_id,
                    behavior=b,
                    scenario=s,
                    recommendation_run_id=db_run.id,
                    existing_test_mappings=[
                        {
                            "test_name": f"test_{b.slug.replace('-', '_')}_success",
                            "confidence": "HIGH",
                            "coverage_files": [ev.source_path for ev in b.evidences if ev.source_path] if b.evidences else [],
                        }
                    ],
                    current_pr_test_runs=[],
                    file_coverage_data={},
                )

        # 14. Persist Recommended Tests (RecommendationTest and RecommendedTest)
        from app.services.scenario_intent_normalizer import ScenarioIntentNormalizer
        from app.repositories.scenario_intent import ScenarioIntentRepository
        
        intent_repo = ScenarioIntentRepository(self.db)
        
        for t in ranked_bundle.ranked_candidates:
            tc_id_str = str(t.test_case_id)
            trace = candidate_trace.get(tc_id_str, {
                "reason_type": "direct_file_coverage",
                "reason_details": {}
            })
            
            # Create ScenarioIntent for this test
            tc = tcs_map.get(tc_id_str)
            test_name = tc.test_name if tc else t.stable_identity.split("::")[-1]
            
            intent_data = ScenarioIntentNormalizer.create_intent_from_scenario(
                title=test_name,
                priority="MUST" if t.priority_score >= 0.8 else "SHOULD" if t.priority_score >= 0.6 else "OPTIONAL",
                risk_category="Functional",
                related_changed_files=changed_files,
                recommendation_run_id=db_run.id
            )
            
            # Check if intent already exists in this run (deduplication)
            if not intent_repo.check_intent_exists_in_run(db_run.id, intent_data["canonical_key"]):
                intent = intent_repo.create_intent(
                    recommendation_run_id=db_run.id,
                    domain=intent_data["domain"],
                    feature=intent_data["feature"],
                    behavior=intent_data["behavior"],
                    layer=intent_data["layer"],
                    case_type=intent_data["case_type"],
                    canonical_key=intent_data["canonical_key"],
                    title=intent_data["title"],
                    priority=intent_data["priority"],
                    risk_category=intent_data["risk_category"],
                    related_changed_files=intent_data["related_changed_files"]
                )
            else:
                # Get existing intent
                intent = intent_repo.get_intent_by_canonical_key(intent_data["canonical_key"])
            
            db_test = RecommendationTest(
                recommendation_run_id=db_run.id,
                test_case_id=t.stable_identity,
                scenario_intent_id=intent.id if intent else None,
                reason_type=trace["reason_type"],
                reason_details=trace["reason_details"],
                priority_score=t.priority_score
            )
            self.repo.create_test(db_test)

            # Persist clean, durable test record
            tc = tcs_map.get(tc_id_str)
            db_recommended_test = RecommendedTest(
                id=uuid.uuid4(),
                recommendation_run_id=db_run.id,
                test_identifier=t.stable_identity,
                test_name=tc.test_name if tc else t.stable_identity.split("::")[-1],
                class_name=tc.suite_name if tc else None,
                priority=t.priority_score,
                confidence=t.mapping_confidence if engine_version_str in ("v3.0.0", "v3") else ("LOW" if not has_direct_coverage else ("HIGH" if t.priority_score >= 0.8 else "MEDIUM" if t.priority_score >= 0.6 else "LOW")),
                reason=t.reasons[0] if engine_version_str in ("v3.0.0", "v3") else ("No direct coverage match found; selected tests using historical/path fallback." if not has_direct_coverage else (t.reasons[0] if t.reasons else "Recommended via algorithm fallback.")),
                source_signal=t.evidence_sources[0] if t.evidence_sources else "UNKNOWN",
                estimated_duration_seconds=t.execution_cost,
                included=not t.is_excluded,
                warning=t.flaky_status if t.flaky_status in ("unstable", "quarantined") else None,
                created_at=datetime.utcnow()
            )
            self.db.add(db_recommended_test)

        # 14.5 Generate and Persist structural explanations
        if 'v3_recs' not in locals() or not v3_recs:
            v3_recs_local = []
            for t in ranked_bundle.ranked_candidates:
                tc = tcs_map.get(str(t.test_case_id))
                trace = candidate_trace.get(str(t.test_case_id), {})
                v3_recs_local.append({
                    "test_identifier": t.stable_identity,
                    "test_name": tc.test_name if tc else t.stable_identity.split("::")[-1],
                    "class_name/module": tc.suite_name if tc else None,
                    "priority": t.priority_score,
                    "estimated_duration_seconds": t.execution_cost,
                    "reason": t.reasons[0] if t.reasons else "Recommended.",
                    "confidence": t.mapping_confidence or "MEDIUM",
                    "source_signal": t.evidence_sources[0] if t.evidence_sources else "UNKNOWN",
                    "reason_details": trace.get("reason_details") or {
                        "coverage_link": 40 if "coverage_link" in trace.get("reason_type", "") or "direct" in trace.get("reason_type", "") else 0,
                        "knowledge_graph": 30 if "graph" in trace.get("reason_type", "") else 0,
                        "historical_failure": 10 if "history" in trace.get("reason_type", "") or "failure" in trace.get("reason_type", "") else 0,
                        "manual_override_history": 20 if "override" in trace.get("reason_type", "") else 0
                    }
                })
            v3_recs = v3_recs_local

        from app.services.recommendation_explainability_engine import RecommendationExplainabilityEngine
        explanations = RecommendationExplainabilityEngine.explain_and_persist(
            db=self.db,
            recommendation_run_id=db_run.id,
            v3_recs=v3_recs,
            changed_files=changed_files
        )

        from app.services.change_impact_graph import ChangeImpactGraphEngine
        db_run.impact_graph = ChangeImpactGraphEngine.build_graph(explanations)

        # 15. Persist RecommendationReasoningEntry records
        # Reasoning for fallback policy decision
        db_fallback_reasoning = RecommendationReasoningEntry(
            id=uuid.uuid4(),
            recommendation_run_id=db_run.id,
            reason_type="fallback_decision",
            source_entity="FallbackPolicyEngine",
            source_reference="fallback_policy",
            human_readable_reason=" / ".join(fallback_decision.reasons),
            confidence_level=fallback_decision.evidence_quality,
            evidence_priority="CRITICAL",
            metadata=fallback_decision.model_dump(),
            created_at=datetime.utcnow()
        )
        self.repo.create_reasoning_entry(db_fallback_reasoning)

        # Reasoning for each ranked test case
        for t in ranked_bundle.ranked_candidates:
            tc_id_str = str(t.test_case_id)
            trace = candidate_trace.get(tc_id_str)
            if not trace:
                continue

            ref = "HEAD"
            source_ent = t.stable_identity
            if trace["reason_type"] == "direct_file_coverage":
                source_ent = trace["reason_details"].get("file", t.stable_identity)
                ref = "coverage_report"
                human_reason = f"Direct changes detected in source '{source_ent}' mapped to test case '{t.stable_identity}' (priority: {t.priority_score:.2f})."
            elif trace["reason_type"] == "path_heuristic_fallback":
                source_ent = trace["reason_details"].get("source_file_path", t.stable_identity)
                ref = "heuristics"
                human_reason = f"Direct changed source file '{source_ent}' mapped via heuristic '{trace['reason_details'].get('heuristic_type')}' to test '{t.stable_identity}'."
            elif trace["reason_type"] == "dependency_expansion":
                source_ent = trace["reason_details"].get("referenced_by", t.stable_identity)
                ref = "dependencies"
                human_reason = f"Transitive changed file neighbor '{source_ent}' maps to test '{t.stable_identity}'."
            elif trace["reason_type"] == "historical_fragility":
                source_ent = trace["reason_details"].get("normalized_pattern_key", t.stable_identity)
                ref = "fragility"
                pid = trace["reason_details"].get("pattern_id")
                explanation = trace["reason_details"].get("explanation")
                evidence_count = trace["reason_details"].get("evidence_count")
                risk_level = trace["reason_details"].get("risk_level")
                # Rule 3 & 4: Traceable human reasoning matching example pattern ID, expl, evidence, risk
                human_reason = (
                    f"Historical fragility pattern detected: {explanation} "
                    f"[Pattern ID: {pid} | Risk Level: {risk_level} | Evidence: {evidence_count} regressions]"
                )
            else:
                human_reason = f"Recommended test case '{t.stable_identity}' via reason '{trace['reason_type']}' (priority: {t.priority_score:.2f})."

            if engine_version_str in ("v3.0.0", "v3"):
                human_reason = t.reasons[0]
                confidence_level = t.mapping_confidence
                evidence_priority = "CRITICAL" if t.priority_score >= 80 else "IMPORTANT" if t.priority_score >= 50 else "SUPPORTING"
            else:
                if not has_direct_coverage:
                    human_reason = "No direct coverage match found; selected tests using historical/path fallback."
                    confidence_level = "LOW"
                    evidence_priority = "SUPPORTING"
                else:
                    confidence_level = "HIGH" if t.priority_score >= 0.8 else "MEDIUM" if t.priority_score >= 0.6 else "LOW"
                    evidence_priority = "CRITICAL" if t.priority_score >= 0.8 else "IMPORTANT" if t.priority_score >= 0.6 else "SUPPORTING"

            db_reasoning = RecommendationReasoningEntry(
                recommendation_run_id=db_run.id,
                test_case_id=t.test_case_id,
                reason_type=trace["reason_type"],
                source_entity=source_ent,
                source_reference=ref,
                human_readable_reason=human_reason,
                confidence_level=confidence_level,
                evidence_priority=evidence_priority,
                created_at=datetime.utcnow()
            )
            self.repo.create_reasoning_entry(db_reasoning)

        # Flaky warn reasoning entries from step 10
        for entry_dict in adjusted_bundle.reasoning_entries:
            db_flaky_entry = RecommendationReasoningEntry(
                id=uuid.UUID(entry_dict["id"]),
                recommendation_run_id=db_run.id,
                test_case_id=uuid.UUID(entry_dict["test_case_id"]) if entry_dict["test_case_id"] else None,
                reason_type=entry_dict["reason_type"],
                source_entity=entry_dict["source_entity"],
                source_reference=entry_dict["source_reference"],
                human_readable_reason=entry_dict["human_readable_reason"],
                confidence_level=entry_dict["confidence_level"],
                evidence_priority=entry_dict["evidence_priority"],
                metadata=entry_dict["metadata"],
                created_at=datetime.utcnow()
            )
            self.repo.create_reasoning_entry(db_flaky_entry)

        # 16. Persist RecommendationInputSnapshot
        # Gather external context for snapshot
        linked_work_items_snapshot = []
        acceptance_criteria_snapshot = []
        external_test_cases_snapshot = []
        external_requirement_coverage_snapshot = []
        integration_sync_status_snapshot = []
        external_context_gaps_snapshot = []

        # Include manually pasted AC from input snapshot if available
        if manual_acceptance_criteria and len(manual_acceptance_criteria) > 0:
            # Convert back to dicts for JSON-serializable snapshot persistence
            acceptance_criteria_snapshot = [
                vars(ac) if not isinstance(ac, dict) else ac
                for ac in manual_acceptance_criteria
            ]

        # Get linked work items
        from app.models.external_work_item import ExternalWorkItem
        from app.models.pull_request_work_item_link import PullRequestWorkItemLink
        work_item_links = self.db.query(PullRequestWorkItemLink).filter(
            PullRequestWorkItemLink.pull_request_id == db_pr.id
        ).all()
        for link in sorted(work_item_links, key=lambda x: str(x.external_work_item_id)):
            wi = self.db.query(ExternalWorkItem).filter(
                ExternalWorkItem.id == link.external_work_item_id
            ).first()
            if wi:
                linked_work_items_snapshot.append({
                    "id": str(wi.id),
                    "external_key": wi.external_key,
                    "provider": wi.provider,
                    "title": wi.title,
                    "status": wi.status,
                    "priority": wi.priority
                })
        
        # Get acceptance criteria
        from app.models.acceptance_criterion import AcceptanceCriterion
        ac_list = self.db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == db_pr.id
        ).all()
        for ac in sorted(ac_list, key=lambda x: str(x.id)):
            acceptance_criteria_snapshot.append({
                "id": str(ac.id),
                "text": ac.text,
                "criterion_type": ac.criterion_type,
                "source": ac.source,
                "external_work_item_id": None
            })
        
        # Get external test cases (deterministic ordering)
        from app.models.external_test_case_detailed import ExternalTestCase
        external_tests = self.db.query(ExternalTestCase).filter(
            ExternalTestCase.repository_id == run_in.repository_id,
            ExternalTestCase.is_active == True
        ).order_by(ExternalTestCase.external_key.asc()).all()
        for test in external_tests:
            external_test_cases_snapshot.append({
                "id": str(test.id),
                "external_key": test.external_key,
                "provider": test.provider,
                "title": test.title,
                "priority": test.priority,
                "automation_status": test.automation_status
            })
        
        # Get external requirement coverage from impact_profile
        if "external_requirement_coverage" in impact_profile:
            external_requirement_coverage_snapshot = impact_profile["external_requirement_coverage"]
        
        # Get integration sync status
        if "integration_sync_status" in impact_profile:
            integration_sync_status_snapshot = impact_profile["integration_sync_status"]
        
        # Get external context gaps
        if "external_context_evidence_gaps" in impact_profile:
            external_context_gaps_snapshot = impact_profile["external_context_evidence_gaps"]
        
        db_snapshot = RecommendationInputSnapshot(
            recommendation_run_id=db_run.id,
            changed_files=changed_files,
            direct_mappings_used=[
                {"test_case_id": tc_id_str} for tc_id_str in coverage_evidence.direct_test_mappings
            ],
            heuristic_mappings_used=[
                {"test_case_id": str(h.test_case_id), "type": h.heuristic_type} for h in (heuristic_bundle.heuristic_test_candidates if 'heuristic_bundle' in locals() else [])
            ],
            dependency_files_expanded=dep_expansion.expanded_files,
            coverage_links_used=[
                {"file_path": link} for link in coverage_evidence.coverage_links_by_file.keys()
            ],
            flaky_profiles_used=adjusted_bundle.flaky_profiles_used,
            historical_failures_used=history_failures_used,
            degradation_rules_triggered=fallback_decision.reasons,
            ranking_inputs={
                str(t.test_case_id): t.priority_score for t in ranked_bundle.ranked_candidates
            },
            linked_work_items=linked_work_items_snapshot,
            acceptance_criteria=acceptance_criteria_snapshot,
            external_test_cases=external_test_cases_snapshot,
            external_requirement_coverage=external_requirement_coverage_snapshot,
            integration_sync_status=integration_sync_status_snapshot,
            external_context_gaps=external_context_gaps_snapshot,
            created_at=datetime.utcnow()
        )
        self.db.add(db_snapshot)

        # 16b. Persist FragilitySnapshot (Refined deterministic snapshots)
        from app.models.fragility_pattern import FragilitySnapshot, FragilityPattern
        total_p = self.db.query(FragilityPattern).filter(FragilityPattern.repository_id == run_in.repository_id).count()
        active_p = self.db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == run_in.repository_id,
            FragilityPattern.status == "ACTIVE"
        ).count()
        stale_p = self.db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == run_in.repository_id,
            FragilityPattern.status == "STALE"
        ).count()

        sorted_ids = sorted(active_fragility_pattern_ids)
        sorted_hashes = sorted(active_fragility_pattern_hashes)
        scoring_v = "weighted.v2"
        gen_v = "v1.2.0"
        evidence_w = {"start": (datetime.utcnow() - timedelta(days=30)).isoformat(), "end": datetime.utcnow().isoformat()}
        
        evidence_window_str = str(sorted(evidence_w.items()))
        raw_snapshot_payload = f"ids:{sorted_ids}|hashes:{sorted_hashes}|scoring:{scoring_v}|gen:{gen_v}|window:{evidence_window_str}"
        snap_hash = hashlib.sha256(raw_snapshot_payload.encode("utf-8")).hexdigest()

        fragility_snap = FragilitySnapshot(
            id=uuid.uuid4(),
            repository_id=run_in.repository_id,
            recommendation_run_id=db_run.id,
            snapshot_hash=snap_hash,
            generated_at=datetime.utcnow(),
            total_patterns=total_p,
            active_patterns=active_p,
            stale_patterns=stale_p,
            generation_version=gen_v,
            scoring_version=scoring_v,
            evidence_window=evidence_w,
            generation_trigger="RECOMMENDATION_RUN",
            snapshot_metadata={
                "max_risk_level": max_risk_level,
                "intersected_patterns_count": len(changed_files_intersecting_fragility)
            },
            active_pattern_ids=active_fragility_pattern_ids,
            pattern_hashes=active_fragility_pattern_hashes,
            created_at=datetime.utcnow()
        )
        self.db.add(fragility_snap)

        self.db.commit()

        # Enqueue Phase 5 Explainable GitHub PR Comment delivery if associated with a PR.
        # Skip for dry runs — MANUAL_DRY_RUN must never post a GitHub comment.
        if db_run.pull_request_id and db_run.triggered_by != "MANUAL_DRY_RUN":
            try:
                import logging
                logger = logging.getLogger("veriscope.recommendation")

                from app.services.pr_comment_update_strategy import PRCommentUpdateStrategy
                from app.services.pr_comment_service import PRCommentService

                # Atomically upsert + coalesce: pins this run as the latest and
                # resets status to PENDING. Any earlier enqueued job will self-cancel
                # when it evaluates and finds it is superseded.
                strategy = PRCommentUpdateStrategy(self.db)
                strategy.coalesce_pending_runs(
                    repository_id=db_run.repository_id,
                    pull_request_id=db_run.pull_request_id,
                    new_run_id=db_run.id,
                )
                self.db.commit()

                # Enqueue delivery (idempotency check inside enqueue_delivery_task)
                service = PRCommentService(self.db)
                service.enqueue_delivery_task(db_run.id)
            except Exception as e:
                # Failure isolation: Do NOT let commenting failures crash recommendation generation
                import logging
                logger = logging.getLogger("veriscope.recommendation")
                logger.error(
                    f"Failed to initiate PR comment delivery for recommendation run {db_run.id}: {e}"
                )


        # 16c. Initialize outcome records using RecommendationOutcomeInitializer (idempotent)
        from app.services.recommendation_outcome_initializer import RecommendationOutcomeInitializer
        init_result = RecommendationOutcomeInitializer.initialize_outcomes(
            db=self.db,
            recommendation_run_id=db_run.id,
            repository_id=db_run.repository_id,
            workspace_id=db_run.workspace_id
        )
        
        # 16d. Generate and persist suggested test scenarios when exact automated coverage is weak/missing
        try:
            from app.services.suggested_test_scenario_generator import SuggestedTestScenarioGenerator
            suggested_scenarios = SuggestedTestScenarioGenerator.generate_scenarios(self.db, db_run, changed_files)
            for scenario in suggested_scenarios:
                self.db.add(scenario)
            self.db.commit()
            
            # Re-initialize outcomes to include scenario outcomes
            init_result = RecommendationOutcomeInitializer.initialize_outcomes(
                db=self.db,
                recommendation_run_id=db_run.id,
                repository_id=db_run.repository_id,
                workspace_id=db_run.workspace_id
            )
        except Exception as exc:
            import logging
            logger = logging.getLogger("veriscope.recommendation")
            logger.exception(f"Failed to generate suggested test scenarios: {exc}")

        # 17. Return populated run
        return self.repo.get_run(db_run.id)

    def record_outcome(self, run_id: uuid.UUID, outcome_in: OutcomeCreate) -> RecommendationOutcome:
        """Record human feedback and deviations with mandatory override reason constraints."""
        # 1. Ensure the run exists
        db_run = self.repo.get_run(run_id)
        if not db_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation run with ID {run_id} not found."
            )

        # 2. Check if outcome is already registered (outcomes must be unique per run)
        existing = self.repo.get_outcome_by_run_id(run_id)
        is_placeholder = False
        if existing:
            # Check if it is a default placeholder
            is_placeholder = (
                existing.executed_tests == []
                and existing.manually_added_tests == []
                and existing.manually_removed_tests == []
                and existing.was_followed is True
                and existing.override_reason is None
                and existing.feedback is None
                and existing.rollback_occurred is False
                and existing.escaped_defect is False
            )
            if not is_placeholder:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An outcome outcome has already been recorded for this recommendation run."
                )

        # 3. Check for human override and require validation
        is_overridden = (
            not outcome_in.was_followed
            or len(outcome_in.manually_added_tests) > 0
            or len(outcome_in.manually_removed_tests) > 0
        )

        VALID_OVERRIDE_REASONS = {
            "LOW_TRUST",
            "MISSING_COVERAGE",
            "KNOWN_RISKY_AREA",
            "FLAKY_TEST_CONCERN",
            "DEPLOYMENT_SENSITIVITY",
            "COMPLIANCE_REQUIREMENT",
            "OTHER"
        }

        if is_overridden:
            if not outcome_in.override_reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="override_reason is mandatory when the recommendation was overridden or not fully followed."
                )
            if outcome_in.override_reason not in VALID_OVERRIDE_REASONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid override_reason. Must be one of: {', '.join(VALID_OVERRIDE_REASONS)}"
                )

        if existing and is_placeholder:
            # Update the existing placeholder outcome record
            existing.executed_tests = outcome_in.executed_tests
            existing.manually_added_tests = outcome_in.manually_added_tests
            existing.manually_removed_tests = outcome_in.manually_removed_tests
            existing.was_followed = outcome_in.was_followed
            existing.override_reason = outcome_in.override_reason
            existing.feedback = outcome_in.feedback
            existing.rollback_occurred = outcome_in.rollback_occurred
            existing.escaped_defect = outcome_in.escaped_defect
            self.db.flush()
            
            # Create RecommendationOverride records for manually added/removed tests
            from app.models.recommendation import RecommendationOverride
            for test_id in outcome_in.manually_added_tests:
                override = RecommendationOverride(
                    recommendation_outcome_id=existing.id,
                    recommendation_run_id=run_id,
                    override_type="TEST_ADDED",
                    test_identifier=test_id,
                    reason=outcome_in.override_reason,
                    source="API"
                )
                self.db.add(override)
            
            for test_id in outcome_in.manually_removed_tests:
                override = RecommendationOverride(
                    recommendation_outcome_id=existing.id,
                    recommendation_run_id=run_id,
                    override_type="TEST_REMOVED",
                    test_identifier=test_id,
                    reason=outcome_in.override_reason,
                    source="API"
                )
                self.db.add(override)
            
            # Invoke new priority classifier (Rule 2 & Rule 3)
            from app.services.recommendation_outcome_classifier import RecommendationOutcomeClassifier
            RecommendationOutcomeClassifier.classify_and_update(self.db, existing)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing

        db_outcome = RecommendationOutcome(
            recommendation_run_id=run_id,
            executed_tests=outcome_in.executed_tests,
            manually_added_tests=outcome_in.manually_added_tests,
            manually_removed_tests=outcome_in.manually_removed_tests,
            was_followed=outcome_in.was_followed,
            override_reason=outcome_in.override_reason,
            feedback=outcome_in.feedback,
            rollback_occurred=outcome_in.rollback_occurred,
            escaped_defect=outcome_in.escaped_defect
        )
        outcome = self.repo.create_outcome(db_outcome)
        self.db.flush()
        
        # Invoke new priority classifier (Rule 2 & Rule 3)
        from app.services.recommendation_outcome_classifier import RecommendationOutcomeClassifier
        RecommendationOutcomeClassifier.classify_and_update(self.db, outcome)
        
        self.db.commit()
        return outcome

    def get_debug_chain(self, run_id: uuid.UUID) -> Dict[str, Any]:
        """Compile a highly detailed internal audit timeline for diagnostic investigations."""
        # 1. Fetch run
        db_run = self.repo.get_run(run_id)
        if not db_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation run with ID {run_id} not found."
            )

        # 2. Get reasoning entries sorted by priority
        reasoning_entries = self.repo.get_reasoning_entries(run_id)

        # 3. Formulate mock debug attributes for advisory mapping paths
        active_rules = []
        dependency_expansion_path = []

        if db_run.evidence_quality == "UNKNOWN":
            active_rules.append("INSUFFICIENT_EVIDENCE_SAFE_FALLBACK")
            dependency_expansion_path.append("system -> safe_fallback -> FULL_REGRESSION")
        elif db_run.evidence_quality == "LOW":
            if "parent_directory_fallback" in [t.reason_type for t in db_run.tests]:
                active_rules.append("MISSING_COVERAGE_MAP_SCOPE_WIDENING")
                dependency_expansion_path.append("auth/middleware.py -> Parent folder heuristic -> app/routers")
            else:
                active_rules.append("WEAK_DEPENDENCY_DATA_FULL_TRANSITIVE_EXPANSION")
                dependency_expansion_path.append("auth/middleware.py -> recursive full imports")
        elif db_run.evidence_quality == "MODERATE":
            active_rules.append("PARTIAL_MAPPING_TRANSITIVE_EXPANSION")
            dependency_expansion_path.append("auth/middleware.py -> levels: 2 -> app/models/organization.py")
        else:
            dependency_expansion_path.append("auth/middleware.py -> levels: 1 -> app/models/organization.py")

        # 4. Fetch associated ingestion jobs for the repository
        jobs = self.observability_repo.get_ingestion_jobs_by_repo(db_run.repository_id)

        # 5. Extract/derive changed files
        from app.models.pull_request import PullRequest
        changed_files = []
        pr = None
        if db_run.pr_id and db_run.pr_id.isdigit():
            pr = self.db.query(PullRequest).filter(
                PullRequest.repository_id == db_run.repository_id,
                PullRequest.number == int(db_run.pr_id)
            ).first()
        if not pr:
            pr = self.db.query(PullRequest).filter(
                PullRequest.repository_id == db_run.repository_id,
                PullRequest.head_commit_sha == db_run.pr_id
            ).first()
        if pr:
            changed_files = [f.file_path for f in pr.changed_files]
        
        if not changed_files:
            for entry in reasoning_entries:
                if entry.reason_type == "direct_file_coverage" and entry.source_entity:
                    if entry.source_entity not in changed_files:
                        changed_files.append(entry.source_entity)

        # 6. Raw Inputs Block
        raw_inputs = {
            "pr_id": db_run.pr_id,
            "repository_id": str(db_run.repository_id),
            "triggered_by": db_run.triggered_by,
            "engine_version": db_run.engine_version,
            "ruleset_version": db_run.ruleset_version,
            "degradation_policy_version": db_run.degradation_policy_version,
            "pr_snapshot_id": str(db_run.pr_snapshot_id) if db_run.pr_snapshot_id else None,
            "pr_sync_job_id": str(db_run.pr_sync_job_id) if db_run.pr_sync_job_id else None,
            "evidence_health_status": db_run.evidence_health_status,
            "evidence_consistency_status": db_run.evidence_consistency_status,
            "readiness_dimensions": db_run.readiness_dimensions,
            "evidence_fingerprint": db_run.evidence_fingerprint,
            "changed_files": changed_files
        }

        # 7. Derived Relationships Block
        derived_relationships = {
            "predicted_tests": [t.test_case_id for t in db_run.tests],
            "test_reasons": {
                t.test_case_id: {
                    "reason_type": t.reason_type,
                    "priority_score": t.priority_score,
                    "reason_details": t.reason_details
                }
                for t in db_run.tests
            },
            "dependency_expanded_files": list(set([
                entry.source_entity
                for entry in reasoning_entries
                if entry.reason_type == "dependency_expansion"
            ])),
            "flaky_warnings": list(set([
                entry.source_entity
                for entry in reasoning_entries
                if entry.reason_type == "flaky_test_warning"
            ])),
            "has_outcome": db_run.outcome is not None,
            "outcome": {
                "executed_tests": db_run.outcome.executed_tests,
                "manually_added_tests": db_run.outcome.manually_added_tests,
                "manually_removed_tests": db_run.outcome.manually_removed_tests,
                "was_followed": db_run.outcome.was_followed,
                "override_reason": db_run.outcome.override_reason,
                "feedback": db_run.outcome.feedback,
                "rollback_occurred": db_run.outcome.rollback_occurred,
                "escaped_defect": db_run.outcome.escaped_defect
            } if db_run.outcome else None
        }

        # 8. Fallback Heuristics Used
        fallback_heuristics_used = []
        if db_run.evidence_quality == "LOW" or any(entry.reason_type == "safe_fallback_mode" for entry in reasoning_entries):
            fallback_heuristics_used.append("safe_fallback_regression_safety")
        if any(t.reason_type == "path_heuristic_fallback" or t.reason_type == "parent_directory_fallback" for t in db_run.tests):
            fallback_heuristics_used.append("parent_directory_fallback_heuristic")
        if any(t.reason_type == "fallback_smoke" for t in db_run.tests):
            fallback_heuristics_used.append("fallback_smoke_default_heuristic")
        if db_run.evidence_consistency_status == "BROKEN" or db_run.evidence_health_status == "DEGRADED":
            fallback_heuristics_used.append("degraded_evidence_fallback_widening")

        # 9. Warnings
        warnings = []
        for entry in reasoning_entries:
            if entry.reason_type == "flaky_test_warning":
                warnings.append(f"Recommended test '{entry.source_entity}' is unstable/flaky: {entry.human_readable_reason}")
        if db_run.evidence_quality in ("LOW", "UNKNOWN"):
            warnings.append(f"Confidence/evidence quality is low/unknown: {db_run.evidence_quality}")
        if db_run.evidence_health_status in ("DEGRADED", "INSUFFICIENT"):
            warnings.append(f"Evidence health is degraded: {db_run.evidence_health_status}")
        
        # Check if there are missing coverage reports
        from app.models.coverage import CoverageReport
        latest_coverage = (
            self.db.query(CoverageReport)
            .filter(CoverageReport.repository_id == db_run.repository_id)
            .order_by(CoverageReport.created_at.desc())
            .first()
        )
        if not latest_coverage:
            warnings.append("No active coverage report found for this repository. Operating in path-heuristic mode.")

        # 10. Confidence Issues
        confidence_issues = []
        if db_run.evidence_health_status:
            confidence_issues.append(f"health:{db_run.evidence_health_status}")
        if db_run.evidence_consistency_status:
            confidence_issues.append(f"consistency:{db_run.evidence_consistency_status}")
        if db_run.evidence_quality:
            confidence_issues.append(f"quality:{db_run.evidence_quality}")
        if getattr(db_run, "unsafe_for_optimization", False):
            confidence_issues.append("unsafe_for_optimization")
        if db_run.outcome:
            if db_run.outcome.escaped_defect:
                confidence_issues.append("escaped_defect_reported")
            if db_run.outcome.rollback_occurred:
                confidence_issues.append("rollback_occurred_reported")

        # 11. Telemetry Block
        sync_jobs_list = []
        if db_run.pr_snapshot and db_run.pr_snapshot.pull_request:
            for job in db_run.pr_snapshot.pull_request.sync_jobs:
                sync_jobs_list.append({
                    "job_id": str(job.id),
                    "status": job.status,
                    "sync_reason": job.sync_reason,
                    "retry_count": job.retry_count,
                    "error_message": job.error_message
                })
        
        telemetry = {
            "correlation_id": db_run.evidence_fingerprint or str(db_run.id),
            "engine_version": db_run.engine_version,
            "ruleset_version": db_run.ruleset_version,
            "degradation_policy_version": db_run.degradation_policy_version,
            "sync_jobs": sync_jobs_list,
            "total_associated_jobs": len(jobs)
        }

        return {
            "run_id": db_run.id,
            "evidence_quality": db_run.evidence_quality,
            "reasoning_entries": reasoning_entries,
            "active_risk_amplification_rules": active_rules,
            "dependency_expansion_path": dependency_expansion_path,
            "evidence_quality_logic": db_run.recommendation_reasoning_summary,
            "associated_ingestion_jobs": jobs,
            "raw_inputs": raw_inputs,
            "derived_relationships": derived_relationships,
            "fallback_heuristics_used": fallback_heuristics_used,
            "warnings": warnings,
            "confidence_issues": confidence_issues,
            "telemetry": telemetry
        }


    def record_feedback(self, run_id: UUID, feedback_in: FeedbackCreate) -> RecommendationOutcome:
        """Record human feedback/feedback_state for a recommendation run in an append-only timeline."""
        from app.services.recommendation_engineer_feedback_capture import RecommendationEngineerFeedbackCapture
        
        # 1. Ensure the run exists
        db_run = self.repo.get_run(run_id)
        if not db_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation run with ID {run_id} not found."
            )

        # 2. Delegate logic to RecommendationEngineerFeedbackCapture
        try:
            # We map any feedback state to the capture service
            RecommendationEngineerFeedbackCapture.capture_feedback(
                db=self.db,
                recommendation_run_id=run_id,
                feedback_type=feedback_in.feedback_state,
                feedback_text=feedback_in.details
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc)
            )

        # 3. Retrieve and return parent outcome associated with the run
        outcome = self.repo.get_outcome_by_run_id(run_id)
        return outcome

    def get_detailed_debug(
        self,
        run_id: UUID,
        include_input_snapshot: bool,
        include_reasoning: bool,
        include_tests: bool,
        reasoning_limit: int
    ) -> Dict[str, Any]:
        """Compile a highly detailed internal audit timeline with bounded queries and snapshots."""
        # 1. Fetch the base debug chain (which gives us all the raw/derived diagnostics)
        debug_chain = self.get_debug_chain(run_id)
        
        # 2. Fetch the recommendation run from DB
        db_run = self.repo.get_run(run_id)
        if not db_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation run with ID {run_id} not found."
            )

        # 3. Construct skipped summary
        skipped_summary = {
            "skipped_reason_summary": db_run.skipped_reason_summary,
            "skipped_count": db_run.skipped_count,
            "top_skipped_examples": db_run.top_skipped_examples
        }

        # 4. Construct test history window
        test_history_window = {
            "test_history_window_start": db_run.test_history_window_start,
            "test_history_window_end": db_run.test_history_window_end
        }

        # Build response base
        response_dict = {
            # RecommendationRun fields
            "id": db_run.id,
            "repository_id": db_run.repository_id,
            "pr_id": db_run.pr_id,
            "triggered_by": db_run.triggered_by,
            "created_at": db_run.created_at,
            "engine_version": db_run.engine_version,
            "ruleset_version": db_run.ruleset_version,
            "degradation_policy_version": db_run.degradation_policy_version,
            "recommendation_reasoning_summary": db_run.recommendation_reasoning_summary,

            # Core Debug Fields
            "run_id": db_run.id,
            "evidence_quality": db_run.evidence_quality,
            "recommendation_mode": db_run.recommendation_mode or "NORMAL",
            "unsafe_for_optimization": db_run.unsafe_for_optimization,
            "coverage_report_id": db_run.coverage_report_id,
            "dependency_state_hash": db_run.dependency_state_hash,
            "test_history_window_start": db_run.test_history_window_start,
            "test_history_window_end": db_run.test_history_window_end,
            "test_history_window": test_history_window,
            "flakiness_profile_hash": db_run.flakiness_profile_hash,
            "estimated_runtime_seconds": db_run.estimated_runtime_seconds,
            "runtime_confidence": db_run.runtime_confidence or "LOW",
            "skipped_reason_summary": db_run.skipped_reason_summary,
            "skipped_count": db_run.skipped_count,
            "top_skipped_examples": db_run.top_skipped_examples,
            "skipped_summary": skipped_summary,

            # Diagnostics timeline / Legacy fields
            "active_risk_amplification_rules": debug_chain["active_risk_amplification_rules"],
            "dependency_expansion_path": debug_chain["dependency_expansion_path"],
            "evidence_quality_logic": debug_chain["evidence_quality_logic"],
            "associated_ingestion_jobs": debug_chain["associated_ingestion_jobs"],
            "raw_inputs": debug_chain["raw_inputs"],
            "derived_relationships": debug_chain["derived_relationships"],
            "fallback_heuristics_used": debug_chain["fallback_heuristics_used"],
            "warnings": debug_chain["warnings"],
            "confidence_issues": debug_chain["confidence_issues"],
            "telemetry": debug_chain["telemetry"],
        }

        # 5. Handle input snapshot if requested
        if include_input_snapshot:
            # Query RecommendationInputSnapshot
            from app.models.recommendation import RecommendationInputSnapshot
            snapshot = self.db.query(RecommendationInputSnapshot).filter(
                RecommendationInputSnapshot.recommendation_run_id == run_id
            ).first()
            if snapshot:
                response_dict["input_snapshot"] = {
                    "changed_files": snapshot.changed_files,
                    "direct_mappings_used": snapshot.direct_mappings_used,
                    "heuristic_mappings_used": snapshot.heuristic_mappings_used,
                    "dependency_files_expanded": snapshot.dependency_files_expanded,
                    "coverage_links_used": snapshot.coverage_links_used,
                    "flaky_profiles_used": snapshot.flaky_profiles_used,
                    "historical_failures_used": snapshot.historical_failures_used,
                    "degradation_rules_triggered": snapshot.degradation_rules_triggered,
                    "ranking_inputs": snapshot.ranking_inputs,
                    "linked_work_items": snapshot.linked_work_items,
                    "acceptance_criteria": snapshot.acceptance_criteria,
                    "external_test_cases": snapshot.external_test_cases,
                    "external_requirement_coverage": snapshot.external_requirement_coverage,
                    "integration_sync_status": snapshot.integration_sync_status,
                    "external_context_gaps": snapshot.external_context_gaps,
                }
            else:
                response_dict["input_snapshot"] = {}
        else:
            response_dict["input_snapshot"] = None

        # 6. Handle reasoning entries if requested (bounded by reasoning_limit)
        if include_reasoning:
            # Since get_reasoning_entries returns sorted entries, we just slice it up to reasoning_limit
            reasoning_entries = self.repo.get_reasoning_entries(run_id)
            response_dict["reasoning_entries"] = reasoning_entries[:reasoning_limit]
        else:
            response_dict["reasoning_entries"] = None

        # 7. Handle recommended tests if requested
        if include_tests:
            response_dict["recommended_tests"] = db_run.tests
        else:
            response_dict["recommended_tests"] = None

        # 8. Handle fragility snapshot
        from app.models.fragility_pattern import FragilitySnapshot
        frag_snap = self.db.query(FragilitySnapshot).filter(
            FragilitySnapshot.recommendation_run_id == run_id
        ).first()
        if frag_snap:
            response_dict["fragility_snapshot"] = {
                "id": str(frag_snap.id),
                "repository_id": str(frag_snap.repository_id),
                "recommendation_run_id": str(frag_snap.recommendation_run_id) if frag_snap.recommendation_run_id else None,
                "snapshot_hash": frag_snap.snapshot_hash,
                "generated_at": frag_snap.generated_at.isoformat() if frag_snap.generated_at else None,
                "total_patterns": frag_snap.total_patterns,
                "active_patterns": frag_snap.active_patterns,
                "stale_patterns": frag_snap.stale_patterns,
                "generation_version": frag_snap.generation_version,
                "scoring_version": frag_snap.scoring_version,
                "evidence_window": frag_snap.evidence_window,
                "generation_trigger": frag_snap.generation_trigger,
                "snapshot_metadata": frag_snap.snapshot_metadata,
                "active_pattern_ids": frag_snap.active_pattern_ids,
                "pattern_hashes": frag_snap.pattern_hashes,
                "created_at": frag_snap.created_at.isoformat()
            }
        else:
            response_dict["fragility_snapshot"] = None

        return response_dict


