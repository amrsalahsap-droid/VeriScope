"""
app/services/pilot_reporting_hardened_service.py
=================================================

Production-hardened pilot reporting service with:
- Idempotent report generation (duplicate prevention)
- Reporting drift detection (aggregation, snapshot, lineage, runtime)
- Conservative fallback behavior (explicit limitations, no silent estimation)
- Replay-safe regeneration (from snapshots, lineage, outcomes)
- Minimal observability (latency, failures, mismatches, warnings)
- Recovery tooling (replay, rebuild, repair)
"""

import uuid
import json
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.pilot import (
    PilotReportSnapshot,
    PilotWorkspaceProfile,
    PilotRepositoryEnrollment,
    PilotReport,
    PilotSnapshot
)
from app.models.repository import Repository
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationTestOutcome,
    RecommendationEngineerFeedback
)
from app.models.fragility_pattern import FragilityPattern
from app.services.pilot_metrics_aggregator import PilotMetricsAggregator
from app.services.regression_savings_calculator import RegressionSavingsCalculator
from app.services.fragility_pilot_summary_builder import FragilityPilotSummaryBuilder
from app.services.escaped_defect_safety_analyzer import EscapedDefectSafetyAnalyzer
from app.services.pilot_roi_snapshot_generator import PilotROISnapshotGenerator
from app.services.pilot_report_generator import PilotReportGenerator
from app.services.recommendation_ignore_detector import RecommendationIgnoreDetector

logger = logging.getLogger("veriscope.pilot_reporting_hardened")


class DriftType(Enum):
    """Types of reporting drift that can be detected."""
    AGGREGATION_MISMATCH = "aggregation_mismatch"
    SNAPSHOT_INCONSISTENCY = "snapshot_inconsistency"
    STALE_LINEAGE = "stale_lineage"
    MISSING_RUNTIME_DATA = "missing_runtime_data"
    HASH_MISMATCH = "hash_mismatch"
    SUB_HASH_MISMATCH = "sub_hash_mismatch"


class RecoveryAction(Enum):
    """Available recovery actions for stale or corrupted reporting state."""
    REPLAY_REPORT = "replay_report"
    REBUILD_SNAPSHOT = "rebuild_snapshot"
    REPAIR_AGGREGATION = "repair_aggregation"


@dataclass
class GenerationMetrics:
    """Observability metrics for report generation."""
    generation_latency_ms: float = 0.0
    aggregation_latency_ms: float = 0.0
    snapshot_latency_ms: float = 0.0
    db_query_count: int = 0
    missing_evidence_warnings: List[str] = field(default_factory=list)
    aggregation_failures: List[str] = field(default_factory=list)


@dataclass
class DriftReport:
    """Detailed drift detection report."""
    drift_detected: bool = False
    drift_types: List[DriftType] = field(default_factory=list)
    stored_hash: Optional[str] = None
    computed_hash: Optional[str] = None
    aggregation_differences: Dict[str, Any] = field(default_factory=dict)
    lineage_gaps: List[str] = field(default_factory=list)
    missing_runtime_count: int = 0
    sub_hash_mismatches: Dict[str, bool] = field(default_factory=dict)


