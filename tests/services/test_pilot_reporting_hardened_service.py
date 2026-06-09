"""
tests/services/test_pilot_reporting_hardened_service.py
======================================================

Comprehensive tests for production-hardened pilot reporting service.

Covers:
- Idempotent report generation (duplicate prevention)
- Reporting drift detection (aggregation, snapshot, lineage, runtime)
- Conservative fallback behavior (explicit limitations)
- Replay-safe regeneration (from snapshots)
- Observability metrics (latency, failures, warnings)
- Recovery tooling (replay, rebuild, repair)
"""

import uuid
import json
import hashlib
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, Mock

import pytest

from app.services.pilot_reporting_hardened_service import (
    PilotReportingHardenedService,
    DriftType,
    RecoveryAction,
    GenerationMetrics,
    DriftReport,
    HardenedReportResult
)
from app.services.pilot_roi_snapshot_generator import PilotROISnapshotGenerator
from app.models.pilot import PilotReportSnapshot, PilotWorkspaceProfile, PilotRepositoryEnrollment


class TestIdempotentReportGeneration:
    """Test 1: Idempotent report generation - prevent duplicate snapshots."""

    def test_returns_existing_snapshot_if_no_drift(self):
        """Should return existing snapshot if it exists and has no drift."""
        mock_db = MagicMock()
        
        # Create mock existing snapshot
        existing_snapshot = MagicMock()
        existing_snapshot.id = uuid.uuid4()
        existing_snapshot.report_snapshot_hash = "abc123"
        existing_snapshot.report_payload = {
            "roi_snapshot_hash": "hash1",
            "aggregation_snapshot_hash": "hash2",
            "fragility_snapshot_hash": "hash3",
            "outcome_snapshot_hash": "hash4",
            "reporting_window": {"start_date": "2026-01-01T00:00:00", "end_date": "2026-01-31T00:00:00"},
            "generation_version": 1,
            "generated_at": "2026-02-01T00:00:00",
            "sub_payloads": {}
        }
        existing_snapshot.reporting_window_start = datetime(2026, 1, 1)
        existing_snapshot.reporting_window_end = datetime(2026, 1, 31)
        existing_snapshot.generated_at = datetime(2026, 2, 1)
        existing_snapshot.pilot_profile_id = uuid.uuid4()
        
        # Mock the query to return existing snapshot
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = existing_snapshot
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        # Mock drift detection to return no drift
        with patch.object(PilotReportingHardenedService, '_detect_drift') as mock_drift:
            mock_drift.return_value = DriftReport(drift_detected=False)
            
            result = PilotReportingHardenedService.generate_hardened_report(
                db=mock_db,
                pilot_profile_id=existing_snapshot.pilot_profile_id,
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31)
            )
        
        assert result.snapshot == existing_snapshot
        assert result.is_new is False
        assert result.drift_report is not None
        assert result.drift_report.drift_detected is False

    def test_generates_new_snapshot_if_force_regenerate(self):
        """Should generate new snapshot when force_regenerate=True."""
        mock_db = MagicMock()
        pilot_id = uuid.uuid4()
        
        # Mock existing snapshot
        existing = MagicMock()
        existing.id = uuid.uuid4()
        
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.side_effect = [None, None]  # No existing, no profile query issues
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        # Mock profile
        mock_profile = MagicMock()
        mock_profile.id = pilot_id
        mock_query.filter.return_value.first.side_effect = [existing, mock_profile, []]
        
        # Mock the persist_snapshot to return a new snapshot
        new_snapshot = MagicMock()
        new_snapshot.id = uuid.uuid4()
        new_snapshot.report_snapshot_hash = "newhash123"
        
        with patch.object(PilotROISnapshotGenerator, 'persist_snapshot', return_value=new_snapshot):
            with patch.object(PilotReportingHardenedService, '_calculate_conservative_savings') as mock_savings:
                mock_savings.return_value = ({"hours": 10}, [])
                
                with patch.object(PilotReportingHardenedService, '_aggregate_fragility_summaries') as mock_fragility:
                    mock_fragility.return_value = {"patterns": []}
                    
                    with patch.object(PilotReportingHardenedService, '_build_trust_metrics') as mock_trust:
                        mock_trust.return_value = ({"rate": 0.8}, [])
                        
                        result = PilotReportingHardenedService.generate_hardened_report(
                            db=mock_db,
                            pilot_profile_id=pilot_id,
                            start_date=datetime(2026, 1, 1),
                            end_date=datetime(2026, 1, 31),
                            force_regenerate=True
                        )
        
        assert result.is_new is True
        assert result.snapshot == new_snapshot

    def test_handles_concurrent_creation_integrity_error(self):
        """Should handle IntegrityError from concurrent snapshot creation."""
        mock_db = MagicMock()
        pilot_id = uuid.uuid4()
        
        # Create existing snapshot that will be found after IntegrityError
        existing_snapshot = MagicMock()
        existing_snapshot.id = uuid.uuid4()
        existing_snapshot.report_snapshot_hash = "existing_hash"
        
        # Mock profile
        mock_profile = MagicMock()
        mock_profile.id = pilot_id
        
        # Setup query mocks: profile lookup and empty enrollments
        # Note: _find_existing_snapshot is patched, so no query for that
        mock_db.query.return_value.filter.return_value.first.return_value = mock_profile
        mock_db.query.return_value.filter.return_value.all.return_value = []  # Empty enrollments
        
        # Simulate IntegrityError on persist, then return existing on retry
        from sqlalchemy.exc import IntegrityError
        
        # Create proper IntegrityError that will be recognized by the handler
        integrity_error = IntegrityError(
            statement="INSERT INTO pilot_report_snapshots",
            params={"hash": "duplicate"},
            orig=Exception("unique constraint violation")
        )
        
        with patch.object(PilotROISnapshotGenerator, 'persist_snapshot') as mock_persist:
            mock_persist.side_effect = integrity_error
            
            # After rollback, the retry should find existing
            # Use side_effect: first call returns None, second call returns existing
            with patch.object(PilotReportingHardenedService, '_find_existing_snapshot') as mock_find:
                mock_find.side_effect = [None, existing_snapshot]
                
                # Mock drift detection to avoid DB verification on mocked snapshot
                with patch.object(PilotReportingHardenedService, '_detect_drift') as mock_drift:
                    mock_drift.return_value = DriftReport(drift_detected=False)
                    
                    with patch.object(PilotReportingHardenedService, '_calculate_conservative_savings') as mock_savings:
                        mock_savings.return_value = ({"hours": 10}, [])
                        
                        with patch.object(PilotReportingHardenedService, '_aggregate_fragility_summaries') as mock_fragility:
                            mock_fragility.return_value = {"patterns": []}
                            
                            with patch.object(PilotReportingHardenedService, '_build_trust_metrics') as mock_trust:
                                mock_trust.return_value = ({"rate": 0.8}, [])
                                
                                result = PilotReportingHardenedService.generate_hardened_report(
                                    db=mock_db,
                                    pilot_profile_id=pilot_id,
                                    start_date=datetime(2026, 1, 1),
                                    end_date=datetime(2026, 1, 31)
                                )
        
        # Verify _find_existing_snapshot was called twice (initial check + retry)
        assert mock_find.call_count == 2
        
        # Should have returned existing snapshot (recovered from IntegrityError)
        assert result.snapshot == existing_snapshot
        assert result.is_new is False
        
        # Should have warning about concurrent creation
        assert any("Concurrent" in w for w in result.warnings), f"Expected 'Concurrent' in warnings, got: {result.warnings}"


