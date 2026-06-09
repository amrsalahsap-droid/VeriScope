import uuid
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.recommendation import SuggestedTestScenario, RecommendationRun
from app.services.missing_coverage_analyzer import MissingCoverageAnalyzer

class SuggestedTestScenarioGenerator:
    """
    Generates suggested test scenarios when exact automated test coverage is weak or missing.
    Matches missing coverage items to concrete functional scenarios.
    """

    @classmethod
    def generate_scenarios(
        cls,
        db: Session,
        run: RecommendationRun,
        changed_files: List[str]
    ) -> List[SuggestedTestScenario]:
        scenarios: List[SuggestedTestScenario] = []
        coverage_status_map = {}  # Initialize early to avoid UnboundLocalError

        # Initialize risk-related variables early to avoid UnboundLocalError
        impact_profile = run.impact_profile or {}
        risk_level = impact_profile.get("risk_level", "MODERATE")
        business_journey_criticality = impact_profile.get("business_journey_criticality", "MEDIUM")

        # 1. Fetch missing coverage items
        missing_items = MissingCoverageAnalyzer.analyze_missing_coverage(db, run, changed_files)

        # 1.5. Map existing tests to scenario intents to understand what's already covered
        from app.services.existing_test_to_scenario_mapper import ExistingTestToScenarioMapper
        from app.models.test_result import TestCase
        from app.services.existing_test_to_scenario_mapper import ConfidenceLevel
        from app.services.scenario_priority_resolver import ScenarioPriorityResolver

        # Fetch existing test cases for the repository
        existing_tests = db.query(TestCase).filter(
            TestCase.repository_id == run.repository_id
        ).all()

        # Get project understanding snapshot from impact_profile
        snapshot = impact_profile.get("project_understanding_snapshot", {})
        domain_vocab = impact_profile.get("domain_vocabulary", {})

        # Map existing tests to scenario intents
        test_results = []
        for tc in existing_tests:
            test_results.append({
                "test_identifier": tc.stable_identity,
                "test_name": tc.test_name,
                "suite_name": tc.suite_name,
                "class_name": tc.suite_name  # Using suite_name as class_name fallback
            })

        existing_coverages = ExistingTestToScenarioMapper.map_tests_to_intents(
            test_results=test_results,
            project_understanding=snapshot,
            domain_vocab=domain_vocab
        )
        
        # Get covered intent keys (MODERATE confidence and above)
        covered_intent_keys = ExistingTestToScenarioMapper.get_covered_intent_keys(
            coverages=existing_coverages,
            min_confidence=ConfidenceLevel.MODERATE
        )

        # 2. Check if automated coverage is weak or missing
        is_coverage_weak_or_missing = (
            run.evidence_quality in ("LOW", "UNKNOWN")
            or run.recommendation_mode in ("CONSERVATIVE", "FULL_REGRESSION", "SAFE_FALLBACK")
            or not run.coverage_report_id
            or not run.tests
        )

        # If no missing coverage items are found but the coverage is weak, add a general gap
        if not missing_items and is_coverage_weak_or_missing:
            # Phase 2E: First try to infer from impacted behaviors/journeys in impact_profile
            behavior_inferred = False
            impact_profile = run.impact_profile or {}
            journey_intelligence = impact_profile.get("journey_intelligence", {})
            behavior_impact_summary = impact_profile.get("behavior_impact", {})

            # Use impacted behaviors from behavior_impact analysis
            impacted_behaviors = behavior_impact_summary.get("impacted_behaviors", [])
            for ib in impacted_behaviors:
                b_name = ib.get("behavior_name", "")
                impact_level = ib.get("impact_level", "MEDIUM")
                impact_type = ib.get("impact_type", "INDIRECT")
                impacted_files = ib.get("impacted_files", [])
                # Infer domain from behavior name
                b_lower = b_name.lower()
                domain = "General"
                if any(k in b_lower for k in ["auth", "login", "password", "token", "session"]):
                    domain = "Authentication"
                elif any(k in b_lower for k in ["billing", "payment", "subscription", "invoice"]):
                    domain = "Billing"
                elif any(k in b_lower for k in ["notification", "email", "alert"]):
                    domain = "Notifications"
                elif any(k in b_lower for k in ["signup", "register", "onboard"]):
                    domain = "User Registration"
                missing_items.append({
                    "domain": domain,
                    "feature": b_name,
                    "reason": f"Behavior '{b_name}' is {impact_type}LY impacted (level: {impact_level}) but lacks automated coverage.",
                    "behavior_id": ib.get("behavior_id"),
                    "impact_type": impact_type,
                    "impact_level": impact_level,
                })
                behavior_inferred = True

            # Use impacted journeys from journey intelligence
            affected_journeys = journey_intelligence.get("affected_journeys", [])
            for aj in affected_journeys:
                j_name = aj.get("journey_name", "")
                j_impact = aj.get("impact_level", "MEDIUM")
                j_behaviors = aj.get("affected_behaviors", [])
                if j_name and not any(mi.get("feature") == j_name for mi in missing_items):
                    missing_items.append({
                        "domain": j_name,
                        "feature": "Journey Coverage",
                        "reason": f"Journey '{j_name}' is impacted (level: {j_impact}) with {len(j_behaviors)} affected behaviors but lacks automated coverage.",
                        "journey_name": j_name,
                        "impact_level": j_impact,
                    })
                    behavior_inferred = True

            # Fallback: Infer feature or domain based on changed files
            inferred = behavior_inferred
            if not inferred:
                pass  # Fall through to keyword-based inference below
            for f in changed_files:
                if inferred:
                    break
                f_lower = f.lower()
                if "password" in f_lower:
                    missing_items.append({
                        "domain": "Authentication",
                        "feature": "Password Reset",
                        "reason": "Exact automated coverage is missing or weak for changed password reset files."
                    })
                    missing_items.append({
                        "domain": "Authentication",
                        "feature": "Password Validation",
                        "reason": "Exact automated coverage is missing or weak for password validation rules."
                    })
                    inferred = True
                    break
                elif "signup" in f_lower or "register" in f_lower:
                    missing_items.append({
                        "domain": "Authentication",
                        "feature": "Signup",
                        "reason": "Exact automated coverage is missing or weak for changed registration files."
                    })
                    inferred = True
                    break
                elif "auth" in f_lower or "login" in f_lower or "token" in f_lower:
                    feature_name = "Login" if "login" in f_lower else "General"
                    missing_items.append({
                        "domain": "Authentication",
                        "feature": feature_name,
                        "reason": f"Exact automated coverage is missing or weak for changed {feature_name.lower()} files."
                    })
                    inferred = True
                    break
                elif "billing" in f_lower or "payment" in f_lower or "stripe" in f_lower or "subscription" in f_lower:
                    missing_items.append({
                        "domain": "Billing",
                        "feature": "General",
                        "reason": "Exact automated coverage is missing or weak for changed billing files."
                    })
                    inferred = True
                    break
                elif "notification" in f_lower or "email" in f_lower or "mail" in f_lower:
                    missing_items.append({
                        "domain": "Notifications",
                        "feature": "General",
                        "reason": "Exact automated coverage is missing or weak for changed notification files."
                    })
                    inferred = True
                    break
            
            if not inferred:
                missing_items.append({
                    "domain": "General",
                    "feature": "General",
                    "reason": "Exact automated coverage is missing or weak for changed codebase files."
                })

        from app.services.missing_scenario_generator import MissingScenarioGenerator
        from app.services.testing_scope_generator import TestingScopeGenerator

        testing_scope = TestingScopeGenerator.generate_scope(db, run, changed_files)
        impacted_areas = (run.impact_profile or {}).get("affected_domains") or []

        # Extract project understanding snapshot and domain vocabulary if available
        snapshot = None
        domain_vocab = None
        if run.impact_profile:
            snapshot = run.impact_profile.get("project_understanding_snapshot")
            domain_vocab = run.impact_profile.get("domain_vocabulary")

        generated_dicts = MissingScenarioGenerator.generate_missing_scenarios(
            potential_missing_coverage=missing_items,
            recommended_scope=testing_scope,
            impacted_areas=impacted_areas,
            project_understanding_snapshot=snapshot,
            domain_vocab=domain_vocab,
            changed_files=changed_files,
            db=db,
            repository_id=run.repository_id
        )

        from app.services.scenario_intent_normalizer import ScenarioIntentNormalizer
        from app.repositories.scenario_intent import ScenarioIntentRepository
        
        intent_repo = ScenarioIntentRepository(db)
        
        for d in generated_dicts:
            # Create ScenarioIntent for this scenario
            intent_data = ScenarioIntentNormalizer.create_intent_from_scenario(
                title=d["title"],
                priority=d["priority"],
                risk_category=d.get("risk_category", "Functional"),
                related_changed_files=d.get("related_changed_files", []),
                recommendation_run_id=run.id,
                domain=d.get("impacted_area", "general"),
                feature=d.get("impacted_area", "general"),
                behavior=d["title"],
                layer=d.get("impacted_layer", "api"),
                case_type=d.get("risk_category", "positive").lower() if d.get("risk_category") == "Functional" else "negative"
            )
            
            # Check coverage status for this intent
            coverage_status = coverage_status_map.get(intent_data["canonical_key"])
            
            # Skip if already covered by existing tests (basic check)
            if intent_data["canonical_key"] in covered_intent_keys:
                continue
            
            # Filter based on final coverage status
            if coverage_status:
                final_status = coverage_status.final_status
                
                # COVERED_AND_VERIFIED: do not create suggested missing scenario
                if final_status == FinalCoverageStatus.COVERED_AND_VERIFIED:
                    logger.info(
                        f"Skipping scenario '{d['title']}' - already COVERED_AND_VERIFIED"
                    )
                    continue
                
                # COVERED_NOT_RUN: recommend existing automated test to run, do not create missing scenario
                if final_status == FinalCoverageStatus.COVERED_NOT_RUN:
                    logger.info(
                        f"Skipping scenario '{d['title']}' - COVERED_NOT_RUN, recommend existing test to run"
                    )
                    continue
                
                # PARTIALLY_COVERED: create suggested scenario only for missing assertion/edge case
                if final_status == FinalCoverageStatus.PARTIALLY_COVERED:
                    # Modify reason to indicate this is for expanding coverage
                    d["reason"] = f"[Expand Coverage] {d['reason']} - Partial coverage detected, add missing assertions/edge cases"
                    d["priority"] = "SHOULD"  # Lower priority for expansion
                
                # SUGGEST_MANUAL_VALIDATION: create manual validation scenario
                if final_status == FinalCoverageStatus.SUGGEST_MANUAL_VALIDATION:
                    d["automation_candidate"] = False
                    d["reason"] = f"[Manual Validation Required] {d['reason']} - Weak automated coverage evidence"
                    d["priority"] = "OPTIONAL"  # Lower priority for manual validation
                
                # MISSING_AUTOMATED_COVERAGE: create full suggested scenario (default behavior)
            
            # Resolve final priority using ScenarioPriorityResolver
            resolved_priority = ScenarioPriorityResolver.resolve_priority_from_scenario(
                scenario_data=d,
                coverage_status=coverage_status,
                risk_level=risk_level,
                business_journey_criticality=business_journey_criticality,
                historical_failure=False  # Could be enhanced with historical data
            )
            
            # Skip if priority is VERIFIED (already covered)
            if resolved_priority.value == "VERIFIED":
                logger.info(
                    f"Skipping scenario '{d['title']}' - priority resolved to VERIFIED"
                )
                continue
            
            # Apply resolved priority to scenario data
            d["priority"] = resolved_priority.value
            
            files_str = ", ".join(d.get("related_changed_files") or [])
            tests_str = ", ".join(d.get("related_existing_tests") or []) if d.get("related_existing_tests") else "None detected (no invented tests)"
            
            # Add coverage status to reason if available
            coverage_info = ""
            if coverage_status:
                coverage_info = f"\nCoverage Status: {coverage_status.final_status.value} (Confidence: {coverage_status.confidence})"
            
            # Phase 2E: Enrich reason with behavior/journey context
            behavior_context = ""
            impact_profile = run.impact_profile or {}
            behavior_impact_data = impact_profile.get("behavior_impact", {})
            impacted_behaviors_list = behavior_impact_data.get("impacted_behaviors", [])
            for ib in impacted_behaviors_list:
                b_name_lower = ib.get("behavior_name", "").lower()
                title_lower = d["title"].lower()
                if any(token in title_lower for token in b_name_lower.split()):
                    behavior_context = (
                        f"\nImpacted Behavior: {ib.get('behavior_name')} "
                        f"(Impact: {ib.get('impact_type', 'UNKNOWN')}/{ib.get('impact_level', 'UNKNOWN')}, "
                        f"Confidence: {ib.get('behavior_confidence', 'MEDIUM')})"
                    )
                    break

            journey_context = ""
            journey_intelligence = impact_profile.get("journey_intelligence", {})
            affected_journeys_data = journey_intelligence.get("affected_journeys", [])
            for aj in affected_journeys_data:
                j_name_lower = aj.get("journey_name", "").lower()
                title_lower = d["title"].lower()
                if any(token in title_lower for token in j_name_lower.split()):
                    journey_context = (
                        f"\nImpacted Journey: {aj.get('journey_name')} "
                        f"(Impact: {aj.get('impact_level', 'UNKNOWN')})"
                    )
                    break

            reason_formatted = (
                f"{d['reason']}\n\n"
                f"Journey: {d.get('affected_journey')}\n"
                f"Layer: {d.get('impacted_layer')}\n"
                f"Risk Category: {d.get('risk_category')}\n"
                f"Suggested Automation Layer: {d.get('suggested_automation_layer')}\n"
                f"Related Changed Files: {files_str}\n"
                f"Related Existing Tests: {tests_str}"
                f"{coverage_info}"
                f"{behavior_context}"
                f"{journey_context}"
            )
            
            # Check if intent already exists globally (deduplication across all runs)
            # Use get_or_create_intent to handle the global unique constraint on canonical_key
            intent = intent_repo.get_or_create_intent(
                recommendation_run_id=run.id,
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

            scenarios.append(SuggestedTestScenario(
                id=uuid.uuid4(),
                recommendation_run_id=run.id,
                scenario_intent_id=intent.id if intent else None,
                title=d["title"],
                testing_type=d["testing_type"],
                impacted_area=d["impacted_area"],
                priority=d["priority"],
                preconditions=d["preconditions"],
                test_data=d.get("test_data", {}),
                steps=d["steps"],
                expected_result=d["expected_result"],
                automation_candidate=d["automation_candidate"],
                related_changed_files=changed_files,
                reason=reason_formatted,
                confidence=d["confidence"],
                source_signal=d["source_signal"]
            ))

        # Resolve test data dynamically using TestDataSuggestionEngine
        from app.services.test_data_suggestion_engine import TestDataSuggestionEngine
        from app.models.risk_assessment import RiskAssessment

        impact_profile = run.impact_profile or {}
        risk_assessment = None
        if run.pull_request_id:
            risk_assessment = db.query(RiskAssessment).filter(RiskAssessment.pull_request_id == run.pull_request_id).order_by(RiskAssessment.created_at.desc()).first()

        for s in scenarios:
            match_key = s.title
            if "password reset" in s.title.lower() or "reset password" in s.title.lower():
                match_key = "reset password"
            elif "password" in s.title.lower():
                match_key = "password validation"
            elif "signup" in s.title.lower() or "sign-up" in s.title.lower() or "user registration" in s.title.lower():
                match_key = "signup"
            
            dynamic_data = TestDataSuggestionEngine.generate_test_data(
                impact_profile=impact_profile,
                risk_assessment=risk_assessment,
                changed_files=changed_files,
                testing_scope=testing_scope,
                domain_or_feature=match_key
            )
            # Merge while preserving template data
            if s.test_data:
                for k, v in dynamic_data.items():
                    if k not in s.test_data:
                        s.test_data[k] = v
            else:
                s.test_data = dynamic_data

        # Resolve coverage status for scenario intents
        from app.services.scenario_coverage_resolver import ScenarioCoverageResolver
        from app.models.coverage import CoverageFileEntry
        from app.models.test_coverage_link import TestCoverageLink
        from app.models.test_result import TestRun
        from app.services.scenario_coverage_resolver import FinalCoverageStatus
        from app.services.scenario_priority_resolver import ScenarioPriorityResolver
        
        # Fetch coverage evidence
        coverage_file_entries = []
        if run.coverage_report_id:
            coverage_file_entries = db.query(CoverageFileEntry).filter(
                CoverageFileEntry.coverage_report_id == run.coverage_report_id
            ).all()
        
        # Fetch test coverage links
        test_coverage_links = db.query(TestCoverageLink).filter(
            TestCoverageLink.repository_id == run.repository_id
        ).all()
        
        # Fetch current PR test run if available
        current_pr_test_run = None
        if run.pull_request_id:
            current_pr_test_run = db.query(TestRun).filter(
                TestRun.pull_request_id == run.pull_request_id
            ).order_by(TestRun.created_at.desc()).first()
        
        # Fetch historical test runs (last 10 runs for this repository)
        historical_test_runs = db.query(TestRun).filter(
            TestRun.repository_id == run.repository_id
        ).order_by(TestRun.created_at.desc()).limit(10).all()
        
        # Get scenario intents for this run
        scenario_intents = intent_repo.get_intents_by_run(run.id)
        
        # Resolve coverage status for all scenario intents
        coverage_statuses = ScenarioCoverageResolver.resolve_batch_coverage_status(
            scenario_intents=scenario_intents,
            existing_test_coverages=existing_coverages,
            coverage_file_entries=coverage_file_entries,
            test_coverage_links=test_coverage_links,
            current_pr_test_run=current_pr_test_run,
            historical_test_runs=historical_test_runs,
            min_confidence="MODERATE"
        )
        
        # Create a mapping of canonical_key to coverage status
        coverage_status_map = {status.scenario_intent_key: status for status in coverage_statuses}
        
        # Determine risk level from impact profile
        risk_level = (run.impact_profile or {}).get("risk_level", "MODERATE")
        
        # Determine business journey criticality
        business_journey_criticality = (run.impact_profile or {}).get("business_journey_criticality", "MEDIUM")
        
        # Log coverage status for debugging
        import logging
        logger = logging.getLogger("veriscope.scenario_coverage")
        for status in coverage_statuses:
            logger.info(
                f"Scenario Intent: {status.scenario_intent_key} | "
                f"Final Status: {status.final_status.value} | "
                f"Confidence: {status.confidence}"
            )

        # Deduplicate scenarios by title
        seen_titles = set()
        unique_scenarios = []
        for s in scenarios:
            if s.title not in seen_titles:
                seen_titles.add(s.title)
                unique_scenarios.append(s)

        return unique_scenarios
