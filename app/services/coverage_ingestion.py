import uuid
import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.config import settings
from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.test_result import TestCase
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.repository import Repository
from app.services.lcov_parser import SafeLCOVParser
from app.services.cobertura_parser import SafeCoberturaParser, CoberturaParsingError
from app.services.storage import ObjectStorageService
from app.services.coverage_link_expander import CoverageLinkExpander
from app.constants.evidence import EvidenceSource, EvidenceArtifactType, EvidenceHealthStatus, CoverageLevel

logger = logging.getLogger(__name__)

class CoverageIngestionError(ValueError):
    """Custom exception raised when coverage ingestion fails validation."""
    pass

class CoverageIngestionService:
    @staticmethod
    def is_fake_coverage_report(report: CoverageReport) -> bool:
        unknown_sha = not report.commit_sha or str(report.commit_sha).strip().lower() in {"unknown", "null", "none"}
        empty_metrics = (
            not report.files_total
            and not report.total_lines
            and not report.covered_lines_total
        )
        return (
            report.source == EvidenceSource.MANUAL_UPLOAD.value
            and unknown_sha
            and report.file_hash == "dummy_hash_for_direct_ac"
            and empty_metrics
        )

    @staticmethod
    def cleanup_fake_coverage_artifacts(db: Session, repository_id: uuid.UUID) -> dict:
        """Remove only legacy AC-ID pseudo-coverage and empty dummy coverage reports."""
        direct_ac_links = db.query(FileTestLink).join(
            CoverageReport,
            FileTestLink.coverage_report_id == CoverageReport.id,
        ).filter(
            CoverageReport.repository_id == repository_id,
            FileTestLink.file_path.like("AC-%"),
            FileTestLink.mapping_type == "DIRECT_AC_ID",
        ).all()
        for link in direct_ac_links:
            db.delete(link)

        reports = db.query(CoverageReport).filter(
            CoverageReport.repository_id == repository_id,
        ).all()
        fake_reports = [report for report in reports if CoverageIngestionService.is_fake_coverage_report(report)]
        for report in fake_reports:
            db.delete(report)

        if direct_ac_links or fake_reports:
            db.flush()

        return {
            "fake_coverage_reports_removed": len(fake_reports),
            "fake_file_test_links_removed": len(direct_ac_links),
        }

    @staticmethod
    def ingest_coverage(
        db: Session,
        repository_id: uuid.UUID,
        commit_sha: Optional[str],
        payload_bytes: bytes,
        file_name: str,
        pull_request_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
        evidence_source: Optional[str] = None,
        branch: Optional[str] = None,
        source_context: Optional[str] = None,
        current_pr_head_sha: Optional[str] = None,
        commit_sha_source: Optional[str] = None,
        sha_mismatch: bool = False,
        is_current: bool = False,
        coverage_uploaded_at: Optional[datetime] = None
    ) -> CoverageReport:
        """
        Coordinates the LCOV ingestion pipeline:
        1. Validates upload size limits.
        2. Idempotency guard: checks if a report with matching file hash already exists.
        3. Uploads the raw LCOV payload to object storage.
        4. Parses LCOV into file-level records.
        5. Computes direct and fallback (naming, path similarity) file-to-test mappings.
        6. Evaluates mapping quality & sparse coverage to assign Coverage Confidence (HIGH, MODERATE, LOW).
        7. Commits the transaction and returns the report.
        """
        evidence_source = evidence_source or EvidenceSource.MANUAL_UPLOAD.value
        # 1. Size Validation
        size_mb = len(payload_bytes) / (1024 * 1024)
        if size_mb > settings.MAX_LCOV_SIZE_MB:
            raise CoverageIngestionError(
                f"LCOV upload size ({size_mb:.2f} MB) exceeds maximum allowed limit of {settings.MAX_LCOV_SIZE_MB} MB."
            )

        # 2. Idempotency Guard
        file_hash = hashlib.sha256(payload_bytes).hexdigest()
        existing_report = (
            db.query(CoverageReport)
            .filter(
                CoverageReport.repository_id == repository_id,
                CoverageReport.file_hash == file_hash
            )
            .first()
        )
        if existing_report:
            # Replay idempotent result
            return existing_report

        # 3. Store raw report in Object Storage
        storage_service = ObjectStorageService(db)
        raw_artifact = storage_service.upload_coverage_report(
            file_bytes=payload_bytes,
            filename=file_name,
            repository_id=repository_id,
            correlation_id=correlation_id
        )

        # 4. Safe Parsing
        try:
            content_str = payload_bytes.decode("utf-8", errors="replace").strip()
        except Exception as e:
            raise CoverageIngestionError(f"Failed to decode payload bytes: {str(e)}") from e

        # Get repository to get its workspace_id
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise CoverageIngestionError(f"Repository {repository_id} not found.")
        workspace_id = repo.workspace_id

        is_cobertura = content_str.startswith("<?xml") or content_str.startswith("<coverage") or file_name.endswith(".xml")
        
        overall_branch_ratio = None
        if is_cobertura:
            coverage_format = "COBERTURA"
            try:
                parse_res = SafeCoberturaParser.parse_cobertura(content_str)
                parsed_files = parse_res["files"]
                overall_branch_ratio = parse_res["overall_branch_coverage_ratio"]
            except Exception as e:
                raise CoverageIngestionError(f"Malformed or unsafe COBERTURA report payload: {str(e)}") from e
        else:
            coverage_format = "LCOV"
            try:
                parsed_files = SafeLCOVParser.parse_lcov(content_str)
                # Aggregate overall branch coverage ratio from LCOV files if present
                total_brf = 0
                total_brh = 0
                for pf in parsed_files:
                    if pf.get("brf") is not None and pf.get("brh") is not None:
                        total_brf += pf["brf"]
                        total_brh += pf["brh"]
                if total_brf > 0:
                    overall_branch_ratio = total_brh / total_brf
            except Exception as e:
                raise CoverageIngestionError(f"Malformed or unsafe LCOV report payload: {str(e)}") from e

        # Validate that coverage parsing produced actual file records
        if not parsed_files or len(parsed_files) == 0:
            raise CoverageIngestionError(
                "Coverage file uploaded but no file coverage records were parsed. "
                "The coverage artifact may be invalid, empty, or in an unsupported format."
            )

        # Calculate overall counts to construct the parent report
        total_lines = 0
        total_covered = 0
        total_uncovered = 0
        for pf in parsed_files:
            total_lines += pf["total_lines_count"]
            total_covered += pf["covered_lines_count"]
            total_uncovered += pf["uncovered_lines_count"]

        overall_pct = (total_covered / total_lines) if total_lines > 0 else 0.0

        logger.info("[COVERAGE INGESTION] Parsed coverage summary", {
            "files_total": len(parsed_files),
            "total_lines": total_lines,
            "total_covered": total_covered,
            "total_uncovered": total_uncovered,
            "overall_coverage_pct": overall_pct,
            "coverage_format": coverage_format,
        })

        # Detect coverage level honestly
        # LCOV aggregate coverage is RUN_LEVEL by default
        # Only TEST_CASE_LEVEL if artifact provides per-test data with test_name context
        coverage_level = CoverageLevel.RUN_LEVEL
        has_per_test_data = any(pf.get("test_name") for pf in parsed_files)
        if has_per_test_data:
            coverage_level = CoverageLevel.TEST_CASE_LEVEL

        # Construct and flush CoverageReport
        report = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repository_id,
            workspace_id=workspace_id,
            commit_sha=commit_sha,
            pull_request_id=pull_request_id,
            current_pr_head_sha=current_pr_head_sha,
            commit_sha_source=commit_sha_source or "MANUAL",
            sha_mismatch=sha_mismatch,
            is_current=is_current,
            coverage_uploaded_at=coverage_uploaded_at or datetime.utcnow(),
            raw_artifact_id=raw_artifact.id,
            
            # Final Contract Fields
            format=coverage_format,
            source=evidence_source,
            branch=branch,
            coverage_level=coverage_level,
            files_total=len(parsed_files),
            covered_lines_total=total_covered,
            uncovered_lines_total=total_uncovered,
            total_lines=total_lines,
            line_coverage_ratio=overall_pct,
            branch_coverage_ratio=overall_branch_ratio,
            coverage_confidence="PENDING",
            evidence_health_status="HEALTHY",
            parser_version="cobertura_parser.v1" if coverage_format == "COBERTURA" else "lcov_parser.v1",
            normalization_schema_version="cobertura_result.v1" if coverage_format == "COBERTURA" else "lcoc_result.v1",

            # Legacy / backward compatibility
            evidence_source=evidence_source,
            evidence_artifact_type=coverage_format,
            correlation_id=correlation_id,
            file_hash=file_hash,
            overall_coverage_pct=overall_pct,
            covered_lines_count=total_covered,
            uncovered_lines_count=total_uncovered,
            confidence_score="PENDING", # Decided after mappings are built
            confidence_logic="Initializing..."
        )
        db.add(report)
        db.flush()

        # Build granular CoverageFileEntry records
        file_entries: List[CoverageFileEntry] = []
        for pf in parsed_files:
            fe_total = pf["total_lines_count"]
            fe_covered = pf["covered_lines_count"]
            fe_ratio = (fe_covered / fe_total) if fe_total > 0 else 0.0

            file_entry = CoverageFileEntry(
                id=uuid.uuid4(),
                coverage_report_id=report.id,
                repository_id=repository_id,
                file_path=pf["file_path"],
                covered_lines=pf["covered_lines"],
                uncovered_lines=pf["uncovered_lines"],
                
                # Final Contract Fields
                total_lines=fe_total,
                line_coverage_ratio=fe_ratio,
                branch_coverage_ratio=pf.get("branch_coverage_ratio"),
                functions_covered=pf.get("functions_covered"),
                functions_total=pf.get("functions_total"),

                # Legacy / backward compatibility
                total_lines_count=fe_total,
                covered_lines_count=fe_covered,
                uncovered_lines_count=pf["uncovered_lines_count"]
            )
            db.add(file_entry)
            file_entries.append(file_entry)
        db.flush()

        # 5. Build file-to-test mappings
        test_cases = db.query(TestCase).filter(TestCase.repository_id == repository_id).all()
        mapped_files_with_links = set()
        test_links_count = 0

        # Subdirectory blacklist for path similarity heuristic
        BLACKLIST_DIRS = {"", ".", "..", "app", "src", "lib", "tests", "test", "build", "dist", "utils", "helpers"}

        for entry in file_entries:
            file_path = entry.file_path
            filename_only = file_path.split("/")[-1]
            stem = filename_only.split(".")[0].lower() if "." in filename_only else filename_only.lower()
            
            # Extract parent directory for path similarity
            parent_dir = ""
            path_parts = [p for p in file_path.split("/") if p]
            if len(path_parts) > 1:
                parent_dir = path_parts[-2].lower()

            direct_mapped = False
            
            # Try Direct Mappings (Matching LCOV Test Name Context if present)
            # Find parsed LCOV record details to check test_name
            matching_parsed = next((pf for pf in parsed_files if pf["file_path"] == file_path), None)
            if matching_parsed and matching_parsed.get("test_name"):
                lcov_test_name = matching_parsed["test_name"].lower()
                for tc in test_cases:
                    tc_stable = tc.stable_identity.lower()
                    tc_name = tc.test_name.lower()
                    tc_suite = tc.suite_name.lower()
                    
                    if (lcov_test_name == tc_stable or 
                        lcov_test_name == tc_name or 
                        lcov_test_name == tc_suite):
                        
                        link = FileTestLink(
                            id=uuid.uuid4(),
                            coverage_report_id=report.id,
                            file_path=file_path,
                            test_case_id=tc.id,
                            mapping_type="DIRECT",
                            confidence_score="HIGH"
                        )
                        db.add(link)
                        mapped_files_with_links.add(file_path)
                        test_links_count += 1
                        direct_mapped = True

            if direct_mapped:
                continue

            # Try Naming Heuristics Fallback
            naming_mapped = False
            if len(stem) >= 3:
                for tc in test_cases:
                    tc_stable = tc.stable_identity.lower()
                    tc_suite = tc.suite_name.lower()
                    
                    # Naming matches: e.g. suite_name contains "test_auth" or "auth_test" or starts with test_auth
                    if (f"test_{stem}" in tc_stable or 
                        f"{stem}_test" in tc_stable or 
                        f"test_{stem}" in tc_suite or 
                        f"{stem}_test" in tc_suite):
                        
                        link = FileTestLink(
                            id=uuid.uuid4(),
                            coverage_report_id=report.id,
                            file_path=file_path,
                            test_case_id=tc.id,
                            mapping_type="HEURISTIC_NAMING",
                            confidence_score="MODERATE"
                        )
                        db.add(link)
                        mapped_files_with_links.add(file_path)
                        test_links_count += 1
                        naming_mapped = True

            if naming_mapped:
                continue

            # Try Path Similarity Fallback
            if parent_dir and parent_dir not in BLACKLIST_DIRS:
                for tc in test_cases:
                    tc_stable = tc.stable_identity.lower()
                    tc_suite = tc.suite_name.lower()
                    
                    if (parent_dir in tc_stable or parent_dir in tc_suite):
                        link = FileTestLink(
                            id=uuid.uuid4(),
                            coverage_report_id=report.id,
                            file_path=file_path,
                            test_case_id=tc.id,
                            mapping_type="HEURISTIC_PATH",
                            confidence_score="LOW"
                        )
                        db.add(link)
                        mapped_files_with_links.add(file_path)
                        test_links_count += 1

        db.flush()

        # 5b. Expand the persistent TestCoverageLink knowledge graph.
        #
        # Coverage evidence is authoritative — these links will be stronger than
        # any heuristic-derived links that may already exist for the same edge.
        # Expansion is wrapped so a failure never rolls back the ingestion.
        try:
            _expansion = CoverageLinkExpander.expand_from_report(
                db=db,
                workspace_id=workspace_id,
                repository_id=repository_id,
                coverage_report_id=report.id,
                observed_at=report.created_at,
            )
            if not _expansion.success:
                _log = logging.getLogger(__name__)
                _log.warning(
                    "CoverageLinkExpander encountered errors for report %s: %s",
                    report.id,
                    _expansion.errors,
                )
        except Exception as _exp_exc:
            logging.getLogger(__name__).error(
                "CoverageLinkExpander raised an unexpected exception for report %s: %s",
                report.id,
                _exp_exc,
            )

        confidence_score = "LOW"
        confidence_logic = ""

        # Determine metadata presence
        commit_sha_provided = bool(commit_sha and commit_sha not in ("unknown_sha", "unknown", ""))
        branch_provided = bool(branch and branch not in ("unknown", "unknown_branch", ""))

        # Fetch PR if applicable
        pr = None
        if pull_request_id:
            pr = db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()

        path_mapping_uncertain = False
        mapped_ratio = 1.0
        avg_changed_cov = 1.0

        # Initialize changed file tracking
        changed_paths = []
        matched_changed_paths = []

        if pr:
            # Evaluate using Pull Request changed files
            changed_files = (
                db.query(PullRequestChangedFile)
                .filter(
                    PullRequestChangedFile.pull_request_id == pull_request_id,
                    PullRequestChangedFile.status != "removed"
                )
                .all()
            )

            # Filter changed files to those that exist in the LCOV report
            changed_paths = [cf.file_path for cf in changed_files]

            logger.info("[COVERAGE INGESTION] PR changed files", {
                "pr_id": str(pull_request_id),
                "changed_files_total": len(changed_paths),
                "changed_files_sample": changed_paths[:5] if changed_paths else [],
            })

            # Map changed files to normalized entries we have
            for path in changed_paths:
                # Find matching file entry (handle fuzzy slash comparisons)
                norm_p = SafeLCOVParser.normalize_path(path)
                matching_entry = next((fe for fe in file_entries if fe.file_path == norm_p), None)
                if matching_entry:
                    matched_changed_paths.append(norm_p)

            logger.info("[COVERAGE INGESTION] Changed file matching", {
                "matched_changed_paths_count": len(matched_changed_paths),
                "matched_changed_paths_sample": matched_changed_paths[:5] if matched_changed_paths else [],
            })

            if not matched_changed_paths and changed_paths:
                path_mapping_uncertain = True
                mapped_ratio = 0.0
                avg_changed_cov = 0.0
            elif changed_paths:
                # Calculate metrics for changed files
                mapped_changed_count = sum(1 for p in changed_paths if SafeLCOVParser.normalize_path(p) in mapped_files_with_links)
                mapped_ratio = mapped_changed_count / len(changed_paths)

                # Calculate average coverage of matched changed files
                total_cov_sum = 0.0
                for path in matched_changed_paths:
                    fe = next(f for f in file_entries if f.file_path == path)
                    fe_cov = (fe.covered_lines_count / fe.total_lines_count) if fe.total_lines_count > 0 else 0.0
                    total_cov_sum += fe_cov
                avg_changed_cov = total_cov_sum / len(matched_changed_paths)
        else:
            # Standard commits / no Pull Request: evaluate across all files in LCOV
            all_files_count = len(file_entries)
            if all_files_count > 0:
                mapped_ratio = len(mapped_files_with_links) / all_files_count
            else:
                mapped_ratio = 0.0

        # Persist changed-file coverage context on the report for readiness and UI.
        if pr and changed_paths:
            report.changed_files_total = len(changed_paths)
            report.changed_files_with_coverage = len(matched_changed_paths)
            report.changed_files_without_coverage = max(0, len(changed_paths) - len(matched_changed_paths))
        else:
            report.changed_files_total = 0
            report.changed_files_with_coverage = 0
            report.changed_files_without_coverage = 0

        # Deterministic Coverage Confidence Scoring Engine
        # MVP confidence calculation rules
        evidence_health_status = report.evidence_health_status

        if evidence_health_status != "HEALTHY":
            confidence_score = "INVALID"
            confidence_logic = f"Invalid: parser health is {evidence_health_status}."
        elif len(file_entries) == 0 or total_lines == 0:
            confidence_score = "LOW"
            confidence_logic = "Low confidence: Coverage report is empty (no source files or statements found)."
        elif total_lines < 50:
            confidence_score = "LOW"
            confidence_logic = f"Low confidence: Very small coverage file (total lines {total_lines} < 50)."
        elif not commit_sha_provided and not branch_provided:
            confidence_score = "LOW"
            confidence_logic = "Low confidence: Missing important metadata (both commit_sha and branch are missing)."
        elif path_mapping_uncertain:
            confidence_score = "LOW"
            confidence_logic = "Low confidence: No changed files from the Pull Request exist in the coverage report (path mapping uncertain)."
        elif test_links_count == 0:
            confidence_score = "LOW"
            confidence_logic = "Low confidence: Zero test case mappings could be resolved."
        elif pr and (mapped_ratio < 0.5 or avg_changed_cov < 0.3 or overall_pct < 0.3):
            confidence_score = "LOW"
            confidence_logic = (
                f"Low confidence: Changed files mapped ratio is {mapped_ratio * 100:.1f}%, "
                f"average changed files coverage is {avg_changed_cov * 100:.1f}%, "
                f"overall coverage is {overall_pct * 100:.1f}% (sparse coverage or missing mappings)."
            )
        elif not pr and (mapped_ratio < 0.5 or overall_pct < 0.3):
            confidence_score = "LOW"
            confidence_logic = (
                f"Low confidence: Mapped files ratio is {mapped_ratio * 100:.1f}%, "
                f"overall coverage is {overall_pct * 100:.1f}%."
            )
        elif (
            evidence_health_status == "HEALTHY"
            and len(file_entries) > 0
            and total_lines >= 50
            and commit_sha_provided
            and branch_provided
            and (not pr or (mapped_ratio >= 0.8 and avg_changed_cov >= 0.5 and overall_pct >= 0.5))
            and (pr or (mapped_ratio >= 0.8 and overall_pct >= 0.5))
        ):
            confidence_score = "HIGH"
            if pr:
                confidence_logic = (
                    f"High confidence: Most changed files mapped ({mapped_ratio * 100:.1f}%), "
                    f"average changed files coverage is {avg_changed_cov * 100:.1f}%, "
                    f"overall coverage is {overall_pct * 100:.1f}%."
                )
            else:
                confidence_logic = (
                    f"High confidence: {mapped_ratio * 100:.1f}% of files mapped, "
                    f"overall coverage is {overall_pct * 100:.1f}%."
                )
        else:
            confidence_score = "MODERATE"
            if pr:
                confidence_logic = (
                    f"Moderate confidence: Changed files mapped ratio is {mapped_ratio * 100:.1f}%, "
                    f"average changed files coverage is {avg_changed_cov * 100:.1f}%, "
                    f"overall coverage is {overall_pct * 100:.1f}%."
                )
            else:
                confidence_logic = (
                    f"Moderate confidence: {mapped_ratio * 100:.1f}% of files mapped, "
                    f"overall coverage is {overall_pct * 100:.1f}%."
                )

        # Update the report and write
        report.confidence_score = confidence_score
        if source_context:
            confidence_logic = f"[{source_context}] {confidence_logic}"
        report.confidence_logic = confidence_logic
        report.coverage_confidence = confidence_score
        # The PR-current signal is only meaningful when the coverage SHA matches the selected PR.
        report.current_pr_coverage_confidence = confidence_score if report.is_current else "NONE"
        db.add(report)
        db.flush()

        # Recompute recommendation run snapshots if coverage was linked to a PR
        # This ensures coverageStatus reflects the new coverage-to-test mappings
        if pull_request_id:
            try:
                from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService
                graph_service = RequirementEvidenceGraphService(db)
                updated_count = graph_service.recompute_snapshot_for_pr(
                    repository_id=str(repository_id),
                    pull_request_id=str(pull_request_id)
                )
                if updated_count > 0:
                    logger.info(f"Recomputed {updated_count} recommendation run snapshots after coverage ingestion")
            except Exception as e:
                logger.warning(f"Failed to recompute snapshots after coverage ingestion: {e}")

        return report