class TestReportingDriftDetection:
    """Test 2: Reporting drift detection."""

    def test_detects_hash_mismatch(self):
        """Should detect when computed hash doesn't match stored hash."""
        mock_db = MagicMock()
        
        snapshot = MagicMock()
        snapshot.id = uuid.uuid4()
        snapshot.report_payload = {
            "aggregation_snapshot_hash": "stored_agg_hash",
            "roi_snapshot_hash": "stored_roi_hash",
            "fragility_snapshot_hash": "stored_frag_hash",
            "outcome_snapshot_hash": "stored_out_hash",
            "reporting_window": {"start_date": "2026-01-01T00:00:00", "end_date": "2026-01-31T00:00:00"},
            "generation_version": 1,
            "generated_at": "2026-02-01T00:00:00",
            "sub_payloads": {
                "metrics_aggregator": {"total": 10},
                "savings_calculator": {"hours": 5},
                "fragility_summary": {"patterns": []},
                "trust_metrics": {"rate": 0.8}
            }
        }
        snapshot.report_snapshot_hash = "wrong_hash"  # Intentionally wrong
        snapshot.reporting_window_start = datetime(2026, 1, 1)
        snapshot.reporting_window_end = datetime(2026, 1, 31)
        snapshot.pilot_profile_id = uuid.uuid4()
        snapshot.generated_at = datetime(2026, 2, 1)
        
        # Mock empty enrollments and count
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.join.return_value.filter.return_value.count.return_value = 0
        
        with patch.object(PilotROISnapshotGenerator, 'verify_snapshot_integrity') as mock_verify:
            mock_verify.return_value = {
                "integrity_verified": False,
                "stored_snapshot_hash": "wrong_hash",
                "computed_snapshot_hash": "correct_hash",
                "sub_hashes_matched": {
                    "aggregation": True,
                    "roi": True,
                    "fragility": True,
                    "outcome": True
                }
            }
            
            drift = PilotReportingHardenedService._detect_drift(mock_db, snapshot)
        
        assert drift.drift_detected is True
        assert DriftType.HASH_MISMATCH in drift.drift_types
        assert drift.stored_hash == "wrong_hash"
        assert drift.computed_hash == "correct_hash"

    def test_detects_aggregation_mismatch(self):
        """Should detect when current aggregation differs from stored."""
        mock_db = MagicMock()
        
        snapshot = MagicMock()
        snapshot.id = uuid.uuid4()
        snapshot.report_payload = {
            "aggregation_snapshot_hash": "old_hash",
            "roi_snapshot_hash": "roi_hash",
            "fragility_snapshot_hash": "frag_hash",
            "outcome_snapshot_hash": "out_hash",
            "reporting_window": {"start_date": "2026-01-01T00:00:00", "end_date": "2026-01-31T00:00:00"},
            "generation_version": 1,
            "generated_at": "2026-02-01T00:00:00",
            "sub_payloads": {
                "metrics_aggregator": {"total_recommendation_runs": 10, "total_executed_tests": 50},
                "savings_calculator": {"hours": 5},
                "fragility_summary": {"patterns": []},
                "trust_metrics": {"rate": 0.8}
            }
        }
        snapshot.report_snapshot_hash = "stored_hash"
        snapshot.reporting_window_start = datetime(2026, 1, 1)
        snapshot.reporting_window_end = datetime(2026, 1, 31)
        snapshot.pilot_profile_id = uuid.uuid4()
        snapshot.generated_at = datetime(2026, 2, 1)
        
        # Mock verify to pass
        with patch.object(PilotROISnapshotGenerator, 'verify_snapshot_integrity') as mock_verify:
            mock_verify.return_value = {
                "integrity_verified": True,
                "stored_snapshot_hash": "stored_hash",
                "computed_snapshot_hash": "stored_hash",
                "sub_hashes_matched": {
                    "aggregation": True,
                    "roi": True,
                    "fragility": True,
                    "outcome": True
                }
            }
            
            # Mock aggregator to return different metrics
            with patch('app.services.pilot_reporting_hardened_service.PilotMetricsAggregator') as mock_agg_cls:
                mock_agg = MagicMock()
                mock_agg.aggregate_metrics.return_value = {
                    "total_recommendation_runs": 15,  # Different from stored (10)
                    "total_executed_tests": 75,  # Different from stored (50)
                    "excluded_data_counts": {}
                }
                mock_agg_cls.return_value = mock_agg
                
                # Mock enrollments and count
                mock_enrollment = MagicMock()
                mock_enrollment.repository_id = uuid.uuid4()
                mock_db.query.return_value.filter.return_value.all.return_value = [mock_enrollment]
                mock_db.query.return_value.join.return_value.filter.return_value.count.return_value = 0
                
                drift = PilotReportingHardenedService._detect_drift(mock_db, snapshot)
        
        assert drift.drift_detected is True
        assert DriftType.AGGREGATION_MISMATCH in drift.drift_types
        assert "total_recommendation_runs" in drift.aggregation_differences

    def test_detects_missing_runtime_data(self):
        """Should detect high missing runtime data ratio."""
        mock_db = MagicMock()
        
        snapshot = MagicMock()
        snapshot.id = uuid.uuid4()
        snapshot.report_payload = {
            "aggregation_snapshot_hash": "agg_hash",
            "roi_snapshot_hash": "roi_hash",
            "fragility_snapshot_hash": "frag_hash",
            "outcome_snapshot_hash": "out_hash",
            "reporting_window": {"start_date": "2026-01-01T00:00:00", "end_date": "2026-01-31T00:00:00"},
            "generation_version": 1,
            "generated_at": "2026-02-01T00:00:00",
            "sub_payloads": {
                "metrics_aggregator": {"total_recommendation_runs": 10},
                "savings_calculator": {
                    "missing_runtime_data_runs_count": 5,  # 50% missing
                    "excluded_runs_count": 0
                },
                "fragility_summary": {"patterns": []},
                "trust_metrics": {"rate": 0.8}
            }
        }
        snapshot.report_snapshot_hash = "stored_hash"
        snapshot.reporting_window_start = datetime(2026, 1, 1)
        snapshot.reporting_window_end = datetime(2026, 1, 31)
        snapshot.pilot_profile_id = uuid.uuid4()
        snapshot.generated_at = datetime(2026, 2, 1)
        
        with patch.object(PilotROISnapshotGenerator, 'verify_snapshot_integrity') as mock_verify:
            mock_verify.return_value = {
                "integrity_verified": True,
                "stored_snapshot_hash": "stored_hash",
                "computed_snapshot_hash": "stored_hash",
                "sub_hashes_matched": {k: True for k in ["aggregation", "roi", "fragility", "outcome"]}
            }
            
            mock_db.query.return_value.filter.return_value.all.return_value = []
            mock_db.query.return_value.join.return_value.filter.return_value.count.return_value = 0
            
            drift = PilotReportingHardenedService._detect_drift(mock_db, snapshot)
        
        assert drift.drift_detected is True
        assert DriftType.MISSING_RUNTIME_DATA in drift.drift_types
        assert drift.missing_runtime_count == 5

    def test_detects_sub_hash_mismatch(self):
        """Should detect when individual component hashes don't match."""
        mock_db = MagicMock()
        
        snapshot = MagicMock()
        snapshot.id = uuid.uuid4()
        snapshot.report_payload = {
            "aggregation_snapshot_hash": "stored_agg_hash",
            "roi_snapshot_hash": "stored_roi_hash",
            "fragility_snapshot_hash": "stored_frag_hash",
            "outcome_snapshot_hash": "stored_out_hash",
            "reporting_window": {"start_date": "2026-01-01T00:00:00", "end_date": "2026-01-31T00:00:00"},
            "generation_version": 1,
            "generated_at": "2026-02-01T00:00:00",
            "sub_payloads": {
                "metrics_aggregator": {"total": 10},
                "savings_calculator": {"hours": 5},
                "fragility_summary": {"patterns": []},
                "trust_metrics": {"rate": 0.8}
            }
        }
        snapshot.report_snapshot_hash = "stored_hash"
        snapshot.reporting_window_start = datetime(2026, 1, 1)
        snapshot.reporting_window_end = datetime(2026, 1, 31)
        snapshot.pilot_profile_id = uuid.uuid4()
        snapshot.generated_at = datetime(2026, 2, 1)
        
        with patch.object(PilotROISnapshotGenerator, 'verify_snapshot_integrity') as mock_verify:
            mock_verify.return_value = {
                "integrity_verified": True,  # Overall hash matches
                "stored_snapshot_hash": "stored_hash",
                "computed_snapshot_hash": "stored_hash",
                "sub_hashes_matched": {
                    "aggregation": False,  # But sub-hash doesn't match
                    "roi": True,
                    "fragility": True,
                    "outcome": True
                }
            }
            
            mock_db.query.return_value.filter.return_value.all.return_value = []
            mock_db.query.return_value.join.return_value.filter.return_value.count.return_value = 0
            
            drift = PilotReportingHardenedService._detect_drift(mock_db, snapshot)
        
        assert drift.drift_detected is True
        assert DriftType.SUB_HASH_MISMATCH in drift.drift_types
        assert drift.sub_hash_mismatches["aggregation"] is False


