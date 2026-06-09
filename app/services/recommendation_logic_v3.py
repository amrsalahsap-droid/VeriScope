import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from fastapi import HTTPException
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestRun, TestResult, TestCase
from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.flaky_test import FlakyTestProfile
from app.models.user import Workspace
from app.models.test_coverage_link import TestCoverageLink
from app.models.module_risk_profile import ModuleRiskProfile
from app.models.domain_map import DomainMap
from app.models.pattern_memory_v2 import (
    PatternMemoryV2,
    SIGNAL_TYPE_MANUAL_ADDITION,
    SIGNAL_TYPE_MANUAL_REMOVAL,
    SIGNAL_TYPE_ACCEPTED_SCENARIO,
    SIGNAL_TYPE_DISMISSED_SCENARIO,
    SIGNAL_TYPE_ESCAPED_DEFECT,
    SIGNAL_TYPE_ROLLBACK,
    SIGNAL_TYPE_EXECUTION_RESULT,
)
from app.services.domain_intelligence_engine import DomainIntelligenceEngine
from app.services.recommendation_reasoning_engine import RecommendationReasoningEngine
from app.config import settings


class RecommendationLogicV3:
    @classmethod
    def generate_recommendations(
        cls,
        db: Session,
        repository_id: UUID,
        pull_request_id: UUID,
        workspace: Workspace,
        sme_orchestrated: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes Recommendation Engine V3 multi-signal ranking algorithm,
        returning a list of recommended test entries with complete signal breakdowns.
        """
        # 1. Load changed files
        changed_files_db = (
            db.query(PullRequestChangedFile)
            .filter(PullRequestChangedFile.pull_request_id == pull_request_id)
            .order_by(PullRequestChangedFile.file_path.asc())
            .all()
        )

        # Check for empty changed files list (Case 3)
        if not changed_files_db:
            raise HTTPException(
                status_code=400,
                detail="Pull request has no changed files available for analysis."
            )

        # Check for missing test history (Case 2)
        test_runs_count = db.query(func.count(TestRun.id)).filter(
            TestRun.repository_id == repository_id
        ).scalar() or 0
        if test_runs_count == 0:
            raise HTTPException(
                status_code=400,
                detail="Repository requires test history before recommendations can run."
            )

        changed_paths = [f.file_path for f in changed_files_db]

        # Query pull request to get head_commit_sha for static architectural impact analysis
        pr = db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
        commit_sha = pr.head_commit_sha if pr else "unknown"

        # Resolve Coverage Evidence
        from app.services.coverage_evidence_resolver import CoverageEvidenceResolver
        coverage_evidence = CoverageEvidenceResolver.resolve_coverage(
            db=db,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            head_commit_sha=commit_sha,
            changed_files=changed_paths
        )

        # Analyze static architectural impact (with feature flag for V2)
        if settings.USE_ARCHITECTURE_V2:
            from app.services.architecture_v2_impact_engine import ArchitectureV2ImpactEngine
            impact_analysis = ArchitectureV2ImpactEngine.analyze_impact(
                db,
                repository_id=repository_id,
                changed_files=changed_paths
            )
        else:
            from app.services.architectural_impact_engine import ArchitecturalImpactEngine
            impact_analysis = ArchitecturalImpactEngine.analyze_impact(
                db,
                repository_id=repository_id,
                commit_sha=commit_sha,
                changed_files=changed_paths
            )
        impacted_files = set(impact_analysis.get("impacted_files", []))

        # Analyze static dependency impact
        from app.services.dependency_impact_engine import DependencyImpactEngine
        dep_impact = DependencyImpactEngine.analyze_dependency_impact(
            db,
            repository_id=repository_id,
            commit_sha=commit_sha,
            changed_files=changed_paths
        )
        indirect_impact_components = {imp["target"] for imp in dep_impact.get("indirect_impacts", [])}
        trace_by_component = {}
        for imp in dep_impact.get("indirect_impacts", []):
            target = imp["target"]
            path = imp["path"]
            trace_by_component[target] = " → ".join(path)

        # Get all test cases for repository
        test_cases = (
            db.query(TestCase)
            .filter(TestCase.repository_id == repository_id)
            .order_by(TestCase.stable_identity.asc())
            .all()
        )
        tc_map = {str(tc.id): tc for tc in test_cases}

        # Unpack ProjectUnderstandingSnapshot variables from sme_orchestrated
        snapshot = None
        domain_vocab = None
        test_term_map = {}
        affected_domains = []
        affected_journeys = []
        touched_layers = []
        has_security_risks = False
        
        if sme_orchestrated:
            snapshot = sme_orchestrated.get("project_understanding_snapshot", {})
            domain_vocab = sme_orchestrated.get("domain_vocabulary", {})
            test_term_map = domain_vocab.get("test_term_map", {}) if domain_vocab else {}
            affected_domains = snapshot.get("affected_domains", [])
            affected_journeys = snapshot.get("affected_journeys", [])
            touched_layers = snapshot.get("touched_layers", [])
            sec_assessment = snapshot.get("security_assessment", {})
            if sec_assessment and sec_assessment.get("security_risks"):
                has_security_risks = True

        # 2. Get flaky profiles
        flaky_profiles = (
            db.query(FlakyTestProfile)
            .filter(FlakyTestProfile.repository_id == repository_id)
            .all()
        )
        flaky_map = {str(p.test_case_id): p.status for p in flaky_profiles}

        # 3. Load historical failures (last 30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        recent_failures = (
            db.query(TestResult.test_case_id, func.count(TestResult.id))
            .join(TestRun, TestResult.test_run_id == TestRun.id)
            .filter(
                TestRun.repository_id == repository_id,
                TestResult.status == "failed",
                TestResult.created_at >= cutoff
            )
            .group_by(TestResult.test_case_id)
            .all()
        )
        failed_test_case_ids = set(str(row[0]) for row in recent_failures)
        failure_count_map = {str(row[0]): row[1] for row in recent_failures}

        # 4. Load average test execution cost
        avg_durations_db = (
            db.query(TestResult.test_case_id, func.avg(TestResult.duration))
            .join(TestRun, TestResult.test_run_id == TestRun.id)
            .filter(TestRun.repository_id == repository_id)
            .group_by(TestResult.test_case_id)
            .all()
        )
        duration_map = {
            str(row[0]): float(row[1]) for row in avg_durations_db if row[1] is not None
        }

        # Load Module Risk Profiles
        risk_profiles = (
            db.query(ModuleRiskProfile)
            .filter(ModuleRiskProfile.repository_id == repository_id)
            .all()
        )
        risk_map = {p.module_path: p.risk_score for p in risk_profiles}

        # Query all TestCoverageLinks for this repository and changed files
        tcl_edges = (
            db.query(TestCoverageLink)
            .filter(
                TestCoverageLink.repository_id == repository_id,
                TestCoverageLink.file_path.in_(changed_paths)
            )
            .all()
        )
        # Create a nested mapping: test_identifier -> file_path -> TestCoverageLink record
        tcl_map = {}
        for edge in tcl_edges:
            tcl_map.setdefault(edge.test_identifier, {})[edge.file_path] = edge

        # Query all PatternMemoryV2 records for this repository
        pmv2_records = []
        try:
            pmv2_records = (
                db.query(PatternMemoryV2)
                .filter(PatternMemoryV2.repository_id == repository_id)
                .all()
            )
        except Exception as exc:
            import logging
            logging.getLogger("veriscope.recommendation").warning(
                f"PatternMemoryV2 optional intelligence layer unavailable: {exc}"
            )

        # Create mappings for different signal types
        # test_identifier -> list of PatternMemoryV2 records
        pmv2_test_map = {}
        # scenario_intent_key -> list of PatternMemoryV2 records
        pmv2_scenario_map = {}
        # behavior_id -> list of PatternMemoryV2 records
        pmv2_behavior_map = {}
        
        for pm in pmv2_records:
            if pm.test_identifier:
                pmv2_test_map.setdefault(pm.test_identifier, []).append(pm)
            if pm.scenario_intent_key:
                pmv2_scenario_map.setdefault(pm.scenario_intent_key, []).append(pm)
            if pm.behavior_id:
                pmv2_behavior_map.setdefault(pm.behavior_id, []).append(pm)

        # Load FragilitySnapshotV2 for the repository
        from app.models.fragility_pattern import FragilitySnapshot
        from app.services.fragility_snapshot_generator_v2 import FragilitySnapshotGeneratorV2
        
        fragility_snapshot = None
        fragility_data = {
            "behavior_fragility": [],
            "journey_fragility": [],
            "scenario_fragility": [],
            "file_hotspots": [],
            "risky_combinations": [],
        }
        
        try:
            fragility_snapshot = (
                db.query(FragilitySnapshot)
                .filter(FragilitySnapshot.repository_id == repository_id)
                .order_by(FragilitySnapshot.generated_at.desc())
                .first()
            )
            
            if fragility_snapshot and fragility_snapshot.snapshot_metadata:
                metadata = fragility_snapshot.snapshot_metadata
                if metadata.get("v2"):
                    fragility_data = {
                        "behavior_fragility": metadata.get("behavior_fragility", []),
                        "journey_fragility": metadata.get("journey_fragility", []),
                        "scenario_fragility": metadata.get("scenario_fragility", []),
                        "file_hotspots": metadata.get("file_hotspots", []),
                        "risky_combinations": metadata.get("risky_combinations", []),
                    }
        except Exception as exc:
            import logging
            logging.getLogger("veriscope.recommendation").warning(
                f"FragilitySnapshotV2 optional intelligence layer unavailable: {exc}"
            )
        
        # Build fragility lookup maps
        # behavior_id -> fragility data
        fragile_behavior_map = {f["subject_id"]: f for f in fragility_data["behavior_fragility"] if f["subject_id"]}
        # journey_id -> fragility data
        fragile_journey_map = {f["subject_id"]: f for f in fragility_data["journey_fragility"] if f["subject_id"]}
        # scenario_key -> fragility data
        fragile_scenario_map = {f["subject_name"]: f for f in fragility_data["scenario_fragility"]}
        # file_path -> fragility data
        fragile_file_map = {f["subject_name"]: f for f in fragility_data["file_hotspots"]}


        # Load Behavior & Journey Intelligence for ranking signals
        from app.models.behavior import Behavior
        from app.models.journey import Journey
        from app.models.behavior_evidence import BehaviorEvidence as BehaviorEvidenceModel
        from app.models.behavior_scenario import BehaviorScenario
        from app.models.journey_behavior import JourneyBehavior
        from app.services.behavior_impact_analyzer import BehaviorImpactAnalyzer

        repo_behaviors = db.query(Behavior).filter(
            Behavior.repository_id == repository_id, Behavior.is_deleted == False
        ).all()
        repo_journeys = db.query(Journey).filter(
            Journey.repository_id == repository_id, Journey.is_deleted == False
        ).all()
        repo_journey_behaviors = db.query(JourneyBehavior).all()
        repo_behavior_evidences = db.query(BehaviorEvidenceModel).all()
        repo_behavior_scenarios = db.query(BehaviorScenario).all()

        # Run behavior impact analysis
        behavior_impact_analyzer = BehaviorImpactAnalyzer(db=db)
        behavior_impact_result = behavior_impact_analyzer.analyze_behavior_impact(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            changed_files=changed_paths,
            behaviors=repo_behaviors,
            behavior_evidences=repo_behavior_evidences,
            behavior_scenarios=repo_behavior_scenarios,
            journey_behaviors=repo_journey_behaviors,
            journeys=repo_journeys,
            pr_title=pr.title if pr else None,
            pr_description=None,
        )

        # Build lookup maps for fast per-test matching
        impacted_behavior_names = {b["behavior_name"].lower() for b in behavior_impact_result["impacted_behaviors"]}
        impacted_behavior_slugs = set()
        for b in behavior_impact_result["impacted_behaviors"]:
            beh = next((rb for rb in repo_behaviors if str(rb.id) == b["behavior_id"]), None)
            if beh:
                impacted_behavior_slugs.add(beh.slug.lower())

        impacted_journey_names = {j["journey_name"].lower() for j in behavior_impact_result["impacted_journeys"]}
        impacted_journey_ids = {j["journey_id"] for j in behavior_impact_result["impacted_journeys"]}

        # Map behavior to journey for journey matching
        behavior_id_to_journey_ids = {}
        for jb in repo_journey_behaviors:
            bid = str(jb.behavior_id)
            jid = str(jb.journey_id)
            behavior_id_to_journey_ids.setdefault(bid, set()).add(jid)

        # Fragile behaviors: behaviors with CRITICAL or HIGH risk
        fragile_behavior_names = set()
        for b in repo_behaviors:
            if b.risk_level in ("CRITICAL", "HIGH"):
                fragile_behavior_names.add(b.name.lower())
                fragile_behavior_names.add(b.slug.lower().replace("-", ""))

        # Load and/or learn repository domain mappings
        domains = db.query(DomainMap).filter(DomainMap.repository_id == repository_id).all()
        if not domains:
            domains = DomainIntelligenceEngine.learn_domains(db, repository_id)

        # Identify active domains matching changed files in the pull request
        active_domains = {}
        for f in changed_paths:
            f_lower = f.lower()
            for d_map in domains:
                is_in_domain = False
                if f in d_map.files:
                    is_in_domain = True
                else:
                    for domain_file in d_map.files:
                        if domain_file.lower() in f_lower or f_lower in domain_file.lower():
                            is_in_domain = True
                            break
                    if not is_in_domain:
                        for domain_mod in d_map.modules:
                            if domain_mod.lower() in f_lower or f_lower in domain_mod.lower():
                                is_in_domain = True
                                break
                
                if is_in_domain:
                    active_domains.setdefault(d_map.domain, []).append(f)

        recommended_tests = []

        for tc in test_cases:
            tc_id_str = str(tc.id)
            flaky_status = flaky_map.get(tc_id_str)

            # Quarantine exclusion
            if flaky_status == "quarantined":
                continue

            # Signals evaluation
            has_coverage_link = False
            has_knowledge_graph = False
            has_module_risk = False
            has_historical_failure = tc_id_str in failed_test_case_ids
            has_manual_override = False
            has_escaped_defect = False

            # Check matching direct links for changed files
            all_test_links = (
                db.query(FileTestLink)
                .filter(FileTestLink.test_case_id == tc.id)
                .all()
            )
            direct_links = [link for link in all_test_links if link.file_path in changed_paths]
            cov_confidence = None
            if direct_links:
                has_coverage_link = True
                conf_ranks = {"HIGH": 3, "MODERATE": 2, "LOW": 1}
                best_link = max(direct_links, key=lambda l: conf_ranks.get(l.confidence_score, 0))
                cov_confidence = best_link.confidence_score
            
            # Link via CoverageEvidenceResolver direct mappings
            if coverage_evidence and tc.stable_identity in (coverage_evidence.direct_test_mappings or []):
                has_coverage_link = True

            # Check TestCoverageLink graph edges
            tc_edges = tcl_map.get(tc.stable_identity, {})
            if tc_edges:
                has_knowledge_graph = True
                for f_path, edge in tc_edges.items():
                    if edge.override_count > 0:
                        has_manual_override = True
                    if edge.defect_count > 0:
                        has_escaped_defect = True

            # Check Module Risk for any direct link path or knowledge-graph edge
            associated_files = set(link.file_path for link in direct_links) | set(tc_edges.keys())
            for f in associated_files:
                for mod_path, risk_score in risk_map.items():
                    if (f == mod_path or f.startswith(mod_path + "/")) and risk_score > 0:
                        has_module_risk = True
                        break

            # Check Architectural Impact Boost (+30 points)
            has_architectural_impact = False
            if associated_files & impacted_files:
                has_architectural_impact = True

            # Check Indirect Dependency Impact Boost (+25 points)
            has_indirect_dependency_impact = False
            matched_indirect_trace = ""
            all_covered_files = set(link.file_path for link in all_test_links) | set(tc_edges.keys())
            for f in all_covered_files:
                comp = DependencyImpactEngine.map_path_to_component(f)
                if comp in indirect_impact_components:
                    has_indirect_dependency_impact = True
                    matched_indirect_trace = trace_by_component.get(comp, "")
                    break

            # Check Domain Match Boost (+50 points)
            domain_match_boost = 0
            matched_domain_name = ""
            tc_stable_lower = tc.stable_identity.lower()
            tc_suite_lower = tc.suite_name.lower()
            
            for d_map in domains:
                if d_map.domain in active_domains:
                    is_test_in_domain = False
                    for df in d_map.files:
                        df_lower = df.lower()
                        if df_lower in tc_stable_lower or tc_stable_lower in df_lower or df_lower in tc_suite_lower or tc_suite_lower in df_lower:
                            is_test_in_domain = True
                            break
                    if not is_test_in_domain:
                        for dm in d_map.modules:
                            dm_lower = dm.lower()
                            if dm_lower in tc_stable_lower or tc_stable_lower in dm_lower or dm_lower in tc_suite_lower or tc_suite_lower in dm_lower:
                                is_test_in_domain = True
                                break
                    if is_test_in_domain:
                        domain_match_boost = 50
                        matched_domain_name = d_map.domain
                        break

            # Module match (+30 points)
            has_module_match = False
            suite_clean = tc.suite_name.lower() if tc.suite_name else ""
            from app.services.coverage_evidence_resolver import normalize_path
            for path in changed_paths:
                norm_path = normalize_path(path)
                path_parts = [p.lower() for p in norm_path.split("/") if p]
                if suite_clean in path_parts or any(p in suite_clean for p in path_parts if p not in ("src", "app", "api")):
                    has_module_match = True
                    break

            # Token similarity (+20 points)
            has_token_match = False
            import re
            
            def get_tokens(s: str) -> set:
                if not s:
                    return set()
                words = re.split(r"[.\/\\_:-]", s.lower())
                stop_words = {"src", "app", "api", "tests", "test", "route", "page", "form", "tsx", "ts", "js", "jsx", "py", "css", "html", "modules", "spec"}
                return {w for w in words if w and w not in stop_words}
            
            changed_tokens = set()
            for path in changed_paths:
                changed_tokens.update(get_tokens(path))
            
            tc_tokens = get_tokens(tc.stable_identity)
            if tc_tokens & changed_tokens:
                has_token_match = True

            # Calculate learning-based score from PatternMemoryV2
            learning_score = 0
            learning_signals = []
            
            if tc.stable_identity in pmv2_test_map:
                for pm in pmv2_test_map[tc.stable_identity]:
                    if pm.signal_type == SIGNAL_TYPE_MANUAL_ADDITION:
                        # Manually added before: +20
                        learning_score += 20
                        learning_signals.append("manual_addition")
                    elif pm.signal_type == SIGNAL_TYPE_MANUAL_REMOVAL:
                        # Frequently removed: -10
                        learning_score -= 10
                        learning_signals.append("manual_removal")
                    elif pm.signal_type == SIGNAL_TYPE_ESCAPED_DEFECT:
                        # Previous escaped defect: +25
                        learning_score += 25
                        learning_signals.append("escaped_defect")
                    elif pm.signal_type == SIGNAL_TYPE_ROLLBACK:
                        # Previous rollback: -10 (fragile)
                        learning_score -= 10
                        learning_signals.append("rollback")
                    elif pm.signal_type == SIGNAL_TYPE_EXECUTION_RESULT:
                        # Execution result: small boost based on success rate
                        if pm.usage_count > 0:
                            success_rate = pm.success_count / pm.usage_count
                            learning_score += int(success_rate * 5)
                            learning_signals.append("execution_result")

            # Calculate SME boosts
            sme_domain_score = 0
            sme_journey_score = 0
            sme_security_score = 0
            sme_layer_score = 0
            sme_synonym_score = 0
            
            matched_sme_domains = []
            has_sme_domain_match = False
            has_sme_journey_match = False
            has_sme_security_match = False
            has_sme_layer_match = False
            has_sme_synonym_match = False
            strong_coverage_boost = 0

            if sme_orchestrated is not None:
                # 1. Domain match from SME (+25)
                for domain in affected_domains:
                    if domain in test_term_map and tc.stable_identity in test_term_map[domain]:
                        sme_domain_score = 25
                        has_sme_domain_match = True
                        matched_sme_domains.append(domain)
                        
                # 2. Journey match (+20)
                JOURNEY_TO_CAPABILITY = {
                    "User Registration Flow": "signup",
                    "User Authentication Flow": "login",
                    "Password Recovery Flow": "password reset",
                    "Payment Checkout Flow": "checkout",
                    "Subscription Billing Flow": "subscription",
                    "Notification Dispatch Flow": "notifications",
                    "User Profile Modification Flow": "profile/account",
                    "Administrative Control Flow": "admin/settings"
                }
                for j_item in affected_journeys:
                    journey_name = j_item.get("journey")
                    cap = JOURNEY_TO_CAPABILITY.get(journey_name)
                    if cap and cap in test_term_map and tc.stable_identity in test_term_map[cap]:
                        sme_journey_score = 20
                        has_sme_journey_match = True
                        break
                        
                # 3. Security-required test (+20)
                if has_security_risks:
                    sec_caps = {"login", "password reset", "signup", "admin/settings"}
                    for cap in sec_caps:
                        if cap in test_term_map and tc.stable_identity in test_term_map[cap]:
                            sme_security_score = 20
                            has_sme_security_match = True
                            break
                    if sme_security_score == 0:
                        tc_lower = tc.stable_identity.lower()
                        if any(kw in tc_lower for kw in ("security", "exploit", "abuse", "auth", "permission", "lockout", "token")):
                            sme_security_score = 20
                            has_sme_security_match = True
                            
                # 4. Touched layer match (+15)
                tc_lower = tc.stable_identity.lower()
                for layer in touched_layers:
                    if "api" in layer.lower() and any(kw in tc_lower for kw in ("api", "route", "controller", "endpoint")):
                        sme_layer_score = 15
                        has_sme_layer_match = True
                    elif "ui" in layer.lower() and any(kw in tc_lower for kw in ("ui", "page", "component", "view", "client", "frontend", "style")):
                        sme_layer_score = 15
                        has_sme_layer_match = True
                    elif "service" in layer.lower() and any(kw in tc_lower for kw in ("service", "module", "db", "model", "backend", "repo")):
                        sme_layer_score = 15
                        has_sme_layer_match = True
                        
                # 5. Synonym match (+10)
                from app.services.domain_sme_analyzer import DomainSMEAnalyzer
                for f in changed_paths:
                    if DomainSMEAnalyzer.match_terms(f, tc.stable_identity):
                        sme_synonym_score = 10
                        has_sme_synonym_match = True
                        break

                # Strong coverage link boost (+200) to ensure SME signals cannot override strong coverage links
                if has_coverage_link and cov_confidence == "HIGH":
                    strong_coverage_boost = 200

            has_sme_signals = (
                has_sme_domain_match or has_sme_journey_match or 
                has_sme_security_match or has_sme_layer_match or 
                has_sme_synonym_match
            )

            # Behavior/Journey Intelligence Matching
            behavior_match_score = 0
            journey_match_score = 0
            fragile_behavior_score = 0
            has_behavior_match = False
            has_journey_match = False
            has_fragile_behavior = False
            matched_behavior_name = ""
            matched_journey_name = ""

            tc_lower = tc.stable_identity.lower()
            tc_name_lower = (tc.test_name or "").lower()
            tc_suite_lower = (tc.suite_name or "").lower()
            tc_combined = f"{tc_lower} {tc_name_lower} {tc_suite_lower}"

            # Check if test matches any impacted behavior (+35)
            for b_name in impacted_behavior_names:
                b_tokens = b_name.replace(" ", "").replace("-", "")
                if b_tokens in tc_combined.replace(" ", "").replace("-", "").replace("_", ""):
                    behavior_match_score = 35
                    has_behavior_match = True
                    matched_behavior_name = b_name
                    break
            if not has_behavior_match:
                for b_slug in impacted_behavior_slugs:
                    b_clean = b_slug.replace("-", "")
                    if b_clean in tc_combined.replace(" ", "").replace("-", "").replace("_", ""):
                        behavior_match_score = 35
                        has_behavior_match = True
                        matched_behavior_name = b_slug
                        break

            # Check if test matches any impacted journey (+30)
            for j_name in impacted_journey_names:
                j_tokens = j_name.replace(" ", "").replace("-", "")
                if j_tokens in tc_combined.replace(" ", "").replace("-", "").replace("_", ""):
                    journey_match_score = 30
                    has_journey_match = True
                    matched_journey_name = j_name
                    break

            # Check if test covers a fragile behavior (+20)
            for fb_name in fragile_behavior_names:
                fb_clean = fb_name.replace(" ", "").replace("-", "")
                if fb_clean in tc_combined.replace(" ", "").replace("-", "").replace("_", ""):
                    fragile_behavior_score = 20
                    has_fragile_behavior = True
                    break

            # Fragility-based scoring from FragilitySnapshotV2
            fragility_score = 0
            fragility_reasons = []
            has_fragility_signals = False
            
            # Check if test is linked to fragile behavior via BehaviorScenario
            test_behavior_scenarios = [bs for bs in repo_behavior_scenarios if bs.test_identifier == tc.stable_identity]
            for bs in test_behavior_scenarios:
                behavior_id_str = str(bs.behavior_id)
                if behavior_id_str in fragile_behavior_map:
                    frag_data = fragile_behavior_map[behavior_id_str]
                    # Impacted fragile behavior: +20
                    if behavior_id_str in {b["behavior_id"] for b in behavior_impact_result["impacted_behaviors"]}:
                        fragility_score += 20
                        fragility_reasons.append(f"impacted fragile behavior: {frag_data['subject_name']}")
                        has_fragility_signals = True
                    # Previous escaped defect on behavior: +30
                    if frag_data.get("memory_type") == "ESCAPED_DEFECT_PATTERN":
                        fragility_score += 30
                        fragility_reasons.append(f"previous escaped defect on behavior: {frag_data['subject_name']}")
                        has_fragility_signals = True
                    # Rollback pattern on journey: +25
                    if frag_data.get("memory_type") == "ROLLBACK_PATTERN":
                        fragility_score += 25
                        fragility_reasons.append(f"rollback pattern on behavior: {frag_data['subject_name']}")
                        has_fragility_signals = True
                    # Repeated failure test: +15
                    if frag_data.get("memory_type") == "REPEATED_TEST_FAILURE":
                        fragility_score += 15
                        fragility_reasons.append(f"repeated failure on behavior: {frag_data['subject_name']}")
                        has_fragility_signals = True
                    # Missing coverage pattern: +15
                    if frag_data.get("memory_type") == "MISSING_COVERAGE_PATTERN":
                        fragility_score += 15
                        fragility_reasons.append(f"missing coverage on behavior: {frag_data['subject_name']}")
                        has_fragility_signals = True
                    # Stale fragility: +5 only
                    if frag_data.get("risk_level") == "LOW":
                        fragility_score += 5
                        fragility_reasons.append(f"stale fragility on behavior: {frag_data['subject_name']}")
                        has_fragility_signals = True
            
            # Check if test is linked to fragile journey
            for bs in test_behavior_scenarios:
                behavior = next((b for b in repo_behaviors if str(b.id) == str(bs.behavior_id)), None)
                if behavior and behavior.journey_id:
                    journey_id_str = str(behavior.journey_id)
                    if journey_id_str in fragile_journey_map:
                        frag_data = fragile_journey_map[journey_id_str]
                        # Rollback pattern on journey: +25
                        if frag_data.get("memory_type") == "ROLLBACK_PATTERN":
                            fragility_score += 25
                            fragility_reasons.append(f"rollback pattern on journey: {frag_data['subject_name']}")
                            has_fragility_signals = True
                        # Escaped defect on journey: +30
                        if frag_data.get("memory_type") == "ESCAPED_DEFECT_PATTERN":
                            fragility_score += 30
                            fragility_reasons.append(f"previous escaped defect on journey: {frag_data['subject_name']}")
                            has_fragility_signals = True
            
            # Check if test is linked to fragile scenario
            for bs in test_behavior_scenarios:
                scenario_key = bs.scenario_key
                if scenario_key in fragile_scenario_map:
                    frag_data = fragile_scenario_map[scenario_key]
                    # Missing coverage pattern: +15
                    if frag_data.get("memory_type") == "MISSING_COVERAGE_PATTERN":
                        fragility_score += 15
                        fragility_reasons.append(f"missing coverage pattern on scenario: {scenario_key}")
                        has_fragility_signals = True
            
            # Check if test covers fragile file hotspots
            for f_path in associated_files:
                if f_path in fragile_file_map:
                    frag_data = fragile_file_map[f_path]
                    # File failure hotspot: +15
                    fragility_score += 15
                    fragility_reasons.append(f"file failure hotspot: {f_path}")
                    has_fragility_signals = True

            has_behavior_signals = has_behavior_match or has_journey_match or has_fragile_behavior or has_fragility_signals
            has_learning_signals = len(learning_signals) > 0

            # If no signals are present at all, this test shouldn't be recommended (unless fallback triggers)
            if not (has_coverage_link or has_knowledge_graph or has_historical_failure or has_module_risk or has_manual_override or has_escaped_defect or domain_match_boost > 0 or has_architectural_impact or has_indirect_dependency_impact or has_module_match or has_token_match or has_learning_signals or has_sme_signals or has_behavior_signals):
                continue

            # Compute Signal Breakdown
            cov_score = 40 if has_coverage_link else 0
            kg_score = 30 if has_knowledge_graph else 0
            risk_score = 15 if has_module_risk else 0
            fail_score = 10 if has_historical_failure else 0
            override_score = 20 if has_manual_override else 0
            defect_score = 30 if has_escaped_defect else 0
            arch_score = 30 if has_architectural_impact else 0
            module_score = 30 if has_module_match else 0
            token_score = 20 if has_token_match else 0
            indirect_dep_score = 25 if has_indirect_dependency_impact else 0
            learning_score_final = learning_score if has_learning_signals else 0
            fragility_score_final = fragility_score if has_fragility_signals else 0

            # Compute new mathematical evidence scoring categories
            # 1. Coverage (max 40)
            coverage_conf_score = 0
            if cov_confidence == "HIGH":
                coverage_conf_score = 40
            elif cov_confidence == "MODERATE":
                coverage_conf_score = 20
            elif cov_confidence == "LOW":
                coverage_conf_score = 10
            if coverage_evidence and tc.stable_identity in (coverage_evidence.direct_test_mappings or []):
                coverage_conf_score = max(coverage_conf_score, 40)

            # 2. Graph (max 30)
            graph_conf_score = 0
            if tc_edges:
                best_edge = max(tc_edges.values(), key=lambda e: e.confidence if e.confidence is not None else 0.0)
                edge_conf = best_edge.confidence
                if edge_conf is not None:
                    graph_conf_score = int(round(edge_conf * 30))
                else:
                    graph_conf_score = 30

            # 3. History (max 10)
            fail_count = failure_count_map.get(tc_id_str, 0)
            history_conf_score = 0
            if fail_count >= 2:
                history_conf_score = 10
            elif fail_count == 1:
                history_conf_score = 5

            # 4. Domain Matches (max 20)
            domain_conf_score = 0
            if domain_match_boost > 0:
                modified_files_in_domain = len(active_domains.get(matched_domain_name, []))
                if modified_files_in_domain >= 2:
                    domain_conf_score = 20
                elif modified_files_in_domain == 1:
                    domain_conf_score = 15
                else:
                    domain_conf_score = 10

            # 5. Overrides (max 20)
            override_conf_score = 0
            if tc_edges:
                max_overrides = max(edge.override_count for edge in tc_edges.values())
                if max_overrides >= 2:
                    override_conf_score = 20
                elif max_overrides == 1:
                    override_conf_score = 10

            # 6. Dependency Analysis (max 30)
            dep_conf_score = (10 if has_indirect_dependency_impact else 0) + \
                             (10 if has_architectural_impact else 0) + \
                             (5 if has_module_match else 0) + \
                             (5 if has_token_match else 0)

            # Calculate mathematical evidence confidence score
            actual_points = 0
            max_points = 0
            breakdown_lines = []

            if coverage_conf_score > 0:
                actual_points += coverage_conf_score
                max_points += 40
                breakdown_lines.append(f"Coverage: {coverage_conf_score}/40")

            if graph_conf_score > 0:
                actual_points += graph_conf_score
                max_points += 30
                breakdown_lines.append(f"Graph: {graph_conf_score}/30")

            if history_conf_score > 0:
                actual_points += history_conf_score
                max_points += 10
                breakdown_lines.append(f"History: {history_conf_score}/10")

            if domain_conf_score > 0:
                actual_points += domain_conf_score
                max_points += 20
                breakdown_lines.append(f"Domain: {domain_conf_score}/20")

            if override_conf_score > 0:
                actual_points += override_conf_score
                max_points += 20
                breakdown_lines.append(f"Overrides: {override_conf_score}/20")

            if dep_conf_score > 0:
                actual_points += dep_conf_score
                max_points += 30
                breakdown_lines.append(f"Dependency: {dep_conf_score}/30")

            if sme_domain_score > 0:
                actual_points += 25
                max_points += 25
                breakdown_lines.append(f"SME Domain Match: 25/25")
            if sme_journey_score > 0:
                actual_points += 20
                max_points += 20
                breakdown_lines.append(f"SME Journey Match: 20/20")
            if sme_security_score > 0:
                actual_points += 20
                max_points += 20
                breakdown_lines.append(f"SME Security Match: 20/20")
            if sme_layer_score > 0:
                actual_points += 15
                max_points += 15
                breakdown_lines.append(f"SME Layer Match: 15/15")
            if sme_synonym_score > 0:
                actual_points += 10
                max_points += 10
                breakdown_lines.append(f"SME Synonym Match: 10/10")

            # Learning signals (max 50, but never override high-confidence evidence)
            if learning_score_final > 0:
                # Only apply learning score if direct evidence is not HIGH confidence
                if cov_confidence != "HIGH" and graph_conf_score < 30:
                    actual_points += min(learning_score_final, 50)
                    max_points += 50
                    breakdown_lines.append(f"Learning: {min(learning_score_final, 50)}/50 ({', '.join(learning_signals)})")
            elif not pmv2_records:
                # Evidence gap: No outcome learning yet
                breakdown_lines.append("Learning: No outcome learning captured yet (evidence gap)")

            # Fragility signals (max 100, applied only if related to current PR impact)
            if fragility_score_final > 0:
                actual_points += min(fragility_score_final, 100)
                max_points += 100
                breakdown_lines.append(f"Fragility: {fragility_score_final}/100 ({', '.join(fragility_reasons)})")

            confidence_score_val = 0
            if max_points > 0:
                confidence_score_val = int(round((actual_points / max_points) * 100))

            confidence_str = f"{confidence_score_val}/100"

            breakdown_details = ""
            if breakdown_lines:
                breakdown_details = f"Confidence Score: {confidence_str}\n\nBreakdown:\n" + "\n".join(f"- {line}" for line in breakdown_lines)

            # Runtime cost calculation (-1 point per second of average duration)
            avg_dur = duration_map.get(tc_id_str)
            estimated_duration = avg_dur if (avg_dur is not None and avg_dur > 0) else 5.0
            runtime_score = -int(round(estimated_duration))

            total_score = (
                cov_score + kg_score + risk_score + fail_score + override_score + 
                defect_score + runtime_score + domain_match_boost + arch_score + 
                module_score + token_score + indirect_dep_score + learning_score_final +
                sme_domain_score + sme_journey_score + sme_security_score + 
                sme_layer_score + sme_synonym_score + strong_coverage_boost +
                behavior_match_score + journey_match_score + fragile_behavior_score +
                fragility_score_final
            )

            # Generate human-readable reasoning explanation
            signals_dict = {
                "coverage_link": cov_score,
                "knowledge_graph": kg_score,
                "module_risk": risk_score,
                "historical_failure": fail_score,
                "manual_override_history": override_score,
                "escaped_defect_learning": defect_score,
                "runtime_cost": runtime_score,
                "domain_match": domain_match_boost,
                "domain_name": matched_domain_name,
                "architectural_impact": arch_score,
                "module_match": module_score,
                "token_similarity": token_score,
                "indirect_dependency_impact": indirect_dep_score,
                "learning_signals": learning_score_final,
                "learning_signal_types": learning_signals,
                "behavior_match": behavior_match_score,
                "journey_match": journey_match_score,
                "fragile_behavior": fragile_behavior_score,
                "fragility_signals": fragility_score_final,
                "fragility_reasons": fragility_reasons,
            }
            bullets_str = RecommendationReasoningEngine.format_explanation(signals_dict)

            # Build Formatted Signal Breakdown Explanation String
            domain_str = f"Domain Match:\n+{domain_match_boost}\n\n" if domain_match_boost > 0 else ""
            arch_str = f"Architectural Impact:\n+{arch_score}\n\n" if arch_score > 0 else ""
            module_str = f"Module Match:\n+{module_score}\n\n" if module_score > 0 else ""
            token_str = f"Token Similarity:\n+{token_score}\n\n" if token_score > 0 else ""
            ind_str = f"Indirect Dependency Impact:\n+{indirect_dep_score}\n\n" if indirect_dep_score > 0 else ""
            learning_str = f"Learning Signals:\n+{learning_score_final} ({', '.join(learning_signals)})\n\n" if learning_score_final > 0 else ""
            fragility_str = f"Fragility Signals:\n+{fragility_score_final}\n\n" if fragility_score_final > 0 else ""

            sme_bullet_lines = []
            if sme_domain_score > 0:
                sme_bullet_lines.append(f"• Domain match from SME (+25) for domains: {', '.join(matched_sme_domains)}")
            if sme_journey_score > 0:
                sme_bullet_lines.append(f"• User journey match from SME (+20)")
            if sme_security_score > 0:
                sme_bullet_lines.append(f"• Security-required test from SME (+20)")
            if sme_layer_score > 0:
                sme_bullet_lines.append(f"• Touched architectural layer match from SME (+15)")
            if sme_synonym_score > 0:
                sme_bullet_lines.append(f"• Synonym match from SME (+10)")
            if strong_coverage_boost > 0:
                sme_bullet_lines.append(f"• Strong coverage link boost (+200)")

            # Behavior/Journey signal bullets
            if behavior_match_score > 0:
                sme_bullet_lines.append(f"• Impacted behavior match (+35): '{matched_behavior_name}'")
            if journey_match_score > 0:
                sme_bullet_lines.append(f"• Impacted journey match (+30): '{matched_journey_name}'")
            if fragile_behavior_score > 0:
                sme_bullet_lines.append(f"• Fragile behavior coverage (+20)")
            
            # Fragility signal bullets
            for reason in fragility_reasons:
                sme_bullet_lines.append(f"• {reason}")

            sme_str = ""
            if sme_bullet_lines:
                sme_str = "SME Signals:\n" + "\n".join(sme_bullet_lines) + "\n\n"

            breakdown_str = bullets_str + "\n\n" + (
                f"{sme_str}"
                f"Coverage Link:\n{'+' if cov_score >= 0 else ''}{cov_score}\n\n"
                f"Knowledge Graph:\n{'+' if kg_score >= 0 else ''}{kg_score}\n\n"
                f"Module Risk:\n{'+' if risk_score >= 0 else ''}{risk_score}\n\n"
                f"Historical Failure:\n{'+' if fail_score >= 0 else ''}{fail_score}\n\n"
                f"{domain_str}"
                f"{arch_str}"
                f"{module_str}"
                f"{token_str}"
                f"{ind_str}"
                f"{learning_str}"
                f"{fragility_str}"
                f"Runtime Cost:\n{runtime_score}\n\n"
                f"Total:\n{total_score}"
            )
            if breakdown_details:
                breakdown_str += "\n\n" + breakdown_details

            source_signal = "DIRECT_COVERAGE"
            if has_coverage_link:
                source_signal = "DIRECT_COVERAGE"
            elif has_knowledge_graph:
                source_signal = "TEST_COVERAGE_GRAPH"
            elif has_historical_failure:
                source_signal = "HISTORICAL_FAILURE"
            elif has_sme_security_match:
                source_signal = "SECURITY_REQUIRED"
            elif has_sme_domain_match:
                source_signal = "DOMAIN_MATCH"
            elif domain_match_boost > 0:
                source_signal = "DOMAIN_MATCH"
            elif has_architectural_impact:
                source_signal = "ARCHITECTURAL_IMPACT"
            elif has_indirect_dependency_impact:
                source_signal = "INDIRECT_DEPENDENCY_IMPACT"
            elif has_learning_signals:
                source_signal = "PATTERN_MEMORY"
            elif has_module_match:
                source_signal = "MODULE_MATCH"
            elif has_token_match:
                source_signal = "TOKEN_MATCH"
            else:
                source_signal = "MODULE_RISK"

            if flaky_status == "unstable":
                breakdown_str += "\n\n[FLAKY WARNING: Test is unstable]"

            recommended_tests.append({
                "test_identifier": tc.stable_identity,
                "test_name": tc.test_name,
                "class_name/module": tc.suite_name,
                "priority": float(total_score),
                "estimated_duration_seconds": round(estimated_duration, 2),
                "reason": breakdown_str,
                "confidence": confidence_str,
                "source_signal": source_signal,
                "reason_details": {
                    "coverage_link": cov_score,
                    "knowledge_graph": kg_score,
                    "module_risk": risk_score,
                    "historical_failure": fail_score,
                    "manual_override_history": override_score,
                    "escaped_defect_learning": defect_score,
                    "runtime_cost": runtime_score,
                    "domain_match": domain_match_boost,
                    "architectural_impact": arch_score,
                    "module_match": module_score,
                    "token_similarity": token_score,
                    "indirect_dependency_impact": indirect_dep_score,
                    "dependency_impact_trace": matched_indirect_trace,
                    "pattern_memory": learning_score_final,
                    "behavior_match": behavior_match_score,
                    "journey_match": journey_match_score,
                    "fragile_behavior": fragile_behavior_score,
                    "fragility_signals": fragility_score_final,
                    "fragility_reasons": fragility_reasons,
                    "sme_domain_match": sme_domain_score,
                    "sme_journey_match": sme_journey_score,
                    "sme_security_required": sme_security_score,
                    "sme_architecture_layer": sme_layer_score,
                    "sme_synonym_match": sme_synonym_score,
                    "strong_coverage_link": strong_coverage_boost,
                    "total": total_score
                }
            })

        # MVP Fallback Mode
        if not recommended_tests and test_runs_count > 0 and test_cases:
            # Select up to 5 conservative historical test cases (deterministically sorted by identity)
            fallback_tcs = test_cases[:5]
            for tc in fallback_tcs:
                tc_id_str = str(tc.id)
                avg_dur = duration_map.get(tc_id_str)
                estimated_duration = avg_dur if (avg_dur is not None and avg_dur > 0) else 5.0
                runtime_score = -int(round(estimated_duration))

                # Default fallback scores
                cov_score = 0
                kg_score = 0
                risk_score = 0
                fail_score = 10 if tc_id_str in failed_test_case_ids else 0
                override_score = 0
                defect_score = 0

                total_score = cov_score + kg_score + risk_score + fail_score + override_score + defect_score + runtime_score

                # Generate human-readable reasoning explanation for fallback test
                signals_dict = {
                    "coverage_link": cov_score,
                    "knowledge_graph": kg_score,
                    "module_risk": risk_score,
                    "historical_failure": fail_score,
                    "manual_override_history": override_score,
                    "escaped_defect_learning": defect_score,
                    "runtime_cost": runtime_score,
                    "domain_match": 0,
                    "domain_name": "",
                    "architectural_impact": 0
                }
                bullets_str = RecommendationReasoningEngine.format_explanation(signals_dict)

                breakdown_str = bullets_str + "\n\n" + (
                    f"Coverage Link:\n+{cov_score}\n\n"
                    f"Knowledge Graph:\n+{kg_score}\n\n"
                    f"Module Risk:\n+{risk_score}\n\n"
                    f"Historical Failure:\n{'+' if fail_score >= 0 else ''}{fail_score}\n\n"
                    f"Runtime Cost:\n{runtime_score}\n\n"
                    f"Total:\n{total_score}"
                )

                recommended_tests.append({
                    "test_identifier": tc.stable_identity,
                    "test_name": tc.test_name,
                    "class_name/module": tc.suite_name,
                    "priority": float(total_score),
                    "estimated_duration_seconds": round(estimated_duration, 2),
                    "reason": "No direct coverage match found; selected tests using historical/path fallback.\n\n" + breakdown_str,
                    "confidence": "0/100",
                    "source_signal": "HISTORICAL_FAILURE_FALLBACK",
                    "reason_details": {
                        "coverage_link": cov_score,
                        "knowledge_graph": kg_score,
                        "module_risk": risk_score,
                        "historical_failure": fail_score,
                        "manual_override_history": override_score,
                        "escaped_defect_learning": defect_score,
                        "runtime_cost": runtime_score,
                        "domain_match": 0,
                        "architectural_impact": 0,
                        "total": total_score
                    }
                })

        # Sort deterministically:
        # - priority desc
        # - estimated_duration_seconds asc
        # - test_identifier asc
        def sort_key(t):
            return (-t["priority"], t["estimated_duration_seconds"], t["test_identifier"])

        recommended_tests.sort(key=sort_key)
        return recommended_tests
