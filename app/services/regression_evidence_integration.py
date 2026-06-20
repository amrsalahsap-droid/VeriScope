"""Integration layer to convert existing database models to Regression Evidence Classifier nodes."""
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.test_result import TestCase, TestResult
from app.models.coverage import CoverageReport, FileTestLink
from app.models.pull_request import PullRequest

from app.services.regression_evidence_classifier import (
    RequirementNode,
    TestNode,
    ExecutionNode,
    CoverageNode,
    ScenarioSignature,
    ScenarioSignatureGenerator,
)


class RegressionEvidenceIntegration:
    """Converts existing database models to Regression Evidence Classifier nodes."""

    def __init__(self, db: Session):
        self.db = db
        self.signature_generator = ScenarioSignatureGenerator()

    def build_requirement_nodes(
        self,
        acceptance_criteria: List[AcceptanceCriterion],
        context: Optional[Dict[str, Any]] = None
    ) -> List[RequirementNode]:
        """Build RequirementNodes from AcceptanceCriterion models."""
        if context is None:
            context = {}

        requirement_nodes = []
        for ac in acceptance_criteria:
            # Generate scenario signature
            signature = self.signature_generator.generate_signature(
                ac.text,
                context={
                    "flow": context.get("flow", ""),
                    "action": context.get("action", ""),
                    "condition": context.get("condition", ""),
                    "expected_outcome": context.get("expected_outcome", ""),
                }
            )

            # Extract flow, action, condition, expected_outcome from signature
            req_node = RequirementNode(
                requirement_id=str(ac.id),
                readable_id=ac.label or f"AC-{len(requirement_nodes) + 1:02d}",
                title=ac.text,
                flow=signature.flow,
                action=signature.action,
                condition=signature.condition,
                expected_outcome=signature.expected_outcome,
                polarity=signature.polarity,
                validation_layer=signature.validation_layer,
                risk_level=self._determine_risk_level(ac),
                source=ac.source or "acceptance_criteria",
                is_real_testable_requirement=ac.confidence > 0.5,  # Use confidence as proxy
                parent_requirement_id=None,
                scenario_signature=signature,
                source_number=ac.source_number,  # Phase 6.4: Add source_number for manual evidence matching
            )
            requirement_nodes.append(req_node)

        return requirement_nodes

    def build_test_nodes(
        self,
        test_cases: List[TestCase],
        context: Optional[Dict[str, Any]] = None
    ) -> List[TestNode]:
        """Build TestNodes from TestCase models."""
        if context is None:
            context = {}

        test_nodes = []
        for tc in test_cases:
            # Generate scenario signature
            signature = self.signature_generator.generate_signature(
                tc.test_name,
                context={
                    "flow": context.get("flow", ""),
                    "action": context.get("action", ""),
                    "condition": context.get("condition", ""),
                    "expected_outcome": context.get("expected_outcome", ""),
                }
            )

            # Determine test type from stable_identity or suite_name
            test_type = self._determine_test_type(tc)

            test_node = TestNode(
                test_id=str(tc.id),
                title=tc.test_name,
                normalized_title=self._normalize_test_title(tc.test_name),
                classname=tc.suite_name,
                file_path="",  # Not available in TestCase model
                test_type=test_type,
                automation_status="existing_automated",  # Assume automated for now
                mapped_requirement_ids=[],  # Will be populated by matching
                scenario_signature=signature,
                scenario_signature_hash=ScenarioSignatureGenerator.compute_signature_hash(signature),
                properties=getattr(tc, "properties", {}),
                acceptance_criterion_metadata=getattr(tc, "acceptance_criterion_metadata", None),
            )
            test_nodes.append(test_node)

        return test_nodes

    def build_execution_nodes(
        self,
        test_results: List[TestResult],
        pull_request_id: str,
        head_sha: str,
        test_map: Optional[Dict[str, TestNode]] = None
    ) -> List[ExecutionNode]:
        """Build ExecutionNodes from TestResult models."""
        if test_map is None:
            test_map = {}

        execution_nodes = []
        for tr in test_results:
            # Find corresponding test node
            test_node = test_map.get(str(tr.test_case_id))

            execution_node = ExecutionNode(
                test_id=str(tr.id),
                test_name=tr.test_case.test_name if tr.test_case else "Unknown",
                classname=tr.test_case.suite_name if tr.test_case else "Unknown",
                status=tr.status,
                duration=tr.duration or 0.0,
                pull_request_id=pull_request_id,
                head_sha=head_sha,
                source_file="",
                mapped_test_node_id=str(tr.test_case_id) if tr.test_case else None,
                mapped_requirement_ids=[],  # Will be populated by matching
                properties=getattr(tr, "properties", {}),
                acceptance_criterion_metadata=getattr(tr, "acceptance_criterion_metadata", None),
            )
            execution_nodes.append(execution_node)

        return execution_nodes

    def build_coverage_nodes(
        self,
        coverage_report: Optional[CoverageReport],
        changed_files: List[str],
        requirement_nodes: Optional[List[RequirementNode]] = None
    ) -> List[CoverageNode]:
        """Build CoverageNodes from CoverageReport model."""
        if not coverage_report:
            return []

        if requirement_nodes is None:
            requirement_nodes = []

        coverage_nodes = []
        
        # Get granular coverage entries mapped per source file
        from app.models.coverage import CoverageFileEntry
        file_entries = self.db.query(CoverageFileEntry).filter(
            CoverageFileEntry.coverage_report_id == coverage_report.id
        ).all()
        entry_map = {entry.file_path: entry for entry in file_entries}
        
        # Get file test links for the coverage report
        file_test_links = self.db.query(FileTestLink).filter(
            FileTestLink.coverage_report_id == coverage_report.id
        ).all()

        # Group by file path
        file_coverage_map = {}
        for ftl in file_test_links:
            if ftl.file_path not in file_coverage_map:
                file_coverage_map[ftl.file_path] = {
                    "line_coverage": 0.0,
                    "branch_coverage": 0.0,
                    "uncovered_lines": [],
                    "partially_covered_branches": [],
                }

        # Create coverage nodes for changed files
        for file_path in changed_files:
            # Try exact match first
            entry = entry_map.get(file_path)
            
            # If no exact match, try normalized path matching
            if not entry:
                # Normalize by removing leading/trailing slashes and common prefixes
                normalized_path = file_path.lstrip('/').lstrip('./')
                for entry_path, entry_data in entry_map.items():
                    normalized_entry_path = entry_path.lstrip('/').lstrip('./')
                    # Check if normalized paths match or if one is a suffix of the other
                    if (normalized_path == normalized_entry_path or
                        normalized_path.endswith(normalized_entry_path) or
                        normalized_entry_path.endswith(normalized_path)):
                        entry = entry_data
                        break
            
            # If still no match, try basename matching (last component of path)
            if not entry:
                import os
                changed_basename = os.path.basename(file_path)
                for entry_path, entry_data in entry_map.items():
                    entry_basename = os.path.basename(entry_path)
                    if changed_basename == entry_basename:
                        entry = entry_data
                        break
            
            if entry:
                line_coverage = entry.line_coverage_ratio if entry.line_coverage_ratio is not None else 0.0
                if line_coverage <= 1.0:
                    line_coverage *= 100.0
                branch_coverage = entry.branch_coverage_ratio if entry.branch_coverage_ratio is not None else 0.0
                if branch_coverage <= 1.0:
                    branch_coverage *= 100.0
                uncovered_lines = entry.uncovered_lines or []
                partially_covered_branches = []
            elif file_path in file_coverage_map:
                file_data = file_coverage_map[file_path]
                line_coverage = file_data["line_coverage"]
                branch_coverage = file_data["branch_coverage"]
                uncovered_lines = file_data["uncovered_lines"]
                partially_covered_branches = file_data["partially_covered_branches"]
            else:
                import logging
                logging.getLogger(__name__).warning(f"No coverage entry found for changed file: {file_path}")
                continue

            coverage_strength = self._determine_coverage_strength(
                line_coverage,
                branch_coverage
            )

            # Determine related flows from file path
            related_flows = self._extract_flows_from_file_path(file_path)

            # Infer code area from file path
            code_area = self._infer_code_area_from_file_path(file_path)

            # Find related requirements by flow
            related_requirement_ids = [
                req.requirement_id
                for req in requirement_nodes
                if req.flow in related_flows
            ]

            coverage_node = CoverageNode(
                file_path=file_path,
                line_coverage=line_coverage,
                branch_coverage=branch_coverage,
                uncovered_lines=uncovered_lines,
                partially_covered_branches=partially_covered_branches,
                related_flows=related_flows,
                related_requirement_ids=related_requirement_ids,
                coverage_strength=coverage_strength,
                code_area=code_area,
            )
            coverage_nodes.append(coverage_node)

        return coverage_nodes

    def _determine_risk_level(self, ac: AcceptanceCriterion) -> str:
        """Determine risk level from acceptance criterion."""
        text_lower = ac.text.lower()
        
        # High-risk keywords
        high_risk_keywords = ["security", "auth", "password", "token", "session", "critical"]
        if any(kw in text_lower for kw in high_risk_keywords):
            return "high"
        
        # Medium-risk keywords
        medium_risk_keywords = ["validate", "verify", "check", "ensure", "confirm"]
        if any(kw in text_lower for kw in medium_risk_keywords):
            return "medium"
        
        return "low"

    def _determine_test_type(self, tc: TestCase) -> str:
        """Determine test type from test case metadata."""
        stable_identity_lower = tc.stable_identity.lower()
        suite_name_lower = tc.suite_name.lower()

        if "api" in stable_identity_lower or "api" in suite_name_lower:
            return "API"
        elif "ui" in stable_identity_lower or "ui" in suite_name_lower:
            return "UI"
        elif "e2e" in stable_identity_lower or "e2e" in suite_name_lower:
            return "E2E"
        elif "integration" in stable_identity_lower or "integration" in suite_name_lower:
            return "integration"
        
        return "unit"

    def _normalize_test_title(self, title: str) -> str:
        """Normalize test title for comparison."""
        # Remove parameterized test suffixes
        import re
        normalized = re.sub(r'\[.*?\]$', '', title)
        normalized = re.sub(r'\(.*?\)$', '', normalized)
        return normalized.lower().strip()

    def _determine_coverage_strength(self, line_coverage: float, branch_coverage: float) -> str:
        """Determine coverage strength from metrics."""
        if line_coverage >= 90 and branch_coverage >= 80:
            return "strong"
        elif line_coverage >= 70 and branch_coverage >= 60:
            return "partial"
        elif line_coverage >= 50:
            return "weak"
        return "unrelated"

    def _extract_flows_from_file_path(self, file_path: str) -> List[str]:
        """Extract related flows from file path."""
        file_path_lower = file_path.lower()
        flows = []

        flow_keywords = {
            "password_reset": ["reset", "password", "reset-password"],
            "sign_up": ["signup", "sign-up", "register", "registration"],
            "update_password": ["update", "password", "change"],
            "login": ["login", "auth", "authentication"],
        }

        for flow, keywords in flow_keywords.items():
            if any(kw in file_path_lower for kw in keywords):
                flows.append(flow)

        return flows

    def _infer_code_area_from_file_path(self, file_path: str) -> str:
        """Infer code area from file path using generic heuristics.
        
        This is a generic implementation that works across different codebases
        without domain-specific hardcoding.
        """
        file_path_lower = file_path.lower()
        
        # Infer from directory structure
        if "api" in file_path_lower or "routes" in file_path_lower:
            return "backend_api"
        elif "app" in file_path_lower and ("page" in file_path_lower or "component" in file_path_lower):
            return "frontend_ui"
        elif "test" in file_path_lower or "__tests__" in file_path_lower:
            return "test"
        elif "module" in file_path_lower or "lib" in file_path_lower:
            return "shared_library"
        elif "util" in file_path_lower or "helper" in file_path_lower:
            return "utility"
        elif "config" in file_path_lower or "settings" in file_path_lower:
            return "configuration"
        elif "type" in file_path_lower or "interface" in file_path_lower:
            return "types"
        
        # Infer from file extension
        if file_path.endswith(".tsx") or file_path.endswith(".jsx"):
            return "frontend_ui"
        elif file_path.endswith(".ts") or file_path.endswith(".js"):
            if "test" in file_path_lower:
                return "test"
            elif "api" in file_path_lower or "route" in file_path_lower:
                return "backend_api"
            else:
                return "shared_library"
        elif file_path.endswith(".py"):
            return "backend_logic"
        elif file_path.endswith(".java"):
            return "backend_logic"
        
        return "unknown"

    def build_excluded_fragments(
        self,
        excluded_fragments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build excluded fragments list from AC extraction results."""
        return [
            {
                "text": fragment["text"],
                "reason": fragment["reason"],
                "source": fragment.get("source", "unknown"),
            }
            for fragment in excluded_fragments
        ]
