import uuid
import hashlib
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models.test_result import TestCase, TestRun, TestResult
from app.models.artifact import RawArtifact
from app.models.observability import SystemEvent
from app.services.storage import ObjectStorageService
from app.services.junit_parser import SafeJUnitParser, XMLParsingError, OversizedXMLException
from app.constants.evidence import EvidenceSource, EvidenceArtifactType, EvidenceHealthStatus

class TestIngestionService:
    def __init__(self, db: Session):
        self.db = db
        self.storage_service = ObjectStorageService(db)

    def ingest_junit_xml(
        self,
        file_bytes: bytes,
        filename: str,
        repository_id: uuid.UUID,
        commit_sha: Optional[str] = None,
        pull_request_id: Optional[uuid.UUID] = None,
        parent_test_run_id: Optional[uuid.UUID] = None,
        ingestion_reason: str = "ORIGINAL_UPLOAD",
        correlation_id: Optional[str] = None,
        source_correlation_id: Optional[str] = None,
        request_origin: Optional[str] = None,
        evidence_source: Optional[str] = None,
        branch: Optional[str] = None,
        source_context: Optional[str] = None
    ) -> Tuple[TestRun, bool]:
        """
        Coordinates the complete, production-grade All-or-Nothing atomic ingestion workflow.
        Returns the TestRun model and a boolean indicating if it was coalesced (duplicate).
        """
        total_start = time.time()
        correlation_id = correlation_id or str(uuid.uuid4())
        evidence_source = evidence_source or EvidenceSource.MANUAL_UPLOAD.value

        self._emit_event(
            repository_id,
            "junit_upload_received",
            {
                "filename": filename,
                "correlation_id": correlation_id,
                "source_correlation_id": source_correlation_id,
                "request_origin": request_origin
            }
        )

        # 1. Size Guard Check
        max_bytes = settings.MAX_JUNIT_XML_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            self._emit_event(
                repository_id,
                "junit_upload_rejected_size_limit",
                {
                    "filename": filename,
                    "size_bytes": len(file_bytes),
                    "limit_mb": settings.MAX_JUNIT_XML_SIZE_MB,
                    "correlation_id": correlation_id
                }
            )
            raise OversizedXMLException(
                f"Payload too large: JUnit XML size {len(file_bytes) / 1024 / 1024:.2f} MB "
                f"exceeds maximum allowed limit of {settings.MAX_JUNIT_XML_SIZE_MB} MB."
            )

        # 2. File Hash Check (First Idempotency Shield)
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        existing_by_hash = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.file_hash == file_hash
        ).first()

        if existing_by_hash:
            self._emit_event(
                repository_id,
                "junit_duplicate_file_hash_detected",
                {"file_hash": file_hash, "existing_run_id": str(existing_by_hash.id), "correlation_id": correlation_id}
            )
            self._emit_event(
                repository_id,
                "junit_ingestion_coalesced",
                {"test_run_id": str(existing_by_hash.id), "reason": "duplicate_file_hash", "correlation_id": correlation_id}
            )
            return existing_by_hash, True

        # 3. Parse XML securely
        parse_start = time.time()
        xml_str = file_bytes.decode("utf-8", errors="replace")
        parsed_results = SafeJUnitParser.parse_xml(xml_str)
        parsing_duration_ms = (time.time() - parse_start) * 1000

        # 4. Consistency Validation & Telemetry Timing
        consistency_start = time.time()
        consistency_status, consistency_severity, consistency_diagnostics, diagnostics_truncated = (
            self._validate_consistency(parsed_results)
        )
        consistency_duration_ms = (time.time() - consistency_start) * 1000

        # Determine evidence health based on consistency mapping
        if consistency_severity == "CRITICAL":
            evidence_health_status = "INSUFFICIENT"
            consistency_status = "BROKEN"
            self._emit_event(
                repository_id,
                "junit_consistency_broken",
                {"severity": consistency_severity, "correlation_id": correlation_id}
            )
        elif consistency_severity == "IMPORTANT":
            evidence_health_status = "DEGRADED"
            consistency_status = "PARTIALLY_INCONSISTENT"
            self._emit_event(
                repository_id,
                "junit_consistency_warning",
                {"severity": consistency_severity, "correlation_id": correlation_id}
            )
        else:
            evidence_health_status = "HEALTHY"
            consistency_status = "CONSISTENT"

        if diagnostics_truncated:
            self._emit_event(
                repository_id,
                "junit_diagnostics_truncated",
                {"correlation_id": correlation_id}
            )

        # 5. Generate stable Normalized Execution Fingerprint
        norm_start = time.time()
        fingerprint_parts = [
            str(repository_id),
            str(commit_sha or ""),
            str(parsed_results["total_tests"]),
            str(parsed_results["passed_tests"]),
            str(parsed_results["failed_tests"]),
            str(parsed_results["skipped_tests"])
        ]
        # Sort test cases by stable canonical hash and status (independent of duration jitter)
        sorted_cases = sorted(
            [(tc["canonical_identity_hash"], tc["status"]) for tc in parsed_results["test_cases"]],
            key=lambda x: x[0]
        )
        for cid_hash, status in sorted_cases:
            fingerprint_parts.append(f"{cid_hash}:{status}")

        fingerprint_str = "|".join(fingerprint_parts)
        normalized_execution_fingerprint = hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()
        normalization_duration_ms = (time.time() - norm_start) * 1000

        # Check Fingerprint Idempotency
        existing_by_fingerprint = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.normalized_execution_fingerprint == normalized_execution_fingerprint
        ).first()

        if existing_by_fingerprint:
            self._emit_event(
                repository_id,
                "junit_duplicate_execution_fingerprint_detected",
                {"fingerprint": normalized_execution_fingerprint, "existing_run_id": str(existing_by_fingerprint.id), "correlation_id": correlation_id}
            )
            self._emit_event(
                repository_id,
                "junit_ingestion_coalesced",
                {"test_run_id": str(existing_by_fingerprint.id), "reason": "duplicate_fingerprint", "correlation_id": correlation_id}
            )
            return existing_by_fingerprint, True

        # 6. Upload Raw Artifact
        upload_start = time.time()
        raw_artifact = self.storage_service.upload_artifact(
            file_bytes=file_bytes,
            filename=filename,
            repository_id=repository_id,
            correlation_id=correlation_id
        )
        artifact_upload_duration_ms = (time.time() - upload_start) * 1000

        # 7. Database Transaction Commits atomically
        commit_start = time.time()
        
        # Calculate sequence sequence number
        max_seq = self.db.query(func.max(TestRun.execution_sequence_number)).filter(
            TestRun.repository_id == repository_id
        ).scalar()
        execution_sequence_number = (max_seq or 0) + 1

        # Pre-assign metrics
        run_status = "SUCCESS" if parsed_results["failed_tests"] == 0 else "FAILURE"

        # Construct diagnostics timing telemetry object
        total_ingestion_duration_ms = (time.time() - total_start) * 1000 + 1.0 # Guarantee non-zero
        ingestion_diagnostics = {
            "timing_telemetry_ms": {
                "artifact_upload_duration_ms": artifact_upload_duration_ms,
                "parsing_duration_ms": parsing_duration_ms,
                "normalization_duration_ms": normalization_duration_ms,
                "consistency_validation_duration_ms": consistency_duration_ms,
                "db_commit_duration_ms": 0.0, # Filled after commit succeeds
                "total_ingestion_duration_ms": total_ingestion_duration_ms
            },
            "warnings": parsed_results["diagnostics"]["warnings"][:20],
            "correlation_id": correlation_id,
            "source_correlation_id": source_correlation_id,
            "request_origin": request_origin,
            "branch": branch,
            "source_context": source_context
        }

        try:
            # Atomic creation within open transaction block
            # First insert TestCase stubs per repository scoped constraint
            case_mappings = {}
            for tc in parsed_results["test_cases"]:
                # Scoped query
                test_case = self.db.query(TestCase).filter(
                    TestCase.repository_id == repository_id,
                    TestCase.canonical_identity_hash == tc["canonical_identity_hash"]
                ).first()

                if not test_case:
                    test_case = TestCase(
                        id=uuid.uuid4(),
                        repository_id=repository_id,
                        suite_name=tc["suite_name"],
                        test_name=tc["test_name"],
                        stable_identity=tc["stable_identity"],
                        raw_test_name=tc["raw_test_name"],
                        normalized_test_name=tc["normalized_test_name"],
                        normalized_identity_strategy=tc["normalized_identity_strategy"],
                        framework_name=tc["framework_name"],
                        framework_version=tc["framework_version"],
                        identity_normalization_version=tc["identity_normalization_version"],
                        canonical_identity_hash=tc["canonical_identity_hash"],
                        previous_identity_hash=None,
                        identity_lineage_root_hash=tc["canonical_identity_hash"],
                        identity_version=1,
                        identity_resolution_strategy="EXACT",
                        created_at=datetime.utcnow()
                    )
                    self.db.add(test_case)
                    self.db.flush()
                
                case_mappings[tc["canonical_identity_hash"]] = test_case.id

            test_run = TestRun(
                id=uuid.uuid4(),
                repository_id=repository_id,
                commit_sha=commit_sha,
                pull_request_id=pull_request_id,
                raw_artifact_id=raw_artifact.id,
                parent_test_run_id=parent_test_run_id,
                evidence_source=evidence_source,
                evidence_artifact_type=EvidenceArtifactType.JUNIT_XML.value,
                ingestion_reason=ingestion_reason,
                correlation_id=correlation_id,
                source_correlation_id=source_correlation_id,
                request_origin=request_origin,
                file_hash=file_hash,
                normalized_execution_fingerprint=normalized_execution_fingerprint,
                parser_version="junit_parser.v1",
                parser_support_status="ACTIVE",
                normalization_schema_version="junit_result.v1",
                replay_verification_status="NOT_VERIFIED",
                retention_class="KEEP_FOREVER" if run_status == "FAILURE" else "ARCHIVE",
                retention_locked=True if run_status == "FAILURE" else False,
                retention_lock_reason="AUDIT_REFERENCED" if run_status == "FAILURE" else None,
                status=run_status,
                evidence_health_status=evidence_health_status,
                consistency_status=consistency_status,
                consistency_severity=consistency_severity,
                total_tests=parsed_results["total_tests"],
                passed_tests=parsed_results["passed_tests"],
                failed_tests=parsed_results["failed_tests"],
                skipped_tests=parsed_results["skipped_tests"],
                duration=parsed_results["duration"],
                ingestion_diagnostics=ingestion_diagnostics,
                consistency_diagnostics=consistency_diagnostics,
                diagnostics_truncated=diagnostics_truncated,
                execution_sequence_number=execution_sequence_number,
                created_at=datetime.utcnow()
            )
            self.db.add(test_run)
            self.db.flush()

            # Create TestResults
            for tc in parsed_results["test_cases"]:
                test_result = TestResult(
                    id=uuid.uuid4(),
                    test_run_id=test_run.id,
                    test_case_id=case_mappings[tc["canonical_identity_hash"]],
                    status=tc["status"],
                    duration=tc["duration"],
                    failure_message=tc["failure_message"],
                    stack_trace=tc["stack_trace"],
                    stack_trace_redaction_status="NOT_REDACTED",
                    encryption_status="PLAINTEXT",
                    created_at=datetime.utcnow()
                )
                self.db.add(test_result)
            self.db.flush()
            
            # Record failures for covered modules in ModuleRiskProfile
            failed_test_case_ids = [
                case_mappings[tc["canonical_identity_hash"]]
                for tc in parsed_results["test_cases"]
                if tc.get("status") and tc["status"].lower() in ("failed", "failure")
            ]
            if failed_test_case_ids:
                from app.models.coverage import FileTestLink
                from app.models.test_coverage_link import TestCoverageLink
                from app.repositories.module_risk_profile import ModuleRiskProfileRepository
                
                profile_repo = ModuleRiskProfileRepository(self.db)
                
                # Fetch unique file paths via FileTestLink
                ftl_files = self.db.query(FileTestLink.file_path).filter(
                    FileTestLink.test_case_id.in_(failed_test_case_ids)
                ).distinct().all()
                
                # Fetch unique file paths via TestCoverageLink
                failed_identities = [
                    tc["stable_identity"]
                    for tc in parsed_results["test_cases"]
                    if tc.get("status") and tc["status"].lower() in ("failed", "failure")
                ]
                tcl_files = self.db.query(TestCoverageLink.file_path).filter(
                    TestCoverageLink.repository_id == repository_id,
                    TestCoverageLink.test_identifier.in_(failed_identities)
                ).distinct().all()
                
                unique_files = {f[0] for f in ftl_files + tcl_files}
                for file_path in unique_files:
                    profile_repo.record_failure(repository_id, file_path)

            self.db.flush()

            
            # Record final commit timing details inside diagnostics
            db_commit_duration_ms = (time.time() - commit_start) * 1000
            ingestion_diagnostics["timing_telemetry_ms"]["db_commit_duration_ms"] = db_commit_duration_ms
            ingestion_diagnostics["timing_telemetry_ms"]["total_ingestion_duration_ms"] += db_commit_duration_ms
            test_run.ingestion_diagnostics = ingestion_diagnostics

            self.db.commit()

            self._emit_event(
                repository_id,
                "junit_ingestion_committed",
                {"test_run_id": str(test_run.id), "correlation_id": correlation_id}
            )
            return test_run, False

        except IntegrityError as e:
            self.db.rollback()
            # If parallel inserts race, query the database safely
            existing_by_race = self.db.query(TestRun).filter(
                TestRun.repository_id == repository_id,
                TestRun.normalized_execution_fingerprint == normalized_execution_fingerprint
            ).first()

            if existing_by_race:
                self._emit_event(
                    repository_id,
                    "junit_execution_fingerprint_collision_detected",
                    {"fingerprint": normalized_execution_fingerprint, "correlation_id": correlation_id}
                )
                self._emit_event(
                    repository_id,
                    "junit_ingestion_coalesced",
                    {"test_run_id": str(existing_by_race.id), "reason": "concurrency_race", "correlation_id": correlation_id}
                )
                return existing_by_race, True
            
            self._emit_event(
                repository_id,
                "junit_ingestion_rolled_back",
                {"error": str(e), "correlation_id": correlation_id}
            )
            raise e
        except Exception as e:
            self.db.rollback()
            self._emit_event(
                repository_id,
                "junit_ingestion_rolled_back",
                {"error": str(e), "correlation_id": correlation_id}
            )
            raise e

    def _validate_consistency(self, results: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any], bool]:
        """
        Validates parsed JUnit XML entries for structural and execution consistency.
        Uses diagnostic bounding rules and aggregates/truncates warnings safely.
        """
        severity = "NONE"
        diagnostics = {
            "duplicate_stable_identities": [],
            "conflicting_statuses": [],
            "negative_or_impossible_durations": [],
            "declared_vs_parsed_mismatches": [],
            "missing_suite_names": []
        }
        
        # Keep count trackers to avoid JSONB explosion
        counts = {
            "duplicate_stable_identities": 0,
            "conflicting_statuses": 0,
            "negative_or_impossible_durations": 0,
            "declared_vs_parsed_mismatches": 0,
            "missing_suite_names": 0
        }

        # Check declared count vs parsed count
        declared_tests = results.get("xml_declared_tests")
        if declared_tests is not None and declared_tests != results["total_tests"]:
            severity = "CRITICAL"
            counts["declared_vs_parsed_mismatches"] += 1
            diagnostics["declared_vs_parsed_mismatches"].append({
                "message": f"XML declared count '{declared_tests}' mismatches parsed count '{results['total_tests']}'"
            })

        # Scan for duplicate stable identities, negative durations, or conflicting statuses
        case_map = {}
        for tc in results["test_cases"]:
            stable_id = tc["stable_identity"]
            duration = tc["duration"]
            status = tc["status"]
            suite_name = tc["suite_name"]

            # Duration consistency check
            if duration < 0.0 or duration > 86400.0:
                severity = max_severity(severity, "IMPORTANT")
                counts["negative_or_impossible_durations"] += 1
                if len(diagnostics["negative_or_impossible_durations"]) < 20:
                    diagnostics["negative_or_impossible_durations"].append({
                        "stable_identity": stable_id,
                        "duration": duration
                    })

            # Missing suite name check
            if suite_name.startswith("suite_") and suite_name != "suite_0":
                # Stubs generated by parser fallback
                severity = max_severity(severity, "IMPORTANT")
                counts["missing_suite_names"] += 1
                if len(diagnostics["missing_suite_names"]) < 20:
                    diagnostics["missing_suite_names"].append({
                        "stable_identity": stable_id
                    })

            if stable_id in case_map:
                # Duplicate case identity detected
                counts["duplicate_stable_identities"] += 1
                if case_map[stable_id]["status"] != status:
                    # Conflicting status! CRITICAL
                    severity = max_severity(severity, "CRITICAL")
                    counts["conflicting_statuses"] += 1
                    if len(diagnostics["conflicting_statuses"]) < 20:
                        diagnostics["conflicting_statuses"].append({
                            "stable_identity": stable_id,
                            "statuses": [case_map[stable_id]["status"], status]
                        })
                else:
                    # Just duplicate, IMPORTANT
                    severity = max_severity(severity, "IMPORTANT")
                    if len(diagnostics["duplicate_stable_identities"]) < 20:
                        diagnostics["duplicate_stable_identities"].append({
                            "stable_identity": stable_id
                        })
            else:
                case_map[stable_id] = {"status": status}

        # Check if diagnostic limits are breached (diagnostics bounding)
        truncated = False
        for key in list(diagnostics.keys()):
            if counts[key] > 20:
                truncated = True
            diagnostics[f"{key}_summary_count"] = counts[key]

        consistency_status = "CONSISTENT"
        if severity == "CRITICAL":
            consistency_status = "BROKEN"
        elif severity == "IMPORTANT":
            consistency_status = "PARTIALLY_INCONSISTENT"

        return consistency_status, severity, diagnostics, truncated

    def _emit_event(self, repository_id: uuid.UUID, event_type: str, payload: Dict[str, Any]):
        """Helper to create and persist a SystemEvent timeline log entry in a dedicated session."""
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            event = SystemEvent(
                id=uuid.uuid4(),
                entity_type="repository",
                entity_id=str(repository_id),
                event_type=event_type,
                payload=payload,
                created_at=datetime.utcnow()
            )
            db.add(event)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

def max_severity(curr: str, proposed: str) -> str:
    """Helper to pick highest severity."""
    ranks = {"NONE": 0, "SUPPORTING": 1, "IMPORTANT": 2, "CRITICAL": 3}
    curr_rank = ranks.get(curr, 0)
    prop_rank = ranks.get(proposed, 0)
    return proposed if prop_rank > curr_rank else curr
