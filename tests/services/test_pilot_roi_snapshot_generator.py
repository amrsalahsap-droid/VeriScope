import json
import hashlib
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.pilot_roi_snapshot_generator import PilotROISnapshotGenerator
from app.models.pilot import PilotReportSnapshot


class TestCalculateDeterministicHash:
    def test_same_input_produces_same_hash(self):
        data = {"b": 2, "a": 1}
        h1 = PilotROISnapshotGenerator.calculate_deterministic_hash(data)
        h2 = PilotROISnapshotGenerator.calculate_deterministic_hash(data)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex length

    def test_key_order_independence(self):
        h1 = PilotROISnapshotGenerator.calculate_deterministic_hash({"a": 1, "b": 2})
        h2 = PilotROISnapshotGenerator.calculate_deterministic_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_uses_compact_separators(self):
        data = {"a": 1, "b": 2}
        expected = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        assert PilotROISnapshotGenerator.calculate_deterministic_hash(data) == expected


class TestBuildDeterministicHashInput:
    def test_excludes_generated_at(self):
        metrics = {"total": 10, "confidence_warning": "low sample size"}
        savings = {"hours": 5, "excluded_runs_count": 2}
        fragility = {"patterns": [], "aggregation_limitation": "none"}
        trust = {"rate": 0.8, "caveat": "partial lineage"}
        start = datetime(2026, 1, 1, 0, 0, 0)
        end = datetime(2026, 1, 31, 23, 59, 59)

        result = PilotROISnapshotGenerator._build_deterministic_hash_input(
            metrics=metrics,
            savings=savings,
            fragility=fragility,
            trust=trust,
            start_date=start,
            end_date=end,
            generation_version=1
        )

        assert "generated_at" not in result
        assert "aggregation_snapshot_hash" in result
        assert "roi_snapshot_hash" in result
        assert "fragility_snapshot_hash" in result
        assert "outcome_snapshot_hash" in result
        assert result["reporting_window"] == {
            "start_date": "2026-01-01T00:00:00",
            "end_date": "2026-01-31T23:59:59"
        }
        assert result["generation_version"] == 1

    def test_same_evidence_same_hash_input(self):
        metrics = {"a": 1}
        savings = {"b": 2}
        fragility = {"c": 3}
        trust = {"d": 4}
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)

        r1 = PilotROISnapshotGenerator._build_deterministic_hash_input(
            metrics, savings, fragility, trust, start, end, 1
        )
        r2 = PilotROISnapshotGenerator._build_deterministic_hash_input(
            metrics, savings, fragility, trust, start, end, 1
        )
        assert r1 == r2

    def test_preserves_caveats_in_sub_hashes(self):
        metrics = {"warning": "excluded data present", "total": 5}
        savings = {"limitation": "missing baseline", "hours": 0}
        fragility = {"caveat": "incomplete lineage", "patterns": []}
        trust = {"confidence": "low", "rate": 0.5}

        result = PilotROISnapshotGenerator._build_deterministic_hash_input(
            metrics, savings, fragility, trust, datetime(2026, 1, 1), datetime(2026, 1, 31), 1
        )

        # Caveats are preserved inside the sub-hashes because the raw dicts are hashed whole
        assert result["aggregation_snapshot_hash"] == PilotROISnapshotGenerator.calculate_deterministic_hash(metrics)
        assert result["roi_snapshot_hash"] == PilotROISnapshotGenerator.calculate_deterministic_hash(savings)


class TestGenerateSnapshotPayload:
    def test_contains_all_required_fields(self):
        metrics = {"total": 10}
        savings = {"hours": 5}
        fragility = {"patterns": []}
        trust = {"rate": 0.8}
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)

        payload = PilotROISnapshotGenerator.generate_snapshot_payload(
            metrics, savings, fragility, trust, start, end, 1
        )

        assert "roi_snapshot_hash" in payload
        assert "aggregation_snapshot_hash" in payload
        assert "fragility_snapshot_hash" in payload
        assert "outcome_snapshot_hash" in payload
        assert "reporting_window" in payload
        assert "generation_version" in payload
        assert "generated_at" in payload
        assert "sub_payloads" in payload

        sub = payload["sub_payloads"]
        assert "metrics_aggregator" in sub
        assert "savings_calculator" in sub
        assert "fragility_summary" in sub
        assert "trust_metrics" in sub

    def test_generated_at_is_isoformat(self):
        payload = PilotROISnapshotGenerator.generate_snapshot_payload(
            {}, {}, {}, {}, datetime(2026, 1, 1), datetime(2026, 1, 31), 1
        )
        # Should be a valid ISO format string, not empty
        assert isinstance(payload["generated_at"], str)
        assert "T" in payload["generated_at"]


class TestDeterminismRules:
    def test_same_evidence_same_snapshot_hash(self):
        metrics = {"total": 10, "warning": "some exclusion"}
        savings = {"hours": 5}
        fragility = {"patterns": [1, 2, 3]}
        trust = {"rate": 0.8}
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)

        payload1 = PilotROISnapshotGenerator.generate_snapshot_payload(
            metrics, savings, fragility, trust, start, end, 1
        )
        payload2 = PilotROISnapshotGenerator.generate_snapshot_payload(
            metrics, savings, fragility, trust, start, end, 1
        )

        # Strip generated_at and sub_payloads to compare deterministic core
        core1 = {k: v for k, v in payload1.items() if k not in ("generated_at", "sub_payloads")}
        core2 = {k: v for k, v in payload2.items() if k not in ("generated_at", "sub_payloads")}
        assert core1 == core2

        hash1 = PilotROISnapshotGenerator.calculate_deterministic_hash(core1)
        hash2 = PilotROISnapshotGenerator.calculate_deterministic_hash(core2)
        assert hash1 == hash2

    def test_different_evidence_different_hash(self):
        base = ({}, {}, {}, {}, datetime(2026, 1, 1), datetime(2026, 1, 31), 1)

        h1 = PilotROISnapshotGenerator.calculate_deterministic_hash(
            PilotROISnapshotGenerator._build_deterministic_hash_input(
                {"total": 10}, *base[1:]
            )
        )
        h2 = PilotROISnapshotGenerator.calculate_deterministic_hash(
            PilotROISnapshotGenerator._build_deterministic_hash_input(
                {"total": 11}, *base[1:]
            )
        )
        assert h1 != h2


