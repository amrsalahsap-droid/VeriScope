"""
Coverage query service for structural evidence.

This module provides query capabilities for coverage data, supporting
different coverage levels (RUN_LEVEL, TEST_FILE_LEVEL, TEST_CASE_LEVEL).
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.pull_request import PullRequest
from app.constants.evidence import CoverageLevel, EvidenceHealthStatus
from app.schemas.coverage import CoverageQueryResponse

logger = logging.getLogger(__name__)


class CoverageQueryService:
    """Service for querying coverage evidence."""

    @staticmethod
    def query_coverage_for_changed_files(
        db: Session,
        repository_id: UUID,
        changed_files: List[str],
        commit_sha: Optional[str] = None,
        pull_request_id: Optional[UUID] = None,
        require_test_level: bool = False,
    ) -> CoverageQueryResponse:
        """
        Query coverage for changed files.

        Args:
            db: Database session
            repository_id: Repository UUID
            changed_files: List of changed file paths
            commit_sha: Optional commit SHA for SHA matching
            pull_request_id: Optional pull request ID
            require_test_level: If True, only return results if test-level coverage exists

        Returns:
            CoverageQueryResponse with coverage details
        """
        # Find the most recent coverage report for this repository
        coverage_report = (
            db.query(CoverageReport)
            .filter(CoverageReport.repository_id == repository_id)
            .order_by(CoverageReport.created_at.desc())
            .first()
        )

        if not coverage_report:
            return CoverageQueryResponse(
                coverage_report_id=None,
                coverage_level=None,
                commit_sha=None,
                is_current=False,
                covered_files=[],
                uncovered_files=changed_files,
                file_coverage_details={},
                test_candidates=[],
                coverage_confidence="LOW",
                evidence_health_status=EvidenceHealthStatus.UNSUPPORTED,
            )

        # Check if coverage is current (matches commit SHA)
        is_current = False
        if commit_sha and coverage_report.commit_sha == commit_sha:
            is_current = True

        # If require_test_level and coverage is not test-level, return empty
        if require_test_level and coverage_report.coverage_level != CoverageLevel.TEST_CASE_LEVEL:
            return CoverageQueryResponse(
                coverage_report_id=coverage_report.id,
                coverage_level=coverage_report.coverage_level,
                commit_sha=coverage_report.commit_sha,
                is_current=is_current,
                covered_files=[],
                uncovered_files=changed_files,
                file_coverage_details={},
                test_candidates=[],
                coverage_confidence="LOW",
                evidence_health_status=EvidenceHealthStatus.DEGRADED,
            )

        # Query file entries for changed files
        file_entries = (
            db.query(CoverageFileEntry)
            .filter(
                CoverageFileEntry.coverage_report_id == coverage_report.id,
                CoverageFileEntry.file_path.in_(changed_files),
            )
            .all()
        )

        # Build coverage details
        covered_files = []
        uncovered_files = []
        file_coverage_details = {}

        for entry in file_entries:
            file_path = entry.file_path
            has_coverage = len(entry.covered_lines) > 0 or entry.line_coverage_ratio > 0

            if has_coverage:
                covered_files.append(file_path)
            else:
                uncovered_files.append(file_path)

            file_coverage_details[file_path] = {
                "covered_lines": entry.covered_lines,
                "uncovered_lines": entry.uncovered_lines,
                "total_lines": entry.total_lines,
                "line_coverage_ratio": entry.line_coverage_ratio,
                "branch_coverage_ratio": entry.branch_coverage_ratio,
            }

        # Files not found in coverage report are considered uncovered
        covered_paths = {entry.file_path for entry in file_entries}
        for file_path in changed_files:
            if file_path not in covered_paths:
                uncovered_files.append(file_path)
                file_coverage_details[file_path] = {
                    "covered_lines": [],
                    "uncovered_lines": [],
                    "total_lines": 0,
                    "line_coverage_ratio": 0.0,
                    "branch_coverage_ratio": None,
                }

        # Query test links only if test-level coverage exists
        test_candidates = []
        if coverage_report.coverage_level == CoverageLevel.TEST_CASE_LEVEL:
            test_links = (
                db.query(FileTestLink)
                .filter(
                    FileTestLink.coverage_report_id == coverage_report.id,
                    FileTestLink.file_path.in_(changed_files),
                )
                .all()
            )

            for link in test_links:
                test_candidates.append({
                    "file_path": link.file_path,
                    "test_case_id": str(link.test_case_id) if link.test_case_id else None,
                    "stable_test_id": link.stable_test_id,
                    "test_file_id": str(link.test_file_id) if link.test_file_id else None,
                    "covered_lines": link.covered_lines,
                    "line_ranges": link.line_ranges,
                    "mapping_type": link.mapping_type,
                    "confidence_score": link.confidence_score,
                    "source": link.source,
                })

        return CoverageQueryResponse(
            coverage_report_id=coverage_report.id,
            coverage_level=coverage_report.coverage_level,
            commit_sha=coverage_report.commit_sha,
            is_current=is_current,
            covered_files=covered_files,
            uncovered_files=uncovered_files,
            file_coverage_details=file_coverage_details,
            test_candidates=test_candidates,
            coverage_confidence=coverage_report.coverage_confidence,
            evidence_health_status=coverage_report.evidence_health_status,
        )

    @staticmethod
    def get_coverage_for_file(
        db: Session,
        repository_id: UUID,
        file_path: str,
        commit_sha: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get coverage details for a specific file.

        Args:
            db: Database session
            repository_id: Repository UUID
            file_path: File path to query
            commit_sha: Optional commit SHA for SHA matching

        Returns:
            Coverage details dict or None if not found
        """
        # Find the most recent coverage report for this repository
        coverage_report = (
            db.query(CoverageReport)
            .filter(CoverageReport.repository_id == repository_id)
            .order_by(CoverageReport.created_at.desc())
            .first()
        )

        if not coverage_report:
            return None

        # Check SHA match if provided
        if commit_sha and coverage_report.commit_sha != commit_sha:
            return None

        # Query file entry
        file_entry = (
            db.query(CoverageFileEntry)
            .filter(
                CoverageFileEntry.coverage_report_id == coverage_report.id,
                CoverageFileEntry.file_path == file_path,
            )
            .first()
        )

        if not file_entry:
            return None

        return {
            "coverage_report_id": str(coverage_report.id),
            "coverage_level": coverage_report.coverage_level,
            "commit_sha": coverage_report.commit_sha,
            "file_path": file_entry.file_path,
            "covered_lines": file_entry.covered_lines,
            "uncovered_lines": file_entry.uncovered_lines,
            "total_lines": file_entry.total_lines,
            "line_coverage_ratio": file_entry.line_coverage_ratio,
            "branch_coverage_ratio": file_entry.branch_coverage_ratio,
        }

    @staticmethod
    def get_test_candidates_for_file(
        db: Session,
        repository_id: UUID,
        file_path: str,
        commit_sha: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get test candidates for a specific file (only if test-level coverage exists).

        Args:
            db: Database session
            repository_id: Repository UUID
            file_path: File path to query
            commit_sha: Optional commit SHA for SHA matching

        Returns:
            List of test candidate dicts
        """
        # Find the most recent coverage report for this repository
        coverage_report = (
            db.query(CoverageReport)
            .filter(CoverageReport.repository_id == repository_id)
            .order_by(CoverageReport.created_at.desc())
            .first()
        )

        if not coverage_report:
            return []

        # Only return test candidates if test-level coverage
        if coverage_report.coverage_level != CoverageLevel.TEST_CASE_LEVEL:
            return []

        # Check SHA match if provided
        if commit_sha and coverage_report.commit_sha != commit_sha:
            return []

        # Query test links
        test_links = (
            db.query(FileTestLink)
            .filter(
                FileTestLink.coverage_report_id == coverage_report.id,
                FileTestLink.file_path == file_path,
            )
            .all()
        )

        return [
            {
                "test_case_id": str(link.test_case_id) if link.test_case_id else None,
                "stable_test_id": link.stable_test_id,
                "test_file_id": str(link.test_file_id) if link.test_file_id else None,
                "covered_lines": link.covered_lines,
                "line_ranges": link.line_ranges,
                "mapping_type": link.mapping_type,
                "confidence_score": link.confidence_score,
                "source": link.source,
            }
            for link in test_links
        ]
