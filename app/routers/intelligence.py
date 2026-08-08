from typing import Optional, List, Any, Dict
from uuid import UUID
import uuid as uuid_lib
import re
import logging
from datetime import datetime
import time

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.dependencies.auth import get_current_workspace, require_workspace_member
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.journey_behavior import JourneyBehavior
from app.services.intelligence_dashboard import IntelligenceDashboardService
from app.services.github_app import GitHubAppService
from app.services.behavior_discovery_refresh_pipeline import BehaviorDiscoveryRefreshPipeline
from app.services.journey_discovery_engine import JourneyDiscoveryEngine
from app.services.repository_readiness import RepositoryReadinessService
from app.services.recommendation_readiness_service import RecommendationReadinessService

logger = logging.getLogger("veriscope.intelligence_refresh")

# Requirement group titles to skip when creating behaviors (too generic to be meaningful)
_SKIP_GROUP_TITLES = {"general requirements", "general", "misc", "miscellaneous", "other"}

router = APIRouter(
    prefix="/api/intelligence",
    tags=["Intelligence Dashboard"],
    dependencies=[Depends(require_workspace_member())],
)


@router.get("/dashboard")
def get_intelligence_dashboard(
    repository_id: Optional[UUID] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """
    Aggregate and return the Intelligence Dashboard data for the current workspace.

    Optionally filter to a single repository via `repository_id`.
    Returns HTTP 403 if `repository_id` does not belong to the authenticated workspace.
    Returns HTTP 200 with empty/zero values when no runs exist in the lookback window.
    """
    service = IntelligenceDashboardService(db)
    return service.aggregate_dashboard(
        workspace_id=workspace.id,
        repository_id=repository_id,
    )


# APIRouter for /intelligence without /api prefix
intelligence_refresh_router = APIRouter(
    prefix="/intelligence",
    tags=["Intelligence Refresh"],
    dependencies=[Depends(require_workspace_member())]
)

class RefreshRequest(BaseModel):
    include_architecture: bool = True
    include_behaviors: bool = True
    include_journeys: bool = True
    pull_request_id: Optional[str] = None
    head_commit_sha: Optional[str] = None

@intelligence_refresh_router.get("/runs/{run_id}")
def get_intelligence_run(
    run_id: UUID,
    db: Session = Depends(get_db)
):
    """Get the status and details of a specific intelligence run by run_id."""
    from app.models.repository_intelligence_run import RepositoryIntelligenceRun
    
    run = db.query(RepositoryIntelligenceRun).filter(RepositoryIntelligenceRun.id == run_id).first()
    if not run:
        return JSONResponse(status_code=404, content={
            "success": False,
            "error": "Run not found",
            "error_code": "RUN_NOT_FOUND",
        })
    
    return {
        "success": True,
        "run_id": str(run.id),
        "repository_id": str(run.repository_id),
        "pull_request_id": str(run.pull_request_id) if run.pull_request_id else None,
        "head_commit_sha": run.head_commit_sha,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "score": run.score,
        "max_score": run.max_score,
        "completed_steps": run.completed_steps_json if run.completed_steps_json else [],
        "failed_steps": run.failed_steps_json if run.failed_steps_json else [],
        "partial_errors": run.partial_errors_json if run.partial_errors_json else [],
    }

@intelligence_refresh_router.post("/repositories/{repository_id}/refresh")
def refresh_repository_intelligence(
    repository_id: UUID,
    payload: RefreshRequest,
    db: Session = Depends(get_db)
):
    from app.models.repository_intelligence_run import RepositoryIntelligenceRun
    from app.models.pull_request import PullRequest
    from app.models.requirement_package import RequirementPackage
    from app.models.requirement_group import RequirementGroup
    from app.models.acceptance_criterion import AcceptanceCriterion as ACModel
    from app.models.business_behavior_mapping import BusinessBehaviorMapping
    from app.models.behavior_scenario import BehaviorScenario
    from app.services.business_behavior_mapper import BusinessBehaviorMapper
    from app.services.input_readiness_v2_service import InputReadinessV2Service

    # 1. Lookup repository
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        return JSONResponse(status_code=404, content={
            "success": False, "error_code": "REPOSITORY_NOT_FOUND",
            "message": "Repository not found.", "recoverable": False,
        })

    if not repo.is_active or not repo.installation_id:
        return JSONResponse(status_code=400, content={
            "success": False, "error_code": "REPOSITORY_NOT_CONNECTED",
            "message": "Repository is not connected to GitHub App. Connect repository first.",
            "recoverable": True, "next_action": "CONNECT_REPOSITORY",
        })

    if not repo.last_synced_at or repo.latest_sync_status == "FAILED":
        return JSONResponse(status_code=400, content={
            "success": False, "error_code": "SOURCE_NOT_SYNCED",
            "message": "Repository source files are not synced yet. Sync repository before running intelligence.",
            "recoverable": True, "next_action": "SYNC_REPOSITORY",
        })

    # 2. Resolve PR id
    db_pr_id = None
    pr = None
    if payload.pull_request_id:
        try:
            db_pr_id = UUID(payload.pull_request_id)
            pr = db.query(PullRequest).filter(PullRequest.id == db_pr_id).first()
        except ValueError:
            pr_rec = db.query(PullRequest).filter(
                PullRequest.repository_id == repository_id,
                PullRequest.number == int(payload.pull_request_id) if payload.pull_request_id.isdigit() else None
            ).first()
            if pr_rec:
                db_pr_id = pr_rec.id
                pr = pr_rec

    # 3. Create run record
    run_record = RepositoryIntelligenceRun(
        id=uuid_lib.uuid4(),
        repository_id=repository_id,
        pull_request_id=db_pr_id,
        head_commit_sha=payload.head_commit_sha,
        started_at=datetime.utcnow(),
        status="PENDING",
    )
    db.add(run_record)
    db.commit()

    completed_steps: List[str] = []
    failed_steps: List[str] = []
    partial_errors: List[Dict[str, Any]] = []
    architecture_graph_status = "SKIPPED"
    behaviors_discovered = 0
    journeys_discovered = 0
    bbm_count = 0
    specific_behaviors_created = 0
    specific_behaviors_created_this_run = 0
    specific_behaviors_reused = 0
    meaningful_behaviors_total = 0
    requirement_behavior_mapping_attempted = False
    requirement_behavior_mapping_status = None
    requirement_behavior_mapping_error = None

    # PR linkage / changed file mapping tracking
    changed_files_count = 0
    mapped_changed_files_count = 0
    unmapped_product_files: List[str] = []
    low_confidence_files: List[str] = []
    requirement_package_exists = False
    requirement_package_id = None
    requirement_groups_count = 0
    active_requirement_groups_count = 0
    acceptance_criteria_count = 0
    active_ac_count = 0
    stable_ac_keys_count = 0
    package_source = None
    package_status = None
    changed_files_list: List[str] = []

    # Step timing tracking
    start_time = time.time()
    step_durations_ms: Dict[str, float] = {}
    step_start = start_time

    def _end_step(step_name: str, step_start_ts: float):
        step_durations_ms[step_name] = round((time.time() - step_start_ts) * 1000, 2)

    def _infer_specific_behaviors_from_pr(
        db,
        repository_id: UUID,
        pr_id: UUID,
        changed_files: list,
        pr: Optional[Any],
    ):
        """Create specific product-flow behaviors from PR changed files and metadata.

        Extracts specific product flows (e.g. 'Password Reset', 'Sign-up') from file
        paths, route names, and PR title. Generic categories such as 'Authentication',
        'User Management' are ignored as standalone behaviors.
        """
        nonlocal specific_behaviors_created, specific_behaviors_created_this_run, specific_behaviors_reused, behaviors_discovered

        from app.services.behavior_discovery_engine import BehaviorDiscoveryEngine
        from app.models.behavior_evidence import BehaviorEvidence
        from app.models.behavior import Behavior as BehaviorModel

        engine = BehaviorDiscoveryEngine(str(repository_id), db=db)

        # Collect sources: changed file paths, PR title, PR description
        all_texts = [f.file_path for f in changed_files]
        if pr:
            if pr.title:
                all_texts.append(pr.title)
            if hasattr(pr, "description") and pr.description:
                all_texts.append(pr.description)

        # Build a set of specific product flow names discovered from paths
        discovered = {}
        for text in all_texts:
            flow = engine._extract_product_flow_from_path(text)
            if flow and not engine._is_generic_category_name(flow):
                discovered.setdefault(flow, []).append(text)

        for flow_name, evidence_paths in discovered.items():
            slug = flow_name.lower().replace(" ", "-").replace("_", "-")
            existing = db.query(BehaviorModel).filter(
                BehaviorModel.repository_id == repository_id,
                BehaviorModel.slug == slug,
                BehaviorModel.is_deleted == False,
            ).first()

            if not existing:
                existing = BehaviorModel(
                    id=uuid_lib.uuid4(),
                    repository_id=repository_id,
                    name=flow_name,
                    slug=slug,
                    description=f"Specific product flow inferred from changed files/PR: {flow_name}",
                    risk_level=engine.RISK_MAPPING.get(flow_name, "MEDIUM"),
                    discovery_source="PR_INFERRED",
                    confidence="HIGH",
                    is_deleted=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(existing)
                db.flush()
                specific_behaviors_created += 1
                specific_behaviors_created_this_run += 1
                behaviors_discovered += 1
            else:
                specific_behaviors_reused += 1

            # Add evidence for each distinct path
            for path in set(evidence_paths):
                existing_ev = db.query(BehaviorEvidence).filter(
                    BehaviorEvidence.behavior_id == existing.id,
                    BehaviorEvidence.source_path == path,
                    BehaviorEvidence.evidence_type == "CHANGED_FILE",
                ).first()
                if not existing_ev:
                    db.add(BehaviorEvidence(
                        id=uuid_lib.uuid4(),
                        behavior_id=existing.id,
                        evidence_type="CHANGED_FILE",
                        source_path=path,
                        source_name=path,
                        excerpt=f"Detected in PR changed file: {path}",
                        confidence="HIGH",
                        created_at=datetime.utcnow(),
                    ))

        db.commit()

    try:
        # ── Step 1: Architecture graph ──────────────────────────────────────
        step_start = time.time()
        if payload.include_architecture:
            try:
                svc = GitHubAppService(db)
                svc.sync_repository_architecture(repo.id, repo.installation_id)
                architecture_graph_status = "AVAILABLE"
                completed_steps.append("ARCHITECTURE_GRAPH")
            except Exception as e:
                logger.exception(f"Architecture refresh failed: {e}")
                architecture_graph_status = "FAILED"
                failed_steps.append("ARCHITECTURE_GRAPH")
                partial_errors.append({
                    "code": "ARCHITECTURE_GRAPH_FAILED",
                    "severity": "warning",
                    "message": f"Architecture graph refresh failed: {str(e)[:200]}",
                })
        _end_step("ARCHITECTURE_GRAPH", step_start)

        # ── Step 2: Behavior discovery ──────────────────────────────────────
        step_start = time.time()
        if payload.include_behaviors:
            try:
                pipeline = BehaviorDiscoveryRefreshPipeline(db)
                result = pipeline.trigger_manual_refresh(repo)
                if result.success:
                    behaviors_discovered = result.behaviors_discovered
                    completed_steps.append("BEHAVIOR_DISCOVERY")
                else:
                    failed_steps.append("BEHAVIOR_DISCOVERY")
                    partial_errors.append({
                        "code": "BEHAVIOR_DISCOVERY_FAILED",
                        "severity": "warning",
                        "message": result.error_message or "Behavior discovery pipeline did not complete successfully.",
                    })
            except Exception as e:
                logger.exception(f"Behavior discovery failed: {e}")
                failed_steps.append("BEHAVIOR_DISCOVERY")
                partial_errors.append({
                    "code": "BEHAVIOR_DISCOVERY_FAILED",
                    "severity": "warning",
                    "message": str(e)[:200],
                })
        _end_step("BEHAVIOR_DISCOVERY", step_start)

        def _specific_behavior_name_from_ac(ac, group_title):
            """Derive a specific behavior name from an AC title or text."""
            text = (ac.title or ac.text or "").strip()
            if not text:
                return group_title
            # Normalize: take first sentence, remove trailing period, keep alphanumeric and spaces
            first = text.split(".")[0]
            first = re.sub(r"[^a-zA-Z0-9 ]", "", first).strip()
            # Title case first letter
            if first:
                return first[0].upper() + first[1:]
            return group_title

        # ── Step 2.5: Specific behaviors + BBMs from requirement groups ─────
        step_start = time.time()
        if payload.include_behaviors and db_pr_id:
            try:
                # Load PR changed files for fallback behavior discovery
                from app.models.pull_request import PullRequestChangedFile
                pr_changed_files = db.query(PullRequestChangedFile).filter(
                    PullRequestChangedFile.pull_request_id == db_pr_id
                ).all()
                changed_files_list = [f.file_path for f in pr_changed_files]
                changed_files_count = len(changed_files_list)

                req_pkg = db.query(RequirementPackage).filter(
                    RequirementPackage.pull_request_id == db_pr_id
                ).first()

                # Track package metadata for response
                if req_pkg:
                    requirement_package_exists = True
                    requirement_package_id = req_pkg.id
                    requirement_behavior_mapping_attempted = True
                    package_source = f"{req_pkg.source_type}:{req_pkg.source_id}" if req_pkg.source_id else req_pkg.source_type
                    package_status = req_pkg.status
                    req_groups = db.query(RequirementGroup).filter(
                        RequirementGroup.requirement_package_id == req_pkg.id
                    ).all()
                    requirement_groups_count = len(req_groups)
                    active_requirement_groups_count = len(
                        [g for g in req_groups if g.status not in ("REMOVED", "DELETED")]
                    )

                    group_ids = [g.id for g in req_groups]
                    acs = db.query(ACModel).filter(
                        ACModel.requirement_group_id.in_(group_ids)
                    ).all()
                    acceptance_criteria_count = len(acs)
                    active_acs = [ac for ac in acs if ac.status == "ACTIVE"]
                    active_ac_count = len(active_acs)
                    stable_ac_keys_count = len([ac for ac in acs if ac.stable_ac_key])

                    # Helper to detect non-behavioral / metadata-only groups
                    non_behavioral_keywords = [
                        "leftover", "parser metadata", "test data example", "junk", "placeholder",
                        "metadata bucket", "non-functional", "security note", "integration note",
                    ]

                    def _is_active_behavioral_group(group, group_active_acs):
                        if not group_active_acs:
                            return False
                        # A generic/skip-title group is only behavioral if its active ACs are
                        # not purely metadata/test text.
                        is_skip_title = group.title.lower().strip() in _SKIP_GROUP_TITLES
                        if not is_skip_title:
                            return True
                        all_non_behavioral = True
                        for ac in group_active_acs:
                            text = (ac.text or "").lower()
                            if any(k in text for k in non_behavioral_keywords):
                                pass
                            else:
                                all_non_behavioral = False
                                break
                        return not all_non_behavioral

                    for group in req_groups:
                        group_active_acs = [ac for ac in acs if ac.requirement_group_id == group.id and ac.status == "ACTIVE"]

                        if group.title.lower().strip() in _SKIP_GROUP_TITLES:
                            if not _is_active_behavioral_group(group, group_active_acs):
                                continue

                        # Determine behavior name. For regular groups, use the group title.
                        # For generic/skip-title groups with active behavioral ACs, derive the
                        # behavior name from the first active AC so it is specific.
                        if group.title.lower().strip() in _SKIP_GROUP_TITLES:
                            behavior_name = _specific_behavior_name_from_ac(group_active_acs[0], group.title)
                        else:
                            behavior_name = group.title

                        slug = re.sub(r"[^a-z0-9]+", "-", behavior_name.lower()).strip("-")
                        behavior = db.query(Behavior).filter(
                            Behavior.repository_id == repository_id,
                            Behavior.slug == slug,
                            Behavior.is_deleted == False,
                        ).first()

                        if not behavior:
                            behavior = Behavior(
                                id=uuid_lib.uuid4(),
                                repository_id=repository_id,
                                name=behavior_name,
                                slug=slug,
                                description=group.description or f"Product behavior: {behavior_name}",
                                risk_level=group.risk_level or "MEDIUM",
                                discovery_source="PR_INFERRED",
                                confidence="HIGH",
                                is_deleted=False,
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow(),
                            )
                            db.add(behavior)
                            db.flush()
                            specific_behaviors_created += 1
                            specific_behaviors_created_this_run += 1
                        else:
                            specific_behaviors_reused += 1

                        # Direct structural BBM: every active AC in the group → this behavior
                        for ac in group_active_acs:
                            existing = db.query(BusinessBehaviorMapping).filter(
                                BusinessBehaviorMapping.acceptance_criterion_id == ac.id,
                                BusinessBehaviorMapping.behavior_id == behavior.id,
                            ).first()
                            if not existing:
                                db.add(BusinessBehaviorMapping(
                                    id=uuid_lib.uuid4(),
                                    acceptance_criterion_id=ac.id,
                                    behavior_id=behavior.id,
                                    pull_request_id=db_pr_id,
                                    match_confidence=0.9,
                                    matched_terms=[group.title],
                                    reason=(
                                        f"AC belongs to requirement group '{group.title}' "
                                        f"which maps directly to this behavior."
                                    ),
                                    is_candidate_missing_scenario="false",
                                ))
                                bbm_count += 1

                    db.commit()
                    completed_steps.append("REQUIREMENT_BEHAVIOR_MAPPING")
                    requirement_behavior_mapping_status = "COMPLETED"
                    logger.info(
                        f"BBM step: {specific_behaviors_created} specific behaviors created, "
                        f"{bbm_count} BBMs created for repo {repository_id}"
                    )
                else:
                    # No requirement package: fall back to inferring specific product behaviors
                    # from PR changed files and title/description.
                    _infer_specific_behaviors_from_pr(
                        db,
                        repository_id,
                        db_pr_id,
                        pr_changed_files,
                        pr,
                    )
                    # REQUIREMENT_BEHAVIOR_MAPPING is not a failed step; it is skipped with a
                    # distinct, non-duplicated partial reason.
                    completed_steps.append("REQUIREMENT_BEHAVIOR_MAPPING")
                    partial_errors.append({
                        "code": "REQUIREMENT_BEHAVIOR_MAPPING_SKIPPED",
                        "severity": "warning",
                        "message": "Requirement-behavior mapping skipped because no requirement package exists for this PR.",
                        "details": {
                            "pull_request_id": str(db_pr_id),
                            "next_action": "ADD_REVIEW_REQUIREMENTS",
                        },
                    })

            except Exception as e:
                logger.exception(f"BBM step failed: {e}")
                requirement_behavior_mapping_status = "FAILED"
                requirement_behavior_mapping_error = str(e)
                failed_steps.append("REQUIREMENT_BEHAVIOR_MAPPING")
                partial_errors.append({
                    "code": "REQUIREMENT_BEHAVIOR_MAPPING_FAILED",
                    "severity": "warning",
                    "message": str(e)[:200],
                })
        _end_step("REQUIREMENT_BEHAVIOR_MAPPING", step_start)

        # ── Step 2.6: BehaviorScenario + BehaviorScenarioCoverage ──────────
        step_start = time.time()
        scenarios_created = 0
        coverage_records_created = 0
        if payload.include_behaviors and db_pr_id:
            try:
                from app.models.behavior_scenario import BehaviorScenario
                from app.models.behavior_scenario_coverage import BehaviorScenarioCoverage
                from app.models.test_result import TestCase
                from app.services.existing_test_to_behavior_scenario_mapper import ExistingTestToBehaviorScenarioMapper

                # Re-fetch after Step 2.5 commits
                req_pkg2 = db.query(RequirementPackage).filter(
                    RequirementPackage.pull_request_id == db_pr_id
                ).first()

                if req_pkg2:
                    req_groups2 = db.query(RequirementGroup).filter(
                        RequirementGroup.requirement_package_id == req_pkg2.id
                    ).all()

                    for group2 in req_groups2:
                        if group2.title.lower().strip() in _SKIP_GROUP_TITLES:
                            continue
                        slug2 = re.sub(r"[^a-z0-9]+", "-", group2.title.lower()).strip("-")
                        behavior2 = db.query(Behavior).filter(
                            Behavior.repository_id == repository_id,
                            Behavior.slug == slug2,
                            Behavior.is_deleted == False,
                        ).first()
                        if not behavior2:
                            continue

                        group_acs2 = db.query(ACModel).filter(
                            ACModel.requirement_group_id == group2.id
                        ).all()

                        for ac2 in group_acs2:
                            ac_text = (ac2.text or ac2.raw_text or "").strip()
                            if not ac_text:
                                continue

                            # Determine scenario type from AC text keywords
                            ac_lower = ac_text.lower()
                            if any(w in ac_lower for w in ["reject", "invalid", "fail", "error", "not allow", "prevent", "block", "deny"]):
                                sc_type = "NEGATIVE"
                            elif any(w in ac_lower for w in ["security", "token", "auth", "xss", "injection", "csrf", "brute"]):
                                sc_type = "SECURITY"
                            else:
                                sc_type = "POSITIVE"

                            sc_title = ac_text[:200]

                            # Find or create deterministic BehaviorScenario
                            existing_sc = db.query(BehaviorScenario).filter(
                                BehaviorScenario.behavior_id == behavior2.id,
                                BehaviorScenario.title == sc_title,
                            ).first()
                            if not existing_sc:
                                existing_sc = BehaviorScenario(
                                    id=uuid_lib.uuid4(),
                                    behavior_id=behavior2.id,
                                    title=sc_title,
                                    description=ac2.description or "",
                                    priority="MUST",
                                    scenario_type=sc_type,
                                    status="ACTIVE",
                                )
                                db.add(existing_sc)
                                db.flush()
                                scenarios_created += 1

                            # Link BBM to this scenario if not already set
                            bbm2 = db.query(BusinessBehaviorMapping).filter(
                                BusinessBehaviorMapping.acceptance_criterion_id == ac2.id,
                                BusinessBehaviorMapping.behavior_id == behavior2.id,
                            ).first()
                            if bbm2 and bbm2.behavior_scenario_id is None:
                                bbm2.behavior_scenario_id = existing_sc.id

                    db.commit()

                # Infer test coverage via token matching against new scenarios
                test_cases_all = db.query(TestCase).filter(
                    TestCase.repository_id == repository_id
                ).all()
                behaviors_all = db.query(Behavior).filter(
                    Behavior.repository_id == repository_id,
                    Behavior.is_deleted == False,
                ).all()
                scenarios_all = (
                    db.query(BehaviorScenario)
                    .join(Behavior, BehaviorScenario.behavior_id == Behavior.id)
                    .filter(Behavior.repository_id == repository_id)
                    .all()
                )

                if test_cases_all and scenarios_all:
                    mapper = ExistingTestToBehaviorScenarioMapper(db=db)
                    tc_mappings = mapper.map_tests_to_scenarios(
                        test_cases=test_cases_all,
                        behaviors=behaviors_all,
                        scenarios=scenarios_all,
                    )
                    for m in tc_mappings:
                        if m["confidence"] not in ("HIGH", "MEDIUM"):
                            continue
                        tc_obj = next((t for t in test_cases_all if t.stable_identity == m["test_identifier"]), None)
                        if not tc_obj:
                            continue
                        sc_id = uuid_lib.UUID(m["behavior_scenario_id"])
                        beh_id = uuid_lib.UUID(m["behavior_id"])
                        tc_id_str = str(tc_obj.id)

                        existing_cov = db.query(BehaviorScenarioCoverage).filter(
                            BehaviorScenarioCoverage.repository_id == repository_id,
                            BehaviorScenarioCoverage.behavior_scenario_id == sc_id,
                        ).first()
                        if not existing_cov:
                            db.add(BehaviorScenarioCoverage(
                                id=uuid_lib.uuid4(),
                                repository_id=repository_id,
                                behavior_id=beh_id,
                                behavior_scenario_id=sc_id,
                                coverage_status="COVERED_BY_EXISTING_TEST",
                                confidence=m["confidence"],
                                reason=m["reason"],
                                existing_tests=[tc_id_str],
                                suggested_scenarios=[],
                                coverage_files=[],
                            ))
                            coverage_records_created += 1
                        else:
                            existing_list = list(existing_cov.existing_tests or [])
                            if tc_id_str not in existing_list:
                                existing_list.append(tc_id_str)
                                existing_cov.existing_tests = existing_list
                                existing_cov.coverage_status = "COVERED_BY_EXISTING_TEST"

                    db.commit()
                    completed_steps.append("BEHAVIOR_SCENARIO_COVERAGE")
                    logger.info(
                        f"Scenario step: {scenarios_created} scenarios created, "
                        f"{coverage_records_created} coverage records created for repo {repository_id}"
                    )

            except Exception as e:
                logger.exception(f"BehaviorScenario/Coverage step failed: {e}")
                failed_steps.append("BEHAVIOR_SCENARIO_COVERAGE")
                partial_errors.append({
                    "code": "BEHAVIOR_SCENARIO_COVERAGE_FAILED",
                    "severity": "warning",
                    "message": str(e)[:200],
                })
        _end_step("BEHAVIOR_SCENARIO_COVERAGE", step_start)

        # ── Step 3: Journey discovery ───────────────────────────────────────
        step_start = time.time()
        if payload.include_journeys and "BEHAVIOR_DISCOVERY_FAILED" not in failed_steps:
            try:
                behaviors = db.query(Behavior).filter(
                    Behavior.repository_id == repo.id,
                    Behavior.is_deleted == False,
                ).all()
                if behaviors:
                    journey_engine = JourneyDiscoveryEngine(db)
                    candidates = journey_engine.discover_journeys(behaviors, str(repo.id))
                    journeys_created = 0
                    for candidate in candidates:
                        existing_journey = db.query(Journey).filter(
                            Journey.repository_id == repo.id,
                            Journey.name == candidate.name,
                            Journey.is_deleted == False,
                        ).first()
                        if existing_journey:
                            existing_journey.description = candidate.description
                            existing_journey.risk_level = candidate.risk_level
                            existing_journey.business_value = candidate.business_value
                            existing_journey.updated_at = datetime.utcnow()
                            journey = existing_journey
                        else:
                            journey = Journey(
                                id=uuid_lib.uuid4(),
                                repository_id=repo.id,
                                name=candidate.name,
                                slug=candidate.name.lower().replace(" ", "-"),
                                description=candidate.description,
                                risk_level=candidate.risk_level,
                                business_value=candidate.business_value,
                                is_deleted=False,
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow(),
                            )
                            db.add(journey)
                            journeys_created += 1
                        db.flush()
                        for behavior_name in candidate.behaviors:
                            beh = db.query(Behavior).filter(
                                Behavior.repository_id == repo.id,
                                Behavior.name == behavior_name,
                                Behavior.is_deleted == False,
                            ).first()
                            if not beh:
                                continue
                            existing_jb = db.query(JourneyBehavior).filter(
                                JourneyBehavior.journey_id == journey.id,
                                JourneyBehavior.behavior_id == beh.id,
                            ).first()
                            if not existing_jb:
                                db.add(JourneyBehavior(
                                    id=uuid_lib.uuid4(),
                                    journey_id=journey.id,
                                    behavior_id=beh.id,
                                    relationship_type="PART_OF",
                                    confidence="HIGH",
                                ))
                    db.commit()
                    journeys_discovered = journeys_created
                completed_steps.append("JOURNEY_DISCOVERY")
            except Exception as e:
                logger.exception(f"Journey discovery failed: {e}")
                failed_steps.append("JOURNEY_DISCOVERY")
                partial_errors.append({
                    "code": "JOURNEY_DISCOVERY_FAILED",
                    "severity": "warning",
                    "message": str(e)[:200],
                })
        _end_step("JOURNEY_DISCOVERY", step_start)

        # ── Step 4: Recalculate readiness ───────────────────────────────────
        step_start = time.time()
        score: Optional[float] = None
        max_score: Optional[float] = None
        readiness_reasons: List[Dict[str, Any]] = []

        try:
            repo_readiness_svc = RepositoryReadinessService(db)
            repo_readiness_svc.calculate_readiness(repo.id, repo.workspace_id)

            rec_readiness_svc = RecommendationReadinessService(db)
            rec_readiness_svc.assess_readiness(repository_id=repo.id)
            completed_steps.append("READINESS_RECALCULATION")
        except Exception as e:
            logger.exception(f"Readiness recalculation failed: {e}")
            failed_steps.append("READINESS_RECALCULATION")
        _end_step("READINESS_RECALCULATION", step_start)

        # ── Step 5: Compute Input 3 score and capture changed-file mapping metadata ─
        step_start = time.time()
        i3 = None
        try:
            readiness_svc = InputReadinessV2Service(db)
            i3 = readiness_svc._evaluate_input_3(repository_id, db_pr_id)
            score = i3.earned_score
            max_score = i3.max_score

            details = i3.details or {}
            mapped_changed_files_count = details.get("mapped_changed_files_count", 0)
            unmapped_product_files = details.get("unmapped_product_files", [])
            low_confidence_files = details.get("low_confidence_files", [])
            meaningful_behaviors_total = details.get("meaningful_behaviors_count", 0)
            behaviors_discovered = max(behaviors_discovered, meaningful_behaviors_total)

            if i3.status != "READY":
                details = i3.details or {}
                if details.get("generic_only"):
                    partial_errors.append({
                        "code": "GENERIC_BEHAVIORS_ONLY",
                        "severity": "warning",
                        "message": "Behavior map contains only generic technical categories. Specific product flows not yet discovered.",
                        "details": {
                            "behaviors_count": details.get("behaviors_count", 0),
                            "meaningful_behaviors_count": details.get("meaningful_behaviors_count", 0),
                        },
                    })
                if not details.get("mapped_changed_files_count"):
                    partial_errors.append({
                        "code": "CHANGED_FILE_BEHAVIOR_MAPPING_INCOMPLETE",
                        "severity": "warning",
                        "message": "No changed files are mapped to product behaviors.",
                        "details": {
                            "unmapped_product_files": details.get("unmapped_product_files", []),
                        },
                    })
                if not details.get("requirement_mappings_count"):
                    # Avoid duplicating the dependency error: if no requirement package exists,
                    # REQUIREMENT_BEHAVIOR_MAPPING_SKIPPED is already reported by Step 2.5.
                    if requirement_package_exists:
                        partial_errors.append({
                            "code": "REQUIREMENT_BEHAVIOR_MAPPING_MISSING",
                            "severity": "warning",
                            "message": "No requirement groups or AC stable IDs were mapped to product behaviors.",
                            "details": {
                                "business_behavior_mapping_count": 0,
                                "unmapped_requirement_groups": details.get("unmapped_requirement_groups", []),
                            },
                        })

                # Determine reason code / summary with the required priority:
                # 1. mapping step failed, 2. package missing, 3. generic-only,
                # 4. requirement mapping missing, 5. changed files unmapped.
                if "REQUIREMENT_BEHAVIOR_MAPPING" in failed_steps:
                    reason_code = "REQUIREMENT_BEHAVIOR_MAPPING_FAILED"
                    summary = f"Requirement-behavior mapping failed: {requirement_behavior_mapping_error or i3.summary}"
                elif not requirement_package_exists:
                    reason_code = "REQUIREMENT_PACKAGE_MISSING"
                    summary = "No requirement package exists for this PR."
                elif details.get("generic_only"):
                    reason_code = "GENERIC_BEHAVIORS_ONLY"
                    summary = i3.summary
                elif not details.get("requirement_mappings_count") or details.get("unmapped_requirement_groups"):
                    reason_code = "REQUIREMENT_BEHAVIOR_MAPPING_MISSING"
                    summary = i3.summary
                elif not details.get("mapped_changed_files_count"):
                    reason_code = "CHANGED_FILE_BEHAVIOR_MAPPING_INCOMPLETE"
                    summary = i3.summary
                else:
                    reason_code = "REQUIREMENT_BEHAVIOR_MAPPING_INCOMPLETE"
                    summary = i3.summary

                readiness_reasons.append({
                    "input": "INPUT_3",
                    "status": i3.status,
                    "reason_code": reason_code,
                    "summary": summary,
                    "score": i3.earned_score,
                    "max_score": i3.max_score,
                })
        except Exception as e:
            logger.warning(f"Input 3 score assessment failed: {e}")
        _end_step("INPUT_3_EVALUATION", step_start)

        # ── Determine overall run status ────────────────────────────────────
        critical_failures = [
            s for s in failed_steps
            if s not in ("READINESS_RECALCULATION", "JOURNEY_DISCOVERY")
        ]
        if not failed_steps:
            run_status = "SUCCESS"
        elif critical_failures:
            run_status = "PARTIAL" if completed_steps else "FAILED"
        else:
            run_status = "PARTIAL"

        # Promote to PARTIAL if behaviors were found but scoring shows partial
        if run_status == "SUCCESS" and score is not None and max_score and score < max_score:
            run_status = "PARTIAL"

        # ── Persist run record ──────────────────────────────────────────────
        run_record.status = run_status
        run_record.completed_at = datetime.utcnow()
        run_record.score = score
        run_record.max_score = max_score
        run_record.partial_errors_json = partial_errors or None
        run_record.completed_steps_json = completed_steps or None
        run_record.failed_steps_json = failed_steps or None
        if failed_steps:
            run_record.error_message = f"Steps with issues: {', '.join(failed_steps)}"
        db.commit()

    except Exception as e:
        run_record.status = "FAILED"
        run_record.completed_at = datetime.utcnow()
        run_record.error_message = str(e)
        db.commit()
        raise

    # ── Build response ──────────────────────────────────────────────────────
    total_duration_ms = round((time.time() - start_time) * 1000, 2)
    slowest_step = max(step_durations_ms, key=step_durations_ms.get, default="")

    success = run_status in ("SUCCESS", "PARTIAL")
    message = (
        "Repository intelligence refreshed successfully."
        if run_status == "SUCCESS"
        else "Repository intelligence refreshed with partial errors."
        if run_status == "PARTIAL"
        else "Repository intelligence refresh failed."
    )

    # Determine meaningful behavior count from the latest Input 3 evaluation
    meaningful_behaviors_count = 0
    generic_only = True
    if i3 and i3.details:
        meaningful_behaviors_count = i3.details.get("meaningful_behaviors_count", 0)
        generic_only = i3.details.get("generic_only", True)

    readiness_block = {
        "input": "INPUT_3",
        "status": i3.status if i3 else "UNKNOWN",
        "score": score,
        "max_score": max_score,
        "generic_only": generic_only,
        "meaningful_behaviors_count": meaningful_behaviors_count,
        "changed_files_count": changed_files_count,
        "mapped_changed_files_count": mapped_changed_files_count,
        "requirement_package_exists": requirement_package_exists,
        "requirement_package_id": str(requirement_package_id) if requirement_package_id else None,
        "requirement_groups_count": requirement_groups_count,
        "active_requirement_groups_count": active_requirement_groups_count,
        "acceptance_criteria_count": acceptance_criteria_count,
        "active_ac_count": active_ac_count,
        "stable_ac_keys_count": stable_ac_keys_count,
        "package_source": package_source,
        "package_status": package_status,
        "requirement_mappings_count": i3.details.get("requirement_mappings_count", 0) if i3 and i3.details else 0,
        "unmapped_requirement_groups": i3.details.get("unmapped_requirement_groups", []) if i3 and i3.details else [],
        "stale": i3.details.get("is_stale", False) if i3 and i3.details else False,
    }

    requirement_package_status = {
        "exists": requirement_package_exists,
        "requirement_package_id": str(requirement_package_id) if requirement_package_id else None,
        "groups_count": requirement_groups_count,
        "active_groups_count": active_requirement_groups_count,
        "acceptance_criteria_count": acceptance_criteria_count,
        "active_ac_count": active_ac_count,
        "stable_ac_keys_count": stable_ac_keys_count,
    }

    specific_behavior_status = {
        "created_this_run": specific_behaviors_created_this_run,
        "meaningful_behaviors_total": meaningful_behaviors_total,
        "reused_existing": specific_behaviors_reused,
    }

    requirement_behavior_mapping_status = {
        "attempted": requirement_behavior_mapping_attempted,
        "status": requirement_behavior_mapping_status,
        "created_count": bbm_count,
        "unmapped_requirement_groups": i3.details.get("unmapped_requirement_groups", []) if i3 and i3.details else [],
        "error": requirement_behavior_mapping_error,
    }

    return {
        "success": success,
        "status": run_status,
        "run_id": str(run_record.id),
        "repository_id": str(repository_id),
        "pull_request_id": str(db_pr_id) if db_pr_id else None,
        "head_commit_sha": pr.head_commit_sha if pr else payload.head_commit_sha,
        "changed_files_count": changed_files_count,
        "changed_files": changed_files_list,
        "changed_files_snapshot_exists": pr is not None and pr.changed_files_count > 0,
        "mapped_changed_files_count": mapped_changed_files_count,
        "unmapped_product_files": unmapped_product_files,
        "low_confidence_files": low_confidence_files,
        "score": score,
        "max_score": max_score,
        "architecture_graph_status": architecture_graph_status,
        "behaviors_discovered": behaviors_discovered,
        "journeys_discovered": journeys_discovered,
        "specific_behaviors_created": specific_behaviors_created,
        "business_behavior_mappings_created": bbm_count,
        "behavior_scenarios_created": scenarios_created,
        "behavior_scenario_coverages_created": coverage_records_created,
        "completed_steps": completed_steps,
        "failed_steps": failed_steps,
        "partial_errors": partial_errors,
        "readiness_reasons": readiness_reasons,
        "readiness": readiness_block,
        "requirement_package_status": requirement_package_status,
        "specific_behavior_status": specific_behavior_status,
        "requirement_behavior_mapping_status": requirement_behavior_mapping_status,
        "total_duration_ms": total_duration_ms,
        "step_durations_ms": step_durations_ms,
        "slowest_step": slowest_step,
        "message": message,
    }
