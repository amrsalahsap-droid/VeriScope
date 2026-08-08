"""
Structural Impact Selection Service.

This service provides the core candidate discovery layer based on:
changed files → directed dependency expansion → impacted files → coverage-mapped tests.

AC mappings, behavior mappings, risk, and AI are overlays for prioritization and explanation.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from uuid import UUID
from sqlalchemy.orm import Session

from app.schemas.structural_impact import (
    StructuralImpactSelectionRequest,
    StructuralImpactSelectionResult,
    StructuralTestCandidate,
)
from app.services.dependency_expansion_resolver import DependencyExpansionResolver
from app.services.coverage_query import CoverageQueryService
from app.constants.evidence import CoverageLevel

logger = logging.getLogger(__name__)


class StructuralImpactSelectionService:
    """Service for structural impact selection as the core candidate discovery layer."""

    @staticmethod
    def select_structural_impact(
        db: Session,
        request: StructuralImpactSelectionRequest,
    ) -> StructuralImpactSelectionResult:
        """
        Select structural impact candidates based on changed files and dependency expansion.

        Steps:
        A. Load changed file paths.
        B. Expand impacted files using directed DependencyExpansionResolver.
        C. impacted_files = changed_files ∪ expanded_dependent_files.
        D. Query coverage mapping based on coverage level.
        E. Return StructuralImpactSelectionResult with evidence paths.

        Args:
            db: Database session
            request: Structural impact selection request

        Returns:
            StructuralImpactSelectionResult with structural candidates and evidence
        """
        # Step A: Load changed file paths (already in request)
        changed_files = request.changed_files

        # Step B: Expand impacted files using dependency expansion
        expansion_bundle = DependencyExpansionResolver.expand_dependencies(
            db=db,
            repository_id=request.repository_id,
            changed_files=changed_files,
            max_depth=request.max_expansion_depth,
            max_nodes=request.max_expansion_nodes,
        )

        # Step C: Combine changed and expanded files
        expanded_files = expansion_bundle.expanded_dependent_files
        impacted_files = list(set(changed_files + expanded_files))

        # Step D: Query coverage mapping
        coverage_response = CoverageQueryService.query_coverage_for_changed_files(
            db=db,
            repository_id=request.repository_id,
            changed_files=impacted_files,
            commit_sha=request.head_commit_sha,
            require_test_level=request.require_test_level,
        )

        # Build structurally impacted tests based on coverage level
        structurally_impacted_tests = []
        unmapped_impacted_files = []
        coverage_gaps = []
        evidence_paths = {}

        # Determine coverage level
        coverage_level = coverage_response.coverage_level or CoverageLevel.RUN_LEVEL

        # If TEST_CASE_LEVEL coverage exists, map specific tests
        if coverage_level == CoverageLevel.TEST_CASE_LEVEL:
            for test_candidate in coverage_response.test_candidates:
                file_path = test_candidate["file_path"]
                
                # Build evidence path
                impact_depth = 0
                if file_path in changed_files:
                    impact_depth = 0
                    evidence_path = [f"Changed file: {file_path}"]
                elif file_path in expanded_files:
                    impact_depth = expansion_bundle.depth_per_file.get(file_path, 1)
                    evidence_path = [
                        f"Changed file: {file_path}",
                        f"Dependency expansion (depth {impact_depth})",
                    ]
                else:
                    evidence_path = [f"Impacted file: {file_path}"]

                test = StructuralTestCandidate(
                    test_case_id=UUID(test_candidate["test_case_id"]) if test_candidate.get("test_case_id") else None,
                    stable_test_id=test_candidate.get("stable_test_id"),
                    test_file_id=UUID(test_candidate["test_file_id"]) if test_candidate.get("test_file_id") else None,
                    file_path=file_path,
                    covered_lines=test_candidate.get("covered_lines"),
                    line_ranges=test_candidate.get("line_ranges"),
                    mapping_type=test_candidate["mapping_type"],
                    confidence_score=test_candidate["confidence_score"],
                    source=test_candidate.get("source"),
                    impact_reason=f"Test covers structurally impacted file (depth {impact_depth})",
                    impact_depth=impact_depth,
                    evidence_path=evidence_path,
                )
                structurally_impacted_tests.append(test)
                evidence_paths[test.stable_test_id or str(test.test_case_id)] = evidence_path

        # If TEST_FILE_LEVEL coverage exists, return test files/specs
        elif coverage_level == CoverageLevel.TEST_FILE_LEVEL:
            # For test-file level, we can't map specific test cases but can identify test files
            # This is a placeholder for future implementation
            pass

        # If only RUN_LEVEL coverage exists, use it as risk evidence, not exact test selection
        elif coverage_level == CoverageLevel.RUN_LEVEL:
            # Aggregate coverage only - use as risk evidence
            for file_path in coverage_response.covered_files:
                if file_path in impacted_files:
                    coverage_gaps.append({
                        "file_path": file_path,
                        "gap_type": "aggregate_coverage_only",
                        "reason": "Only aggregate coverage available, cannot select exact tests",
                        "coverage_ratio": coverage_response.file_coverage_details.get(file_path, {}).get("line_coverage_ratio"),
                    })

        # Identify unmapped impacted files (no coverage/test mapping)
        for file_path in impacted_files:
            if file_path not in coverage_response.covered_files:
                unmapped_impacted_files.append(file_path)
                coverage_gaps.append({
                    "file_path": file_path,
                    "gap_type": "no_coverage",
                    "reason": "No coverage data available for impacted file",
                })

        # Build selection reasons
        selection_reasons = []
        if expanded_files:
            selection_reasons.append(f"Dependency expansion added {len(expanded_files)} files")
        if structurally_impacted_tests:
            selection_reasons.append(f"Selected {len(structurally_impacted_tests)} tests via structural impact")
        if unmapped_impacted_files:
            selection_reasons.append(f"{len(unmapped_impacted_files)} impacted files have no coverage mapping")

        # Determine selection confidence
        if coverage_level == CoverageLevel.TEST_CASE_LEVEL and structurally_impacted_tests:
            selection_confidence = "HIGH"
        elif coverage_level == CoverageLevel.TEST_FILE_LEVEL:
            selection_confidence = "MODERATE"
        elif coverage_level == CoverageLevel.RUN_LEVEL:
            selection_confidence = "LOW"
        else:
            selection_confidence = "LOW"

        return StructuralImpactSelectionResult(
            repository_id=request.repository_id,
            pull_request_id=request.pull_request_id,
            head_commit_sha=request.head_commit_sha,
            changed_files=changed_files,
            expanded_files=expanded_files,
            impacted_files=impacted_files,
            structurally_impacted_tests=[t.model_dump() for t in structurally_impacted_tests],
            coverage_level=coverage_level,
            unmapped_impacted_files=unmapped_impacted_files,
            coverage_gaps=coverage_gaps,
            evidence_paths=evidence_paths,
            dependency_expansion_used=len(expanded_files) > 0,
            expansion_depth_reached=expansion_bundle.expansion_depth_reached,
            expansion_limit_exceeded=expansion_bundle.limit_exceeded,
            dependency_state_hash=expansion_bundle.dependency_state_hash,
            selection_confidence=selection_confidence,
            selection_reasons=selection_reasons,
        )

    @staticmethod
    def get_structural_test_candidates(
        db: Session,
        repository_id: UUID,
        pull_request_id: Optional[UUID],
        head_commit_sha: str,
        changed_files: List[str],
        max_expansion_depth: int = 1,
        require_test_level: bool = False,
    ) -> List[StructuralTestCandidate]:
        """
        Get structural test candidates for a PR.

        This is a convenience method that creates the request and returns only the test candidates.

        Args:
            db: Database session
            repository_id: Repository UUID
            pull_request_id: Optional pull request UUID
            head_commit_sha: Head commit SHA
            changed_files: List of changed file paths
            max_expansion_depth: Max dependency expansion depth
            require_test_level: Require test-level coverage for test selection

        Returns:
            List of StructuralTestCandidate
        """
        request = StructuralImpactSelectionRequest(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            head_commit_sha=head_commit_sha,
            changed_files=changed_files,
            max_expansion_depth=max_expansion_depth,
            require_test_level=require_test_level,
        )

        result = StructuralImpactSelectionService.select_structural_impact(db, request)

        return [
            StructuralTestCandidate(**test_data)
            for test_data in result.structurally_impacted_tests
        ]
