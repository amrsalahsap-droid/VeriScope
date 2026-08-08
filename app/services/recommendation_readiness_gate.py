import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session

from app.schemas.readiness import (
    AvailableInputSignal,
    MissingInputSignal,
    NextBestAction,
    RecommendationReadinessGateResult
)
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.pull_request_work_item_link import PullRequestWorkItemLink
from app.models.test_result import TestRun, TestCase
from app.models.coverage import CoverageReport
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.architecture_node import ArchitectureNode
from app.models.architecture_edge import ArchitectureEdge
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.requirement_package import RequirementPackage
from app.models.requirement_group import RequirementGroup
from app.models.business_intent import BusinessIntentOverride
from app.models.external_work_item import ExternalWorkItem
from app.models.external_test_case_detailed import ExternalTestCase
from app.models.recommendation import RecommendationRun, RecommendationOutcome
from app.models.fragility_pattern import FragilityPattern
from app.models.test_asset import TestAsset
from app.models.repository_semantic_entry import RepositorySemanticEntry
from app.services.signal_metadata import calculate_confidence_and_ceiling

logger = logging.getLogger(__name__)

def safe_count(db: Session, query: Any) -> int:
    """Helper to safely get count of a query, rolling back sub-transaction if table is missing."""
    try:
        db.begin_nested()
        count = query.count()
        db.commit()
        return count
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to execute query count: {str(e)}. Returning 0.")
        return 0

def safe_all(db: Session, query: Any) -> List[Any]:
    """Helper to safely fetch all items of a query, rolling back sub-transaction if table is missing."""
    try:
        db.begin_nested()
        results = query.all()
        db.commit()
        return results
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to execute query all: {str(e)}. Returning empty list.")
        return []

