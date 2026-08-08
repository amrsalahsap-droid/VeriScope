"""Gap Analyzer Service for Phase 8

Integrates semantic diff analysis, coverage gaps, requirement gaps,
and risk heuristics to produce ranked missing test recommendations.
"""

import uuid
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from app.schemas.regression_scope_v2 import (
    ChangeSummary, CoverageGap, MissingTestRecommendation, DetailedScenario
)
from app.services.diff_analyzer import DiffAnalyzer
from app.services.coverage_impact_analyzer import CoverageImpactAnalyzer
from app.services.evidence_graph.recommendation_detail_builder import build_detailed_scenario
from app.services.evidence_graph.rationale_builder import build_rationale
from app.services.evidence_graph.deduplication_service import deduplicate_recommendations


class GapAnalyzer:
    """Analyzes gaps and generates missing test recommendations."""
    
    # Priority weights for ranking
    PRIORITY_WEIGHTS = {
        'COVERAGE_GAP': 1,  # Highest priority
        'REQUIREMENT_GAP': 2,
        'RISK_HEURISTIC': 3,
    }

    @staticmethod
    def get_untested_child_rules(req: Any, existing_test_names: Set[str]) -> List[Any]:
        untested = []
        child_rules = getattr(req, "child_rules", []) or []
        for rule in child_rules:
            rule_title = getattr(rule, "title", "") if not isinstance(rule, dict) else rule.get("title", "")
            if not rule_title:
                continue
            
            from app.services.evidence_graph.recommendation_detail_builder import _is_child_rule_tested
            if not _is_child_rule_tested(rule_title, existing_test_names):
                untested.append(rule)
        return untested

    @staticmethod
    def create_child_rule_gap(req: Any, rule: Any, change_summary: Any) -> MissingTestRecommendation:
        import uuid
        rule_title = getattr(rule, "title", "") if not isinstance(rule, dict) else rule.get("title", "")
        rule_name = rule_title.replace("System must require ", "").replace("System must require at least one ", "").strip()
        
        from app.services.evidence_graph.recommendation_detail_builder import build_detailed_scenario
        from app.services.regression_evidence_classifier import RequirementNode
        dummy_node = RequirementNode(
            requirement_id=getattr(rule, "requirement_id", None) or getattr(rule, "id", None) or str(uuid.uuid4()),
            readable_id=getattr(rule, "readable_id", "") or "AC-CHILD",
            title=rule_title,
            flow=getattr(req, "flow", "sign-up"),
            is_real_testable_requirement=True,
            child_rules=[]
        )
        scenarios = build_detailed_scenario(
            source="REQUIREMENT_GAP",
            requirement_node=dummy_node,
            flow_name=getattr(req, "flow", "sign-up")
        )
        ds = scenarios[0] if scenarios else None
        if not ds:
            from app.schemas.regression_scope_v2 import DetailedScenario
            from app.services.evidence_graph.recommendation_detail_builder import _derive_precondition, _generate_input_for_rule
            precondition = _derive_precondition(getattr(req, "flow", "sign-up"))
            test_input = _generate_input_for_rule(rule_title, getattr(req, "linked_test_data", []))
            ds = DetailedScenario(
                precondition=precondition,
                test_input=f"Password: '{test_input}' (meets all rules except {rule_name})",
                expected_result=f"Password rejected with message indicating {rule_name} is required",
                test_layer="API"
            )
            
        req_id = getattr(req, "requirement_id", None) or getattr(req, "id", None)
        file_path = change_summary.file_path if change_summary else None
        
        # Use rationale_builder for change-aware rationale
        risk_rationale = build_rationale(
            source="REQUIREMENT_GAP",
            requirement_node=req,
            change_summary=change_summary,
            gap_description=f"child rule '{rule_title}'",
            file_path=file_path,
            flow_name=getattr(req, "flow", "sign-up")
        )
            
        return MissingTestRecommendation(
            id=str(uuid.uuid4()),
            title=f"Test child rule: {rule_title}",
            source="REQUIREMENT_GAP",
            priority=2,
            risk_rationale=risk_rationale,
            suggested_test_scenario=f"Validate child rule: {rule_name}",
            detailed_scenario=ds,
            linked_requirement_id=req_id,
            linked_file=file_path,
            estimated_effort="LOW"
        )

    @staticmethod
    def create_missing_coverage_gap(req: Any, change_summary: Any) -> MissingTestRecommendation:
        import uuid
        from app.services.evidence_graph.recommendation_detail_builder import build_detailed_scenario
        
        scenarios = build_detailed_scenario(
            source="REQUIREMENT_GAP",
            requirement_node=req,
            flow_name=getattr(req, "flow", "sign-up")
        )
        ds = scenarios[0] if scenarios else None
        if not ds:
            from app.schemas.regression_scope_v2 import DetailedScenario
            from app.services.evidence_graph.recommendation_detail_builder import _derive_precondition
            precondition = _derive_precondition(getattr(req, "flow", "sign-up"))
            ds = DetailedScenario(
                precondition=precondition,
                test_input="Password: 'StrongPass#2026'",
                expected_result="Validation success",
                test_layer="API"
            )
            
        req_id = getattr(req, "requirement_id", None) or getattr(req, "id", None)
        file_path = change_summary.file_path if change_summary else None
        
        # Use rationale_builder for change-aware rationale
        risk_rationale = build_rationale(
            source="REQUIREMENT_GAP",
            requirement_node=req,
            change_summary=change_summary,
            gap_description=getattr(req, 'title', 'this requirement'),
            file_path=file_path,
            flow_name=getattr(req, "flow", "sign-up")
        )
            
        return MissingTestRecommendation(
            id=str(uuid.uuid4()),
            title=f"Test requirement: {getattr(req, 'title', '')}",
            source="REQUIREMENT_GAP",
            priority=1,
            risk_rationale=risk_rationale,
            suggested_test_scenario=f"Validate requirement: {getattr(req, 'title', '')}",
            detailed_scenario=ds,
            linked_requirement_id=req_id,
            linked_file=file_path,
            estimated_effort="MEDIUM"
        )

    @staticmethod
    def create_review_gap(req: Any, change_summary: Any) -> MissingTestRecommendation:
        import uuid
        from app.services.evidence_graph.recommendation_detail_builder import build_detailed_scenario
        
        scenarios = build_detailed_scenario(
            source="REQUIREMENT_GAP",
            requirement_node=req,
            flow_name=getattr(req, "flow", "sign-up")
        )
        ds = scenarios[0] if scenarios else None
        if not ds:
            from app.schemas.regression_scope_v2 import DetailedScenario
            from app.services.evidence_graph.recommendation_detail_builder import _derive_precondition
            precondition = _derive_precondition(getattr(req, "flow", "sign-up"))
            ds = DetailedScenario(
                precondition=precondition,
                test_input="Password: 'StrongPass#2026'",
                expected_result="Validation success",
                test_layer="API"
            )
            
        req_id = getattr(req, "requirement_id", None) or getattr(req, "id", None)
        file_path = change_summary.file_path if change_summary else None
        
        # Use rationale_builder for change-aware rationale
        risk_rationale = build_rationale(
            source="REQUIREMENT_GAP",
            requirement_node=req,
            change_summary=change_summary,
            gap_description="test execution in this PR run",
            file_path=file_path,
            flow_name=getattr(req, "flow", "sign-up")
        )
            
        return MissingTestRecommendation(
            id=str(uuid.uuid4()),
            title=f"Review requirement execution: {getattr(req, 'title', '')}",
            source="REQUIREMENT_GAP",
            priority=3,
            risk_rationale=risk_rationale,
            suggested_test_scenario=f"Review test execution or trigger re-run for: {getattr(req, 'title', '')}",
            detailed_scenario=ds,
            linked_requirement_id=req_id,
            linked_file=file_path,
            estimated_effort="LOW"
        )

    @staticmethod
    def extract_requirement_gaps(
        requirements: List[Any],
        evidence_overlay: Dict[str, str],
        change_summaries: Dict[str, Any],
        existing_test_names: Optional[Set[str]] = None
    ) -> List[MissingTestRecommendation]:
        """Extract requirement gaps from the evidence overlay and change summaries."""
        gaps = []
        existing_test_names = existing_test_names or set()
        
        for req in requirements:
            req_id = getattr(req, 'requirement_id', None) or getattr(req, 'id', None)
            if not req_id:
                continue
                
            from app.services.ac_identity_resolver import normalize_ac_text, build_ac_canonical_key
            
            db_ac_id = getattr(req, 'database_ac_id', None)
            source_ac_num = getattr(req, 'source_number', None) or getattr(req, 'source_ac_number', None)
            canonical_key = getattr(req, 'canonical_key', None) or getattr(req, 'canonical_ac_key', None)
            if not canonical_key:
                canonical_key = build_ac_canonical_key(req)
            norm_title = normalize_ac_text(getattr(req, 'title', '') or getattr(req, 'text', ''))
            
            bucket = None
            if db_ac_id and str(db_ac_id) in evidence_overlay:
                bucket = evidence_overlay[str(db_ac_id)]
            elif source_ac_num is not None and f"num_{source_ac_num}" in evidence_overlay:
                bucket = evidence_overlay[f"num_{source_ac_num}"]
            elif canonical_key in evidence_overlay:
                bucket = evidence_overlay[canonical_key]
            elif norm_title in evidence_overlay:
                bucket = evidence_overlay[norm_title]
            
            if not bucket:
                bucket = evidence_overlay.get(str(req_id), "NOT_MAPPED_TRACEABILITY_RISK")
            
            # Retrieve related change summary if available
            linked_file = getattr(req, 'linked_file', None)
            if not linked_file:
                for fp in change_summaries.keys():
                    if getattr(req, 'flow', '').lower() in fp.lower() or any(term in fp.lower() for term in getattr(req, 'flow', '').lower().split("-")):
                        linked_file = fp
                        break
            
            cs = change_summaries.get(linked_file) if linked_file else None
            
            if bucket == "ALREADY_VERIFIED":
                classification_str = getattr(req, 'classification', None)
                if hasattr(classification_str, 'value'):
                    classification_str = classification_str.value
                elif classification_str is not None:
                    classification_str = str(classification_str)
                else:
                    classification_str = ""
                
                # Also treat "PARTIAL" or "Partially covered" or "complexity" in requirement title as partial
                is_partial = "PARTIAL" in classification_str.upper() or "PARTIALLY" in classification_str.upper() or "complexity" in getattr(req, 'title', '').lower()
                
                if is_partial and getattr(req, 'child_rules', None):
                    untested = GapAnalyzer.get_untested_child_rules(req, existing_test_names)
                    if untested:
                        for rule in untested:
                            gap = GapAnalyzer.create_child_rule_gap(req, rule, cs)
                            gaps.append(gap)
                continue  # skip fully verified
            elif bucket in ("MISSING_AUTOMATED_COVERAGE", "REQUIRED", "MISSING", "NOT_MAPPED_TRACEABILITY_RISK"):
                gaps.append(GapAnalyzer.create_missing_coverage_gap(req, cs))
            elif bucket in ("REQUIRED_NOT_RUN_THIS_PR", "EXISTING_TEST_NOT_RUN_IN_CURRENT_PR", "REVIEW_NEEDED"):
                gaps.append(GapAnalyzer.create_review_gap(req, cs))
                
        return gaps

    @staticmethod
    def convert_coverage_gaps_to_recommendations(
        coverage_data: Optional[Dict[str, Any]],
        change_summaries: Dict[str, ChangeSummary]
    ) -> List[MissingTestRecommendation]:
        """Convert coverage gaps into missing test recommendations."""
        recommendations = []
        import logging
        logger = logging.getLogger(__name__)
        
        for file_path, summary in change_summaries.items():
            file_coverage = coverage_data.get(file_path, {}) if coverage_data else {}
            
            # Check if new_conditionals exists and has elements or is greater than 0
            new_conds_val = getattr(summary, "new_conditionals", 0)
            has_new_conds = False
            if isinstance(new_conds_val, list):
                has_new_conds = len(new_conds_val) > 0
            elif isinstance(new_conds_val, int):
                has_new_conds = new_conds_val > 0
            
            # Retrieve uncovered lines/branches
            uncovered_branches = file_coverage.get('uncovered_branches') or file_coverage.get('uncovered_lines') or []
            if not uncovered_branches:
                logger.warning(f"No uncovered branches/lines found in coverage data for {file_path}")
                # If we don't have explicit uncovered branches, we can check if there are functions with low coverage
                funcs_low = [f"low coverage in function '{f}'" for f, cov in file_coverage.get('functions', {}).items() if cov.get('coverage', 1.0) < 0.8]
                uncovered_branches = funcs_low or ["uncovered branches"]
            
            gap_info = {
                "file_path": file_path,
                "uncovered_branches": uncovered_branches,
                "risk": "HIGH" if any("low coverage" in b or "0%" in b or "new" in b for b in uncovered_branches) else "MEDIUM",
                "gap_type": "NEW_BRANCH" if has_new_conds else "UNCOVERED_FUNCTION"
            }
            
            scenarios = build_detailed_scenario(
                source="COVERAGE_GAP",
                requirement_node=None,
                coverage_gap_info=gap_info,
                flow_name=None,
                existing_tests=None,
                change_summary=summary
            )
            ds = scenarios[0] if scenarios else None
            
            file_basename = file_path.split('/')[-1]
            title = f"Test new conditional branches in {file_basename}" if has_new_conds else f"Test uncovered functions in {file_basename}"
            
            # Use rationale_builder for change-aware rationale
            risk_rationale = build_rationale(
                source="COVERAGE_GAP",
                change_summary=summary,
                file_path=file_path
            )
            
            recommendations.append(MissingTestRecommendation(
                id=str(uuid.uuid4()),
                title=title,
                source="COVERAGE_GAP",
                priority=1 if gap_info["risk"] == "HIGH" else 2,
                risk_rationale=risk_rationale,
                suggested_test_scenario=ds.test_input if ds else "Add tests to cover the identified gaps",
                detailed_scenario=ds,
                linked_requirement_id=None,
                linked_file=file_path,
                estimated_effort="MEDIUM"
            ))
            
        return recommendations

    @staticmethod
    def analyze_risk_heuristics(
        impacted_flows: Any,
        existing_tests: Optional[Set[str]] = None,
        change_summaries: Optional[Dict[str, ChangeSummary]] = None
    ) -> List[MissingTestRecommendation]:
        """Analyze risk heuristics to generate recommendations for shallow coverage flows."""
        recommendations = []
        existing_tests = existing_tests or set()
        change_summaries = change_summaries or {}
        
        from app.services.evidence_graph.edge_case_knowledge import EDGE_CASE_KNOWLEDGE
        from app.services.evidence_graph.recommendation_detail_builder import _derive_precondition
        
        norm_to_kb = {
            "sign_up": "sign-up",
            "sign-up": "sign-up",
            "login": "login",
            "reset_password": "reset-password",
            "reset-password": "reset-password",
            "update_password": "update-password",
            "update-password": "update-password"
        }
        
        # Parse impacted flows input
        flows_list = []
        if isinstance(impacted_flows, str):
            flows_list = [impacted_flows]
        elif hasattr(impacted_flows, '__iter__'):
            for f in impacted_flows:
                flow_name = f.flow if hasattr(f, 'flow') else str(f)
                flows_list.append(flow_name)
                
        unique_flows = set(flows_list)
        
        for flow in unique_flows:
            normalized = flow.lower().replace(" ", "_").replace("-", "_")
            kb_key = norm_to_kb.get(normalized) or norm_to_kb.get(flow.lower())
            if not kb_key or kb_key not in EDGE_CASE_KNOWLEDGE:
                # Substring check
                for k in EDGE_CASE_KNOWLEDGE.keys():
                    k_norm = k.replace("-", "_")
                    if k in normalized or normalized in k_norm:
                        kb_key = k
                        break
            
            if not kb_key:
                continue
                
            edge_cases = EDGE_CASE_KNOWLEDGE[kb_key]
            
            # Filter covered edge cases
            uncovered_cases = []
            for ec_desc, ec_expected in edge_cases:
                is_covered = False
                flow_words = {kb_key, kb_key.replace("-", ""), "login", "signup", "password", "reset", "update"}
                ec_words = [w.lower() for w in ec_desc.split() if len(w) > 3 and w.lower() not in flow_words]
                
                ec_normalized = ec_desc.lower().replace(" ", "_")
                ec_normalized_dash = ec_desc.lower().replace(" ", "-")
                
                for test in existing_tests:
                    test_lower = test.lower()
                    if ec_desc.lower() in test_lower or ec_normalized in test_lower or ec_normalized_dash in test_lower:
                        is_covered = True
                        break
                    if ec_words and any(w in test_lower for w in ec_words):
                        is_covered = True
                        break
                if not is_covered:
                    uncovered_cases.append((ec_desc, ec_expected))
                    
            # Generate at least 2 recommendations for flows with shallow coverage
            for ec_desc, ec_expected in uncovered_cases[:3]:
                from app.services.evidence_graph.recommendation_detail_builder import build_detailed_scenario
                scenarios = build_detailed_scenario(
                    source="RISK_HEURISTIC",
                    requirement_node=None,
                    coverage_gap_info=None,
                    flow_name=kb_key,
                    existing_tests=existing_tests
                )
                
                ds = None
                for s in scenarios:
                    if ec_desc in s.test_input:
                        ds = s
                        break
                if not ds:
                    precondition = _derive_precondition(kb_key)
                    if any(kw in ec_desc.lower() for kw in ["security", "concurrent", "race"]):
                        layer = "E2E"
                    elif any(kw in ec_desc.lower() for kw in ["token", "boundary", "api"]):
                        layer = "API"
                    else:
                        layer = "UI"
                    ds = DetailedScenario(
                        precondition=precondition,
                        test_input=f"Edge case: {ec_desc}",
                        expected_result=ec_expected,
                        test_layer=layer
                    )
                
                # Try to map a ChangeSummary to this flow for code context
                summary = None
                for fp, cs in change_summaries.items():
                    if kb_key in fp.lower() or any(term in fp.lower() for term in kb_key.split("-")):
                        summary = cs
                        break
                
                # Use rationale_builder for change-aware rationale
                risk_rationale = build_rationale(
                    source="RISK_HEURISTIC",
                    change_summary=summary,
                    gap_description=ec_desc,
                    flow_name=kb_key,
                    existing_test_info={"count": len(existing_tests)}
                )
                
                recommendations.append(MissingTestRecommendation(
                    id=str(uuid.uuid4()),
                    title=f"Add risk test ({ec_desc}) for: {kb_key}",
                    source="RISK_HEURISTIC",
                    priority=2,
                    risk_rationale=risk_rationale,
                    suggested_test_scenario=f"Validate edge case: {ec_desc} on {kb_key}",
                    detailed_scenario=ds,
                    linked_requirement_id=None,
                    linked_file=summary.file_path if summary else None,
                    estimated_effort="MEDIUM"
                ))
                
        return recommendations

    @staticmethod
    def rank_recommendations(recommendations: List[MissingTestRecommendation]) -> List[MissingTestRecommendation]:
        """Rank recommendations by priority and source."""
        return sorted(
            recommendations,
            key=lambda r: (
                r.priority,
                GapAnalyzer.PRIORITY_WEIGHTS.get(r.source, 99)
            )
        )

    @staticmethod
    def analyze_gaps(
        pr_diff: Optional[str],
        snapshot_data: Dict[str, Any],
        changed_files: List[str],
        change_impact_model: Optional[Any] = None,
        existing_test_names: Optional[Set[str]] = None,
        db: Optional[Any] = None,
        pr: Optional[Any] = None
    ) -> List[MissingTestRecommendation]:
        """Main entry point: analyze all gaps and produce recommendations."""
        existing_test_names = existing_test_names or set()
        
        # Build evidence overlay
        evidence_overlay = {}
        if change_impact_model and hasattr(change_impact_model, 'release_action_scope'):
            for item in change_impact_model.release_action_scope:
                overlay_key = getattr(item, 'requirement_id', None) or getattr(item, 'id', None) or getattr(item, 'source_ac_id', None)
                if overlay_key:
                    final_bucket_val = item.final_bucket.value if hasattr(item.final_bucket, 'value') else str(item.final_bucket)
                    evidence_overlay[str(overlay_key)] = final_bucket_val
        
        # Load requirement nodes
        ac_requirements = []
        if db and pr and getattr(pr, "description", None):
            try:
                from app.services.evidence_graph.ac_extraction_service import ACExtractionService
                ac_service = ACExtractionService()
                context = {"flow": "general", "repository_id": str(pr.repository_id) if hasattr(pr, "repository_id") else None}
                extraction_result = ac_service.extract_acceptance_criteria(pr.description, context)
                ac_requirements = extraction_result.requirement_nodes
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to extract criteria in analyze_gaps: {e}")
        
        if not ac_requirements and snapshot_data:
            from app.services.regression_evidence_classifier import RequirementNode, ScenarioSignature
            ac_traceability = snapshot_data.get('acTraceability', []) or []
            for trace in ac_traceability:
                req_id = trace.get('requirementId')
                readable_id = trace.get('readableId', 'Unknown')
                title = trace.get('title', 'Unknown requirement')
                flow = trace.get('flow', 'sign-up')
                ac_requirements.append(RequirementNode(
                    requirement_id=req_id,
                    readable_id=readable_id,
                    title=title,
                    flow=flow,
                    scenario_signature=ScenarioSignature(
                        flow=flow,
                        action="validate",
                        condition="general",
                        expected_outcome="success",
                        subject="password",
                        validation_layer="API",
                        polarity="positive"
                    ),
                    classification=trace.get("coverageStatus", "MISSING"),
                    is_real_testable_requirement=True
                ))
                
        # Build impacted flows
        impacted_flows = set()
        if change_impact_model:
            for f in change_impact_model.directly_impacted_flows:
                flow_name = f.flow if hasattr(f, 'flow') else str(f)
                impacted_flows.add(flow_name)
            for f in change_impact_model.indirectly_impacted_flows:
                flow_name = f.flow if hasattr(f, 'flow') else str(f)
                impacted_flows.add(flow_name)
                
        # Extract change summaries
        change_summaries = {}
        if change_impact_model and hasattr(change_impact_model, 'change_summaries'):
            change_summaries = change_impact_model.change_summaries or {}
        elif pr_diff:
            change_summaries = DiffAnalyzer.analyze(pr_diff)
            
        coverage_data = CoverageImpactAnalyzer.extract_coverage_from_snapshot(snapshot_data) if snapshot_data else None

        req_recommendations = GapAnalyzer.extract_requirement_gaps(
            ac_requirements, evidence_overlay, change_summaries, existing_test_names
        )
        coverage_recommendations = GapAnalyzer.convert_coverage_gaps_to_recommendations(
            coverage_data, change_summaries
        )
        risk_recommendations = GapAnalyzer.analyze_risk_heuristics(
            impacted_flows, existing_test_names, change_summaries
        )
        
        all_recommendations = req_recommendations + coverage_recommendations + risk_recommendations
        
        if existing_test_names:
            all_recommendations = deduplicate_recommendations(
                all_recommendations, existing_test_names
            )
        
        all_recommendations = GapAnalyzer.rank_recommendations(all_recommendations)
        return all_recommendations[:15]