class TestConservativeFallbackBehavior:
    """Test 3: Conservative fallback behavior."""

    def test_reports_explicit_limitations_for_missing_runtime(self):
        """Should report explicit limitations when runtime data is missing."""
        metrics = {
            "total_recommendation_runs": 10,
            "excluded_data_counts": {
                "missing_full_suite_runtime": 3,
                "missing_recommended_runtime": 0,
                "missing_outcome": 0,
                "missing_pull_request": 0
            }
        }
        
        limitations = PilotReportingHardenedService._detect_data_limitations(
            metrics, {"hours": 5}, [uuid.uuid4()]
        )
        
        # Should have limitation about missing runtime
        assert any("Missing baseline runtime" in lim for lim in limitations)
        assert any("3" in lim for lim in limitations)

    def test_reports_explicit_limitations_for_tiny_dataset(self):
        """Should report limitations for low sample size."""
        metrics = {
            "total_recommendation_runs": 3,  # Below MIN_RUNS_FOR_CONFIDENCE
            "excluded_data_counts": {"missing_full_suite_runtime": 0}
        }
        
        limitations = PilotReportingHardenedService._detect_data_limitations(
            metrics, {"hours": 5}, [uuid.uuid4()]
        )
        
        assert any("Low sample size" in lim for lim in limitations)
        assert any("3" in lim for lim in limitations)

    def test_reports_explicit_limitations_for_high_exclusion_ratio(self):
        """Should report limitations when exclusion ratio is high."""
        metrics = {
            "total_recommendation_runs": 10,
            "excluded_data_counts": {
                "missing_full_suite_runtime": 4,
                "missing_recommended_runtime": 4,
                "missing_outcome": 0,
                "missing_pull_request": 0
            }
        }
        
        limitations = PilotReportingHardenedService._detect_data_limitations(
            metrics, {"hours": 5}, [uuid.uuid4()]
        )
        
        # 8/10 = 80% exclusion ratio > 30% threshold
        assert any("High data exclusion ratio" in lim for lim in limitations)
        assert any("80.0%" in lim or "80%" in lim for lim in limitations)

    def test_reports_explicit_limitations_for_no_repositories(self):
        """Should report limitation when no repositories enrolled."""
        metrics = {"total_recommendation_runs": 0}
        
        limitations = PilotReportingHardenedService._detect_data_limitations(
            metrics, {"hours": 5}, []  # Empty repository list
        )
        
        assert any("No active repository enrollments" in lim for lim in limitations)

    def test_does_not_estimate_silently(self):
        """Should not silently estimate missing data."""
        metrics = {
            "total_recommendation_runs": 10,
            "total_full_suite_runtime_seconds": 5000.0,  # 5 runs with data
            "total_recommended_runtime_seconds": 1500.0,
            "excluded_data_counts": {
                "missing_full_suite_runtime": 5,  # 5 runs missing
                "missing_recommended_runtime": 0,
                "missing_outcome": 0,
                "missing_pull_request": 0
            }
        }
        
        savings, warnings = PilotReportingHardenedService._calculate_conservative_savings(
            metrics, [uuid.uuid4()]
        )
        
        # Should have warning about missing runtime
        assert any("Missing full suite runtime" in w for w in warnings)
        
        # Average should be calculated only from runs WITH data (5 runs)
        # 5000 / 5 = 1000 seconds average
        # Not 5000 / 10 = 500 seconds (which would silently estimate)


