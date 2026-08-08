"""Requirement Evidence Graph Service - Main orchestration service.

This service is the single source of truth for:
- Acceptance Criteria Traceability
- Verified Current PR Tests
- Required Tests Not Run
- Missing Automated Tests
- Coverage Gaps
- Executive Decision Counts
- Recommendation Evidence Summary
"""
from typing import List, Dict, Any, Optional
import logging
from sqlalchemy.orm import Session

from app.services.regression_evidence_classifier import (
    RequirementNode,
    TestNode,
    ExecutionNode,
    CoverageNode,
    EvidenceClassification,
    ClassificationReport,
)
from app.services.regression_evidence_integration import RegressionEvidenceIntegration
from app.services.evidence_graph.ac_extraction_service import ACExtractionService, ExtractionResult, ExtractionAudit
from app.services.evidence_graph.scenario_signature_service import ScenarioSignatureService
from app.services.evidence_graph.evidence_matching_service import EvidenceMatchingService
from app.services.evidence_graph.missing_test_mapper import MissingTestMapper
from app.services.evidence_graph.recommendation_view_model_builder import (
    RecommendationViewModelBuilder,
    RecommendationEvidenceViewModel,
)


class RequirementEvidenceGraphService:
    """Main service for requirement evidence graph and classification."""

    def __init__(self, db: Session):
        self.db = db
        self.ac_extraction_service = ACExtractionService()
        self.signature_service = ScenarioSignatureService()
        self.matching_service = EvidenceMatchingService()
        self.missing_test_mapper = MissingTestMapper()
        self.view_model_builder = RecommendationViewModelBuilder()
        self.integration = RegressionEvidenceIntegration(db)

    def build_evidence_graph(
        self,
        repository_id: str,
        pull_request_id: str,
        head_sha: str,
        changed_files: List[str],
        pr_description: Optional[str] = None,
        recommendation_run_id: str = None,
        canonical_ac_rows: Optional[List] = None,
        change_impact_model: Optional[Any] = None
    ) -> RecommendationEvidenceViewModel:
        """Build the complete evidence graph and view model.

        Args:
            repository_id: Repository ID
            pull_request_id: Pull request ID
            head_sha: Current commit SHA
            changed_files: List of changed files
            pr_description: Optional PR description for AC extraction
            recommendation_run_id: Optional recommendation run ID
            canonical_ac_rows: Optional list of AcceptanceCriterion DB rows to use directly
            change_impact_model: Optional ChangeImpactModel for unified classification

        Returns:
            RecommendationEvidenceViewModel as single source of truth
        """
        # Step 1: Extract clean RequirementNodes from PR description or use canonical AC rows
        if canonical_ac_rows is not None:
            extraction_result = self._build_requirement_nodes_from_canonical_rows(canonical_ac_rows)
        else:
            extraction_result = self._extract_requirements(pr_description)

        # Step 2: Build TestNodes from existing tests
        test_nodes = self._build_test_nodes(repository_id)

        # Step 3: Build ExecutionNodes from current PR test results
        execution_nodes = self._build_execution_nodes(pull_request_id, head_sha, test_nodes)

        # Step 4: Build CoverageNodes from coverage reports
        coverage_nodes = self._build_coverage_nodes(
            repository_id,
            head_sha,
            changed_files,
            pull_request_id,
            extraction_result.requirement_nodes
        )

        # Step 5: Generate scenario signatures for all nodes
        self._generate_signatures(extraction_result.requirement_nodes, test_nodes, execution_nodes)

        # Step 6: Match evidence to requirements
        self._match_evidence(extraction_result.requirement_nodes, test_nodes, execution_nodes)

        # Step 7: Classify each requirement
        self._classify_requirements(
            extraction_result.requirement_nodes,
            test_nodes,
            execution_nodes,
            coverage_nodes,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            head_sha=head_sha
        )

        # Step 8: Generate missing tests only from uncovered requirements
        missing_tests = self.missing_test_mapper.generate_missing_tests(
            extraction_result.requirement_nodes,
            match_table=self.matching_service.match_table
        )

        # Step 8.5: Load manual evidence nodes in bulk
        manual_evidence_nodes = self._load_manual_evidence(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            recommendation_run_id=recommendation_run_id
        )

        # Step 9: Build final view model
        view_model = self.view_model_builder.build_view_model(
            requirements=extraction_result.requirement_nodes,
            tests=test_nodes,
            executions=execution_nodes,
            coverage_nodes=coverage_nodes,
            missing_tests=missing_tests,
            match_table=self.matching_service.match_table,
            excluded_fragments=extraction_result.excluded_fragments,
            extraction_audit=extraction_result.audit.__dict__ if extraction_result.audit else None,
            recommendation_run_id=recommendation_run_id,
            repository_id=repository_id,
            db_session=self.db,
            manual_evidence_nodes=manual_evidence_nodes,
            change_impact_model=change_impact_model
        )

        return view_model

    def _extract_requirements(self, pr_description: Optional[str]) -> ExtractionResult:
        """Extract clean RequirementNodes from PR description."""
        if not pr_description:
            res = ExtractionResult()
            res.audit = ExtractionAudit()
            res.audit.has_no_ac_source = True
            return res

        import hashlib
        catalog_hash = hashlib.md5(pr_description.encode("utf-8")).hexdigest()

        context = {"flow": "general"}  # Can be enhanced with PR title
        res = self.ac_extraction_service.extract_acceptance_criteria(pr_description, context)
        
        # Set source_hash on all requirement nodes
        for req in res.requirement_nodes:
            req.source_hash = catalog_hash

        if hasattr(res, "audit") and res.audit is not None:
            res.audit.has_no_ac_source = False
        else:
            res.audit = ExtractionAudit()
            res.audit.has_no_ac_source = False
        return res

    def _build_requirement_nodes_from_canonical_rows(self, ac_rows: List) -> ExtractionResult:
        """Build RequirementNodes directly from canonical AcceptanceCriterion DB rows.
        
        This bypasses AC extraction to preserve all canonical ACs as parent requirements,
        preventing fragment/child rule reclassification that would drop valid requirements.
        """
        from app.services.regression_evidence_classifier import RequirementNode
        from app.services.evidence_graph.ac_extraction_service import ExtractionResult, ExtractionAudit
        
        result = ExtractionResult()
        result.audit = ExtractionAudit()
        result.audit.has_no_ac_source = False
        
        context = {"flow": "general"}
        
        # Use the integration layer to build requirement nodes from AC rows
        requirement_nodes = self.integration.build_requirement_nodes(ac_rows, context)
        
        # Mark all as real testable requirements (they are canonical DB rows)
        for req in requirement_nodes:
            req.is_real_testable_requirement = True
            req.source = "acceptance_criteria_db"
        
        result.requirement_nodes = requirement_nodes
        result.audit.real_requirements_count = len(requirement_nodes)
        result.audit.parent_requirements_count = len(requirement_nodes)
        
        return result

    def _build_test_nodes(self, repository_id: str) -> List[TestNode]:
        """Build TestNodes from existing tests in repository."""
        from app.models.test_result import TestCase

        test_cases = self.db.query(TestCase).filter(
            TestCase.repository_id == repository_id
        ).all()

        context = {"flow": "general"}
        return self.integration.build_test_nodes(test_cases, context)

    def _build_execution_nodes(
        self,
        pull_request_id: str,
        head_sha: str,
        test_nodes: List[TestNode]
    ) -> List[ExecutionNode]:
        """Build ExecutionNodes from current PR test results."""
        test_results = self._load_current_pr_test_results(pull_request_id)

        test_map = {t.test_id: t for t in test_nodes}
        return self.integration.build_execution_nodes(
            test_results,
            pull_request_id,
            head_sha,
            test_map
        )

    def _load_current_pr_test_results(self, pull_request_id: str):
        """
        Load current PR JUnit test results using the real persisted relationship.
        Must not use TestResult.pull_request_id since that field does not exist.
        """
        import logging
        from app.models.test_result import TestResult, TestRun
        
        logger = logging.getLogger(__name__)
        
        if not pull_request_id:
            logger.warning("No pull_request_id provided to load current PR test results.")
            return []
            
        test_results = self.db.query(TestResult).join(TestRun).filter(
            TestRun.pull_request_id == pull_request_id
        ).all()
        
        if not test_results:
            logger.warning("No current PR test execution relationship found for this recommendation run.")
            
        return test_results

    def _load_current_coverage_reports(
        self,
        repository_id: str,
        pull_request_id: str,
        head_sha: str
    ):
        """
        Load the current coverage report using real model fields.
        Must not use CoverageReport.head_commit_sha since it doesn't exist.
        """
        import logging
        from app.models.coverage import CoverageReport
        
        logger = logging.getLogger(__name__)
        
        # Prefer exact PR match first
        if pull_request_id:
            pr_reports = self.db.query(CoverageReport).filter(
                CoverageReport.pull_request_id == pull_request_id
            ).order_by(CoverageReport.created_at.desc()).all()
            
            if pr_reports:
                if len(pr_reports) > 1:
                    logger.warning(f"Found {len(pr_reports)} coverage reports for PR {pull_request_id}. Using the most recent.")
                return pr_reports[0]
                
        # Fallback to commit SHA
        if head_sha and repository_id:
            sha_reports = self.db.query(CoverageReport).filter(
                CoverageReport.repository_id == repository_id,
                CoverageReport.commit_sha == head_sha
            ).order_by(CoverageReport.created_at.desc()).all()
            
            if sha_reports:
                if len(sha_reports) > 1:
                    logger.warning(f"Found {len(sha_reports)} coverage reports for SHA {head_sha}. Using the most recent.")
                return sha_reports[0]
                
        logger.warning("No current coverage report found for this recommendation run.")
        return None

    def _build_coverage_nodes(
        self,
        repository_id: str,
        head_sha: str,
        changed_files: List[str],
        pull_request_id: Optional[str] = None,
        requirement_nodes: Optional[List[RequirementNode]] = None
    ) -> List[CoverageNode]:
        """Build CoverageNodes from coverage reports."""
        coverage_report = self._load_current_coverage_reports(
            repository_id, 
            pull_request_id, 
            head_sha
        )

        if not coverage_report:
            return []

        return self.integration.build_coverage_nodes(coverage_report, changed_files, requirement_nodes)

    def _generate_signatures(
        self,
        requirements: List[RequirementNode],
        tests: List[TestNode],
        executions: List[ExecutionNode]
    ):
        """Generate scenario signatures for all nodes."""
        # Generate for requirements
        for req in requirements:
            if not req.scenario_signature:
                result = self.signature_service.generate_signature(req.title)
                req.scenario_signature = result.signature

        # Generate for tests
        for test in tests:
            if not test.scenario_signature:
                result = self.signature_service.generate_signature(test.title)
                test.scenario_signature = result.signature
                test.scenario_signature_hash = result.hash

        # Generate for executions (use test signature if available)
        for exec_node in executions:
            if exec_node.mapped_test_node_id:
                test = next((t for t in tests if t.test_id == exec_node.mapped_test_node_id), None)
                if test and test.scenario_signature:
                    exec_node.scenario_signature = test.scenario_signature

    def _match_evidence(
        self,
        requirements: List[RequirementNode],
        tests: List[TestNode],
        executions: List[ExecutionNode]
    ):
        """Match evidence to requirements using matching service."""
        self.matching_service.clear_match_table()

        # Build execution map for test_id -> execution
        execution_map = {e.mapped_test_node_id: e for e in executions if e.mapped_test_node_id}

        # Match requirements to tests with execution context
        for req in requirements:
            # Find if there's a current PR execution for this requirement's potential matches
            execution = None
            for test in tests:
                if test.test_id in execution_map:
                    execution = execution_map[test.test_id]
                    break

            best_match, is_confident = self.matching_service.find_best_match(req, tests, execution)
            if best_match:
                req.match_score = best_match.score
                req.match_diagnostics = best_match.diagnostics
                if is_confident:
                    req.matched_test_ids = [best_match.test_id]

        # Link executions to requirements via matched tests
        test_map = {t.test_id: t for t in tests}
        for exec_node in executions:
            if exec_node.mapped_test_node_id:
                test = test_map.get(exec_node.mapped_test_node_id)
                if test:
                    for req in requirements:
                        if exec_node.mapped_test_node_id in req.matched_test_ids:
                            req.matched_execution_ids.append(exec_node.test_id)
                            exec_node.mapped_requirement_ids.append(req.requirement_id)

    def _classify_requirements(
        self,
        requirements: List[RequirementNode],
        tests: List[TestNode],
        executions: List[ExecutionNode],
        coverage_nodes: List[CoverageNode],
        policy: 'EvidenceQualityPolicy' = None,
        repository_id: Optional[str] = None,
        pull_request_id: Optional[str] = None,
        head_sha: Optional[str] = None
    ):
        """Classify each requirement based on evidence."""
        from app.services.evidence_graph.evidence_quality_policy import EvidenceQualityPolicy
        from app.models.coverage import FileTestLink, CoverageReport
        from app.models.test_result import TestCase, TestResult, TestRun
        from app.models.acceptance_criterion import AcceptanceCriterion
        
        if policy is None:
            policy, _ = EvidenceQualityPolicy.load_policy(
                db_session=self.db
            )
        
        test_map = {t.test_id: t for t in tests}
        execution_map = {e.test_id: e for e in executions}

        # Resolve current coverage report to filter FileTestLink queries
        current_report = None
        if repository_id:
            current_report = self._load_current_coverage_reports(
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                head_sha=head_sha
            )

        # Pre-load DIRECT_AC_ID links for all requirements to avoid N+1 queries
        # Build a map of AC identifiers to their linked test cases
        ac_identifier_to_test_cases = {}
        ac_identifier_to_passing_test_cases = {}
        
        # Get all AC identifiers from requirements
        ac_identifiers = set()
        for req in requirements:
            # Try to get AC identifier from readable_id (e.g., "AC-01")
            if req.readable_id and req.readable_id.startswith("AC-"):
                ac_identifiers.add(req.readable_id)
            # Also try source_number if available
            if hasattr(req, 'source_number') and req.source_number is not None:
                ac_identifiers.add(f"AC-{req.source_number:02d}")
        
        # Query FileTestLink for DIRECT_AC_ID mappings
        if ac_identifiers:
            query = self.db.query(FileTestLink).filter(
                FileTestLink.mapping_type == "DIRECT_AC_ID",
                FileTestLink.file_path.in_(ac_identifiers)
            )
            if current_report:
                query = query.filter(FileTestLink.coverage_report_id == current_report.id)
            elif repository_id:
                query = query.join(CoverageReport).filter(CoverageReport.repository_id == repository_id)
                
            direct_links = query.all()
            
            # Group by AC identifier
            for link in direct_links:
                ac_id = link.file_path
                if ac_id not in ac_identifier_to_test_cases:
                    ac_identifier_to_test_cases[ac_id] = []
                ac_identifier_to_test_cases[ac_id].append(link.test_case_id)
        
        # For each AC identifier, check if linked test cases have passing results
        for ac_id, test_case_ids in ac_identifier_to_test_cases.items():
            if not test_case_ids:
                continue
            
            # Get the most recent TestRun for the repository
            # We need to determine repository_id from context - for now, use the first test case
            if test_case_ids:
                first_tc = self.db.query(TestCase).filter(TestCase.id == test_case_ids[0]).first()
                if first_tc:
                    repository_id = first_tc.repository_id
                    
                    # Get the most recent TestRun for this repository
                    latest_run = self.db.query(TestRun).filter(
                        TestRun.repository_id == repository_id
                    ).order_by(TestRun.created_at.desc()).first()
                    
                    if latest_run:
                        # Check for passing TestResults in this run
                        passing_test_cases = self.db.query(TestResult).filter(
                            TestResult.test_run_id == latest_run.id,
                            TestResult.test_case_id.in_(test_case_ids),
                            TestResult.status == "passed"
                        ).all()
                        
                        if passing_test_cases:
                            ac_identifier_to_passing_test_cases[ac_id] = [tr.test_case_id for tr in passing_test_cases]

        for req in requirements:
            # Rule: Exclude fragments
            if not req.is_real_testable_requirement:
                req.classification = EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
                req.classification_reason = "Not a real testable requirement (fragment or test data)"
                continue

            # NEW: Check DIRECT_AC_ID link FIRST before any other logic
            ac_identifier = None
            if req.readable_id and req.readable_id.startswith("AC-"):
                ac_identifier = req.readable_id
            elif hasattr(req, 'source_number') and req.source_number is not None:
                ac_identifier = f"AC-{req.source_number:02d}"
            elif req.title:
                # Parse AC ID from title/label (format: "AC-XX <description>")
                import re
                match = re.match(r'^(AC-\d+)', req.title)
                if match:
                    ac_identifier = match.group(1)
            
            if ac_identifier and ac_identifier in ac_identifier_to_test_cases:
                # There is a DIRECT_AC_ID link
                linked_test_case_ids = ac_identifier_to_test_cases[ac_identifier]
                passing_test_case_ids = ac_identifier_to_passing_test_cases.get(ac_identifier, [])
                
                if passing_test_case_ids:
                    # Has passing test result → COVERED
                    req.classification = EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION
                    req.classification_reason = f"Directly linked test passed via DIRECT_AC_ID mapping (AC: {ac_identifier})"
                    # Set matched_test_ids to the passing test cases
                    req.matched_test_ids = [str(tc_id) for tc_id in passing_test_case_ids]
                    continue
                else:
                    # Has link but no passing result → PARTIALLY_COVERED
                    req.classification = EvidenceClassification.PARTIALLY_COVERED
                    req.classification_reason = f"Directly linked test exists but has no passing result via DIRECT_AC_ID mapping (AC: {ac_identifier})"
                    # Set matched_test_ids to the linked test cases
                    req.matched_test_ids = [str(tc_id) for tc_id in linked_test_case_ids]
                    continue

            # Find matched execution
            matched_execution = None
            for exec_id in req.matched_execution_ids:
                if exec_id in execution_map:
                    matched_execution = execution_map[exec_id]
                    break

            # Rule 1: Current PR passed
            if matched_execution and matched_execution.status == "passed":
                req.classification = EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION
                req.classification_reason = f"Verified by current PR execution (score: {req.match_score:.2f})"
                continue

            # Rule 2: Current PR failed / error
            if matched_execution and matched_execution.status in ("failed", "error"):
                req.classification = EvidenceClassification.FAILED_IN_CURRENT_PR_EXECUTION
                req.classification_reason = f"Failed in current PR execution: {matched_execution.status}"
                continue

            # Rule 3: Current PR skipped
            if matched_execution and matched_execution.status == "skipped":
                req.classification = EvidenceClassification.SKIPPED_IN_CURRENT_PR_EXECUTION
                req.classification_reason = "Skipped in current PR execution"
                continue

            # Rule 4: Existing test not run
            if req.matched_test_ids:
                test = test_map.get(req.matched_test_ids[0])
                if test and test.automation_status == "existing_automated":
                    req.classification = EvidenceClassification.EXISTING_TEST_NOT_RUN_IN_CURRENT_PR
                    req.classification_reason = f"Existing automated test matches (score: {req.match_score:.2f}) but not executed in current PR"
                    continue

            # Rule 7: If real parent requirement cannot be matched confidently (partial match)
            if 0.65 <= req.match_score < 0.85:
                best_entry = next((entry for entry in self.matching_service.match_table if entry.requirement_id == req.requirement_id and entry.score == req.match_score), None)
                has_passed_exec = False
                if best_entry:
                    candidate_test = next((t for t in tests if t.title == best_entry.candidate_test_title), None)
                    if candidate_test:
                        for exec_node in executions:
                            if exec_node.mapped_test_node_id == candidate_test.test_id and exec_node.status == "passed":
                                has_passed_exec = True
                                break
                if policy.enable_partial_classification and has_passed_exec:
                    req.classification = EvidenceClassification.PARTIALLY_COVERED
                    req.classification_reason = f"Partially covered by supporting passed test execution (score: {req.match_score:.2f})"
                else:
                    req.classification = EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK
                    req.classification_reason = f"Real AC but no confident match (score: {req.match_score:.2f})"
                continue

            # Rule 5 & 6: Unmatched / missing automated coverage
            has_coverage = self._check_coverage_evidence(req, coverage_nodes)
            
            # Apply partial classification policy if enabled
            if policy.enable_partial_classification:
                coverage_strength = self._get_coverage_strength(req, coverage_nodes)
                
                # Rule C: Coverage only (no test execution) → PARTIALLY_COVERED
                if has_coverage and not req.matched_test_ids:
                    if policy.partial_classification_allow_coverage_only:
                        if coverage_strength >= policy.partial_classification_min_coverage_threshold:
                            req.classification = EvidenceClassification.PARTIALLY_COVERED
                            req.classification_reason = f"Coverage evidence above threshold ({coverage_strength}% >= {policy.partial_classification_min_coverage_threshold}%), no test match (score: {req.match_score:.2f})"
                        else:
                            req.classification = EvidenceClassification.MISSING_AUTOMATED_COVERAGE
                            req.classification_reason = f"Coverage below threshold ({coverage_strength}% < {policy.partial_classification_min_coverage_threshold}%), no test match (score: {req.match_score:.2f})"
                    else:
                        # Policy requires test execution for partial classification
                        req.classification = EvidenceClassification.MISSING_AUTOMATED_COVERAGE
                        req.classification_reason = f"Coverage exists but policy requires test execution for partial classification (score: {req.match_score:.2f})"
                elif has_coverage and req.matched_test_ids and policy.partial_classification_require_test_execution:
                    # Rule A/B: Coverage + Test Execution
                    if matched_execution and matched_execution.status == "passed":
                        req.classification = EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION
                        req.classification_reason = f"Coverage + test execution passed (score: {req.match_score:.2f})"
                    elif matched_execution and matched_execution.status in ("failed", "error"):
                        req.classification = EvidenceClassification.FAILED_IN_CURRENT_PR_EXECUTION
                        req.classification_reason = f"Coverage + test execution failed (score: {req.match_score:.2f})"
                    elif matched_execution and matched_execution.status == "skipped":
                        req.classification = EvidenceClassification.SKIPPED_IN_CURRENT_PR_EXECUTION
                        req.classification_reason = f"Coverage + test execution skipped (score: {req.match_score:.2f})"
                    else:
                        # Has test match but no execution
                        req.classification = EvidenceClassification.PARTIALLY_COVERED
                        req.classification_reason = f"Coverage + test match but no execution (score: {req.match_score:.2f})"
                else:
                    # Rule D: No coverage, no test
                    req.classification = EvidenceClassification.MISSING_AUTOMATED_COVERAGE
                    req.classification_reason = f"No coverage or test evidence (score: {req.match_score:.2f})"
            else:
                # Original behavior when partial classification is disabled
                if has_coverage:
                    req.classification = EvidenceClassification.PARTIALLY_COVERED
                    req.classification_reason = f"Only coverage evidence exists, no test match (score: {req.match_score:.2f})"
                else:
                    req.classification = EvidenceClassification.MISSING_AUTOMATED_COVERAGE
                    req.classification_reason = f"No existing automated test or current PR execution found (score: {req.match_score:.2f})"

    def _check_coverage_evidence(self, req: RequirementNode, coverage_nodes: List[CoverageNode]) -> bool:
        """Check if there's coverage evidence for this requirement."""
        for coverage in coverage_nodes:
            if req.requirement_id in coverage.related_requirement_ids:
                return True
            if req.flow in coverage.related_flows:
                return True
        return False

    def _get_coverage_strength(self, req: RequirementNode, coverage_nodes: List[CoverageNode]) -> float:
        """Get the maximum coverage strength for a requirement from linked coverage nodes."""
        max_coverage = 0.0
        for coverage in coverage_nodes:
            if req.requirement_id in coverage.related_requirement_ids or req.flow in coverage.related_flows:
                # Use line coverage as the primary metric
                max_coverage = max(max_coverage, coverage.line_coverage)
        return max_coverage

    def persist_graph_snapshot(
        self,
        recommendation_run_id: str,
        view_model: RecommendationEvidenceViewModel
    ):
        """Persist graph snapshot with recommendation run for audit."""
        from app.models.recommendation import RecommendationRun
        import json

        run = self.db.query(RecommendationRun).filter(
            RecommendationRun.id == recommendation_run_id
        ).first()

        if run:
            repository_id = str(run.repository_id)
            # Serialize view model to JSON
            snapshot = {
                "health": view_model.health,
                "counts": view_model.counts,
                "decisionCopy": {
                    "headline": view_model.decision_copy.headline,
                    "explanation": view_model.decision_copy.explanation,
                    "nextAction": view_model.decision_copy.next_action,
                },
                "acTraceability": [
                    {
                        "requirementId": row.requirement_id,
                        "readableId": row.readable_id,
                        "title": row.title,
                        "fullText": row.full_text,
                        "coverageStatus": row.coverage_status,
                        "linkedExistingTests": row.linked_existing_tests,
                        "linkedMissingTest": row.linked_missing_test,
                        "priority": row.priority,
                        "notes": row.notes,
                        "manualSupportStatus": getattr(row, "manual_support_status", "MANUAL_NOT_MAPPED"),
                        "manualValidation": getattr(row, "manual_validation", {}),
                        "sourceAcNumber": getattr(row, "source_ac_number", None),
                        "databaseAcId": self._get_resolved_database_ac_id(row, repository_id),  # Phase 6: Add database AC ID for evidence overlay
                    }
                    for row in view_model.ac_traceability
                ],
                "missingTests": [
                    {
                        "readableId": mt.readable_id,
                        "requirementTitle": mt.requirement_title,
                        "suggestedTestObjective": mt.suggested_test_objective,
                        "riskIfSkipped": mt.risk_if_skipped,
                    }
                    for mt in view_model.missing_tests
                ],
                "matchTable": [
                    {
                        "requirementId": entry.requirement_id,
                        "requirementTitle": entry.requirement_title,
                        "candidateTestTitle": entry.candidate_test_title,
                        "score": entry.score,
                        "decision": entry.decision,
                        "reason": entry.reason,
                        "rejectionReason": entry.rejection_reason,
                        "contradictionRuleTriggered": entry.contradiction_rule_triggered,
                        "matchingDimensions": entry.matching_dimensions,
                        "currentPrExecutionId": entry.current_pr_execution_id,
                        "mapping_type": getattr(entry, "mapping_type", "FUZZY"),
                    }
                    for entry in self.matching_service.match_table
                ],
                "manualEvidenceNodes": getattr(view_model, "manual_evidence_nodes", []),
            }

            # Store in model (assuming JSON columns exist)
            run.requirement_evidence_snapshot_json = json.dumps(snapshot)
            self.db.commit()

    def recompute_snapshot_for_pr(
        self,
        repository_id: str,
        pull_request_id: str
    ) -> int:
        """Recompute acTraceability snapshot for open recommendation runs on a PR.
        
        This function is called after new evidence (JUnit/Cobertura) is uploaded
        to update the coverageStatus in existing recommendation run snapshots.
        
        Args:
            repository_id: Repository ID
            pull_request_id: Pull request ID
            
        Returns:
            Number of recommendation runs updated
        """
        from app.models.recommendation import RecommendationRun
        from app.models.pull_request import PullRequest
        from app.models.acceptance_criterion import AcceptanceCriterion
        from uuid import UUID
        import json
        
        # Resolve UUIDs safely
        pr_uuid = None
        if pull_request_id:
            try:
                pr_uuid = UUID(pull_request_id) if isinstance(pull_request_id, str) else pull_request_id
            except ValueError:
                pass
        
        repo_uuid = None
        if repository_id:
            try:
                repo_uuid = UUID(repository_id) if isinstance(repository_id, str) else repository_id
            except ValueError:
                pass
        
        if not pr_uuid or not repo_uuid:
            logger.warning(f"Invalid repository_id or pull_request_id for snapshot recompute")
            return 0
        
        # Find open recommendation runs for this PR
        # "Open" means not closed/merged - we'll use a simple check: runs created in the last 7 days
        from datetime import datetime, timedelta
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        
        open_runs = self.db.query(RecommendationRun).filter(
            RecommendationRun.repository_id == repo_uuid,
            RecommendationRun.pr_id == str(pr_uuid),
            RecommendationRun.created_at >= recent_cutoff
        ).all()
        
        if not open_runs:
            logger.info(f"No open recommendation runs found for PR {pull_request_id}")
            return 0
        
        updated_count = 0
        
        for run in open_runs:
            try:
                # Load the existing snapshot
                raw_snapshot = run.requirement_evidence_snapshot_json
                if isinstance(raw_snapshot, str):
                    snapshot_data = json.loads(raw_snapshot)
                else:
                    snapshot_data = raw_snapshot
                
                if not snapshot_data or "acTraceability" not in snapshot_data:
                    logger.warning(f"Run {run.id} has no acTraceability snapshot")
                    continue
                
                # Get AC rows for this PR
                ac_rows = self.db.query(AcceptanceCriterion).filter(
                    AcceptanceCriterion.pull_request_id == pr_uuid
                ).all()
                
                if not ac_rows:
                    logger.warning(f"No AC rows found for PR {pull_request_id}")
                    continue
                
                # Build requirement nodes from canonical AC rows
                extraction_result = self._build_requirement_nodes_from_canonical_rows(ac_rows)
                requirement_nodes = extraction_result.requirement_nodes
                
                # Build test nodes
                test_nodes = self._build_test_nodes(str(repo_uuid))
                
                # Build execution nodes (empty since we're not re-running tests)
                execution_nodes = []
                
                # Build coverage nodes (empty since we're not re-running coverage)
                coverage_nodes = []
                
                # Re-classify requirements with the updated DIRECT_AC_ID logic
                self._classify_requirements(
                    requirement_nodes,
                    test_nodes,
                    execution_nodes,
                    coverage_nodes
                )
                
                # Rebuild the view model to get updated ac_traceability
                view_model = self.view_model_builder.build_view_model(
                    requirements=requirement_nodes,
                    tests=test_nodes,
                    executions=execution_nodes,
                    coverage_nodes=coverage_nodes,
                    missing_tests=[],
                    match_table=self.matching_service.match_table,
                    excluded_fragments=[],
                    extraction_audit=extraction_result.audit.__dict__ if extraction_result.audit else None,
                    recommendation_run_id=str(run.id),
                    repository_id=str(repo_uuid),
                    db_session=self.db,
                    manual_evidence_nodes=snapshot_data.get("manualEvidenceNodes", [])
                )
                
                # Update the snapshot with new acTraceability
                snapshot_data["acTraceability"] = [
                    {
                        "requirementId": row.requirement_id,
                        "readableId": row.readable_id,
                        "title": row.title,
                        "fullText": row.full_text,
                        "coverageStatus": row.coverage_status,
                        "linkedExistingTests": row.linked_existing_tests,
                        "linkedMissingTest": row.linked_missing_test,
                        "priority": row.priority,
                        "notes": row.notes,
                        "manualSupportStatus": getattr(row, "manual_support_status", "MANUAL_NOT_MAPPED"),
                        "manualValidation": getattr(row, "manual_validation", {}),
                        "sourceAcNumber": getattr(row, "source_ac_number", None),
                        "databaseAcId": self._get_resolved_database_ac_id(row, str(repo_uuid)),  # Phase 6: Add database AC ID for evidence overlay
                    }
                    for row in view_model.ac_traceability
                ]
                
                # Write updated snapshot back
                run.requirement_evidence_snapshot_json = json.dumps(snapshot_data)
                self.db.commit()
                
                updated_count += 1
                logger.info(f"Updated snapshot for recommendation run {run.id}")
                
            except Exception as e:
                logger.exception(f"Failed to recompute snapshot for run {run.id}: {e}")
                self.db.rollback()
        
        logger.info(f"Recomputed snapshots for {updated_count} recommendation runs")
        return updated_count

    def _load_manual_evidence(
        self,
        repository_id: str,
        pull_request_id: str,
        recommendation_run_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load manual evidence nodes in bulk matching this repository/PR/run context.
        
        Phase 6.5: Includes governance status for each manual evidence node.
        """
        from app.models.manual_test_requirement_mapping import ManualTestRequirementMapping
        from app.models.manual_test_execution import ManualTestExecution
        from app.models.external_test_case_detailed import ExternalTestCase
        from app.models.acceptance_criterion import AcceptanceCriterion
        from app.services.manual_evidence_governance_service import ManualEvidenceGovernanceService
        from sqlalchemy import or_
        from uuid import UUID

        # Resolve UUIDs safely
        run_uuid = None
        if recommendation_run_id:
            try:
                run_uuid = UUID(recommendation_run_id) if isinstance(recommendation_run_id, str) else recommendation_run_id
            except ValueError:
                pass

        pr_uuid = None
        if pull_request_id:
            try:
                pr_uuid = UUID(pull_request_id) if isinstance(pull_request_id, str) else pull_request_id
            except ValueError:
                pass

        repo_uuid = None
        if repository_id:
            try:
                repo_uuid = UUID(repository_id) if isinstance(repository_id, str) else repository_id
            except ValueError:
                pass

        # Bulk load active mappings
        active_mappings = self.db.query(ManualTestRequirementMapping).filter(
            ManualTestRequirementMapping.repository_id == repo_uuid,
            ManualTestRequirementMapping.is_active == True
        ).all()

        if not active_mappings:
            return []

        mapped_test_case_ids = list({m.external_test_case_id for m in active_mappings})

        # Bulk load external test cases to resolve titles
        test_cases_by_id = {}
        if mapped_test_case_ids:
            tcs = self.db.query(ExternalTestCase).filter(ExternalTestCase.id.in_(mapped_test_case_ids)).all()
            test_cases_by_id = {tc.id: tc for tc in tcs}

        # Bulk load latest active executions
        latest_executions_by_test_id = {}
        if mapped_test_case_ids:
            filter_conds = [
                ManualTestExecution.external_test_case_id.in_(mapped_test_case_ids),
                ManualTestExecution.is_active == True
            ]
            
            pr_or_run_conds = []
            if pr_uuid:
                pr_or_run_conds.append(ManualTestExecution.pull_request_id == pr_uuid)
            if run_uuid:
                pr_or_run_conds.append(ManualTestExecution.recommendation_run_id == run_uuid)
                
            if pr_or_run_conds:
                filter_conds.append(or_(*pr_or_run_conds))
                
            executions = self.db.query(ManualTestExecution).filter(*filter_conds).all()
            for exec_rec in executions:
                test_id = exec_rec.external_test_case_id
                existing_exec = latest_executions_by_test_id.get(test_id)
                if not existing_exec or exec_rec.executed_at > existing_exec.executed_at:
                    latest_executions_by_test_id[test_id] = exec_rec

        # Bulk load acceptance criteria to resolve source_number
        ac_ids = list({m.acceptance_criterion_id for m in active_mappings})
        ac_by_id = {}
        if ac_ids:
            acs = self.db.query(AcceptanceCriterion).filter(AcceptanceCriterion.id.in_(ac_ids)).all()
            ac_by_id = {ac.id: ac for ac in acs}

        # Build list of manual evidence nodes
        manual_evidence_nodes = []
        
        # Phase 6.5: Initialize governance service for status lookup
        governance_service = ManualEvidenceGovernanceService(self.db)
        
        for mapping in active_mappings:
            exec_rec = latest_executions_by_test_id.get(mapping.external_test_case_id)
            tc = test_cases_by_id.get(mapping.external_test_case_id)
            ac = ac_by_id.get(mapping.acceptance_criterion_id)
            
            external_key = tc.external_key if tc else None
            readable_id = f"MT-{external_key}" if external_key else (f"MT-{ac.source_number}" if ac and ac.source_number is not None else "MT")
            
            # Phase 6.5: Get governance status for this execution
            governance_status = "PENDING_REVIEW"
            governance_reviewer = None
            governance_reviewed_at = None
            governance_review_note = None
            governance_is_expired = False
            
            if exec_rec:
                try:
                    governance_info = governance_service.get_governance_status(
                        execution_id=str(exec_rec.id),
                        repository_id=str(repo_uuid)
                    )
                    governance_status = governance_info.get("governanceStatus", "PENDING_REVIEW")
                    governance_reviewer = governance_info.get("reviewerName")
                    governance_reviewed_at = governance_info.get("reviewedAt")
                    governance_review_note = governance_info.get("reviewNote")
                    governance_is_expired = governance_info.get("isExpired", False)
                except Exception:
                    # If governance lookup fails, default to pending
                    governance_status = "PENDING_REVIEW"
            
            node = {
                "manualTestId": str(mapping.external_test_case_id),
                "manualTestTitle": tc.title if tc else "Unknown Test",
                "externalKey": external_key,
                "provider": tc.provider if tc else None,
                "readableId": readable_id,
                "acceptanceCriterionId": str(mapping.acceptance_criterion_id),
                "sourceAcNumber": ac.source_number if ac else None,
                "outcome": exec_rec.outcome.upper() if exec_rec else "NOT_EXECUTED",
                "executedBy": exec_rec.executed_by_name if exec_rec else None,
                "executedAt": exec_rec.executed_at.isoformat() + "Z" if exec_rec and exec_rec.executed_at else None,
                "notes": exec_rec.notes if exec_rec else None,
                "evidenceUrl": exec_rec.evidence_url if exec_rec else None,
                "mappingSource": mapping.mapping_source,
                "evidenceSource": "MANUAL",
                # Phase 6.5: Governance fields
                "governanceStatus": governance_status,
                "governanceReviewer": governance_reviewer,
                "governanceReviewedAt": governance_reviewed_at,
                "governanceReviewNote": governance_review_note,
                "governanceIsExpired": governance_is_expired
            }
            manual_evidence_nodes.append(node)

        return manual_evidence_nodes

    def _get_resolved_database_ac_id(self, row, repository_id: str) -> Optional[str]:
        db_ac_id = getattr(row, "database_ac_id", None) or getattr(row, "requirement_id", None) or getattr(row, "id", None)
        if db_ac_id and self.db:
            from app.models.acceptance_criterion import AcceptanceCriterion
            from uuid import UUID
            try:
                # Validate if it is a valid UUID
                if isinstance(db_ac_id, str):
                    UUID(db_ac_id)
                ac_exists = self.db.query(AcceptanceCriterion).filter(AcceptanceCriterion.id == db_ac_id).first() is not None
                if ac_exists:
                    return str(db_ac_id)
            except ValueError:
                pass
            
            # If not a valid UUID or does not exist, resolve via resolver
            from app.services.ac_identity_resolver import resolve_ac_identity
            ac_rows = self.db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.repository_id == repository_id
            ).all()
            resolved = resolve_ac_identity(row, ac_rows)
            if resolved and resolved.confidence >= 0.5:
                return resolved.database_ac_id
        return None
