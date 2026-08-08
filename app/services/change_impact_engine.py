"""Change Impact Engine v1 - Deterministic change impact analysis.

This service provides:
1. Change inventory from PR data
2. File-path classification to business flows
3. Behavior impact mapping
4. AC impact matrix generation
5. Regression candidate selection
6. Evidence overlay
7. Release action scope generation
"""

import logging
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session

from app.schemas.change_impact import (
    ChangeInventory,
    ImpactedBehavior,
    ACImpactMatrix,
    RegressionCandidate,
    ReleaseActionScope,
    ChangeImpactModel,
    ImpactType,
    FinalBucket,
    ReleaseAction,
    ScopeMode,
)
from app.behavior_taxonomy import (
    classify_file_layer,
    classify_file_domain,
    classify_file_risk_tags,
    extract_flows_from_file,
    get_indirect_flows,
    get_security_sensitive_flows,
    get_taxonomy_for_domain,
    AUTH_PASSWORD_TAXONOMY,
)
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.acceptance_criterion import AcceptanceCriterion
from app.services.coverage_query import CoverageQueryService
from app.services.structural_impact_selection import StructuralImpactSelectionService
from app.schemas.structural_impact import StructuralImpactSelectionRequest
from app.services.diff_analyzer_v2 import DiffAnalyzerV2
from app.schemas.change_summary import ChangeSummary
from app.constants.evidence import CoverageLevel

logger = logging.getLogger(__name__)


FUNCTION_FLOW_MAP = {
    "validatePassword": ["sign-up", "update-password", "reset-password"],
    "resetToken": ["reset-password"],
    "authenticateUser": ["login"],
}