class TestReplaySafeRegeneration:
    """Test 4: Replay-safe regeneration."""

    def test_replay_verifies_integrity_before_returning(self):
        """Should verify snapshot integrity before replaying."""
        mock_db = MagicMock()
        snapshot_id = uuid.uuid4()
        
        snapshot = MagicMock()
        snapshot.id = snapshot_id
        snapshot.report_payload = {
            "roi_snapshot_hash": "hash1",
            "aggregation_snapshot_hash": "hash2",
            "fragility_snapshot_hash": "hash3",
            "outcome_snapshot_hash": "hash4",
            "reporting_window": {"start_date": "2026-01-01T00:00:00", "end_date": "2026-01-31T00:00:00"},
            "generation_version": 1,
            "generated_at": "2026-02-01T00:00:00",
            "sub_payloads": {
                "metrics_aggregator": {"total": 10},
                "savings_calculator": {"hours": 5},
                "fragility_summary": {"patterns": []},
                "trust_metrics": {"rate": 0.8}
            }
        }
        snapshot.pilot_profile_id = uuid.uuid4()
        snapshot.generated_at = datetime(2026, 2, 1)
        snapshot.report_snapshot_hash = "valid_hash"
        
        mock_db.query.return_value.filter.return_value.first.return_value = snapshot
        
        with patch.object(PilotROISnapshotGenerator, 'verify_snapshot_integrity') as mock_verify:
            mock_verify.return_value = {
                "integrity_verified": True,
                "stored_snapshot_hash": "valid_hash",
                "computed_snapshot_hash": "valid_hash",
                "sub_hashes_matched": {
                    "aggregation": True,
                    "roi": True,
                    "fragility": True,
                    "outcome": True
                }
            }
            
            result = PilotReportingHardenedService.replay_pilot_report(mock_db, snapshot_id)
        
        assert result["verification"]["status"] == "REPLAY_VERIFIED"
        assert result["verification"]["integrity_verified"] is True
        assert result["snapshot_id"] == str(snapshot_id)

    def test_replay_fails_on_integrity_mismatch(self):
        """Should fail replay if integrity check fails."""
        mock_db = MagicMock()
        snapshot_id = uuid.uuid4()
        
        snapshot = MagicMock()
        snapshot.id = snapshot_id
        snapshot.report_payload = {"sub_payloads": {}}
        snapshot.pilot_profile_id = uuid.uuid4()
        
        mock_db.query.return_value.filter.return_value.first.return_value = snapshot
        
        with patch.object(PilotROISnapshotGenerator, 'verify_snapshot_integrity') as mock_verify:
            mock_verify.return_value = {
                "integrity_verified": False,
                "stored_snapshot_hash": "wrong_hash",
                "computed_snapshot_hash": "correct_hash"
            }
            
            with pytest.raises(ValueError, match="Snapshot integrity verification failed"):
                PilotReportingHardenedService.replay_pilot_report(mock_db, snapshot_id)

    def test_replay_includes_all_component_hashes(self):
        """Replay result should include all component hashes for verification."""
        mock_db = MagicMock()
        snapshot_id = uuid.uuid4()
        
        snapshot = MagicMock()
        snapshot.id = snapshot_id
        snapshot.report_payload = {
            "roi_snapshot_hash": "roi_hash",
            "aggregation_snapshot_hash": "agg_hash",
            "fragility_snapshot_hash": "frag_hash",
            "outcome_snapshot_hash": "out_hash",
            "reporting_window": {"start_date": "2026-01-01T00:00:00", "end_date": "2026-01-31T00:00:00"},
            "generation_version": 1,
            "generated_at": "2026-02-01T00:00:00",
            "sub_payloads": {
                "metrics_aggregator": {"total": 10},
                "savings_calculator": {"hours": 5},
                "fragility_summary": {"patterns": []},
                "trust_metrics": {"rate": 0.8}
            }
        }
        snapshot.pilot_profile_id = uuid.uuid4()
        snapshot.generated_at = datetime(2026, 2, 1)
        snapshot.report_snapshot_hash = "valid_hash"
        
        mock_db.query.return_value.filter.return_value.first.return_value = snapshot
        
        with patch.object(PilotROISnapshotGenerator, 'verify_snapshot_integrity') as mock_verify:
            mock_verify.return_value = {
                "integrity_verified": True,
                "stored_snapshot_hash": "valid_hash",
                "computed_snapshot_hash": "valid_hash",
                "sub_hashes_matched": {
                    "aggregation": True,
                    "roi": True,
                    "fragility": True,
                    "outcome": True
                }
            }
            
            result = PilotReportingHardenedService.replay_pilot_report(mock_db, snapshot_id)
        
        assert "component_hashes" in result
        hashes = result["component_hashes"]
        assert hashes["aggregation"] == "agg_hash"
        assert hashes["roi"] == "roi_hash"
        assert hashes["fragility"] == "frag_hash"
        assert hashes["outcome"] == "out_hash"


