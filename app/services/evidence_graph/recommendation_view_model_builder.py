"""Recommendation View Model Builder - Builds final view model for UI.

This service builds the RecommendationEvidenceViewModel as the single source
of truth for all UI components.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from app.services.regression_evidence_classifier import (
    RequirementNode,
    TestNode,
    ExecutionNode,
    CoverageNode,
    EvidenceClassification,
)
from app.services.evidence_graph.missing_test_mapper import MissingTestCard
from app.services.evidence_graph.evidence_matching_service import MatchTableEntry


@dataclass
class TestCard:
    """Card representing a test in the UI."""
    id: str
    title: str
    classname: str
    status: str
    mapped_requirement_ids: List[str] = field(default_factory=list)


@dataclass
class CoverageGapCard:
    """Card representing a coverage gap."""
    file_path: str
    line_coverage: float
    branch_coverage: float
    flow: str = "general"
    uncovered_lines: List[int] = field(default_factory=list)
    partially_covered_branches: List[str] = field(default_factory=list)
    related_requirement_ids: List[str] = field(default_factory=list)
    linked_test_id: Optional[str] = None
    linked_test_title: Optional[str] = None
    why_link_relevant: Optional[str] = None
    suggested_action: str = "Add automated coverage"
    severity: str = "Recommended"
    mapping_score: float = 0.0
    mapping_method: str = "unmapped"


@dataclass
class ACTraceabilityRow:
    """Row in AC traceability table."""
    requirement_id: str
    readable_id: str
    title: str
    full_text: str
    coverage_status: str
    linked_existing_tests: List[str] = field(default_factory=list)
    linked_missing_test: Optional[str] = None
    priority: str = "Recommended"
    notes: str = ""
    manual_support_status: str = "MANUAL_NOT_MAPPED"
    manual_validation: Dict[str, Any] = field(default_factory=dict)
    # Phase 6.4: Manual evidence risk adjustment fields
    generated_risk_band: Optional[str] = None
    manual_contribution_status: Optional[str] = None
    source_ac_number: Optional[int] = None
    residual_risk_band: Optional[str] = None
    risk_adjustment_reason: Optional[str] = None
    risk_adjustment_delta: Optional[int] = None


@dataclass
class DecisionCopy:
    """User-facing decision copy."""
    headline: str = ""
    explanation: str = ""
    next_action: str = ""
    primary_cta: str = ""
    secondary_cta: str = ""


@dataclass
class RecommendationEvidenceViewModel:
    """Final view model for UI - single source of truth."""
    health: str = "READY"
    can_render_recommendation: bool = True
    counts: Dict[str, int] = field(default_factory=dict)
    verified_by_current_pr: List[TestCard] = field(default_factory=list)
    failed_tests: List[TestCard] = field(default_factory=list)
    skipped_tests: List[TestCard] = field(default_factory=list)
    required_tests_not_run: List[TestCard] = field(default_factory=list)
    missing_tests: List[MissingTestCard] = field(default_factory=list)
    coverage_gaps: List[CoverageGapCard] = field(default_factory=list)
    ac_traceability: List[ACTraceabilityRow] = field(default_factory=list)
    decision_copy: DecisionCopy = field(default_factory=DecisionCopy)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    graph_quality: Dict[str, Any] = field(default_factory=dict)
    requirements: List[Any] = field(default_factory=list)
    tests: List[Any] = field(default_factory=list)
    match_table: List[Any] = field(default_factory=list)
    manual_evidence_nodes: List[Dict[str, Any]] = field(default_factory=list)


class RecommendationViewModelBuilder:
    """Service for building the final view model."""

    def __init__(self):
        self.view_model = RecommendationEvidenceViewModel()

    def build_view_model(
        self,
        requirements: List[RequirementNode],
        tests: List[TestNode],
        executions: List[ExecutionNode],
        coverage_nodes: List[CoverageNode],
        missing_tests: List[MissingTestCard],
        match_table: List[MatchTableEntry],
        excluded_fragments: List[Dict[str, Any]],
        extraction_audit: Dict[str, Any] = None,
        recommendation_run_id: str = None,
        repository_id: str = None,
        db_session: Any = None,
        manual_evidence_nodes: Optional[List[Dict[str, Any]]] = None
    ) -> RecommendationEvidenceViewModel:
        """Build the final view model from classified evidence.

        Args:
            requirements: Classified requirement nodes
            tests: Test nodes
            executions: Execution nodes
            coverage_nodes: Coverage nodes
            missing_tests: Missing test cards
            match_table: Match table for diagnostics
            excluded_fragments: Excluded fragments
            extraction_audit: Extraction audit from AC extraction service
            recommendation_run_id: Optional recommendation run ID
            repository_id: Optional repository ID
            db_session: Optional database session
            manual_evidence_nodes: Optional manual evidence nodes

        Returns:
            RecommendationEvidenceViewModel
        """
        self.view_model = RecommendationEvidenceViewModel()
        self.view_model.manual_evidence_nodes = manual_evidence_nodes or []

        # Build counts
        self._build_counts(requirements, executions)

        # Build test cards
        self._build_test_cards(executions, tests)

        # Build missing tests
        self.view_model.missing_tests = missing_tests

        # Build coverage gaps
        self._build_coverage_gaps(coverage_nodes, requirements, tests)

        # Check for internal ID leaks and sanitize readable_id
        import re
        id_pattern = re.compile(r'^AC-\d+$')
        has_internal_id_leak = False
        
        # Determine if any real requirement has a leaked ID
        for req in requirements:
            if req.is_real_testable_requirement and req.readable_id:
                if not id_pattern.match(req.readable_id):
                    has_internal_id_leak = True
                    break
                    
        # Sanitize the IDs
        if has_internal_id_leak:
            ac_counter = 1
            for req in requirements:
                if req.is_real_testable_requirement:
                    req.readable_id = f"AC-{ac_counter:02d}"
                    ac_counter += 1

        # Build AC traceability
        self._build_ac_traceability(requirements, executions, tests, manual_evidence_nodes=manual_evidence_nodes)

        # Build graph quality metrics
        self._build_graph_quality(requirements, match_table, missing_tests, extraction_audit)

        # Determine health
        self._determine_health(
            requirements,
            executions,
            extraction_audit,
            recommendation_run_id,
            repository_id,
            db_session
        )

        # Build decision copy
        self._build_decision_copy()

        # Build diagnostics
        self._build_diagnostics(requirements, match_table, excluded_fragments, extraction_audit)

        # Store raw inputs for endpoints
        self.view_model.requirements = requirements
        self.view_model.tests = tests
        self.view_model.match_table = match_table

        return self.view_model

    def _build_counts(self, requirements: List[RequirementNode], executions: List[ExecutionNode]):
        """Build executive counts."""
        counts = {
            "verifiedTests": 0,
            "failedTests": 0,
            "skippedTests": 0,
            "requiredNotRun": 0,
            "missingAutomatedCoverage": 0,
            "coverageGaps": 0,
            "partiallySupported": 0,  # Phase 6.4: Add alias for coverageGaps for consistency
            "optionalImprovements": 0,
            "notMappedTraceabilityRisks": 0,
            "excludedFragments": 0,
        }

        # Count from requirements
        for req in requirements:
            if req.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION:
                counts["verifiedTests"] += 1
            elif req.classification == EvidenceClassification.FAILED_IN_CURRENT_PR_EXECUTION:
                counts["failedTests"] += 1
            elif req.classification == EvidenceClassification.SKIPPED_IN_CURRENT_PR_EXECUTION:
                counts["skippedTests"] += 1
            elif req.classification == EvidenceClassification.EXISTING_TEST_NOT_RUN_IN_CURRENT_PR:
                counts["requiredNotRun"] += 1
            elif req.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE:
                counts["missingAutomatedCoverage"] += 1
            elif req.classification == EvidenceClassification.PARTIALLY_COVERED:
                counts["coverageGaps"] += 1
                counts["partiallySupported"] += 1  # Phase 6.4: Increment alias for consistency
            elif req.classification == EvidenceClassification.OPTIONAL_IMPROVEMENT:
                counts["optionalImprovements"] += 1
            elif req.classification == EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK:
                counts["notMappedTraceabilityRisks"] += 1
            elif req.classification == EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA:
                counts["excludedFragments"] += 1

        # Count from executions (for verification)
        counts["uploadedPrTestsTotal"] = len(executions)
        counts["uploadedPrTestsPassed"] = sum(1 for e in executions if e.status == "passed")
        counts["uploadedPrTestsFailed"] = sum(1 for e in executions if e.status == "failed")
        counts["uploadedPrTestsSkipped"] = sum(1 for e in executions if e.status == "skipped")
        counts["totalRequirements"] = sum(1 for r in requirements if r.node_type == "PARENT_REQUIREMENT")

        self.view_model.counts = counts

    def _build_test_cards(self, executions: List[ExecutionNode], tests: List[TestNode]):
        """Build test cards from executions."""
        test_map = {t.test_id: t for t in tests}

        for exec_node in executions:
            test = test_map.get(exec_node.mapped_test_node_id) if exec_node.mapped_test_node_id else None

            card = TestCard(
                id=exec_node.test_id,
                title=exec_node.test_name,
                classname=exec_node.classname,
                status=exec_node.status,
                mapped_requirement_ids=exec_node.mapped_requirement_ids
            )

            if exec_node.status == "passed":
                self.view_model.verified_by_current_pr.append(card)
            elif exec_node.status in ("failed", "error"):
                self.view_model.failed_tests.append(card)
            elif exec_node.status == "skipped":
                self.view_model.skipped_tests.append(card)

    def _build_coverage_gaps(
        self,
        coverage_nodes: List[CoverageNode],
        requirements: List[RequirementNode],
        tests: List[TestNode]
    ):
        """Build coverage gap cards."""
        import os
        for coverage in coverage_nodes:
            if coverage.coverage_strength in ("weak", "partial"):
                # Determine flow:
                # If coverage has related_flows, use the first one, else extract from path
                gap_flow = "general"
                if coverage.related_flows:
                    gap_flow = coverage.related_flows[0]
                else:
                    file_path_lower = coverage.file_path.lower()
                    flow_keywords = {
                        "password_reset": ["reset", "password", "reset-password"],
                        "sign_up": ["signup", "sign-up", "register", "registration"],
                        "update_password": ["update", "password", "change"],
                        "login": ["login", "auth", "authentication"],
                    }
                    for flow, keywords in flow_keywords.items():
                        if any(kw in file_path_lower for kw in keywords):
                            gap_flow = flow
                            break
                
                # Match linked tests using heuristics
                best_test = None
                best_score = 0.0
                best_reason = None
                best_method = "unmapped"

                for test in tests:
                    score = 0.0
                    is_shared_policy = False

                    # Check if it is a signup test
                    is_signup_test = any(kw in test.title.lower() or kw in test.classname.lower() or (test.scenario_signature and kw in test.scenario_signature.flow.lower()) for kw in ["signup", "sign_up", "register", "registration"])

                    # Check for shared password policy
                    gap_has_policy = "policy" in coverage.file_path.lower() or "password_policy" in coverage.file_path.lower()
                    test_has_policy = "policy" in test.title.lower() or "policy" in test.classname.lower() or "password_policy" in test.title.lower() or "password_policy" in test.classname.lower()
                    shared_policy_validation = gap_has_policy or test_has_policy

                    # Rules for signup leak prevention:
                    is_signup_leak_attempt = is_signup_test and not ("signup" in gap_flow.lower() or "sign_up" in gap_flow.lower() or "register" in gap_flow.lower())

                    if is_signup_leak_attempt:
                        if shared_policy_validation:
                            score += 4.0
                            is_shared_policy = True
                        else:
                            # Skip this test completely
                            continue
                    else:
                        is_gap_pwd = "password" in gap_flow.lower() or "password" in coverage.file_path.lower() or "pwd" in coverage.file_path.lower()
                        is_test_pwd = "password" in test.title.lower() or "password" in test.classname.lower() or "pwd" in test.title.lower()
                        if is_gap_pwd and is_test_pwd and shared_policy_validation:
                            score += 4.0
                            is_shared_policy = True

                    # Heuristic 1: Same parent requirement (+10)
                    has_matching_req = False
                    if coverage.related_requirement_ids:
                        for req_id in coverage.related_requirement_ids:
                            if req_id in test.mapped_requirement_ids:
                                score += 10.0
                                has_matching_req = True
                                break

                    # Heuristic 2: Matching flow (+5)
                    has_matching_flow = False
                    if gap_flow != "general":
                        if test.scenario_signature and test.scenario_signature.flow == gap_flow:
                            score += 5.0
                            has_matching_flow = True
                        elif gap_flow in test.title.lower() or gap_flow in test.classname.lower() or gap_flow.replace("_", "-") in test.title.lower():
                            score += 5.0
                            has_matching_flow = True

                    # Heuristic 3: Same module/filename (+3)
                    has_matching_module = False
                    gap_filename = os.path.basename(coverage.file_path).split('.')[0]
                    if gap_filename.lower() in test.classname.lower() or gap_filename.lower() in test.title.lower() or (test.file_path and gap_filename.lower() in test.file_path.lower()):
                        score += 3.0
                        has_matching_module = True

                    # Track best match
                    if score >= 1.0 and score > best_score:
                        best_score = score
                        best_test = test
                        
                        # Build explanation reason
                        reasons = []
                        if is_shared_policy:
                            reasons.append("shared password policy")
                        else:
                            if has_matching_req:
                                reasons.append("same parent requirement")
                            if has_matching_flow:
                                reasons.append("same flow")
                            if has_matching_module:
                                reasons.append("same module/filename")
                        
                        if is_shared_policy:
                            best_reason = "Linked through shared password policy validation logic."
                            best_method = "shared_password_policy"
                        else:
                            best_reason = f"Linked through {', '.join(reasons)}."
                            if has_matching_req:
                                best_method = "parent_requirement"
                            elif has_matching_flow:
                                best_method = "matching_flow"
                            else:
                                best_method = "module_filename"

                # Check severity:
                # Optional if associated requirement is already verified by current PR execution
                related_reqs = [r for r in requirements if r.requirement_id in coverage.related_requirement_ids]
                is_verified = any(r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION for r in related_reqs)
                
                if is_verified:
                    severity = "Optional"
                else:
                    # Critical/Must if related to high risk logic with no tests
                    is_high_risk = any(r.risk_level and r.risk_level.lower() == "high" for r in related_reqs)
                    has_no_tests = all(
                        r.classification in (EvidenceClassification.MISSING_AUTOMATED_COVERAGE, EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK)
                        for r in related_reqs
                    )
                    
                    if is_high_risk and (has_no_tests or not related_reqs):
                        severity = "Must"
                    # Recommended if security sensitive logic (auth, password, token) and branch coverage is weak < 60%
                    elif coverage.branch_coverage < 60.0 and any(kw in coverage.file_path.lower() for kw in ["auth", "password", "token"]):
                        severity = "Recommended"
                    else:
                        severity = "Optional"

                # Build suggested action
                suggested_action = f"Add automated coverage for uncovered statements in {os.path.basename(coverage.file_path)}"

                card = CoverageGapCard(
                    file_path=coverage.file_path,
                    line_coverage=coverage.line_coverage,
                    branch_coverage=coverage.branch_coverage,
                    flow=gap_flow,
                    uncovered_lines=coverage.uncovered_lines or [],
                    partially_covered_branches=coverage.partially_covered_branches or [],
                    related_requirement_ids=coverage.related_requirement_ids or [],
                    linked_test_id=best_test.test_id if best_test else None,
                    linked_test_title=best_test.title if best_test else "No directly linked test",
                    why_link_relevant=best_reason if best_test else None,
                    suggested_action=suggested_action,
                    severity=severity,
                    mapping_score=best_score,
                    mapping_method=best_method
                )
                self.view_model.coverage_gaps.append(card)

    def _build_ac_traceability(
        self,
        requirements: List[RequirementNode],
        executions: List[ExecutionNode],
        tests: List[TestNode],
        manual_evidence_nodes: Optional[List[Dict[str, Any]]] = None
    ):
        """Build AC traceability rows - only for parent requirements, not child rules."""
        test_map = {t.test_id: t for t in tests}

        for req in requirements:
            # Only include parent requirements in traceability, not child rules
            if req.node_type != "PARENT_REQUIREMENT":
                continue
            
            # Skip excluded fragments in main traceability
            if req.classification == EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA:
                continue

            # Determine status
            status = self._map_classification_to_status(req.classification)

            # Determine linked existing tests
            linked_existing_tests = []
            if req.matched_test_ids:
                for t_id in req.matched_test_ids:
                    test = test_map.get(t_id)
                    if test:
                        linked_existing_tests.append(test.title)

            # Determine linked missing test
            linked_missing_test = None
            if status == "Missing":
                for mt in self.view_model.missing_tests:
                    if mt.requirement_id == req.requirement_id:
                        linked_missing_test = mt.suggested_test_objective
                        break

            # Determine priority
            priority = "Must" if (req.risk_level and req.risk_level.lower() == "high") else "Recommended"

            # Determine notes - include classification reason and any attached notes
            notes_parts = []
            if req.classification_reason:
                notes_parts.append(req.classification_reason)
            if req.notes:
                notes_parts.extend(req.notes)
            notes = " | ".join(notes_parts) if notes_parts else ""

            # Compute manual validation metadata
            req_uuid_str = str(req.requirement_id)
            req_manual_nodes = [node for node in (manual_evidence_nodes or []) if str(node.get("acceptanceCriterionId")) == req_uuid_str]
            mapped_count = len(req_manual_nodes)
            
            executed_count = 0
            passed_count = 0
            failed_count = 0
            blocked_count = 0
            skipped_count = 0
            evidence_urls = []
            manual_tests_list = []
            newest_node = None

            for node in req_manual_nodes:
                outcome = node.get("outcome")
                if outcome not in (None, "NOT_EXECUTED"):
                    executed_count += 1
                    if outcome == "PASSED":
                        passed_count += 1
                    elif outcome == "FAILED":
                        failed_count += 1
                    elif outcome == "BLOCKED":
                        blocked_count += 1
                    elif outcome == "SKIPPED":
                        skipped_count += 1

                    if not newest_node or (node.get("executedAt") and newest_node.get("executedAt") and node.get("executedAt") > newest_node.get("executedAt")):
                        newest_node = node
                
                if node.get("evidenceUrl"):
                    evidence_urls.append(node.get("evidenceUrl"))

                manual_tests_list.append({
                    "id": node.get("manualTestId"),
                    "title": node.get("manualTestTitle"),
                    "outcome": outcome or "NOT_EXECUTED",
                    "executedAt": node.get("executedAt"),
                    "executedByName": node.get("executedBy"),
                    "evidenceUrl": node.get("evidenceUrl"),
                    "mappingSource": node.get("mappingSource")
                })

            if mapped_count == 0:
                manual_status = "NOT_MAPPED"
            elif executed_count == 0:
                manual_status = "NOT_EXECUTED"
            elif failed_count > 0:
                manual_status = "FAILED"
            elif blocked_count > 0:
                manual_status = "BLOCKED"
            elif passed_count > 0:
                manual_status = "PASSED"
            else:
                manual_status = "SKIPPED"

            status_to_support_status = {
                "PASSED": "MANUALLY_SUPPORTED",
                "FAILED": "MANUAL_FAILED",
                "BLOCKED": "MANUAL_BLOCKED",
                "SKIPPED": "MANUAL_SKIPPED",
                "NOT_EXECUTED": "MANUAL_NOT_EXECUTED",
                "NOT_MAPPED": "MANUAL_NOT_MAPPED"
            }
            manual_support_status = status_to_support_status[manual_status]

            manual_validation = {
                "status": manual_status,
                "supportStatus": manual_support_status,
                "mappedManualTestsCount": mapped_count,
                "executedManualTestsCount": executed_count,
                "passedManualTestsCount": passed_count,
                "failedManualTestsCount": failed_count,
                "blockedManualTestsCount": blocked_count,
                "skippedManualTestsCount": skipped_count,
                "latestOutcome": newest_node.get("outcome") if newest_node else None,
                "latestExecutedAt": newest_node.get("executedAt") if newest_node else None,
                "latestExecutedByName": newest_node.get("executedBy") if newest_node else None,
                "evidenceUrls": evidence_urls,
                "manualTests": manual_tests_list
            }

            row = ACTraceabilityRow(
                requirement_id=req.requirement_id,
                readable_id=req.readable_id,
                title=req.title,
                full_text=req.title,
                coverage_status=status,
                linked_existing_tests=linked_existing_tests,
                linked_missing_test=linked_missing_test,
                priority=priority,
                notes=notes,
                manual_support_status=manual_support_status,
                manual_validation=manual_validation,
                source_ac_number=getattr(req, 'source_number', None)
            )

            self.view_model.ac_traceability.append(row)

    def _map_classification_to_status(self, classification: EvidenceClassification) -> str:
        """Map classification to display status."""
        mapping = {
            EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION: "Covered",
            EvidenceClassification.FAILED_IN_CURRENT_PR_EXECUTION: "Failed",
            EvidenceClassification.SKIPPED_IN_CURRENT_PR_EXECUTION: "Skipped",
            EvidenceClassification.EXISTING_TEST_NOT_RUN_IN_CURRENT_PR: "Not Run",
            EvidenceClassification.MISSING_AUTOMATED_COVERAGE: "Missing",
            EvidenceClassification.PARTIALLY_COVERED: "Partially covered",
            EvidenceClassification.COVERAGE_GAP_ONLY: "Coverage Gap",
            EvidenceClassification.OPTIONAL_IMPROVEMENT: "Optional",
            EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK: "Not mapped",
            EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA: "Excluded",
        }
        return mapping.get(classification, "Unknown")

    def _determine_evidence(self, req: RequirementNode, exec_map: Dict[str, ExecutionNode]) -> str:
        """Determine evidence description."""
        if req.matched_execution_ids:
            return "Current PR execution"
        elif req.matched_test_ids:
            return "Existing automated test"
        elif req.classification == EvidenceClassification.PARTIALLY_COVERED:
            return "Code coverage only"
        return "No evidence"

    def _build_graph_quality(
        self,
        requirements: List[RequirementNode],
        match_table: List[MatchTableEntry],
        missing_tests: List[MissingTestCard],
        extraction_audit: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Build graph quality metrics."""
        import re
        counts = self.view_model.counts
        
        # 1. extractionQuality
        # real requirements over total segments (real + excluded)
        real_reqs = counts.get("verifiedTests", 0) + counts.get("missingAutomatedCoverage", 0) + counts.get("notMappedTraceabilityRisks", 0) + counts.get("requiredNotRun", 0)
        excluded = counts.get("excludedFragments", 0)
        extraction_quality = real_reqs / (real_reqs + excluded) if (real_reqs + excluded) > 0 else 1.0

        # 2. mappingQuality
        # confident matches over total mapped entries in match table
        confident = sum(1 for entry in match_table if entry.decision == "MATCHED")
        total_mapped = sum(1 for entry in match_table if entry.decision in ("MATCHED", "PARTIAL"))
        mapping_quality = confident / total_mapped if total_mapped > 0 else 1.0

        # 3. traceabilityQuality
        # mapped parent requirements over total parent requirements
        total_parents = counts.get("verifiedTests", 0) + counts.get("missingAutomatedCoverage", 0) + counts.get("requiredNotRun", 0) + counts.get("notMappedTraceabilityRisks", 0)
        mapped = total_parents - counts.get("notMappedTraceabilityRisks", 0)
        traceability_quality = mapped / total_parents if total_parents > 0 else 1.0

        # 4. evidenceCompleteness
        # verified over total required
        total_required = counts.get("verifiedTests", 0) + counts.get("missingAutomatedCoverage", 0) + counts.get("requiredNotRun", 0)
        evidence_completeness = counts.get("verifiedTests", 0) / total_required if total_required > 0 else 1.0

        # 5. hasContextMismatch
        # check contradiction penalty > 0 in match table
        has_context_mismatch = any(entry.contradiction_penalty > 0.0 for entry in match_table)

        # 6. hasInternalIdLeak
        # check if any readable_id has a hexadecimal hash of length >= 8 or a UUID
        uuid_pattern = re.compile(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})|([0-9a-fA-F]{8,})')
        has_internal_id_leak = False
        for req in requirements:
            rid = req.readable_id or ""
            if rid.startswith("AC-"):
                rid = rid[3:]
            if uuid_pattern.search(rid):
                has_internal_id_leak = True
                break

        # 7. hasCountMismatch
        # check if verifiedTests + failedTests + skippedTests matches total executions
        has_count_mismatch = (counts.get("verifiedTests", 0) + counts.get("failedTests", 0) + counts.get("skippedTests", 0)) != counts.get("uploadedPrTestsTotal", 0)

        # 8. hasDuplicateMissingScenario
        # check if there are duplicate requirement_ids in missing_tests
        has_duplicate_missing_scenario = len(set(mt.requirement_id for mt in missing_tests)) < len(missing_tests)

        # 9. hasPassedTestShownAsMissing
        # check if a requirement with passed executions or matched tests is marked missing
        has_passed_test_shown_as_missing = False
        for req in requirements:
            if req.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE:
                if req.matched_execution_ids:
                    has_passed_test_shown_as_missing = True
                    break
                # also check match table for confident or passed entries
                for entry in match_table:
                    if entry.requirement_id == req.requirement_id and entry.decision == "MATCHED":
                        has_passed_test_shown_as_missing = True
                        break

        quality = {
            "extractionQuality": extraction_quality,
            "mappingQuality": mapping_quality,
            "traceabilityQuality": traceability_quality,
            "evidenceCompleteness": evidence_completeness,
            "hasContextMismatch": has_context_mismatch,
            "hasInternalIdLeak": has_internal_id_leak,
            "hasCountMismatch": has_count_mismatch,
            "hasDuplicateMissingScenario": has_duplicate_missing_scenario,
            "hasPassedTestShownAsMissing": has_passed_test_shown_as_missing,
        }
        self.view_model.graph_quality = quality
        return quality

    def _determine_health(
        self,
        requirements: List[RequirementNode],
        executions: List[ExecutionNode],
        extraction_audit: Dict[str, Any] = None,
        recommendation_run_id: str = None,
        repository_id: str = None,
        db_session: Any = None
    ):
        """Determine overall health status using generic quality evaluator and configurable policy."""
        from app.services.evidence_graph.evidence_quality_policy import EvidenceQualityPolicy
        from app.services.evidence_graph.evidence_health_evaluator import EvidenceHealthEvaluator
        
        # Load the policy and check if default is used
        policy, is_default_used = EvidenceQualityPolicy.load_policy(
            recommendation_run_id=recommendation_run_id,
            repository_id=repository_id,
            db_session=db_session
        )
        
        # Extract parent requirements
        parent_reqs = [r for r in requirements if r.node_type == "PARENT_REQUIREMENT"]
        
        # Check primary buckets
        bucket_counts = {
            "VERIFIED_BY_CURRENT_PR_EXECUTION": 0,
            "FAILED_IN_CURRENT_PR_EXECUTION": 0,
            "SKIPPED_IN_CURRENT_PR_EXECUTION": 0,
            "REQUIRED_NOT_RUN": 0,
            "MISSING_AUTOMATED_COVERAGE": 0,
            "PARTIALLY_COVERED": 0,
            "NOT_MAPPED_TRACEABILITY_RISK": 0
        }
        
        seen_ids = set()
        duplicate_ids = []
        unbucketed_ids = []
        
        for req in parent_reqs:
            if req.requirement_id in seen_ids:
                duplicate_ids.append(req.requirement_id)
            seen_ids.add(req.requirement_id)
            
            cls = req.classification
            if cls == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION:
                bucket_counts["VERIFIED_BY_CURRENT_PR_EXECUTION"] += 1
            elif cls == EvidenceClassification.FAILED_IN_CURRENT_PR_EXECUTION:
                bucket_counts["FAILED_IN_CURRENT_PR_EXECUTION"] += 1
            elif cls == EvidenceClassification.SKIPPED_IN_CURRENT_PR_EXECUTION:
                bucket_counts["SKIPPED_IN_CURRENT_PR_EXECUTION"] += 1
            elif cls == EvidenceClassification.EXISTING_TEST_NOT_RUN_IN_CURRENT_PR:
                bucket_counts["REQUIRED_NOT_RUN"] += 1
            elif cls == EvidenceClassification.MISSING_AUTOMATED_COVERAGE:
                bucket_counts["MISSING_AUTOMATED_COVERAGE"] += 1
            elif cls == EvidenceClassification.PARTIALLY_COVERED:
                bucket_counts["PARTIALLY_COVERED"] += 1
            elif cls == EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK:
                bucket_counts["NOT_MAPPED_TRACEABILITY_RISK"] += 1
            else:
                unbucketed_ids.append(req.requirement_id)
                
        total_parent_requirements = len(parent_reqs)
        bucket_sum = sum(bucket_counts.values())
        
        invariant_failed = False
        if bucket_sum != total_parent_requirements or len(duplicate_ids) > 0 or len(unbucketed_ids) > 0:
            invariant_failed = True

        raw_failed_tests_count = sum(1 for e in executions if e.status in ("failed", "error"))
        raw_skipped_tests_count = sum(1 for e in executions if e.status == "skipped")
        
        verified_by_current_pr_count = bucket_counts["VERIFIED_BY_CURRENT_PR_EXECUTION"]
        failed_count = bucket_counts["FAILED_IN_CURRENT_PR_EXECUTION"]
        skipped_count = bucket_counts["SKIPPED_IN_CURRENT_PR_EXECUTION"]
        required_not_run_count = bucket_counts["REQUIRED_NOT_RUN"]
        missing_automated_coverage_count = bucket_counts["MISSING_AUTOMATED_COVERAGE"]
        partial_coverage_count = bucket_counts["PARTIALLY_COVERED"]
        not_mapped_traceability_risk_count = bucket_counts["NOT_MAPPED_TRACEABILITY_RISK"]

        verified_ratio = verified_by_current_pr_count / total_parent_requirements if total_parent_requirements > 0 else 1.0
        failed_ratio = failed_count / total_parent_requirements if total_parent_requirements > 0 else 0.0
        skipped_ratio = skipped_count / total_parent_requirements if total_parent_requirements > 0 else 0.0
        missing_ratio = missing_automated_coverage_count / total_parent_requirements if total_parent_requirements > 0 else 0.0
        partial_ratio = partial_coverage_count / total_parent_requirements if total_parent_requirements > 0 else 0.0
        unmapped_ratio = not_mapped_traceability_risk_count / total_parent_requirements if total_parent_requirements > 0 else 0.0

        metrics = {
            "total_parent_requirements": total_parent_requirements,
            "verified_by_current_pr_count": verified_by_current_pr_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "required_not_run_count": required_not_run_count,
            "missing_automated_coverage_count": missing_automated_coverage_count,
            "partial_coverage_count": partial_coverage_count,
            "not_mapped_traceability_risk_count": not_mapped_traceability_risk_count,
            
            "verified_ratio": verified_ratio,
            "failed_ratio": failed_ratio,
            "skipped_ratio": skipped_ratio,
            "missing_ratio": missing_ratio,
            "partial_ratio": partial_ratio,
            "unmapped_ratio": unmapped_ratio,

            "raw_failed_tests_count": raw_failed_tests_count,
            "raw_skipped_tests_count": raw_skipped_tests_count,
            
            "has_no_ac_source": extraction_audit.get("has_no_ac_source", False) if isinstance(extraction_audit, dict) else (getattr(extraction_audit, "has_no_ac_source", False) if extraction_audit else False),
            "has_stale_inputs": extraction_audit.get("has_stale_inputs", False) if isinstance(extraction_audit, dict) else (getattr(extraction_audit, "has_stale_inputs", False) if extraction_audit else False),
            "is_ac_extraction_empty": total_parent_requirements == 0,
            "invariant_failed": invariant_failed
        }

        # Calculate health using dedicated Evaluator
        health_status, can_render = EvidenceHealthEvaluator.determine_health(metrics, policy)
        self.view_model.health = health_status
        self.view_model.can_render_recommendation = can_render

        # Build policy violations / diagnostics list
        policy_violations = []

        if is_default_used:
            policy_violations.append({
                "code": "DEFAULT_EVIDENCE_QUALITY_POLICY_USED",
                "severity": "INFO",
                "policy_name": policy.policy_name,
                "policy_version": policy.policy_version
            })

        # Check LOW_VERIFIED_REQUIREMENT_COVERAGE
        check_ratios = total_parent_requirements >= policy.minimum_parent_requirements_for_ratio_rules
        if check_ratios and verified_ratio < policy.min_verified_ratio_for_ready:
            policy_violations.append({
                "code": "LOW_VERIFIED_REQUIREMENT_COVERAGE",
                "severity": "WARNING",
                "area": "TRACEABILITY",
                "message": f"Only {verified_by_current_pr_count} of {total_parent_requirements} parent requirements are verified by current PR execution.",
                "details": {
                    "verified_count": verified_by_current_pr_count,
                    "total_parent_requirements": total_parent_requirements,
                    "verified_ratio": verified_ratio,
                    "policy_threshold": policy.min_verified_ratio_for_ready,
                    "policy_name": policy.policy_name,
                    "policy_version": policy.policy_version
                }
            })

        # Check HIGH_UNMAPPED_REQUIREMENT_RATIO
        if (check_ratios and unmapped_ratio > policy.max_not_mapped_ratio_for_ready) or (not_mapped_traceability_risk_count > policy.max_not_mapped_count_for_ready):
            policy_violations.append({
                "code": "HIGH_UNMAPPED_REQUIREMENT_RATIO",
                "severity": "WARNING",
                "area": "TRACEABILITY",
                "message": f"High unmapped requirement ratio: {not_mapped_traceability_risk_count} requirements are not mapped.",
                "details": {
                    "not_mapped_count": not_mapped_traceability_risk_count,
                    "total_parent_requirements": total_parent_requirements,
                    "unmapped_ratio": unmapped_ratio,
                    "policy_threshold": policy.max_not_mapped_ratio_for_ready
                }
            })

        # Check MISSING_ACCEPTANCE_COVERAGE_PRESENT
        if missing_automated_coverage_count > 0:
            policy_violations.append({
                "code": "MISSING_ACCEPTANCE_COVERAGE_PRESENT",
                "severity": "WARNING",
                "area": "TRACEABILITY",
                "message": f"There are {missing_automated_coverage_count} parent requirements missing automated coverage.",
                "details": {
                    "missing_count": missing_automated_coverage_count,
                    "missing_ratio": missing_ratio
                }
            })

        # Check PARTIAL_COVERAGE_PRESENT
        if partial_coverage_count > 0:
            policy_violations.append({
                "code": "PARTIAL_COVERAGE_PRESENT",
                "severity": "WARNING",
                "area": "TRACEABILITY",
                "message": f"There are {partial_coverage_count} parent requirements with partial coverage.",
                "details": {
                    "partial_count": partial_coverage_count,
                    "partial_ratio": partial_ratio
                }
            })

        # Check GRAPH_BUCKET_INVARIANT_FAILED
        if invariant_failed:
            policy_violations.append({
                "code": "GRAPH_BUCKET_INVARIANT_FAILED",
                "severity": "ERROR",
                "area": "INVARIANT",
                "message": "Requirement graph primary bucket invariant check failed.",
                "details": {
                    "total_parent_requirements": total_parent_requirements,
                    "bucket_sum": bucket_sum,
                    "duplicate_requirement_ids": duplicate_ids,
                    "unbucketed_requirement_ids": unbucketed_ids
                }
            })

        self.view_model.diagnostics["policy_violations"] = policy_violations
        
        # Expose generic evidence quality metrics in diagnostics for verification
        self.view_model.diagnostics["generic_evidence_quality_metrics"] = metrics

    def _build_decision_copy(self):
        """Build user-facing decision copy based on health state."""
        health = self.view_model.health
        counts = self.view_model.counts
        verified = counts.get("verifiedTests", 0)
        passed_tests = counts.get("uploadedPrTestsPassed", 0)
        missing = counts.get("missingAutomatedCoverage", 0)
        partial = counts.get("coverageGaps", 0)
        not_mapped = counts.get("notMappedTraceabilityRisks", 0)
        required_not_run = counts.get("requiredNotRun", 0)

        if health == "STALE_INPUTS":
            self.view_model.decision_copy = DecisionCopy(
                headline="Stale Inputs — Regeneration Required",
                explanation=f"Current PR execution passed {passed_tests} tests, but traceability is incomplete. Regenerate the recommendation to rebuild evidence mapping from the latest inputs.",
                next_action="Regenerate the recommendation with fresh inputs.",
                primary_cta="Regenerate Recommendation",
                secondary_cta="Review stale evidence"
            )
        elif health == "BLOCKED_BY_FAILED_TESTS":
            failed = counts.get("failedTests", 0)
            self.view_model.decision_copy = DecisionCopy(
                headline="Evidence Review Blocked by Failed Tests",
                explanation=f"Current PR execution has {failed} failed test(s). Fix failing tests before proceeding with regression scope creation.",
                next_action="Review and fix failing tests.",
                primary_cta="Review Failed Tests",
                secondary_cta="Create Fix Scope"
            )
        elif health == "BLOCKED_BY_SKIPPED_REQUIRED_TESTS":
            skipped = counts.get("skippedTests", 0)
            self.view_model.decision_copy = DecisionCopy(
                headline="Evidence Review Blocked by Skipped Required Tests",
                explanation=f"Current PR execution skipped {skipped} required test(s). Run skipped tests before proceeding with regression scope creation.",
                next_action="Run skipped required tests.",
                primary_cta="Run Skipped Required Tests",
                secondary_cta="Regenerate Recommendation"
            )
        elif health == "NEEDS_TRACEABILITY_REVIEW":
            self.view_model.decision_copy = DecisionCopy(
                headline="Traceability Review Needed",
                explanation=f"Current PR execution passed {passed_tests} tests. Veriscope mapped {verified} acceptance criteria to passed PR evidence. {not_mapped} acceptance criteria require traceability review.",
                next_action="Review unmapped requirements and resolve mapping contradictions.",
                primary_cta="Review Traceability",
                secondary_cta="Regenerate Recommendation"
            )
        elif health == "VALIDATION_PASSED_COVERAGE_INCOMPLETE":
            self.view_model.decision_copy = DecisionCopy(
                headline="Validation Passed, Coverage Incomplete",
                explanation=f"Current PR execution passed {passed_tests} tests. Veriscope mapped {verified} acceptance criteria to passed PR evidence. {partial} acceptance criteria are partially supported and need review. {missing} acceptance criteria still lack automated coverage. {not_mapped} acceptance criteria require traceability review.",
                next_action="Review missing and partial coverage.",
                primary_cta="Review Missing & Partial Coverage",
                secondary_cta="Create Targeted Regression Scope"
            )
        elif health == "VALIDATION_PASSED_TRACEABILITY_INCOMPLETE":
            self.view_model.decision_copy = DecisionCopy(
                headline="Validation Passed, Traceability Incomplete",
                explanation=f"Current PR execution passed {passed_tests} tests. Veriscope mapped {verified} acceptance criteria to passed PR evidence. {not_mapped} acceptance criteria require traceability review. {required_not_run} acceptance criteria need traceability review.",
                next_action="Create scope with traceability warnings.",
                primary_cta="Review Traceability",
                secondary_cta="Create Regression Scope"
            )
        elif health == "READY_WITH_TRACEABILITY_ISSUES":
            self.view_model.decision_copy = DecisionCopy(
                headline="Verified with Missing Automation",
                explanation=f"Current PR execution passed {passed_tests} tests. Veriscope mapped {verified} acceptance criteria to passed PR evidence. {missing} acceptance criteria still lack automated coverage.",
                next_action="Review missing tests and add automated coverage.",
                primary_cta="Create Regression Scope",
                secondary_cta="Review Missing Tests"
            )
        elif health == "READY":
            self.view_model.decision_copy = DecisionCopy(
                headline="All Required Evidence Covered",
                explanation=f"Current PR execution passed {passed_tests} tests. Veriscope mapped all {verified} acceptance criteria to passed PR evidence. No remaining gaps.",
                next_action="Proceed with confidence.",
                primary_cta="Create Regression Scope",
                secondary_cta=""
            )
        else:
            # Fallback for legacy health states
            self.view_model.decision_copy = DecisionCopy(
                headline="Validation Complete",
                explanation=f"Current PR execution passed {passed_tests} tests.",
                next_action="Proceed with confidence.",
                primary_cta="Create Regression Scope",
                secondary_cta=""
            )

    def _build_diagnostics(
        self,
        requirements: List[RequirementNode],
        match_table: List[MatchTableEntry],
        excluded_fragments: List[Dict[str, Any]],
        extraction_audit: Dict[str, Any] = None
    ):
        """Build debug diagnostics."""
        diagnostics = {
            "extractedRequirements": [req.to_dict() for req in requirements],
            "excludedFragments": excluded_fragments,
            "matchTable": [
                {
                    "requirementId": entry.requirement_id,
                    "requirementTitle": entry.requirement_title,
                    "candidateTestTitle": entry.candidate_test_title,
                    "score": entry.score,
                    "decision": entry.decision,
                    "reason": entry.reason,
                    "contradictionPenalty": entry.contradiction_penalty,
                }
                for entry in match_table
            ],
            "finalBuckets": self._build_final_buckets(requirements),
        }

        # Add extraction audit if available
        if extraction_audit:
            diagnostics["extractionAudit"] = extraction_audit

        # Compute manual validation diagnostics based on manual_evidence_nodes
        manual_diags = []
        manual_evidence = getattr(self.view_model, "manual_evidence_nodes", [])
        if manual_evidence:
            manual_diags.append("MANUAL_EVIDENCE_CHANNEL_ACTIVE")
            
            any_failed = any(node.get("outcome") == "FAILED" for node in manual_evidence)
            any_blocked = any(node.get("outcome") == "BLOCKED" for node in manual_evidence)
            any_executed = any(node.get("outcome") not in (None, "NOT_EXECUTED") for node in manual_evidence)
            
            if any_failed:
                manual_diags.append("MANUAL_TEST_FAILED")
            if any_blocked:
                manual_diags.append("MANUAL_TEST_BLOCKED")
            if not any_executed:
                manual_diags.append("MANUAL_TEST_MAPPED_NOT_EXECUTED")

        diagnostics["diagnostics"] = manual_diags

        self.view_model.diagnostics.update(diagnostics)

    def _build_final_buckets(self, requirements: List[RequirementNode]) -> Dict[str, List[str]]:
        """Build final classification buckets."""
        buckets = {cls.value: [] for cls in EvidenceClassification}

        for req in requirements:
            buckets[req.classification.value].append(req.readable_id)

        return buckets