class ChangeImpactEngine:
    """Change Impact Engine v1 - Deterministic impact analysis."""

    @staticmethod
    def build_change_inventory(
        pr: PullRequest,
        changed_files: List[PullRequestChangedFile]
    ) -> ChangeInventory:
        """Build change inventory from PR data.

        Args:
            pr: Pull request model
            changed_files: List of PullRequestChangedFile models

        Returns:
            ChangeInventory with classified change data
        """
        file_paths = [cf.file_path for cf in changed_files]
        
        # Extract components from file paths
        components = set()
        layers = set()
        domains = set()
        flows = set()
        keywords = set()
        all_risk_tags = set()
        
        for file_path in file_paths:
            # Extract component (e.g., "sign-up" from "src/modules/users/sign-up.ts")
            path_parts = file_path.replace("\\", "/").split("/")
            for part in path_parts:
                if part and not part.startswith(".") and not part.endswith((".ts", ".tsx", ".py", ".js")):
                    components.add(part)
            
            # Classify layer
            layer = classify_file_layer(file_path)
            layers.add(layer)
            # Compatibility alias mapping for layers
            if layer == "UI":
                layers.add("frontend/ui")
            elif layer == "API":
                layers.add("api/route")
            elif layer == "Service":
                layers.add("backend/business_logic")
            elif layer == "Data":
                layers.add("database/model")
            elif layer == "Shared":
                layers.add("utility/helper")
            
            # Classify domain
            domain = classify_file_domain(file_path)
            domains.add(domain)
            # Compatibility alias mapping for domains
            if domain == "auth":
                domains.add("authentication")
            elif domain == "profile":
                domains.add("user_management")
            elif domain == "payments":
                domains.add("payment")
            
            # Classify risk tags
            file_risk_tags = classify_file_risk_tags(file_path, domain, layer)
            all_risk_tags.update(file_risk_tags)
            
            # Extract flows using taxonomy
            taxonomy = get_taxonomy_for_domain(domain)
            if taxonomy:
                file_flows = extract_flows_from_file(file_path, taxonomy)
                flows.update(file_flows)
                
                # Extract keywords
                for keyword in taxonomy.get("keywords", []):
                    if keyword in file_path.lower():
                        keywords.add(keyword)
        
        # Determine if security-sensitive using risk tags and fallback keywords
        security_sensitive = "security" in all_risk_tags or "authentication" in domains or any(
            kw in keywords for kw in ["password", "auth", "token", "credential", "security"]
        )
        
        return ChangeInventory(
            changed_files=file_paths,
            changed_components=list(components),
            changed_layers=list(layers),
            changed_domains=list(domains),
            changed_flows=list(flows),
            security_sensitive=security_sensitive,
            change_keywords=list(keywords),
            risk_tags=list(all_risk_tags)
        )

    @staticmethod
    def analyze_semantic_changes(
        changed_files: List[PullRequestChangedFile],
        use_ast: bool = True
    ) -> Dict[str, ChangeSummary]:
        """Analyze semantic changes for changed files using DiffAnalyzerV2.
        
        Args:
            changed_files: List of PullRequestChangedFile models
            use_ast: Whether to use AST parsing (if supported)
            
        Returns:
            Dictionary mapping file paths to ChangeSummary objects
        """
        change_summaries = {}
        
        for cf in changed_files:
            try:
                # For now, we'll use placeholder content since we don't have
                # actual before/after content in PullRequestChangedFile
                # In a real implementation, this would fetch the actual file contents
                # from the git repository or PR diff API
                content_before = ""  # Placeholder
                content_after = ""   # Placeholder
                
                summary = DiffAnalyzerV2.analyze_diff(
                    file_path=cf.file_path,
                    content_before=content_before,
                    content_after=content_after,
                    use_ast=use_ast
                )
                
                change_summaries[cf.file_path] = summary
                
                logger.info(
                    f"Semantic analysis for {cf.file_path}: "
                    f"parser={summary.parser_used}, "
                    f"semantic_changes={summary.semantic_change_count}, "
                    f"non_semantic={summary.non_semantic_changes_only}"
                )
                
            except Exception as e:
                logger.error(f"Failed to analyze semantic changes for {cf.file_path}: {e}")
                # Create a fallback summary with parse error
                change_summaries[cf.file_path] = ChangeSummary(
                    file_path=cf.file_path,
                    parser_used="error",
                    parse_failed=True,
                    parse_error=str(e),
                    fallback_used=True
                )
        
        return change_summaries

    @staticmethod
    def map_changed_files_to_impacted_behaviors(
        change_inventory: ChangeInventory,
        pr_title: str = "",
        pr_description: str = ""
    ) -> Dict[str, List[ImpactedBehavior]]:
        """Map changed files to impacted behaviors.

        Args:
            change_inventory: Change inventory from build_change_inventory
            pr_title: PR title for additional context
            pr_description: PR description for additional context

        Returns:
            Dict mapping impact type to list of impacted behaviors
        """
        result = {
            "direct": [],
            "indirect": [],
            "cross_layer": [],
            "security_sensitive": [],
            "unknown": []
        }
        
        # Get taxonomy for domain
        # Prefer authentication domain if present (most critical for password changes)
        domain = "authentication" if "authentication" in change_inventory.changed_domains else (
            "auth" if "auth" in change_inventory.changed_domains else (
                change_inventory.changed_domains[0] if change_inventory.changed_domains else "unknown"
            )
        )
        taxonomy = get_taxonomy_for_domain(domain)
        
        # Direct impact: file path contains flow keyword
        for flow in change_inventory.changed_flows:
            for file_path in change_inventory.changed_files:
                file_path_lower = file_path.lower()
                # Check both flow patterns and file patterns
                flow_patterns = taxonomy.get("flows", {}).get(flow, [])
                file_patterns = taxonomy.get("file_patterns", {}).get(flow, [])
                all_patterns = flow_patterns + file_patterns
                
                if any(pattern in file_path_lower for pattern in all_patterns):
                    result["direct"].append(ImpactedBehavior(
                        flow=flow,
                        impact_type=ImpactType.DIRECT,
                        impact_confidence=0.9,
                        impact_reason=f"Changed file {file_path} directly affects {flow} flow",
                        changed_files=[file_path],
                        security_sensitive=flow in get_security_sensitive_flows(domain)
                    ))
                    break
        
        # Indirect impact: flows that depend on directly impacted flows
        direct_flows = [b.flow for b in result["direct"]]
        indirect_flow_names = get_indirect_flows(direct_flows, domain)
        
        for flow in indirect_flow_names:
            result["indirect"].append(ImpactedBehavior(
                flow=flow,
                impact_type=ImpactType.INDIRECT,
                impact_confidence=0.7,
                impact_reason=f"Flow {flow} depends on directly impacted flows: {', '.join(direct_flows)}",
                changed_files=change_inventory.changed_files,
                security_sensitive=flow in get_security_sensitive_flows(domain)
            ))
        
        # Cross-layer impact: if both UI and API layers changed
        has_ui = any(l in change_inventory.changed_layers for l in ["frontend/ui", "UI"])
        has_api = any(l in change_inventory.changed_layers for l in ["api/route", "API"])
        if has_ui and has_api:
            result["cross_layer"].append(ImpactedBehavior(
                flow="ui-api-consistency",
                impact_type=ImpactType.CROSS_LAYER,
                impact_confidence=0.85,
                impact_reason="Both UI and API layers changed - cross-layer consistency validation needed",
                changed_files=change_inventory.changed_files,
                security_sensitive=True
            ))
        
        # Security-sensitive impact
        if change_inventory.security_sensitive:
            for behavior in result["direct"] + result["indirect"]:
                if behavior.security_sensitive:
                    result["security_sensitive"].append(ImpactedBehavior(
                        flow=behavior.flow,
                        impact_type=ImpactType.SECURITY_SENSITIVE,
                        impact_confidence=behavior.impact_confidence,
                        impact_reason=f"Security-sensitive flow: {behavior.impact_reason}",
                        changed_files=behavior.changed_files,
                        security_sensitive=True
                    ))
        
        # Unknown impact: flows that don't match any pattern
        all_impacted_flows = set()
        for behaviors in result.values():
            all_impacted_flows.update(b.flow for b in behaviors)
        
        if change_inventory.changed_flows:
            for flow in change_inventory.changed_flows:
                if flow not in all_impacted_flows:
                    result["unknown"].append(ImpactedBehavior(
                        flow=flow,
                        impact_type=ImpactType.UNKNOWN,
                        impact_confidence=0.5,
                        impact_reason=f"Flow {flow} detected but impact classification unknown",
                        changed_files=change_inventory.changed_files,
                        security_sensitive=False
                    ))
        
        return result

    @staticmethod
    def build_ac_impact_matrix(
        acceptance_criteria: List[AcceptanceCriterion],
        impacted_behaviors: Dict[str, List[ImpactedBehavior]],
        change_inventory: ChangeInventory
    ) -> List[ACImpactMatrix]:
        """Build AC impact matrix.

        Args:
            acceptance_criteria: List of AcceptanceCriterion models
            impacted_behaviors: Dict from map_changed_files_to_impacted_behaviors
            change_inventory: Change inventory

        Returns:
            List of ACImpactMatrix entries
        """
        matrix = []
        
        # Build flow -> impact mapping
        flow_to_impact = {}
        for impact_type, behaviors in impacted_behaviors.items():
            for behavior in behaviors:
                flow_to_impact[behavior.flow] = {
                    "type": behavior.impact_type,
                    "confidence": behavior.impact_confidence,
                    "reason": behavior.impact_reason,
                    "changed_files": behavior.changed_files,
                    "security_sensitive": behavior.security_sensitive
                }
        
        for ac in acceptance_criteria:
            title_lower = ac.text.lower() if ac.text else ""
            
            # Determine business flow from AC title
            # Phase 6: Enhanced flow matching with password validation patterns
            business_flow = "unknown"
            
            # First try to match against changed flows using taxonomy patterns
            for flow in change_inventory.changed_flows:
                flow_patterns = []
                for domain_name in change_inventory.changed_domains:
                    tax = get_taxonomy_for_domain(domain_name)
                    if tax:
                        flow_patterns.extend(tax.get("flows", {}).get(flow, []))
                if flow in title_lower or any(pattern in title_lower for pattern in flow_patterns):
                    business_flow = flow
                    break
            
            # If no match, try enhanced password validation patterns (backward-compatible overlay)
            if business_flow == "unknown" and any(d in ["authentication", "auth"] for d in change_inventory.changed_domains):
                if any(kw in title_lower for kw in ["sign-up", "sign up", "registration", "register"]):
                    business_flow = "sign-up"
                elif any(kw in title_lower for kw in ["update-password", "update password", "change password", "password update"]):
                    business_flow = "update-password"
                elif any(kw in title_lower for kw in ["reset-password", "reset password", "forgot password", "password reset"]):
                    business_flow = "reset-password"
                elif any(kw in title_lower for kw in ["login after", "login works", "can log in"]):
                    business_flow = "login"
                elif any(kw in title_lower for kw in ["api", "backend", "direct request"]):
                    business_flow = "ui-api-consistency"
                elif any(kw in title_lower for kw in ["ui", "frontend", "consistency"]):
                    business_flow = "ui-api-consistency"
            
            # Fallback matching for other domains based on keywords
            if business_flow == "unknown":
                for flow in change_inventory.changed_flows:
                    if flow.replace("-flow", "") in title_lower:
                        business_flow = flow
                        break
            
            # Get impact data
            if business_flow not in flow_to_impact:
                is_sec = any(kw in title_lower for kw in ["password", "login", "auth", "credential"])
                if is_sec:
                    impact_data = {
                        "type": ImpactType.SECURITY_SENSITIVE,
                        "confidence": 0.7,
                        "reason": f"Security-sensitive flow {business_flow} related to password changes",
                        "changed_files": change_inventory.changed_files,
                        "security_sensitive": True
                    }
                else:
                    impact_data = {
                        "type": ImpactType.UNKNOWN,
                        "confidence": 0.5,
                        "reason": f"Flow {business_flow} not directly impacted by changes",
                        "changed_files": [],
                        "security_sensitive": False
                    }
            else:
                impact_data = flow_to_impact[business_flow]
            
            # Determine expected regression priority
            if impact_data["type"] == ImpactType.DIRECT:
                expected_priority = "REQUIRED_CANDIDATE"
            elif impact_data["type"] == ImpactType.INDIRECT and impact_data["security_sensitive"]:
                expected_priority = "RECOMMENDED_CANDIDATE"
            elif impact_data["type"] == ImpactType.INDIRECT:
                expected_priority = "OPTIONAL_CANDIDATE"
            else:
                expected_priority = "UNKNOWN"
            
            matrix.append(ACImpactMatrix(
                ac_id=str(ac.id),
                title=ac.text or "",
                business_flow=business_flow,
                impact_type=impact_data["type"],
                impact_confidence=impact_data["confidence"],
                impact_reason=impact_data["reason"],
                changed_files_related=impact_data["changed_files"],
                security_sensitive=impact_data["security_sensitive"],
                expected_regression_priority=expected_priority
            ))
        
        return matrix

    @staticmethod
    def select_regression_candidates(
        ac_impact_matrix: List[ACImpactMatrix],
        mode: ScopeMode
    ) -> List[RegressionCandidate]:
        """Select regression candidates based on mode.

        Args:
            ac_impact_matrix: AC impact matrix
            mode: Scope mode (TARGETED, RISK_BASED, FULL_SUITE)

        Returns:
            List of RegressionCandidate entries
        """
        candidates = []
        
        for ac_matrix in ac_impact_matrix:
            # Determine if this AC should be a candidate based on mode
            mode_selected = False
            candidate_reason = ""
            
            if mode == ScopeMode.TARGETED:
                # Targeted: Only DIRECT impacts (security-sensitive is an annotation, not a separate type)
                if ac_matrix.impact_type == ImpactType.DIRECT:
                    mode_selected = True
                    candidate_reason = "Direct impact on changed business flow"
            
            elif mode == ScopeMode.RISK_BASED:
                # Risk-Based: DIRECT + INDIRECT (security-sensitive) + CROSS_LAYER
                # SECURITY_SENSITIVE is an annotation on DIRECT/INDIRECT, not a separate selection type
                if ac_matrix.impact_type == ImpactType.DIRECT:
                    mode_selected = True
                    candidate_reason = "Direct impact on changed business flow"
                elif ac_matrix.impact_type == ImpactType.INDIRECT and ac_matrix.security_sensitive:
                    mode_selected = True
                    candidate_reason = "High-risk indirect impact (security-sensitive)"
                elif ac_matrix.impact_type == ImpactType.CROSS_LAYER:
                    mode_selected = True
                    candidate_reason = "Cross-layer impact detected"
            
            elif mode == ScopeMode.FULL_SUITE:
                # Full Suite: All ACs in the repository
                mode_selected = True
                candidate_reason = "Full suite: all acceptance criteria"

            # Safe-by-default logic: ALWAYS select candidates that are impacted in any way
            # (i.e. DIRECT, INDIRECT, CROSS_LAYER, or SECURITY_SENSITIVE) so they undergo
            # evidence overlay analysis and are never skipped silently.
            is_impacted = ac_matrix.impact_type in (
                ImpactType.DIRECT,
                ImpactType.INDIRECT,
                ImpactType.CROSS_LAYER,
                ImpactType.SECURITY_SENSITIVE
            )
            
            should_include = mode_selected or is_impacted
            if is_impacted and not mode_selected:
                candidate_reason = f"Safe-by-default selection of impacted flow ({ac_matrix.impact_type.value})"
            
            if should_include:
                # Determine risk level
                if ac_matrix.security_sensitive:
                    risk_level = "CRITICAL"
                elif ac_matrix.impact_type == ImpactType.DIRECT:
                    risk_level = "HIGH"
                elif ac_matrix.impact_type == ImpactType.INDIRECT:
                    risk_level = "MEDIUM"
                else:
                    risk_level = "LOW"
                
                candidates.append(RegressionCandidate(
                    id=ac_matrix.ac_id,
                    title=ac_matrix.title,
                    source_ac_id=ac_matrix.ac_id,
                    source_test_id=None,
                    business_flow=ac_matrix.business_flow,
                    impact_type=ac_matrix.impact_type,
                    impact_reason=ac_matrix.impact_reason,
                    changed_files=ac_matrix.changed_files_related,
                    changed_components=[],  # Will be populated from change inventory
                    changed_routes=[],  # Will be populated from change inventory
                    mapped_tests=[],  # Will be populated from test mappings
                    risk_level=risk_level,
                    selected_by_mode=mode.value,
                    candidate_reason=candidate_reason
                ))
        
        return candidates

    @staticmethod
    def select_structural_candidates(
        repository_id: Any,
        pull_request_id: Optional[Any],
        head_commit_sha: str,
        changed_files: List[str],
        db: Session,
        max_expansion_depth: int = 1,
        require_test_level: bool = False,
    ) -> List[RegressionCandidate]:
        """Select regression candidates based on structural impact.

        This is the core candidate discovery layer:
        changed files → directed dependency expansion → impacted files → coverage-mapped tests

        AC mappings, behavior mappings, risk, and AI are overlays for prioritization and explanation.

        Args:
            repository_id: Repository UUID
            pull_request_id: Optional pull request UUID
            head_commit_sha: Head commit SHA
            changed_files: List of changed file paths
            db: Database session
            max_expansion_depth: Max dependency expansion depth
            require_test_level: Require test-level coverage for test selection

        Returns:
            List of RegressionCandidate from structural impact
        """
        # Create structural impact selection request
        request = StructuralImpactSelectionRequest(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            head_commit_sha=head_commit_sha,
            changed_files=changed_files,
            max_expansion_depth=max_expansion_depth,
            require_test_level=require_test_level,
        )

        # Get structural impact selection result
        structural_result = StructuralImpactSelectionService.select_structural_impact(db, request)

        # Convert structural test candidates to RegressionCandidate format
        candidates = []
        for test_data in structural_result.structurally_impacted_tests:
            # Determine risk level based on impact depth and confidence
            impact_depth = test_data.get("impact_depth", 0)
            confidence_score = test_data.get("confidence_score", "MODERATE")
            
            if impact_depth == 0 and confidence_score == "HIGH":
                risk_level = "HIGH"
            elif impact_depth <= 1 and confidence_score in ("HIGH", "MODERATE"):
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            candidate = RegressionCandidate(
                id=test_data.get("test_case_id") or test_data.get("stable_test_id"),
                title=f"Structural test for {test_data['file_path']}",
                source_ac_id=None,  # Structural candidates don't have AC source
                source_test_id=test_data.get("test_case_id"),
                business_flow=f"structural_impact_{test_data['file_path']}",
                impact_type=ImpactType.DIRECT,  # Structural impact is direct
                impact_reason=test_data.get("impact_reason", "Structural impact from changed file"),
                changed_files=[test_data["file_path"]],
                changed_components=[],
                changed_routes=[],
                mapped_tests=[test_data.get("stable_test_id") or str(test_data.get("test_case_id"))],
                risk_level=risk_level,
                selected_by_mode="STRUCTURAL_IMPACT",
                candidate_reason=f"Selected by structural impact (depth {impact_depth}, confidence {confidence_score})",
            )
            
            # Add structural evidence metadata
            candidate.structural_evidence = {
                "coverage_level": structural_result.coverage_level,
                "impact_depth": impact_depth,
                "evidence_path": test_data.get("evidence_path", []),
                "mapping_type": test_data.get("mapping_type"),
                "mapping_confidence": confidence_score,
            }
            
            candidates.append(candidate)

        logger.info(
            "Structural impact selection: %d candidates from %d changed files (expanded to %d impacted files)",
            len(candidates),
            len(changed_files),
            len(structural_result.impacted_files),
        )

        return candidates

    @staticmethod
    def apply_coverage_evidence(
        candidates: List[RegressionCandidate],
        changed_files: List[str],
        db: Session,
        repository_id: Any,
        commit_sha: str = None,
    ) -> List[RegressionCandidate]:
        """Apply coverage evidence to refine regression candidates.

        This method uses coverage data to:
        1. Identify which changed files have coverage
        2. If test-level coverage exists, map specific tests to changed files
        3. If only run-level coverage exists, use it as risk evidence (not exact test selection)
        4. Never use coverage to skip tests without evidence

        Args:
            candidates: List of regression candidates
            changed_files: List of changed file paths
            db: Database session
            repository_id: Repository UUID
            commit_sha: Optional commit SHA for SHA matching

        Returns:
            List of RegressionCandidate with coverage evidence applied
        """
        if not db or not repository_id:
            return candidates

        # Query coverage for changed files
        coverage_response = CoverageQueryService.query_coverage_for_changed_files(
            db=db,
            repository_id=repository_id,
            changed_files=changed_files,
            commit_sha=commit_sha,
            require_test_level=False,  # Get whatever coverage is available
        )

        # If no coverage data, return candidates unchanged
        if not coverage_response.coverage_report_id:
            logger.info("No coverage data available for repository %s", repository_id)
            return candidates

        # Log coverage level and current status
        logger.info(
            "Coverage data available: level=%s, is_current=%s, covered_files=%d, uncovered_files=%d",
            coverage_response.coverage_level,
            coverage_response.is_current,
            len(coverage_response.covered_files),
            len(coverage_response.uncovered_files),
        )

        # Apply coverage evidence to each candidate
        for candidate in candidates:
            # Add coverage metadata to candidate
            candidate.coverage_evidence = {
                "coverage_report_id": str(coverage_response.coverage_report_id),
                "coverage_level": coverage_response.coverage_level,
                "is_current": coverage_response.is_current,
                "coverage_confidence": coverage_response.coverage_confidence,
            }

            # Check if candidate's changed files have coverage
            candidate_changed_files = candidate.changed_files or []
            covered_changed_files = [
                f for f in candidate_changed_files
                if f in coverage_response.covered_files
            ]
            uncovered_changed_files = [
                f for f in candidate_changed_files
                if f in coverage_response.uncovered_files
            ]

            candidate.coverage_evidence["covered_changed_files"] = covered_changed_files
            candidate.coverage_evidence["uncovered_changed_files"] = uncovered_changed_files

            # If test-level coverage exists, add test candidates
            if coverage_response.coverage_level == CoverageLevel.TEST_CASE_LEVEL:
                # Find test candidates for this candidate's changed files
                test_candidates = [
                    tc for tc in coverage_response.test_candidates
                    if tc["file_path"] in candidate_changed_files
                ]
                candidate.coverage_evidence["test_candidates"] = test_candidates

                # If we have test candidates, use them to refine mapped_tests
                if test_candidates:
                    # Extract unique test_case_ids from test candidates
                    test_ids = list(set(
                        tc["test_case_id"] for tc in test_candidates if tc["test_case_id"]
                    ))
                    candidate.coverage_evidence["coverage_based_test_ids"] = test_ids

            # If only run-level coverage, note that it's risk evidence only
            elif coverage_response.coverage_level == CoverageLevel.RUN_LEVEL:
                candidate.coverage_evidence["coverage_note"] = (
                    "Aggregate coverage only (RUN_LEVEL). "
                    "Use as risk evidence, not exact test selection."
                )

        return candidates

    @staticmethod
    def apply_evidence_overlay(
        candidate: RegressionCandidate,
        execution_status: str,
        freshness_status: str,
        test_exists: bool,
        db: Session = None,
        repository_id: Any = None,
        pr_head_commit_sha: str = None
    ) -> ReleaseActionScope:
        """Apply evidence overlay to a single candidate.

        Args:
            candidate: Regression candidate
            execution_status: Test execution status (PASSED, FAILED, NOT_RUN, etc.)
            freshness_status: Test freshness status (FRESH, STALE, UNKNOWN)
            test_exists: Whether a test exists for this candidate
            db: Database session for real-time lookup
            repository_id: Repository ID for test lookup
            pr_head_commit_sha: PR head commit SHA for freshness check

        Returns:
            ReleaseActionScope with final bucket and release action
        """
        # Determine if impacted
        is_impacted = candidate.impact_type not in (ImpactType.UNCHANGED, ImpactType.UNKNOWN)
        
        # Check mapping review status from DB
        is_suggested_only = False
        if db and repository_id and test_exists and candidate.source_ac_id:
            from app.models.traceability_edge import TraceabilityEdge
            edges = db.query(TraceabilityEdge).filter(
                TraceabilityEdge.repository_id == repository_id,
                TraceabilityEdge.source_node_type == "AcceptanceCriterion",
                TraceabilityEdge.source_node_id == str(candidate.source_ac_id),
                TraceabilityEdge.target_node_type == "TestCase",
                TraceabilityEdge.is_active == True
            ).all()
            if edges:
                unconfirmed_statuses = {"system_suggested", "needs_review", "pending_review", "unresolved"}
                is_suggested_only = all(e.review_status in unconfirmed_statuses for e in edges)

        # Apply rules in order of priority:
        if is_impacted:
            if not test_exists:
                # Impacted AC with no mapped tests
                final_bucket = FinalBucket.REQUIRED
                release_action = ReleaseAction.RUN_OR_CREATE_TEST
                reason_code = "NO_MAPPED_TESTS_FOR_IMPACTED_AC"
                evidence_reason = f"[{reason_code}] Selected due to {candidate.impact_reason.lower()}; no test evidence exists - execution or test creation required before release"
            
            elif is_suggested_only:
                # Impacted AC with only suggested mapping
                final_bucket = FinalBucket.REVIEW_NEEDED
                release_action = ReleaseAction.MANUAL_REVIEW
                reason_code = "ONLY_SUGGESTED_MAPPING_FOR_IMPACTED_AC"
                evidence_reason = f"[{reason_code}] Selected due to {candidate.impact_reason.lower()}; unconfirmed mapping needs manual review"
            
            elif execution_status == "FAILED":
                final_bucket = FinalBucket.REQUIRED
                release_action = ReleaseAction.FIX_OR_RERUN
                reason_code = "MISSING_EXECUTION_FOR_IMPACTED_AC"
                evidence_reason = f"[{reason_code}] Selected due to {candidate.impact_reason.lower()}; test is currently failing - fix required"
                
            elif execution_status == "PASSED" and freshness_status == "FRESH":
                # Confirmed coverage and fresh passing execution
                final_bucket = FinalBucket.ALREADY_VERIFIED
                release_action = ReleaseAction.NONE
                reason_code = "FRESH_PASSING_EXECUTION_ON_CURRENT_HEAD"
                evidence_reason = f"[{reason_code}] Selected due to {candidate.impact_reason.lower()}; already verified by fresh passing evidence on current commit"
                
            elif execution_status == "PASSED" and freshness_status == "STALE":
                # Impacted AC with stale execution
                final_bucket = FinalBucket.REQUIRED
                release_action = ReleaseAction.RE_RUN
                reason_code = "STALE_EXECUTION_ON_CHANGED_CODE"
                evidence_reason = f"[{reason_code}] Selected due to {candidate.impact_reason.lower()}; test passed but is stale - re-run required to verify against current changes"
                
            elif execution_status in ("NOT_RUN", "UNKNOWN") or freshness_status == "UNKNOWN":
                # Impacted AC with missing/unknown execution
                final_bucket = FinalBucket.REQUIRED
                release_action = ReleaseAction.RUN_OR_CREATE_TEST
                reason_code = "MISSING_EXECUTION_FOR_IMPACTED_AC"
                evidence_reason = f"[{reason_code}] Selected due to {candidate.impact_reason.lower()}; no passing execution record on the current head - execution required"
                
            else:
                # Safe fallback
                final_bucket = FinalBucket.REQUIRED
                release_action = ReleaseAction.RUN_OR_CREATE_TEST
                reason_code = "MISSING_EXECUTION_FOR_IMPACTED_AC"
                evidence_reason = f"[{reason_code}] Selected due to {candidate.impact_reason.lower()}; fallback - execution required"
        else:
            # Not impacted
            if execution_status == "PASSED" and freshness_status == "FRESH":
                final_bucket = FinalBucket.ALREADY_VERIFIED
                release_action = ReleaseAction.NONE
                reason_code = "FRESH_PASSING_EXECUTION_ON_CURRENT_HEAD"
                evidence_reason = f"[{reason_code}] Not impacted by changes and has fresh passing execution"
            else:
                final_bucket = FinalBucket.SAFE_TO_SKIP
                release_action = ReleaseAction.NONE
                reason_code = "NOT_IMPACTED_BY_CHANGE"
                evidence_reason = f"[{reason_code}] Acceptance criterion is not impacted by this change."

        return ReleaseActionScope(
            id=candidate.id,
            title=candidate.title,
            source_ac_id=candidate.source_ac_id,
            source_test_id=candidate.source_test_id,
            business_flow=candidate.business_flow,
            impact_type=candidate.impact_type,
            impact_reason=candidate.impact_reason,
            changed_files=candidate.changed_files,
            changed_components=candidate.changed_components,
            changed_routes=candidate.changed_routes,
            mapped_tests=candidate.mapped_tests,
            execution_status=execution_status,
            freshness_status=freshness_status,
            risk_level=candidate.risk_level,
            selected_by_mode=candidate.selected_by_mode,
            candidate_reason=candidate.candidate_reason,
            final_bucket=final_bucket,
            release_action=release_action,
            evidence_reason=evidence_reason,
            selected_by_impact=True,
            reason_code=reason_code
        )

    @staticmethod
    def build_change_impact_model(
        pr: PullRequest,
        changed_files: List[PullRequestChangedFile],
        acceptance_criteria: List[AcceptanceCriterion],
        test_mappings: Dict[str, List[str]],
        mode: ScopeMode = ScopeMode.TARGETED,
        db: Session = None,
        repository_id: Any = None
    ) -> ChangeImpactModel:
        """Build complete change impact model.

        Args:
            pr: Pull request model
            changed_files: List of PullRequestChangedFile models
            acceptance_criteria: List of AcceptanceCriterion models
            test_mappings: Dict mapping AC IDs to test IDs
            mode: Scope mode
            db: Database session for execution status lookup
            repository_id: Repository ID for test lookup

        Returns:
            Complete ChangeImpactModel
        """
        # Step 0: Get the diff text and build change summaries
        pr_diff = None
        if hasattr(pr, 'diff_text') and pr.diff_text:
            pr_diff = pr.diff_text
        elif hasattr(pr, 'diff') and pr.diff:
            pr_diff = pr.diff
        elif db:
            from app.services.diff_analyzer import get_pr_diff_from_db
            pr_diff = get_pr_diff_from_db(pr.id, db)
            
        change_summaries = None
        if pr_diff:
            from app.services.diff_analyzer import DiffAnalyzer
            change_summaries = DiffAnalyzer.analyze(pr_diff, [f.file_path for f in changed_files])
            logger.info(f"Change summaries: {change_summaries}")

        # Step 1: Build change inventory
        change_inventory = ChangeImpactEngine.build_change_inventory(pr, changed_files)
        
        # Step 2: Map changed files to impacted behaviors
        impacted_behaviors = ChangeImpactEngine.map_changed_files_to_impacted_behaviors(
            change_inventory,
            pr.title or "",
            getattr(pr, 'description', '') or ""
        )
        
        # Step 3: Build AC impact matrix
        ac_impact_matrix = ChangeImpactEngine.build_ac_impact_matrix(
            acceptance_criteria,
            impacted_behaviors,
            change_inventory
        )
        
        # Step 3.5: Enhance Candidate Selection with Diff Data (Phase 3)
        if change_summaries:
            for file_path, summary in change_summaries.items():
                for func in getattr(summary, 'changed_functions', []):
                    if func in FUNCTION_FLOW_MAP:
                        affected_flows = FUNCTION_FLOW_MAP[func]
                        affected_flows_normalized = [f.lower().replace(" ", "_").replace("-", "_") for f in affected_flows]
                        for ac in ac_impact_matrix:
                            normalized_flow = ac.business_flow.lower().replace(" ", "_").replace("-", "_")
                            if normalized_flow in affected_flows_normalized and ac.impact_type != ImpactType.DIRECT:
                                ac.impact_type = ImpactType.DIRECT
                                ac.impact_reason = f"Function {func} changed in {file_path}, affecting this flow"
                                if file_path not in ac.changed_files_related:
                                    ac.changed_files_related.append(file_path)
        
        # Step 4: Select regression candidates
        regression_candidates = ChangeImpactEngine.select_regression_candidates(
            ac_impact_matrix,
            mode
        )
        
        # Step 5: Apply evidence overlay to each candidate
        release_action_scope = []
        for candidate in regression_candidates:
            # Get test IDs for this AC
            test_ids = test_mappings.get(candidate.source_ac_id or "", [])
            candidate.mapped_tests = test_ids
            
            # Get execution status from database if available
            execution_status = "NOT_RUN"
            freshness_status = "UNKNOWN"
            
            if db and repository_id and test_ids:
                # Use existing _get_test_execution_status from RegressionScopeV2Service
                from app.services.regression_scope_v2_service import RegressionScopeV2Service
                execution_status, freshness_status, _, _, _ = RegressionScopeV2Service._get_test_execution_status(
                    db, repository_id, test_ids, pr.head_commit_sha or ""
                )
            
            # Apply evidence overlay
            scope_item = ChangeImpactEngine.apply_evidence_overlay(
                candidate,
                execution_status,
                freshness_status,
                test_exists=len(test_ids) > 0,
                db=db,
                repository_id=repository_id,
                pr_head_commit_sha=pr.head_commit_sha or ""
            )
            release_action_scope.append(scope_item)
        
        return ChangeImpactModel(
            change_inventory=change_inventory,
            directly_impacted_flows=impacted_behaviors.get("direct", []),
            indirectly_impacted_flows=impacted_behaviors.get("indirect", []),
            cross_layer_impacts=impacted_behaviors.get("cross_layer", []),
            security_sensitive_impacts=impacted_behaviors.get("security_sensitive", []),
            unknown_impacts=impacted_behaviors.get("unknown", []),
            ac_impact_matrix=ac_impact_matrix,
            regression_candidates=regression_candidates,
            release_action_scope=release_action_scope,
            change_summaries=change_summaries
        )