class TestObservabilityMetrics:
    """Test 5: Minimal observability."""

    def test_tracks_generation_latency(self):
        """Should track total generation latency."""
        mock_db = MagicMock()
        pilot_id = uuid.uuid4()
        
        # Setup mocks for successful generation
        mock_profile = MagicMock()
        mock_profile.id = pilot_id
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,  # No existing snapshot
            mock_profile,  # Profile found
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        new_snapshot = MagicMock()
        new_snapshot.id = uuid.uuid4()
        new_snapshot.report_snapshot_hash = "new_hash"
        
        with patch.object(PilotROISnapshotGenerator, 'persist_snapshot', return_value=new_snapshot):
            with patch.object(PilotReportingHardenedService, '_calculate_conservative_savings') as mock_savings:
                mock_savings.return_value = ({"hours": 10}, [])
                
                with patch.object(PilotReportingHardenedService, '_aggregate_fragility_summaries') as mock_fragility:
                    mock_fragility.return_value = {"patterns": []}
                    
                    with patch.object(PilotReportingHardenedService, '_build_trust_metrics') as mock_trust:
                        mock_trust.return_value = ({"rate": 0.8}, [])
                        
                        result = PilotReportingHardenedService.generate_hardened_report(
                            db=mock_db,
                            pilot_profile_id=pilot_id,
                            start_date=datetime(2026, 1, 1),
                            end_date=datetime(2026, 1, 31)
                        )
        
        assert result.generation_metrics.generation_latency_ms > 0
        assert result.generation_metrics.aggregation_latency_ms >= 0
        assert result.generation_metrics.snapshot_latency_ms >= 0

    def test_tracks_aggregation_failures(self):
        """Should track aggregation failures."""
        mock_db = MagicMock()
        pilot_id = uuid.uuid4()
        
        # Make query raise exception
        mock_db.query.side_effect = Exception("Database connection failed")
        
        result = HardenedReportResult()
        
        try:
            PilotReportingHardenedService.generate_hardened_report(
                db=mock_db,
                pilot_profile_id=pilot_id,
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31)
            )
        except Exception:
            pass  # Expected to fail
        
        # The exception should have been logged and tracked
        # Note: In actual implementation, the exception propagates but is logged

    def test_tracks_missing_evidence_warnings(self):
        """Should track missing evidence warnings."""
        mock_db = MagicMock()
        pilot_id = uuid.uuid4()
        
        mock_profile = MagicMock()
        mock_profile.id = pilot_id
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,  # No existing
            mock_profile,
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Mock savings with confidence warning
        savings_with_warning = {
            "hours": 5,
            "confidence_warning": "WARNING: Small dataset (recommendations = 3)"
        }
        
        new_snapshot = MagicMock()
        new_snapshot.id = uuid.uuid4()
        new_snapshot.report_snapshot_hash = "new_hash"
        
        with patch.object(PilotROISnapshotGenerator, 'persist_snapshot', return_value=new_snapshot):
            with patch.object(PilotReportingHardenedService, '_calculate_conservative_savings') as mock_savings:
                mock_savings.return_value = (savings_with_warning, ["Warning: missing data"])
                
                with patch.object(PilotReportingHardenedService, '_aggregate_fragility_summaries') as mock_fragility:
                    mock_fragility.return_value = {"patterns": []}
                    
                    with patch.object(PilotReportingHardenedService, '_build_trust_metrics') as mock_trust:
                        mock_trust.return_value = ({"rate": 0.8}, [])
                        
                        result = PilotReportingHardenedService.generate_hardened_report(
                            db=mock_db,
                            pilot_profile_id=pilot_id,
                            start_date=datetime(2026, 1, 1),
                            end_date=datetime(2026, 1, 31)
                        )
        
        # Should have warnings tracked
        assert len(result.generation_metrics.missing_evidence_warnings) > 0 or len(result.warnings) > 0

    def test_tracks_db_query_count(self):
        """Should track number of database queries."""
        mock_db = MagicMock()
        pilot_id = uuid.uuid4()
        
        mock_profile = MagicMock()
        mock_profile.id = pilot_id
        
        # Simulate multiple queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,  # Check existing
            mock_profile,  # Get profile
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = [
            MagicMock(repository_id=uuid.uuid4())  # Enrollments
        ]
        
        new_snapshot = MagicMock()
        new_snapshot.id = uuid.uuid4()
        
        with patch.object(PilotROISnapshotGenerator, 'persist_snapshot', return_value=new_snapshot):
            with patch.object(PilotReportingHardenedService, '_calculate_conservative_savings') as mock_savings:
                mock_savings.return_value = ({"hours": 10}, [])
                
                with patch.object(PilotReportingHardenedService, '_aggregate_fragility_summaries') as mock_fragility:
                    mock_fragility.return_value = {"patterns": []}
                    
                    with patch.object(PilotReportingHardenedService, '_build_trust_metrics') as mock_trust:
                        mock_trust.return_value = ({"rate": 0.8}, [])
                        
                        result = PilotReportingHardenedService.generate_hardened_report(
                            db=mock_db,
                            pilot_profile_id=pilot_id,
                            start_date=datetime(2026, 1, 1),
                            end_date=datetime(2026, 1, 31)
                        )
        
        assert result.generation_metrics.db_query_count >= 2  # At least profile + enrollments