@dataclass
class HardenedReportResult:
    """Result of hardened report generation."""
    snapshot: Optional[PilotReportSnapshot] = None
    is_new: bool = False  # True if newly created, False if existing
    generation_metrics: GenerationMetrics = field(default_factory=GenerationMetrics)
    drift_report: Optional[DriftReport] = None
    limitations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class PilotReportingHardenedService:
    """
    Production-hardened pilot reporting service.
    
    Provides idempotent, drift-aware, replay-safe pilot report generation
    with comprehensive observability and recovery capabilities.
    """

    # Thresholds for conservative reporting
    MIN_RUNS_FOR_CONFIDENCE = 5
    MIN_OUTCOMES_FOR_CONFIDENCE = 5
    MAX_ACCEPTABLE_MISSING_RUNTIME_RATIO = 0.3  # 30%

    @classmethod
    def generate_hardened_report(
        cls,
        db: Session,
        pilot_profile_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime,
        is_incident_lineage_complete: bool = True,
        force_regenerate: bool = False
    ) -> HardenedReportResult:
        """
        Generate a production-hardened pilot report with idempotency and drift detection.
        
        Args:
            db: Database session
            pilot_profile_id: Target pilot organization profile
            start_date: Reporting window start
            end_date: Reporting window end
            is_incident_lineage_complete: Whether incident telemetry is complete
            force_regenerate: If True, skip duplicate check and regenerate
            
        Returns:
            HardenedReportResult containing snapshot, metrics, and any warnings
        """
        result = HardenedReportResult()
        total_start_time = time.perf_counter()
        
        logger.info(
            f"Starting hardened report generation for pilot {pilot_profile_id} "
            f"window [{start_date.isoformat()} to {end_date.isoformat()}]"
        )

        try:
            # 1. Check for existing snapshot (Idempotency)
            if not force_regenerate:
                existing = cls._find_existing_snapshot(
                    db, pilot_profile_id, start_date, end_date
                )
                if existing:
                    logger.info(f"Found existing snapshot {existing.id}, verifying integrity...")
                    
                    # Verify existing snapshot integrity
                    drift = cls._detect_drift(db, existing)
                    if not drift.drift_detected:
                        logger.info(f"Existing snapshot {existing.id} verified, returning.")
                        result.snapshot = existing
                        result.is_new = False
                        result.drift_report = drift
                        return result
                    else:
                        logger.warning(
                            f"Drift detected in existing snapshot {existing.id}: "
                            f"{[d.value for d in drift.drift_types]}"
                        )
                        result.warnings.append(f"Drift detected: {[d.value for d in drift.drift_types]}")
                        result.drift_report = drift

            # 2. Gather lineage data with observability
            lineage_start = time.perf_counter()
            
            profile = db.query(PilotWorkspaceProfile).filter(
                PilotWorkspaceProfile.id == pilot_profile_id
            ).first()
            if not profile:
                raise ValueError(f"PilotWorkspaceProfile {pilot_profile_id} not found")
            
            # Get enrolled repositories
            enrollments = db.query(PilotRepositoryEnrollment).filter(
                PilotRepositoryEnrollment.pilot_profile_id == pilot_profile_id,
                PilotRepositoryEnrollment.enrollment_status == "ACTIVE"
            ).all()
            repository_ids = [e.repository_id for e in enrollments]
            
            result.generation_metrics.db_query_count += 2
            
            lineage_time = (time.perf_counter() - lineage_start) * 1000
            logger.debug(f"Lineage gathering took {lineage_time:.2f}ms")

            # 3. Aggregate metrics with latency tracking
            agg_start = time.perf_counter()
            
            if repository_ids:
                metrics = PilotMetricsAggregator.aggregate_metrics(
                    db, repository_ids, start_date, end_date
                )
            else:
                metrics = cls._create_empty_metrics(start_date, end_date)
                result.warnings.append("No active repository enrollments found")
            
            agg_time = (time.perf_counter() - agg_start) * 1000
            result.generation_metrics.aggregation_latency_ms = agg_time
            logger.debug(f"Metrics aggregation took {agg_time:.2f}ms")

            # 4. Calculate savings with conservative validation
            savings, savings_warnings = cls._calculate_conservative_savings(
                metrics, repository_ids
            )
            result.warnings.extend(savings_warnings)

            # 5. Gather fragility summaries (across all enrolled repos)
            fragility = cls._aggregate_fragility_summaries(db, repository_ids)

            # 6. Build trust metrics
            trust, trust_warnings = cls._build_trust_metrics(
                db, repository_ids, start_date, end_date, metrics
            )
            result.warnings.extend(trust_warnings)

            # 7. Detect data limitations
            limitations = cls._detect_data_limitations(metrics, savings, repository_ids)
            result.limitations = limitations

            # 8. Check for missing evidence
            missing_warnings = cls._detect_missing_evidence(metrics, savings, trust)
            result.generation_metrics.missing_evidence_warnings = missing_warnings
            result.warnings.extend(missing_warnings)

            # 9. Generate and persist snapshot
            snapshot_start = time.perf_counter()
            
            try:
                snapshot = PilotROISnapshotGenerator.persist_snapshot(
                    db=db,
                    pilot_profile_id=pilot_profile_id,
                    start_date=start_date,
                    end_date=end_date,
                    metrics=metrics,
                    savings=savings,
                    fragility=fragility,
                    trust=trust,
                    generation_version=1
                )
                
                result.snapshot = snapshot
                result.is_new = True
                
                snapshot_time = (time.perf_counter() - snapshot_start) * 1000
                result.generation_metrics.snapshot_latency_ms = snapshot_time
                
                logger.info(
                    f"Created new snapshot {snapshot.id} with hash {snapshot.report_snapshot_hash[:16]}... "
                    f"({snapshot_time:.2f}ms)"
                )
                
            except IntegrityError as e:
                # Hash collision - existing snapshot was created concurrently
                db.rollback()
                logger.warning(f"Concurrent snapshot creation detected: {e}")
                
                # Retry once to fetch the existing snapshot
                existing = cls._find_existing_snapshot(
                    db, pilot_profile_id, start_date, end_date
                )
                if existing:
                    result.snapshot = existing
                    result.is_new = False
                    result.warnings.append("Concurrent snapshot creation - returning existing")
                else:
                    raise

            # 10. Calculate total latency
            total_time = (time.perf_counter() - total_start_time) * 1000
            result.generation_metrics.generation_latency_ms = total_time
            
            logger.info(
                f"Hardened report generation complete in {total_time:.2f}ms "
                f"(new={result.is_new}, snapshot={result.snapshot.id if result.snapshot else 'None'})"
            )
            
            return result

        except Exception as e:
            result.generation_metrics.aggregation_failures.append(str(e))
            logger.error(f"Hardened report generation failed: {e}", exc_info=True)
            raise

    @classmethod
    def detect_reporting_drift(
        cls,
        db: Session,
        snapshot_id: uuid.UUID
    ) -> DriftReport:
        """
        Detect drift between a stored snapshot and current live data.
        
        Args:
            db: Database session
            snapshot_id: Snapshot to check for drift
            
        Returns:
            DriftReport detailing any detected inconsistencies
        """
        snapshot = db.query(PilotReportSnapshot).filter(
            PilotReportSnapshot.id == snapshot_id
        ).first()
        
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")
        
        return cls._detect_drift(db, snapshot)

    @classmethod
    def replay_pilot_report(
        cls,
        db: Session,
        snapshot_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Replay a pilot report from its immutable snapshot.
        
        Verifies integrity and regenerates the report view without mutating data.
        
        Args:
            db: Database session
            snapshot_id: Snapshot to replay
            
        Returns:
            Dict containing replayed report data and verification status
        """
        start_time = time.perf_counter()
        
        snapshot = db.query(PilotReportSnapshot).filter(
            PilotReportSnapshot.id == snapshot_id
        ).first()
        
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")
        
        # Verify snapshot integrity
        audit = PilotROISnapshotGenerator.verify_snapshot_integrity(db, snapshot_id)
        
        if not audit["integrity_verified"]:
            logger.error(f"Snapshot {snapshot_id} integrity check failed: {audit}")
            raise ValueError(f"Snapshot integrity verification failed: {audit}")
        
        # Extract payload for report regeneration
        payload = snapshot.report_payload
        sub_payloads = payload.get("sub_payloads", {})
        
        # Regenerate report view from snapshot data
        report_view = {
            "snapshot_id": str(snapshot_id),
            "pilot_profile_id": str(snapshot.pilot_profile_id),
            "reporting_window": payload.get("reporting_window"),
            "generation_version": payload.get("generation_version"),
            "generated_at": payload.get("generated_at"),
            
            # Sub-component hashes for verification
            "component_hashes": {
                "aggregation": payload.get("aggregation_snapshot_hash"),
                "roi": payload.get("roi_snapshot_hash"),
                "fragility": payload.get("fragility_snapshot_hash"),
                "outcome": payload.get("outcome_snapshot_hash"),
            },
            
            # Recovered data from sub-payloads
            "metrics_aggregator": sub_payloads.get("metrics_aggregator"),
            "savings_calculator": sub_payloads.get("savings_calculator"),
            "fragility_summary": sub_payloads.get("fragility_summary"),
            "trust_metrics": sub_payloads.get("trust_metrics"),
            
            # Verification metadata
            "verification": {
                "status": "REPLAY_VERIFIED",
                "integrity_verified": True,
                "stored_hash": audit["stored_snapshot_hash"],
                "computed_hash": audit["computed_snapshot_hash"],
                "sub_hashes_matched": audit["sub_hashes_matched"],
            },
            
            # Replay performance
            "replay_latency_ms": round((time.perf_counter() - start_time) * 1000, 2)
        }
        
        logger.info(f"Successfully replayed snapshot {snapshot_id} ({report_view['replay_latency_ms']}ms)")
        
        return report_view

    @classmethod
    def rebuild_roi_snapshot(
        cls,
        db: Session,
        pilot_profile_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime,
        reason: str = "manual_rebuild"
    ) -> PilotReportSnapshot:
        """
        Force rebuild of ROI snapshot from current data.
        
        Use when drift has been detected and data needs to be refreshed.
        Creates a new snapshot version rather than mutating existing.
        
        Args:
            db: Database session
            pilot_profile_id: Target pilot profile
            start_date: Reporting window start
            end_date: Reporting window end
            reason: Reason for rebuild (auditing)
            
        Returns:
            Newly created PilotReportSnapshot
        """
        logger.warning(
            f"Force rebuilding ROI snapshot for pilot {pilot_profile_id} "
            f"window [{start_date} to {end_date}]. Reason: {reason}"
        )
        
        # Delete any existing snapshots for this window (they're immutable anyway)
        existing = db.query(PilotReportSnapshot).filter(
            PilotReportSnapshot.pilot_profile_id == pilot_profile_id,
            PilotReportSnapshot.reporting_window_start == start_date,
            PilotReportSnapshot.reporting_window_end == end_date
        ).all()
        
        if existing:
            logger.info(f"Found {len(existing)} existing snapshots for rebuild window")
            # Note: Immutability events prevent actual deletion, 
            # but we log for audit trail
            for snap in existing:
                logger.info(f"Existing snapshot {snap.id} with hash {snap.report_snapshot_hash}")
        
        # Generate new snapshot with force_regenerate
        result = cls.generate_hardened_report(
            db=db,
            pilot_profile_id=pilot_profile_id,
            start_date=start_date,
            end_date=end_date,
            force_regenerate=True
        )
        
        if not result.snapshot:
            raise RuntimeError("Snapshot rebuild failed - no snapshot created")
        
        # Log rebuild event
        logger.info(
            f"ROI snapshot rebuilt: {result.snapshot.id} "
            f"(hash: {result.snapshot.report_snapshot_hash[:16]}...) "
            f"reason: {reason}"
        )
        
        return result.snapshot

    @classmethod
    def repair_stale_aggregation(
        cls,
        db: Session,
        pilot_profile_id: uuid.UUID,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Detect and optionally repair stale aggregation state.
        
        Identifies snapshots with drift and provides repair recommendations.
        
        Args:
            db: Database session
            pilot_profile_id: Target pilot profile
            dry_run: If True, only report issues without fixing
            
        Returns:
            Dict with stale snapshots and repair actions taken
        """
        logger.info(f"Checking for stale aggregation state for pilot {pilot_profile_id}")
        
        # Get all snapshots for this pilot
        snapshots = db.query(PilotReportSnapshot).filter(
            PilotReportSnapshot.pilot_profile_id == pilot_profile_id
        ).order_by(PilotReportSnapshot.reporting_window_start.desc()).all()
        
        stale_snapshots = []
        repaired = []
        
        for snapshot in snapshots:
            drift = cls._detect_drift(db, snapshot)
            
            if drift.drift_detected:
                stale_info = {
                    "snapshot_id": str(snapshot.id),
                    "window": {
                        "start": snapshot.reporting_window_start.isoformat(),
                        "end": snapshot.reporting_window_end.isoformat()
                    },
                    "stored_hash": snapshot.report_snapshot_hash,
                    "drift_types": [d.value for d in drift.drift_types],
                    "drift_details": {
                        "aggregation_differences": drift.aggregation_differences,
                        "lineage_gaps": drift.lineage_gaps,
                        "missing_runtime_count": drift.missing_runtime_count,
                        "sub_hash_mismatches": drift.sub_hash_mismatches
                    }
                }
                stale_snapshots.append(stale_info)
                
                if not dry_run:
                    # Attempt repair by rebuilding
                    try:
                        new_snapshot = cls.rebuild_roi_snapshot(
                            db=db,
                            pilot_profile_id=pilot_profile_id,
                            start_date=snapshot.reporting_window_start,
                            end_date=snapshot.reporting_window_end,
                            reason=f"repair_stale_aggregation: {[d.value for d in drift.drift_types]}"
                        )
                        
                        repaired.append({
                            "old_snapshot_id": str(snapshot.id),
                            "new_snapshot_id": str(new_snapshot.id),
                            "new_hash": new_snapshot.report_snapshot_hash,
                            "status": "rebuilt"
                        })
                    except Exception as e:
                        repaired.append({
                            "old_snapshot_id": str(snapshot.id),
                            "error": str(e),
                            "status": "failed"
                        })
        
        result = {
            "pilot_profile_id": str(pilot_profile_id),
            "total_snapshots_checked": len(snapshots),
            "stale_snapshots_found": len(stale_snapshots),
            "stale_details": stale_snapshots,
            "dry_run": dry_run
        }
        
        if not dry_run:
            result["repairs_attempted"] = len(repaired)
            result["repairs_succeeded"] = len([r for r in repaired if r.get("status") == "rebuilt"])
            result["repair_details"] = repaired
        
        logger.info(
            f"Stale aggregation check complete: {len(stale_snapshots)}/{len(snapshots)} stale "
            f"({len(repaired)} repairs attempted)"
        )
        
        return result

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    @classmethod
    def _find_existing_snapshot(
        cls,
        db: Session,
        pilot_profile_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[PilotReportSnapshot]:
        """Find existing snapshot for the exact reporting window."""
        return db.query(PilotReportSnapshot).filter(
            PilotReportSnapshot.pilot_profile_id == pilot_profile_id,
            PilotReportSnapshot.reporting_window_start == start_date,
            PilotReportSnapshot.reporting_window_end == end_date
        ).first()

    @classmethod
    def _detect_drift(
        cls,
        db: Session,
        snapshot: PilotReportSnapshot
    ) -> DriftReport:
        """Detect drift between stored snapshot and live data."""
        report = DriftReport()
        payload = snapshot.report_payload
        sub_payloads = payload.get("sub_payloads", {})
        
        # 1. Check hash integrity
        audit = PilotROISnapshotGenerator.verify_snapshot_integrity(db, snapshot.id)
        report.stored_hash = audit["stored_snapshot_hash"]
        report.computed_hash = audit["computed_snapshot_hash"]
        report.sub_hash_mismatches = audit.get("sub_hashes_matched", {})
        
        if not audit["integrity_verified"]:
            report.drift_detected = True
            report.drift_types.append(DriftType.HASH_MISMATCH)
        
        # Check for sub-hash mismatches
        for sub_name, matched in report.sub_hash_mismatches.items():
            if not matched:
                report.drift_detected = True
                if DriftType.SUB_HASH_MISMATCH not in report.drift_types:
                    report.drift_types.append(DriftType.SUB_HASH_MISMATCH)
        
        # 2. Re-aggregate metrics and compare
        stored_metrics = sub_payloads.get("metrics_aggregator", {})
        
        # Get repository IDs from snapshot context or re-query
        profile_id = snapshot.pilot_profile_id
        enrollments = db.query(PilotRepositoryEnrollment).filter(
            PilotRepositoryEnrollment.pilot_profile_id == profile_id,
            PilotRepositoryEnrollment.enrollment_status == "ACTIVE"
        ).all()
        repository_ids = [e.repository_id for e in enrollments]
        
        if repository_ids:
            current_metrics = PilotMetricsAggregator.aggregate_metrics(
                db, repository_ids,
                snapshot.reporting_window_start,
                snapshot.reporting_window_end
            )
            
            # Compare key metrics
            differences = {}
            key_fields = [
                "total_recommendation_runs",
                "total_executed_tests",
                "total_full_suite_runtime_seconds",
                "rollback_linked_outcomes",
                "escaped_defect_linked_outcomes"
            ]
            
            for field in key_fields:
                stored = stored_metrics.get(field)
                current = current_metrics.get(field)
                if stored != current:
                    differences[field] = {"stored": stored, "current": current}
            
            if differences:
                report.drift_detected = True
                report.drift_types.append(DriftType.AGGREGATION_MISMATCH)
                report.aggregation_differences = differences
        
        # 3. Check for missing runtime data
        stored_savings = sub_payloads.get("savings_calculator", {})
        missing_count = stored_savings.get("missing_runtime_data_runs_count", 0)
        excluded_count = stored_savings.get("excluded_runs_count", 0)
        
        total_stored_runs = stored_metrics.get("total_recommendation_runs", 0)
        if total_stored_runs > 0:
            missing_ratio = (missing_count + excluded_count) / total_stored_runs
            if missing_ratio > cls.MAX_ACCEPTABLE_MISSING_RUNTIME_RATIO:
                report.drift_detected = True
                report.drift_types.append(DriftType.MISSING_RUNTIME_DATA)
                report.missing_runtime_count = missing_count + excluded_count
        
        # 4. Check lineage freshness (outcomes newer than snapshot)
        newer_outcomes = db.query(RecommendationOutcome).join(
            RecommendationRun
        ).filter(
            RecommendationRun.repository_id.in_(repository_ids) if repository_ids else False,
            RecommendationRun.created_at >= snapshot.reporting_window_start,
            RecommendationRun.created_at <= snapshot.reporting_window_end,
            RecommendationOutcome.created_at > snapshot.generated_at
        ).count()
        
        if newer_outcomes > 0:
            report.lineage_gaps.append(f"{newer_outcomes} outcomes recorded after snapshot generation")
            # This is expected behavior for append-only, not necessarily drift
            # but we track it for observability
        
        return report

    @classmethod
    def _calculate_conservative_savings(
        cls,
        metrics: Dict[str, Any],
        repository_ids: List[uuid.UUID]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Calculate savings with conservative validation and warnings."""
        warnings = []
        
        total_runs = metrics.get("total_recommendation_runs", 0)
        missing_full = metrics.get("excluded_data_counts", {}).get("missing_full_suite_runtime", 0)
        missing_rec = metrics.get("excluded_data_counts", {}).get("missing_recommended_runtime", 0)
        missing_out = metrics.get("excluded_data_counts", {}).get("missing_outcome", 0)
        
        total_full_suite = metrics.get("total_full_suite_runtime_seconds", 0.0)
        total_recommended = metrics.get("total_recommended_runtime_seconds", 0.0)
        
        runs_with_full = total_runs - missing_full
        runs_with_rec = total_runs - missing_rec
        
        avg_full = total_full_suite / max(runs_with_full, 1) if runs_with_full > 0 else 0.0
        avg_rec = total_recommended / max(runs_with_rec, 1) if runs_with_rec > 0 else 0.0
        
        # Calculate followed count for execution_frequency
        # This is a simplified version - in production would query outcomes
        total_outcomes = total_runs - missing_out
        
        savings = RegressionSavingsCalculator.calculate_savings(
            full_suite_baseline_seconds=avg_full,
            recommended_runtime_seconds=avg_rec,
            recommendation_frequency=total_runs,
            execution_frequency=total_outcomes,  # Conservative: assume all outcomes followed
            excluded_runs=missing_out,
            missing_runtime_data=missing_full
        )
        
        # Add explicit warnings for significant missing data
        if missing_full > 0:
            warnings.append(
                f"Missing full suite runtime for {missing_full}/{total_runs} runs. "
                f"Savings calculations may be understated."
            )
        
        if missing_out > 0:
            warnings.append(
                f"Missing outcomes for {missing_out}/{total_runs} runs. "
                f"Execution frequency may be overstated."
            )
        
        # Check for high exclusion ratio
        if total_runs > 0:
            exclusion_ratio = (missing_full + missing_rec + missing_out) / total_runs
            if exclusion_ratio > 0.5:
                warnings.append(
                    f"High data exclusion ratio ({exclusion_ratio:.1%}). "
                    f"Report has limited statistical reliability."
                )
        
        return savings, warnings

    @classmethod
    def _aggregate_fragility_summaries(
        cls,
        db: Session,
        repository_ids: List[uuid.UUID]
    ) -> Dict[str, Any]:
        """Aggregate fragility summaries across all enrolled repositories."""
        combined = {
            "most_fragile_modules": [],
            "most_repeated_co_failure_patterns": [],
            "rollback_linked_fragility_patterns": [],
            "unstable_dependency_neighborhoods": [],
            "high_churn_modules": [],
            "repository_count": len(repository_ids),
            "aggregation_note": "Top patterns from all enrolled repositories combined"
        }
        
        for repo_id in repository_ids:
            summary = FragilityPilotSummaryBuilder.generate_fragility_summary(db, repo_id)
            
            # Merge top patterns (maintaining top 5 limit per category)
            for key in [
                "most_fragile_modules",
                "most_repeated_co_failure_patterns",
                "rollback_linked_fragility_patterns",
                "unstable_dependency_neighborhoods",
                "high_churn_modules"
            ]:
                existing = {p["pattern_id"] for p in combined[key]}
                for pattern in summary.get(key, []):
                    if pattern["pattern_id"] not in existing:
                        combined[key].append(pattern)
                
                # Re-sort and limit to top 5 by fragility_score
                combined[key] = sorted(
                    combined[key],
                    key=lambda x: x.get("fragility_score", 0.0),
                    reverse=True
                )[:5]
        
        return combined

    @classmethod
    def _build_trust_metrics(
        cls,
        db: Session,
        repository_ids: List[uuid.UUID],
        start_date: datetime,
        end_date: datetime,
        metrics: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Build trust metrics with Wilson score confidence intervals."""
        warnings = []
        
        # Query outcomes for trust calculation
        runs = db.query(RecommendationRun).filter(
            RecommendationRun.repository_id.in_(repository_ids) if repository_ids else False,
            RecommendationRun.created_at >= start_date,
            RecommendationRun.created_at <= end_date
        ).all()
        
        run_ids = [run.id for run in runs]
        
        followed_count = 0
        overridden_count = 0
        ignored_count = 0
        
        if run_ids:
            outcomes = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id.in_(run_ids)
            ).all()
            
            for outcome in outcomes:
                has_overrides = (
                    len(outcome.manually_added_tests or []) > 0 or
                    len(outcome.manually_removed_tests or []) > 0 or
                    outcome.outcome_status == "OVERRIDDEN"
                )
                
                if has_overrides:
                    overridden_count += 1
                elif outcome.outcome_status == "IGNORED":
                    ignored_count += 1
                else:
                    followed_count += 1
        
        total_outcomes = followed_count + overridden_count + ignored_count
        
        # Calculate Wilson score bounds
        lower_bound, upper_bound = RecommendationIgnoreDetector.calculate_wilson_score_interval(
            followed_count,
            total_outcomes,
            confidence_level=0.90
        )
        
        adherence_rate = followed_count / max(total_outcomes, 1) if total_outcomes > 0 else 0.0
        
        # Check for tiny dataset
        if total_outcomes < cls.MIN_OUTCOMES_FOR_CONFIDENCE:
            warnings.append(
                f"Tiny outcome dataset (N={total_outcomes}). "
                f"Trust metrics have low statistical confidence."
            )
        
        trust_metrics = {
            "total_runs": len(runs),
            "total_outcomes": total_outcomes,
            "followed_count": followed_count,
            "overridden_count": overridden_count,
            "ignored_count": ignored_count,
            "adherence_rate": round(adherence_rate, 4),
            "trust_lower_bound": round(lower_bound, 4),
            "trust_upper_bound": round(upper_bound, 4),
            "confidence_level": 0.90,
            "confidence_interval_method": "Wilson Score Interval"
        }
        
        return trust_metrics, warnings

    @classmethod
    def _detect_data_limitations(
        cls,
        metrics: Dict[str, Any],
        savings: Dict[str, Any],
        repository_ids: List[uuid.UUID]
    ) -> List[str]:
        """Detect and report explicit data limitations."""
        limitations = []
        
        total_runs = metrics.get("total_recommendation_runs", 0)
        
        # Low sample size
        if total_runs < cls.MIN_RUNS_FOR_CONFIDENCE:
            limitations.append(
                f"Low sample size: only {total_runs} runs (minimum recommended: {cls.MIN_RUNS_FOR_CONFIDENCE}). "
                f"All statistical estimates have low reliability."
            )
        
        # Missing runtime data
        missing_full = metrics.get("excluded_data_counts", {}).get("missing_full_suite_runtime", 0)
        if missing_full > 0:
            limitations.append(
                f"Missing baseline runtime data for {missing_full} runs. "
                f"Savings calculations use conservative fallback (0.0 for missing data)."
            )
        
        # High exclusion ratio
        if total_runs > 0:
            total_excluded = sum(
                metrics.get("excluded_data_counts", {}).get(k, 0)
                for k in ["missing_full_suite_runtime", "missing_recommended_runtime", "missing_outcome"]
            )
            exclusion_ratio = total_excluded / total_runs
            if exclusion_ratio > 0.3:
                limitations.append(
                    f"High data exclusion ratio: {exclusion_ratio:.1%} of runs have incomplete data. "
                    f"Report is based on limited evidence."
                )
        
        # No enrolled repositories
        if not repository_ids:
            limitations.append(
                "No active repository enrollments. Report contains no operational data."
            )
        
        # Savings confidence warning
        if savings.get("confidence_warning"):
            limitations.append(savings["confidence_warning"])
        
        return limitations

    @classmethod
    def _detect_missing_evidence(
        cls,
        metrics: Dict[str, Any],
        savings: Dict[str, Any],
        trust: Dict[str, Any]
    ) -> List[str]:
        """Detect missing evidence that should be tracked for observability."""
        warnings = []
        
        # Check for confidence warnings in any component
        if metrics.get("confidence_warning"):
            warnings.append(f"Metrics: {metrics['confidence_warning']}")
        
        if savings.get("confidence_warning"):
            warnings.append(f"Savings: {savings['confidence_warning']}")
        
        # Check for tiny dataset in trust metrics
        if trust.get("total_outcomes", 0) < 5:
            warnings.append(
                f"Trust metrics: Tiny dataset (N={trust.get('total_outcomes', 0)} outcomes)"
            )
        
        return warnings

    @classmethod
    def _create_empty_metrics(
        cls,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Create empty metrics structure for when no repositories are enrolled."""
        return {
            "reporting_window_start": start_date.isoformat(),
            "reporting_window_end": end_date.isoformat(),
            "repository_ids": [],
            "aggregation_version": 1,
            "total_prs_analyzed": 0,
            "total_recommendation_runs": 0,
            "total_recommended_tests": 0,
            "total_executed_tests": 0,
            "total_full_suite_runtime_seconds": 0.0,
            "total_recommended_runtime_seconds": 0.0,
            "override_frequency": 0.0,
            "ignored_recommendation_rate": 0.0,
            "rollback_linked_outcomes": 0,
            "escaped_defect_linked_outcomes": 0,
            "excluded_data_counts": {
                "missing_full_suite_runtime": 0,
                "missing_recommended_runtime": 0,
                "missing_pull_request": 0,
                "missing_outcome": 0
            },
            "confidence_warning": "WARNING: No active repository enrollments. Report contains no operational data."
        }