class RecommendationReadinessGate:
    """Service to decide recommendation generation capability and input completeness."""

    def assess(
        self,
        db: Session,
        repository_id: str,
        pull_request_id: Optional[str],
        recommendation_run_id: Optional[str] = None
    ) -> RecommendationReadinessGateResult:
        try:
            logger.info(f"Assessing gate readiness for repo {repository_id}, PR {pull_request_id}")
            
            repo = db.query(Repository).filter(Repository.id == repository_id).first()
            pr = db.query(PullRequest).filter(PullRequest.id == pull_request_id).first() if pull_request_id else None

            # Gather raw counts using savepoint safety
            node_count = safe_count(db, db.query(ArchitectureNode).filter(ArchitectureNode.repository_id == repository_id))
            semantic_count = safe_count(db, db.query(RepositorySemanticEntry).filter(RepositorySemanticEntry.repository_id == repository_id))
            
            changed_files_count = 0
            if pr:
                changed_files_count = safe_count(db, db.query(PullRequestChangedFile).filter(PullRequestChangedFile.pull_request_id == pr.id))
                if changed_files_count == 0 and pr.changed_files_count > 0:
                    changed_files_count = pr.changed_files_count

            total_test_runs = safe_count(db, db.query(TestRun).filter(TestRun.repository_id == repository_id))
            total_coverage_reports = safe_count(db, db.query(CoverageReport).filter(CoverageReport.repository_id == repository_id))
            
            behavior_count = safe_count(db, db.query(Behavior).filter(Behavior.repository_id == repository_id))
            journey_count = safe_count(db, db.query(Journey).filter(Journey.repository_id == repository_id))
            edge_count = safe_count(db, db.query(ArchitectureEdge).filter(ArchitectureEdge.repository_id == repository_id))
            manual_test_count = safe_count(db, db.query(ExternalTestCase).filter(ExternalTestCase.repository_id == repository_id))
            outcomes_count = safe_count(db, db.query(RecommendationOutcome).filter(RecommendationOutcome.repository_id == repository_id))
            fragility_count = safe_count(db, db.query(FragilityPattern).filter(FragilityPattern.repository_id == repository_id))
            assets_count = safe_count(db, db.query(TestAsset).filter(TestAsset.repository_id == repository_id))

            # Determine linked runs and coverage reports for current PR
            linked_runs_count = 0
            is_runs_linked = False
            if pr:
                # 1. FK check
                linked_runs_count = safe_count(db, db.query(TestRun).filter(
                    TestRun.repository_id == repository_id,
                    TestRun.pull_request_id == pr.id
                ))
                if linked_runs_count > 0:
                    is_runs_linked = True
                else:
                    # 2. Commit SHA check
                    sha_count = safe_count(db, db.query(TestRun).filter(
                        TestRun.repository_id == repository_id,
                        TestRun.commit_sha == pr.head_commit_sha
                    ))
                    if sha_count > 0:
                        is_runs_linked = True
                        linked_runs_count = sha_count
                    else:
                        # 3. Ingestion Diagnostics branch & time match
                        runs = safe_all(db, db.query(TestRun).filter(TestRun.repository_id == repository_id))
                        for run in runs:
                            run_branch = None
                            if run.ingestion_diagnostics and isinstance(run.ingestion_diagnostics, dict):
                                run_branch = run.ingestion_diagnostics.get("branch")
                            if not run_branch and run.pull_request_id:
                                run_pr = db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
                                if run_pr:
                                    run_branch = run_pr.source_branch
                            
                            pr_opened_at = pr.created_at
                            if pr.github_created_at:
                                pr_opened_at = min(pr.created_at, pr.github_created_at)
                                
                            if run_branch == pr.source_branch and run.created_at >= pr_opened_at:
                                is_runs_linked = True
                                linked_runs_count += 1

            linked_coverage_count = 0
            is_coverage_linked = False
            if pr:
                # 1. FK check
                linked_coverage_count = safe_count(db, db.query(CoverageReport).filter(
                    CoverageReport.repository_id == repository_id,
                    CoverageReport.pull_request_id == pr.id
                ))
                if linked_coverage_count > 0:
                    is_coverage_linked = True
                else:
                    # 2. Commit SHA check
                    sha_count = safe_count(db, db.query(CoverageReport).filter(
                        CoverageReport.repository_id == repository_id,
                        CoverageReport.commit_sha == pr.head_commit_sha
                    ))
                    if sha_count > 0:
                        is_coverage_linked = True
                        linked_coverage_count = sha_count
                    else:
                        # 3. Branch & time match
                        covs = safe_all(db, db.query(CoverageReport).filter(CoverageReport.repository_id == repository_id))
                        for cov in covs:
                            pr_opened_at = pr.created_at
                            if pr.github_created_at:
                                pr_opened_at = min(pr.created_at, pr.github_created_at)
                            if cov.branch == pr.source_branch and cov.created_at >= pr_opened_at:
                                is_coverage_linked = True
                                linked_coverage_count += 1

            # Determine business intent override
            has_bio = False
            bio_count = 0
            if pr:
                bio = db.query(BusinessIntentOverride).filter(
                    BusinessIntentOverride.pull_request_id == pr.id,
                    BusinessIntentOverride.is_active == True
                ).first()
                if bio and bio.business_change_summary:
                    has_bio = True
                    bio_count = 1
                
                # Check dynamic description/body in python
                pr_desc = getattr(pr, "description", None) or getattr(pr, "body", None)
                if pr_desc and isinstance(pr_desc, str) and ("business change" in pr_desc.lower() or "business intent" in pr_desc.lower() or len(pr_desc.strip()) > 50):
                    has_bio = True
                    bio_count = max(bio_count, 1)

            # Determine acceptance criteria
            has_ac = False
            ac_count = 0
            blocked_states = []
            if pr:
                # 1. RequirementPackage check
                pkg = db.query(RequirementPackage).filter(
                    RequirementPackage.repository_id == repository_id,
                    RequirementPackage.pull_request_id == pr.id
                ).first()
                if not pkg:
                    blocked_states.append("REQUIREMENT_PACKAGE_MISSING")
                else:
                    # 2. RequirementGroup check
                    groups = db.query(RequirementGroup).filter(
                        RequirementGroup.requirement_package_id == pkg.id
                    ).all()
                    if not groups:
                        blocked_states.append("NO_REQUIREMENT_GROUPS")
                    else:
                        # 3. Check group stable keys
                        for g in groups:
                            if not g.stable_group_key:
                                blocked_states.append("AMBIGUOUS_GROUP_MAPPING")
                                break
                        
                        # 4. Check stable keys on confirmed ACs and generated unaccepted ACs
                        all_acs = db.query(AcceptanceCriterion).filter(
                            AcceptanceCriterion.repository_id == repository_id,
                            AcceptanceCriterion.pull_request_id == pr.id
                        ).all()
                        ac_count = len(all_acs)
                        
                        if ac_count == 0:
                            blocked_states.append("AC_MISSING")
                        
                        for g in groups:
                            ac_keys = [ac.stable_ac_key for ac in g.acceptance_criteria if ac.stable_ac_key]
                            if len(ac_keys) != len(set(ac_keys)):
                                blocked_states.append("DUPLICATE_AC_WITHIN_GROUP")
                        
                        for ac in all_acs:
                            if ac.status == "ACCEPTED" and not ac.stable_ac_key:
                                blocked_states.append("AC_WITHOUT_STABLE_ID")
                            if ac.source == "GENERATED" and ac.status == "NEEDS_REVIEW":
                                blocked_states.append("GENERATED_AC_NOT_ACCEPTED")
                
                # Check fallback/stale/backward compatibility if no package exists
                if not pkg:
                    # Source 1: structured AC
                    struct_ac_count = safe_count(db, db.query(AcceptanceCriterion).filter(AcceptanceCriterion.pull_request_id == pr.id))
                    ac_count += struct_ac_count
                    
                    # Source 2: BusinessIntentOverride
                    bio = db.query(BusinessIntentOverride).filter(
                        BusinessIntentOverride.pull_request_id == pr.id,
                        BusinessIntentOverride.is_active == True
                    ).first()
                    if bio and bio.acceptance_criteria:
                        ac_count += 1
                    
                    # Source 3: ExternalWorkItem
                    work_items = safe_all(db, db.query(ExternalWorkItem).join(
                        PullRequestWorkItemLink, PullRequestWorkItemLink.external_work_item_id == ExternalWorkItem.id
                    ).filter(
                        PullRequestWorkItemLink.pull_request_id == pr.id
                    ))
                    for wi in work_items:
                        if wi.acceptance_criteria:
                            if isinstance(wi.acceptance_criteria, list):
                                if len(wi.acceptance_criteria) > 0:
                                    ac_count += len(wi.acceptance_criteria)
                            elif isinstance(wi.acceptance_criteria, str):
                                if wi.acceptance_criteria.strip():
                                    ac_count += 1
                
                # Deduplicate blocked states
                blocked_states = list(set(blocked_states))
                has_ac = (ac_count > 0) and (not blocked_states)

            # Determine linked work items
            has_wi = False
            wi_count = 0
            if pr:
                wi_count = safe_count(db, db.query(PullRequestWorkItemLink).filter(PullRequestWorkItemLink.pull_request_id == pr.id))
                has_wi = wi_count > 0

            # -------------------------------------------------------------
            # Define 16 inputs status and availability
            # -------------------------------------------------------------
            inputs_meta = {
                "source_code": {
                    "label": "Source Code",
                    "source": "git",
                    "description": "Source code access and index status.",
                    "available": repo is not None and repo.is_active and repo.selected_for_analysis and (node_count > 0 or semantic_count > 0),
                    "evidence_count": node_count + semantic_count,
                    "linked_to_current_pr": False,
                    "score": 20,
                    "severity": "BLOCKING",
                    "impact": "Source code access is required to generate recommendations.",
                    "action_key": "CONFIGURE_SOURCE_CODE",
                    "action_label": "Configure Source Code"
                },
                "pull_request_diff": {
                    "label": "Pull Request Diff",
                    "source": "git",
                    "description": "Pull request code changes and diff analysis.",
                    "available": pr is not None and changed_files_count > 0,
                    "evidence_count": changed_files_count,
                    "linked_to_current_pr": True,
                    "score": 20,
                    "severity": "BLOCKING",
                    "impact": "Pull request diff is required to analyze changes.",
                    "action_key": "PROVIDE_PR_DIFF",
                    "action_label": "Provide Pull Request Diff"
                },
                "test_history": {
                    "label": "Test History",
                    "source": "junit",
                    "description": "Automated test execution history.",
                    "available": total_test_runs > 0,
                    "status_override": "CURRENT_PR_EXECUTION" if is_runs_linked else "HISTORICAL_ONLY",
                    "evidence_count": total_test_runs,
                    "linked_to_current_pr": is_runs_linked,
                    "score": 10,
                    "severity": "RECOMMENDED",
                    "impact": "No historical test execution records are available to analyze regression risks.",
                    "action_key": "UPLOAD_TEST_HISTORY",
                    "action_label": "Upload Test History"
                },
                "coverage_report": {
                    "label": "Coverage Report",
                    "source": "lcov",
                    "description": "Code coverage reports.",
                    "available": total_coverage_reports > 0,
                    "status_override": "CURRENT_PR_COVERAGE" if is_coverage_linked else "HISTORICAL_OR_FALLBACK",
                    "evidence_count": total_coverage_reports,
                    "linked_to_current_pr": is_coverage_linked,
                    "score": 10,
                    "severity": "RECOMMENDED",
                    "impact": "No coverage reports are available to trace code coverage.",
                    "action_key": "UPLOAD_COVERAGE_REPORT",
                    "action_label": "Upload Coverage Report"
                },
                "business_intent": {
                    "label": "Business Intent",
                    "source": "pr_description",
                    "description": "Business change intent and summary.",
                    "available": has_bio,
                    "evidence_count": bio_count,
                    "linked_to_current_pr": True if has_bio else False,
                    "score": 5,
                    "severity": "RECOMMENDED",
                    "impact": "Business intent and change summary are not documented.",
                    "action_key": "PROVIDE_BUSINESS_INTENT",
                    "action_label": "Provide Business Intent"
                },
                "acceptance_criteria": {
                    "label": "Acceptance Criteria",
                    "source": "pr_description",
                    "description": "Functional requirement acceptance criteria.",
                    "available": has_ac,
                    "evidence_count": ac_count,
                    "linked_to_current_pr": True if has_ac else False,
                    "score": 10,
                    "severity": "BLOCKING" if blocked_states else "RECOMMENDED",
                    "impact": f"Acceptance criteria blocked: {', '.join(blocked_states)}" if blocked_states else "Requirement coverage cannot be proven.",
                    "action_key": "PASTE_ACCEPTANCE_CRITERIA",
                    "action_label": "Paste Acceptance Criteria"
                },
                "behavior_catalog": {
                    "label": "Behavior Catalog",
                    "source": "veriscope",
                    "description": "Discovered behavior catalog.",
                    "available": behavior_count > 0,
                    "evidence_count": behavior_count,
                    "linked_to_current_pr": False,
                    "score": 10,
                    "severity": "OPTIONAL",
                    "impact": "Behavior catalog is empty.",
                    "action_key": "DISCOVER_BEHAVIORS",
                    "action_label": "Discover Behaviors"
                },
                "journey_catalog": {
                    "label": "Journey Catalog",
                    "source": "veriscope",
                    "description": "User journey catalog.",
                    "available": journey_count > 0,
                    "evidence_count": journey_count,
                    "linked_to_current_pr": False,
                    "score": 10,
                    "severity": "OPTIONAL",
                    "impact": "Journey catalog is empty.",
                    "action_key": "DISCOVER_JOURNEYS",
                    "action_label": "Discover Journeys"
                },
                "architecture_graph": {
                    "label": "Architecture Graph",
                    "source": "veriscope",
                    "description": "Repository architecture graph.",
                    "available": node_count > 0 or edge_count > 0,
                    "evidence_count": node_count + edge_count,
                    "linked_to_current_pr": False,
                    "score": 10,
                    "severity": "OPTIONAL",
                    "impact": "Architecture graph is missing.",
                    "action_key": "BUILD_ARCHITECTURE_GRAPH",
                    "action_label": "Build Architecture Graph"
                },
                "current_pr_execution": {
                    "label": "Current PR Execution",
                    "source": "junit",
                    "description": "Current PR test run execution.",
                    "available": is_runs_linked,
                    "evidence_count": linked_runs_count,
                    "linked_to_current_pr": True,
                    "score": 10,
                    "severity": "OPTIONAL",
                    "impact": "Existing tests are known, but Veriscope cannot confirm they passed on this PR.",
                    "action_key": "ATTACH_TEST_RUN",
                    "action_label": "Attach Test Run"
                },
                "current_pr_coverage": {
                    "label": "Current PR Coverage",
                    "source": "lcov",
                    "description": "Current PR code coverage report.",
                    "available": is_coverage_linked,
                    "evidence_count": linked_coverage_count,
                    "linked_to_current_pr": True,
                    "score": 10,
                    "severity": "OPTIONAL",
                    "impact": "No coverage report matching current PR is available.",
                    "action_key": "UPLOAD_PR_COVERAGE",
                    "action_label": "Upload PR Coverage"
                },
                "manual_test_cases": {
                    "label": "Manual Test Cases",
                    "source": "manual_upload",
                    "description": "Managed manual test cases.",
                    "available": manual_test_count > 0,
                    "evidence_count": manual_test_count,
                    "linked_to_current_pr": False,
                    "score": 5,
                    "severity": "OPTIONAL",
                    "impact": "Manual validation coverage cannot be included in regression scope.",
                    "action_key": "UPLOAD_MANUAL_TEST_CASES",
                    "action_label": "Upload Manual Test Cases"
                },
                "historical_outcomes": {
                    "label": "Historical Outcomes",
                    "source": "veriscope",
                    "description": "Historical recommendation outcomes.",
                    "available": outcomes_count > 0,
                    "evidence_count": outcomes_count,
                    "linked_to_current_pr": False,
                    "score": 5,
                    "severity": "OPTIONAL",
                    "impact": "No historical recommendation outcomes are available.",
                    "action_key": "GENERATE_RECOMMENDATIONS",
                    "action_label": "Generate Recommendations"
                },
                "linked_work_item": {
                    "label": "Linked Work Item",
                    "source": "jira",
                    "description": "Linked project management work item.",
                    "available": has_wi,
                    "evidence_count": wi_count,
                    "linked_to_current_pr": True if has_wi else False,
                    "score": 5,
                    "severity": "OPTIONAL",
                    "impact": "Business context is limited to PR title/description.",
                    "action_key": "CONNECT_WORK_ITEM_LATER",
                    "action_label": "Connect Work Item Later"
                },
                "fragility_memory": {
                    "label": "Fragility Memory",
                    "source": "veriscope",
                    "description": "Historical code fragility memory.",
                    "available": fragility_count > 0,
                    "evidence_count": fragility_count,
                    "linked_to_current_pr": False,
                    "score": 5,
                    "severity": "OPTIONAL",
                    "impact": "No code fragility patterns have been learned yet.",
                    "action_key": "LEARN_FRAGILITY_PATTERNS",
                    "action_label": "Learn Fragility Patterns"
                },
                "managed_test_assets": {
                    "label": "Managed Test Assets",
                    "source": "veriscope",
                    "description": "Managed test assets and artifacts.",
                    "available": assets_count > 0,
                    "evidence_count": assets_count,
                    "linked_to_current_pr": False,
                    "score": 0,
                    "severity": "OPTIONAL",
                    "impact": "No managed test assets exist for the repository.",
                    "action_key": "CREATE_TEST_ASSETS",
                    "action_label": "Create Test Assets"
                }
            }

            # Map inputs to available/missing collections
            available_inputs = []
            missing_inputs = []
            blocking_inputs = []
            recommended_inputs = []
            optional_inputs = []
            next_best_actions = []

            total_score = 0
            for key, meta in inputs_meta.items():
                if meta["available"]:
                    status = meta.get("status_override", "AVAILABLE")
                    available_inputs.append(AvailableInputSignal(
                        key=key,
                        label=meta["label"],
                        status=status,
                        source=meta["source"],
                        confidence_contribution=float(meta["score"]),
                        description=meta["description"],
                        evidence_count=meta["evidence_count"],
                        linked_to_current_pr=meta["linked_to_current_pr"]
                    ))
                    total_score += meta["score"]
                else:
                    missing_sig = MissingInputSignal(
                        key=key,
                        label=meta["label"],
                        severity=meta["severity"],
                        impact=meta["impact"],
                        estimated_confidence_gain=float(meta["score"] if meta["score"] > 0 else 5.0),
                        action_key=meta["action_key"],
                        action_label=meta["action_label"]
                    )
                    missing_inputs.append(missing_sig)
                    
                    if meta["severity"] == "BLOCKING":
                        blocking_inputs.append(missing_sig)
                    elif meta["severity"] == "RECOMMENDED":
                        recommended_inputs.append(missing_sig)
                    else:
                        optional_inputs.append(missing_sig)
                    
                    # Populate next best actions for mapped items
                    next_best_actions.append(NextBestAction(
                        key=key,
                        impact=meta["impact"],
                        action=meta["action_key"]
                    ))

            # -------------------------------------------------------------
            # Score and Confidence Logic
            # -------------------------------------------------------------
            intelligence_completeness_score = min(total_score, 100)

            # Calculate confidence using the helper function
            available_signal_keys = [key for key, meta in inputs_meta.items() if meta["available"]]
            missing_signal_keys = [key for key, meta in inputs_meta.items() if not meta["available"]]
            signal_statuses = {}
            for key, meta in inputs_meta.items():
                if meta["available"]:
                    signal_statuses[key] = meta.get("status_override", "AVAILABLE")
                else:
                    signal_statuses[key] = "MISSING"

            confidence_calc = calculate_confidence_and_ceiling(
                readiness_score=intelligence_completeness_score / 100.0,
                available_signals=available_signal_keys,
                missing_signals=missing_signal_keys,
                signal_statuses=signal_statuses
            )

            expected_confidence = confidence_calc["expected_confidence"]
            confidence_ceiling = confidence_calc["confidence_ceiling"]
            confidence_reason = confidence_calc["confidence_reason"]
            generation_blockers = confidence_calc["generation_blockers"]
            confidence_limiters = confidence_calc["confidence_limiters"]

            # -------------------------------------------------------------
            # Release Confidence Ceiling Rules
            # -------------------------------------------------------------
            has_source = inputs_meta["source_code"]["available"]
            has_diff = inputs_meta["pull_request_diff"]["available"]
            has_test_history = inputs_meta["test_history"]["available"]
            has_coverage = inputs_meta["coverage_report"]["available"]
            has_ac = inputs_meta["acceptance_criteria"]["available"]
            has_execution = inputs_meta["current_pr_execution"]["available"]
            has_manual = inputs_meta["manual_test_cases"]["available"]
            has_current_coverage = inputs_meta["current_pr_coverage"]["available"]

            release_confidence_ceiling = confidence_ceiling

            # -------------------------------------------------------------
            # Readiness Level Rules - based on coverage completeness
            # -------------------------------------------------------------
            has_behavior = inputs_meta["behavior_catalog"]["available"]
            has_journey = inputs_meta["journey_catalog"]["available"]
            has_arch = inputs_meta["architecture_graph"]["available"]

            is_regression_ready = (
                has_source and has_diff and has_test_history and has_coverage and
                has_behavior and has_journey and has_arch
            )

            if not has_source or not has_diff or blocked_states:
                can_generate = False
                readiness_level = "BLOCKED"
                if blocked_states:
                    for b in blocked_states:
                        if b not in generation_blockers:
                            generation_blockers.append(b)
            else:
                can_generate = True
                if is_regression_ready and (has_ac or has_bio) and (has_execution or has_current_coverage):
                    readiness_level = "HIGH_CONFIDENCE_READY"
                elif is_regression_ready:
                    readiness_level = "REGRESSION_READY"
                elif has_test_history or has_coverage:
                    readiness_level = "EVIDENCE_READY"
                else:
                    readiness_level = "MINIMUM_READY"

            # -------------------------------------------------------------
            # Gate Status - based on scope completion state
            # -------------------------------------------------------------
            gate_status = "UNKNOWN"
            gate_reason = ""
            
            # Get scope stats from evidence snapshot
            scope_stats = self._get_scope_stats(db, repository_id, pull_request_id)
            
            if scope_stats:
                required_count = scope_stats["required_count"]
                already_verified_count = scope_stats["already_verified_count"]
                total_count = scope_stats["total_count"]
                has_scope = scope_stats["has_scope"]
                has_override = scope_stats["has_override"]
                
                gate_status = self._compute_gate_status(
                    required_count,
                    already_verified_count,
                    total_count,
                    has_scope,
                    has_override
                )
                
                # Set reason based on status
                if gate_status == "PASSED":
                    gate_reason = f"All requirements verified. {already_verified_count} items already verified, {required_count} require action."
                elif gate_status == "PASSED_WITH_OVERRIDE":
                    gate_reason = f"Scope passed with approved risk override. {required_count} items required with override."
                elif gate_status == "PARTIAL":
                    gate_reason = f"Partial scope completion. {required_count} of {total_count} items require action."
                elif gate_status == "BLOCKED":
                    gate_reason = f"Scope blocked. {required_count} of {total_count} items require action."
                else:
                    gate_reason = "Scope state unknown. Generate regression scope to determine gate status."
            else:
                # Fallback to linkage-based gate logic if no scope exists
                if is_runs_linked and is_coverage_linked:
                    gate_status = "UNKNOWN"
                    gate_reason = "Evidence linked but no scope generated. Generate regression scope to determine gate status."
                elif is_runs_linked or is_coverage_linked:
                    gate_status = "UNKNOWN"
                    gate_reason = "Partial evidence linkage. Generate regression scope to determine gate status."
                else:
                    gate_status = "UNKNOWN"
                    gate_reason = "No test execution or coverage linked. Generate regression scope to determine gate status."

            # Deterministic Sorting
            available_inputs.sort(key=lambda x: x.key)
            missing_inputs.sort(key=lambda x: x.key)
            blocking_inputs.sort(key=lambda x: x.key)
            recommended_inputs.sort(key=lambda x: x.key)
            optional_inputs.sort(key=lambda x: x.key)
            next_best_actions.sort(key=lambda x: x.key)

            # Messages & Reason
            user_messages = {
                "BLOCKED": "Recommendation generation is blocked. Critical input signals are missing.",
                "MINIMUM_READY": "Minimum ready. Veriscope can generate recommendations, but confidence is low.",
                "EVIDENCE_READY": "Evidence ready. Good test and coverage evidence is available.",
                "REGRESSION_READY": "Regression ready. Full behavioral and test evidence is available.",
                "HIGH_CONFIDENCE_READY": "High confidence ready. Comprehensive coverage and validation data are present."
            }
            user_message = user_messages.get(readiness_level, "Readiness check complete.")
            
            technical_reason = (
                f"Readiness score: {intelligence_completeness_score}%. "
                f"Confidence level: {expected_confidence} (ceiling: {release_confidence_ceiling}). "
                f"Level: {readiness_level}."
            )

            # View existing check
            can_view_existing = False
            if pull_request_id:
                can_view_existing = db.query(RecommendationRun).filter(
                    RecommendationRun.repository_id == repository_id,
                    RecommendationRun.pull_request_id == pull_request_id
                ).count() > 0
            else:
                can_view_existing = db.query(RecommendationRun).filter(
                    RecommendationRun.repository_id == repository_id,
                    RecommendationRun.pull_request_id.is_(None)
                ).count() > 0

            # Update blocking_inputs to only include true generation blockers
            true_blocking_inputs = [sig for sig in blocking_inputs if sig.key in generation_blockers]
            
            # Build confidence_limiters from signal keys
            confidence_limiters_signals = []
            for limiter_key in confidence_limiters:
                # Find the corresponding signal from missing_inputs
                for sig in missing_inputs:
                    if sig.key == limiter_key:
                        confidence_limiters_signals.append(sig)
                        break
            
            return RecommendationReadinessGateResult(
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                recommendation_run_id=recommendation_run_id,
                can_generate=can_generate,
                can_view_existing=can_view_existing,
                readiness_level=readiness_level,
                expected_confidence=expected_confidence,
                intelligence_completeness_score=intelligence_completeness_score,
                release_confidence_ceiling=release_confidence_ceiling,
                available_inputs=available_inputs,
                missing_inputs=missing_inputs,
                blocking_inputs=true_blocking_inputs,
                recommended_inputs=recommended_inputs,
                optional_inputs=optional_inputs,
                next_best_actions=next_best_actions,
                user_message=user_message,
                technical_reason=technical_reason,
                created_at=datetime.utcnow(),
                confidence_reason=confidence_reason,
                confidence_ceiling=confidence_ceiling,
                confidence_blockers=generation_blockers,
                confidence_limiters=confidence_limiters_signals,
                gate_status=gate_status,
                gate_reason=gate_reason
            )

        except Exception as e:
            logger.error(f"Error assessing readiness gate: {str(e)}", exc_info=True)
            # Safe fallback output instead of throwing raw exception
            return RecommendationReadinessGateResult(
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                recommendation_run_id=recommendation_run_id,
                can_generate=False,
                can_view_existing=False,
                readiness_level="BLOCKED",
                expected_confidence="LOW",
                intelligence_completeness_score=0,
                release_confidence_ceiling="LOW",
                available_inputs=[],
                missing_inputs=[],
                blocking_inputs=[],
                recommended_inputs=[],
                optional_inputs=[],
                next_best_actions=[],
                user_message="An internal error occurred while evaluating recommendation readiness.",
                technical_reason=f"Exception encountered: {str(e)}",
                created_at=datetime.utcnow(),
                gate_status="BLOCKED",
                gate_reason="Internal error occurred during gate assessment."
            )

    def _get_ac_coverage_stats(self, db: Session, repository_id: str, pull_request_id: Optional[str]) -> Optional[Dict[str, int]]:
        """
        Extract AC coverage statistics from the acTraceability snapshot.
        
        Returns dict with keys: total, covered, missing, partial
        Returns None if no recommendation run or snapshot exists.
        """
        from app.models.recommendation import RecommendationRun
        from uuid import UUID
        if isinstance(repository_id, str):
            try:
                repository_id = UUID(repository_id)
            except ValueError:
                pass
        if isinstance(pull_request_id, str) and pull_request_id:
            try:
                pull_request_id = UUID(pull_request_id)
            except ValueError:
                pass

        # Find the most recent recommendation run for this PR
        run = None
        if pull_request_id:
            run = db.query(RecommendationRun).filter(
                RecommendationRun.repository_id == repository_id,
                RecommendationRun.pull_request_id == pull_request_id
            ).order_by(RecommendationRun.created_at.desc()).first()
        else:
            # Fallback to most recent run without PR
            run = db.query(RecommendationRun).filter(
                RecommendationRun.repository_id == repository_id,
                RecommendationRun.pull_request_id.is_(None)
            ).order_by(RecommendationRun.created_at.desc()).first()

        if not run or not run.ac_traceability_snapshot_json:
            return None

        # Parse the acTraceability snapshot
        ac_traceability = run.ac_traceability_snapshot_json
        if not isinstance(ac_traceability, list):
            return None

        # Count coverage statuses
        total = len(ac_traceability)
        covered = 0
        missing = 0
        partial = 0

        for ac in ac_traceability:
            coverage_status = ac.get("coverageStatus", "").lower()
            if coverage_status == "covered":
                covered += 1
            elif coverage_status == "missing":
                missing += 1
            elif coverage_status == "partially covered":
                partial += 1

        return {
            "total": total,
            "covered": covered,
            "missing": missing,
            "partial": partial
        }

    def _get_scope_stats(self, db: Session, repository_id: str, pull_request_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Extract scope completion statistics from the requirement_evidence_snapshot.
        
        Returns dict with keys: required_count, already_verified_count, total_count, has_scope, has_override
        Returns None if no recommendation run or snapshot exists.
        """
        from app.models.recommendation import RecommendationRun
        from uuid import UUID
        if isinstance(repository_id, str):
            try:
                repository_id = UUID(repository_id)
            except ValueError:
                pass
        if isinstance(pull_request_id, str) and pull_request_id:
            try:
                pull_request_id = UUID(pull_request_id)
            except ValueError:
                pass

        # Find the most recent recommendation run for this PR
        run = None
        if pull_request_id:
            run = db.query(RecommendationRun).filter(
                RecommendationRun.repository_id == repository_id,
                RecommendationRun.pull_request_id == pull_request_id
            ).order_by(RecommendationRun.created_at.desc()).first()
        else:
            # Fallback to most recent run without PR
            run = db.query(RecommendationRun).filter(
                RecommendationRun.repository_id == repository_id,
                RecommendationRun.pull_request_id.is_(None)
            ).order_by(RecommendationRun.created_at.desc()).first()

        if not run or not run.requirement_evidence_snapshot_json:
            return None

        # Parse the requirement_evidence_snapshot
        import json
        snapshot = run.requirement_evidence_snapshot_json
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        
        if not isinstance(snapshot, dict):
            return None

        # Extract counts from the snapshot
        counts = snapshot.get("counts", {})
        
        # Map snapshot counts to scope stats
        # verifiedTests = already verified (covered by existing tests)
        # missingAutomatedCoverage = required but not covered
        # notMappedTraceabilityRisks = required but not mapped
        already_verified_count = counts.get("verifiedTests", 0)
        required_count = counts.get("missingAutomatedCoverage", 0) + counts.get("notMappedTraceabilityRisks", 0)
        total_count = already_verified_count + required_count + counts.get("partiallySupported", 0) + counts.get("optionalImprovements", 0)
        
        has_scope = total_count > 0
        
        # Check for risk overrides
        has_override = False
        # TODO: Check for approved risk overrides in the database
        # For now, set to False since we don't have the override table reference
        
        return {
            "required_count": required_count,
            "already_verified_count": already_verified_count,
            "total_count": total_count,
            "has_scope": has_scope,
            "has_override": has_override
        }

    def _compute_gate_status(
        self,
        required_count: int,
        already_verified_count: int,
        total_count: int,
        has_scope: bool,
        has_override: bool
    ) -> str:
        """
        Compute quality gate status from scope state.
        """
        if not has_scope:
            return "UNKNOWN"
        
        if required_count == 0 and already_verified_count > 0:
            return "PASSED"
        
        if required_count == 0 and already_verified_count == 0:
            # Nothing required and nothing verified
            # means scope is empty — suspicious
            return "UNKNOWN"
        
        if required_count > 0 and has_override:
            return "PASSED_WITH_OVERRIDE"
        
        if required_count > 0:
            if required_count == total_count:
                return "BLOCKED"
            return "PARTIAL"
        
        return "UNKNOWN"