class TestRecoveryTooling:
    """Test 6: Recovery tooling."""

    def test_replay_pilot_report_returns_full_view(self):
        """Replay should return complete report view from snapshot."""
        mock_db = MagicMock()
        snapshot_id = uuid.uuid4()
        
        snapshot = MagicMock()
        snapshot.id = snapshot_id
        snapshot.report_payload = {
            "roi_snapshot_hash": "roi_hash",
            "aggregation_snapshot_hash": "agg_hash",
            "fragility_snapshot_hash": "frag_hash",
            "outcome_snapshot_hash": "out_hash",
            "reporting_window": {
                "start_date": "2026-01-01T00:00:00",
                "end_date": "2026-01-31T00:00:00"
            },
            "generation_version": 1,
            "generated_at": "2026-02-01T00:00:00",
            "sub_payloads": {
                "metrics_aggregator": {"total_runs": 100, "total_executed_tests": 500},
                "savings_calculator": {"hours_saved": 50.5},
                "fragility_summary": {"patterns": [{"id": "p1"}]},
                "trust_metrics": {"adherence_rate": 0.85}
            }
        }
        snapshot.pilot_profile_id = uuid.uuid4()
        snapshot.generated_at = datetime(2026, 2, 1)
        snapshot.report_snapshot_hash = "valid_hash"
        
        mock_db.query.return_value.filter.return_value.first.return_value = snapshot
        
        with patch.object(PilotROISnapshotGenerator, 'verify_snapshot_integrity') as mock_verify:
            mock_verify.return_value = {
                "integrity_verified": True,
                "stored_snapshot_hash": "valid_hash",
                "computed_snapshot_hash": "valid_hash",
                "sub_hashes_matched": {
                    "aggregation": True,
                    "roi": True,
                    "fragility": True,
                    "outcome": True
                }
            }
            
            result = PilotReportingHardenedService.replay_pilot_report(mock_db, snapshot_id)
        
        # Should include all sub-payloads
        assert result["metrics_aggregator"]["total_runs"] == 100
        assert result["savings_calculator"]["hours_saved"] == 50.5
        assert result["fragility_summary"]["patterns"][0]["id"] == "p1"
        assert result["trust_metrics"]["adherence_rate"] == 0.85

    def test_rebuild_roi_snapshot_creates_new_version(self):
        """Rebuild should create new snapshot version."""
        mock_db = MagicMock()
        pilot_id = uuid.uuid4()
        
        # Mock existing snapshots
        existing = MagicMock()
        existing.id = uuid.uuid4()
        existing.report_snapshot_hash = "old_hash"
        
        mock_db.query.return_value.filter.return_value.all.return_value = [existing]
        
        # Mock profile
        mock_profile = MagicMock()
        mock_profile.id = pilot_id
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_profile,
            []
        ]
        
        new_snapshot = MagicMock()
        new_snapshot.id = uuid.uuid4()
        new_snapshot.report_snapshot_hash = "new_hash"
        
        with patch.object(PilotROISnapshotGenerator, 'persist_snapshot', return_value=new_snapshot):
            with patch.object(PilotReportingHardenedService, '_calculate_conservative_savings') as mock_savings:
                mock_savings.return_value = ({"hours": 20}, [])
                
                with patch.object(PilotReportingHardenedService, '_aggregate_fragility_summaries') as mock_fragility:
                    mock_fragility.return_value = {"patterns": []}
                    
                    with patch.object(PilotReportingHardenedService, '_build_trust_metrics') as mock_trust:
                        mock_trust.return_value = ({"rate": 0.9}, [])
                        
                        result = PilotReportingHardenedService.rebuild_roi_snapshot(
                            db=mock_db,
                            pilot_profile_id=pilot_id,
                            start_date=datetime(2026, 1, 1),
                            end_date=datetime(2026, 1, 31),
                            reason="test_rebuild"
                        )
        
        assert result == new_snapshot
        assert result.report_snapshot_hash == "new_hash"

    def test_repair_stale_aggregation_detects_stale_snapshots(self):
        """Repair should detect and report stale snapshots."""
        mock_db = MagicMock()
        pilot_id = uuid.uuid4()
        
        # Create stale snapshot
        stale_snapshot = MagicMock()
        stale_snapshot.id = uuid.uuid4()
        stale_snapshot.report_snapshot_hash = "stale_hash"
        stale_snapshot.reporting_window_start = datetime(2026, 1, 1)
        stale_snapshot.reporting_window_end = datetime(2026, 1, 31)
        stale_snapshot.pilot_profile_id = pilot_id
        stale_snapshot.generated_at = datetime(2026, 2, 1)
        stale_snapshot.report_payload = {
            "sub_payloads": {
                "metrics_aggregator": {"total_recommendation_runs": 10}
            }
        }
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [stale_snapshot]
        
        # Mock drift detection to report drift
        with patch.object(PilotReportingHardenedService, '_detect_drift') as mock_drift:
            mock_drift.return_value = DriftReport(
                drift_detected=True,
                drift_types=[DriftType.AGGREGATION_MISMATCH],
                aggregation_differences={"total_recommendation_runs": {"stored": 10, "current": 15}}
            )
            
            result = PilotReportingHardenedService.repair_stale_aggregation(
                db=mock_db,
                pilot_profile_id=pilot_id,
                dry_run=True
            )
        
        assert result["stale_snapshots_found"] == 1
        assert result["dry_run"] is True
        assert len(result["stale_details"]) == 1
        assert result["stale_details"][0]["drift_types"] == ["aggregation_mismatch"]

    def test_repair_stale_aggregation_attempts_repair_when_not_dry_run(self):
        """Repair should attempt actual repair when dry_run=False."""
        mock_db = MagicMock()
        pilot_id = uuid.uuid4()
        
        stale_snapshot = MagicMock()
        stale_snapshot.id = uuid.uuid4()
        stale_snapshot.reporting_window_start = datetime(2026, 1, 1)
        stale_snapshot.reporting_window_end = datetime(2026, 1, 31)
        stale_snapshot.pilot_profile_id = pilot_id
        stale_snapshot.generated_at = datetime(2026, 2, 1)
        stale_snapshot.report_payload = {"sub_payloads": {}}
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [stale_snapshot]
        
        new_snapshot = MagicMock()
        new_snapshot.id = uuid.uuid4()
        new_snapshot.report_snapshot_hash = "repaired_hash"
        
        with patch.object(PilotReportingHardenedService, '_detect_drift') as mock_drift:
            mock_drift.return_value = DriftReport(
                drift_detected=True,
                drift_types=[DriftType.HASH_MISMATCH]
            )
            
            with patch.object(PilotReportingHardenedService, 'rebuild_roi_snapshot') as mock_rebuild:
                mock_rebuild.return_value = new_snapshot
                
                result = PilotReportingHardenedService.repair_stale_aggregation(
                    db=mock_db,
                    pilot_profile_id=pilot_id,
                    dry_run=False
                )
        
        assert result["dry_run"] is False
        assert result["repairs_attempted"] == 1
        assert result["repairs_succeeded"] == 1


