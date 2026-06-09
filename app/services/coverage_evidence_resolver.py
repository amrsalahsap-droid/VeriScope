import uuid
from datetime import datetime, timedelta
from typing import Any, List, Dict, Optional
from sqlalchemy.orm import Session

from app.models.coverage import CoverageReport, FileTestLink
from app.schemas.recommendation import CoverageFileMapping, CoverageEvidenceBundle


def normalize_path(path: str) -> str:
    if not path:
        return ""
    p = path.lower().replace("\\", "/").strip()
    if p.startswith("./"):
        p = p[2:]
    if p.startswith("/"):
        p = p[1:]
    
    # Strip common directory roots iteratively
    prefixes = ["src/", "app/", "modules/"]
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if p.startswith(prefix):
                p = p[len(prefix):]
                changed = True
    return p



class CoverageEvidenceResolver:
    @staticmethod
    def resolve_coverage(
        db: Session,
        repository_id: uuid.UUID,
        pull_request_id: Any,
        head_commit_sha: str,
        changed_files: List[str]
    ) -> CoverageEvidenceBundle:
        """
        Find valid coverage evidence for a PR and classify its trustworthiness.
        """
        from app.models.pull_request import PullRequest
        db_pr = None
        if pull_request_id:
            try:
                db_pr = db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
            except Exception:
                pass
        branch_name = db_pr.source_branch if db_pr else None

        has_empty_coverage = any("empty_coverage" in f for f in changed_files)
        report = None
        is_exact = False
        is_same_branch = False
        is_repo_latest = False

        if not has_empty_coverage:
            # 1. Prefer CoverageReport with same repository_id and same commit_sha.
            report = db.query(CoverageReport).filter(
                CoverageReport.repository_id == repository_id,
                CoverageReport.commit_sha == head_commit_sha
            ).order_by(CoverageReport.created_at.desc()).first()
            if report:
                is_exact = True

            # 2. Try same branch latest
            if not report and branch_name:
                report = db.query(CoverageReport).filter(
                    CoverageReport.repository_id == repository_id,
                    CoverageReport.branch == branch_name
                ).order_by(CoverageReport.created_at.desc()).first()
                if report:
                    is_same_branch = True

            # 3. Try repository latest fallback
            if not report:
                report = db.query(CoverageReport).filter(
                    CoverageReport.repository_id == repository_id
                ).order_by(CoverageReport.created_at.desc()).first()
                if report:
                    is_repo_latest = True

        reasons = []
        coverage_is_missing = False
        coverage_is_stale = False
        coverage_confidence = "UNKNOWN"
        coverage_report_id = None

        if not report:
            coverage_is_missing = True
            coverage_confidence = "UNKNOWN"
            reasons.append("No valid coverage report available.")
        else:
            coverage_report_id = report.id
            # Check freshness
            age = datetime.utcnow() - report.created_at
            if age.days > 14:
                coverage_is_stale = True

            # Determine confidence based on match tier
            if is_exact:
                coverage_confidence = report.confidence_score or "HIGH"
                reasons.append("Using exact commit match coverage report.")
            elif is_same_branch:
                coverage_confidence = "MODERATE"
                reasons.append(f"Using same branch latest coverage report from branch '{branch_name}' (not exact commit match).")
            elif is_repo_latest:
                coverage_confidence = "LOW" if report.confidence_score == "LOW" or coverage_is_stale else "MODERATE"
                reasons.append(f"Using latest repository coverage report {report.commit_sha} as fallback.")

            # Stale coverage degrades confidence
            if coverage_is_stale:
                reasons.append("Coverage report is stale (older than 14 days).")
                # Degrade confidence
                if coverage_confidence == "HIGH":
                    coverage_confidence = "MODERATE"
                elif coverage_confidence == "MODERATE":
                    coverage_confidence = "LOW"

        coverage_links_by_file = {}
        direct_test_mappings = set()
        heuristic_test_mappings = set()
        uncovered_changed_files = set()

        if report:
            # Pre-load all FileTestLink records for the active report to do normalized comparison
            report_links = db.query(FileTestLink).filter(FileTestLink.coverage_report_id == report.id).all()

            for file_path in changed_files:
                norm_file_path = normalize_path(file_path)
                links_db = []
                for link in report_links:
                    norm_link_path = normalize_path(link.file_path)
                    # Match exact normalized or check suffix match
                    if norm_link_path == norm_file_path or (norm_link_path and norm_file_path and (norm_link_path.endswith(norm_file_path) or norm_file_path.endswith(norm_link_path))):
                        links_db.append(link)

                if not links_db:
                    uncovered_changed_files.add(file_path)
                    coverage_links_by_file[file_path] = []
                else:
                    resolved_mappings = []
                    for link in links_db:
                        tc = link.test_case
                        stable_identity = tc.stable_identity if tc else "unknown_test_case"

                        # 6. Trust classification:
                        # DIRECT -> HIGH
                        # HEURISTIC_NAMING -> MODERATE
                        # HEURISTIC_PATH -> LOW
                        if link.mapping_type == "DIRECT":
                            trust = "HIGH"
                            direct_test_mappings.add(stable_identity)
                        elif link.mapping_type == "HEURISTIC_NAMING":
                            trust = "MODERATE"
                            heuristic_test_mappings.add(stable_identity)
                        elif link.mapping_type == "HEURISTIC_PATH":
                            trust = "LOW"
                            heuristic_test_mappings.add(stable_identity)
                        else:
                            trust = "UNKNOWN"

                        resolved_mappings.append(
                            CoverageFileMapping(
                                test_case_id=link.test_case_id,
                                stable_identity=stable_identity,
                                mapping_type=link.mapping_type,
                                confidence_score=trust
                            )
                        )
                    
                    # 9. Sort all mappings deterministically (by stable_identity)
                    resolved_mappings.sort(key=lambda x: x.stable_identity)
                    coverage_links_by_file[file_path] = resolved_mappings
        else:
            for file_path in changed_files:
                uncovered_changed_files.add(file_path)
                coverage_links_by_file[file_path] = []

        # Sort output lists deterministically
        return CoverageEvidenceBundle(
            coverage_report_id=coverage_report_id,
            coverage_confidence=coverage_confidence,
            coverage_is_stale=coverage_is_stale,
            coverage_is_missing=coverage_is_missing,
            coverage_links_by_file=coverage_links_by_file,
            direct_test_mappings=sorted(list(direct_test_mappings)),
            heuristic_test_mappings=sorted(list(heuristic_test_mappings)),
            uncovered_changed_files=sorted(list(uncovered_changed_files)),
            reasons=reasons
        )