class TestPersistSnapshot:
    def test_persists_with_mock_db(self):
        mock_db = MagicMock()

        # Patch the model symbol where the service imports it
        with patch("app.services.pilot_roi_snapshot_generator.PilotReportSnapshot") as mock_model:
            mock_instance = MagicMock()
            mock_instance.id = uuid.uuid4()
            mock_model.return_value = mock_instance

            PilotROISnapshotGenerator.persist_snapshot(
                db=mock_db,
                pilot_profile_id=uuid.uuid4(),
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31),
                metrics={"total": 10},
                savings={"hours": 5},
                fragility={"patterns": []},
                trust={"rate": 0.8},
                generation_version=2
            )

            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()

            call_kwargs = mock_model.call_args.kwargs
            assert "report_snapshot_hash" in call_kwargs
            assert call_kwargs["report_version"] == 2
            assert call_kwargs["report_payload"]["generation_version"] == 2
            assert "generated_at" in call_kwargs["report_payload"]
            assert "sub_payloads" in call_kwargs["report_payload"]

    def test_hash_is_deterministic_across_calls(self):
        mock_db = MagicMock()
        profile_id = uuid.uuid4()
        args = {
            "pilot_profile_id": profile_id,
            "start_date": datetime(2026, 1, 1),
            "end_date": datetime(2026, 1, 31),
            "metrics": {"total": 10},
            "savings": {"hours": 5},
            "fragility": {"patterns": []},
            "trust": {"rate": 0.8},
            "generation_version": 1
        }

        hashes = []
        for _ in range(3):
            mock_db.reset_mock()
            with patch("app.services.pilot_roi_snapshot_generator.PilotReportSnapshot") as mock_model:
                mock_model.return_value = MagicMock(id=uuid.uuid4())
                PilotROISnapshotGenerator.persist_snapshot(db=mock_db, **args)
                hashes.append(mock_model.call_args.kwargs["report_snapshot_hash"])

        assert hashes[0] == hashes[1] == hashes[2]


class TestVerifySnapshotIntegrity:
    def test_integrity_verified_for_valid_snapshot(self):
        # Build a realistic payload
        metrics = {"total": 10}
        savings = {"hours": 5}
        fragility = {"patterns": []}
        trust = {"rate": 0.8}
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)

        deterministic_input = PilotROISnapshotGenerator._build_deterministic_hash_input(
            metrics, savings, fragility, trust, start, end, 1
        )
        report_hash = PilotROISnapshotGenerator.calculate_deterministic_hash(deterministic_input)

        payload = {
            **deterministic_input,
            "generated_at": datetime.utcnow().isoformat(),
            "sub_payloads": {
                "metrics_aggregator": metrics,
                "savings_calculator": savings,
                "fragility_summary": fragility,
                "trust_metrics": trust
            }
        }

        mock_snapshot = MagicMock()
        mock_snapshot.report_snapshot_hash = report_hash
        mock_snapshot.report_payload = payload

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_snapshot
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        audit = PilotROISnapshotGenerator.verify_snapshot_integrity(mock_db, uuid.uuid4())

        assert audit["integrity_verified"] is True
        assert audit["drift_detected"] is False
        assert all(audit["sub_hashes_matched"].values())

    def test_drift_detected_for_tampered_snapshot(self):
        metrics = {"total": 10}
        savings = {"hours": 5}
        fragility = {"patterns": []}
        trust = {"rate": 0.8}
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)

        deterministic_input = PilotROISnapshotGenerator._build_deterministic_hash_input(
            metrics, savings, fragility, trust, start, end, 1
        )
        report_hash = PilotROISnapshotGenerator.calculate_deterministic_hash(deterministic_input)

        # Tamper with the payload after hashing
        payload = {
            **deterministic_input,
            "roi_snapshot_hash": "tampered_hash",
            "generated_at": datetime.utcnow().isoformat(),
            "sub_payloads": {
                "metrics_aggregator": metrics,
                "savings_calculator": savings,
                "fragility_summary": fragility,
                "trust_metrics": trust
            }
        }

        mock_snapshot = MagicMock()
        mock_snapshot.report_snapshot_hash = report_hash
        mock_snapshot.report_payload = payload

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_snapshot
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        audit = PilotROISnapshotGenerator.verify_snapshot_integrity(mock_db, uuid.uuid4())

        assert audit["integrity_verified"] is False
        assert audit["drift_detected"] is True
        assert audit["sub_hashes_matched"]["roi"] is False
        assert audit["sub_hashes_matched"]["aggregation"] is True

    def test_raises_when_snapshot_missing(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError, match="No PilotReportSnapshot exists"):
            PilotROISnapshotGenerator.verify_snapshot_integrity(mock_db, uuid.uuid4())