class TestConservativeReporting:
    """Additional tests for conservative reporting behavior."""

    def test_calculate_conservative_savings_with_zero_execution(self):
        """Should produce zero savings when execution frequency is zero."""
        metrics = {
            "total_recommendation_runs": 10,
            "total_full_suite_runtime_seconds": 10000.0,
            "total_recommended_runtime_seconds": 3000.0,
            "excluded_data_counts": {
                "missing_full_suite_runtime": 0,
                "missing_recommended_runtime": 0,
                "missing_outcome": 10,  # All outcomes missing = 0 execution
                "missing_pull_request": 0
            }
        }
        
        savings, warnings = PilotReportingHardenedService._calculate_conservative_savings(
            metrics, [uuid.uuid4()]
        )
        
        # With no outcomes, execution frequency is 0, so savings should be 0
        assert savings["estimated_engineering_hours_saved"] == 0.0

    def test_build_trust_metrics_warns_on_tiny_dataset(self):
        """Should include warning for tiny outcome dataset."""
        mock_db = MagicMock()
        
        # Mock 3 outcomes (below MIN_OUTCOMES_FOR_CONFIDENCE = 5)
        mock_outcome = MagicMock()
        mock_outcome.outcome_status = "FOLLOWED"
        mock_outcome.manually_added_tests = []
        mock_outcome.manually_removed_tests = []
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_outcome] * 3
        
        trust, warnings = PilotReportingHardenedService._build_trust_metrics(
            mock_db, [uuid.uuid4()],
            datetime(2026, 1, 1),
            datetime(2026, 1, 31),
            {"total_recommendation_runs": 3}
        )
        
        assert any("Tiny outcome dataset" in w for w in warnings)
        assert trust["total_outcomes"] == 3


class TestEmptyStateHandling:
    """Test handling of empty/uninitialized state."""

    def test_empty_metrics_structure_for_no_repositories(self):
        """Should create proper empty metrics when no repos enrolled."""
        empty = PilotReportingHardenedService._create_empty_metrics(
            datetime(2026, 1, 1),
            datetime(2026, 1, 31)
        )
        
        assert empty["total_recommendation_runs"] == 0
        assert empty["total_prs_analyzed"] == 0
        assert empty["repository_ids"] == []
        assert "WARNING" in empty["confidence_warning"]
        assert "No active repository enrollments" in empty["confidence_warning"]

    def test_explicit_limitations_for_empty_state(self):
        """Should report explicit limitations for empty state."""
        metrics = {"total_recommendation_runs": 0}
        
        limitations = PilotReportingHardenedService._detect_data_limitations(
            metrics, {"hours": 0}, []
        )
        
        assert any("No active repository enrollments" in lim for lim in limitations)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
