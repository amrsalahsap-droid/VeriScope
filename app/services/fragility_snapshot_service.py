import uuid
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.fragility_pattern import FragilitySnapshot, FragilityPattern, FragilityEvidenceLink

logger = logging.getLogger(__name__)

class FragilitySnapshotService:
    """
    Service responsible for generating deterministic, immutable fragility snapshots 
    and resolving full audit lineages for historically synced organizational patterns.
    """
    GENERATION_VERSION = "v1.2.0"
    SCORING_VERSION = "weighted.v2"

    def __init__(self, db: Session):
        self.db = db

    def generate_fragility_snapshot(
        self,
        repository_id: uuid.UUID,
        recommendation_run_id: uuid.UUID = None,
        trigger: str = "MANUAL_RECALCULATION"
    ) -> FragilitySnapshot:
        """
        Deterministically compiles and persists an immutable snapshot of all active fragility patterns
        for the given repository, resolving full lineage and calculating reproducible hashes.
        """
        logger.info(f"Generating deterministic fragility snapshot for repository {repository_id}...")

        # 1. Query active fragility patterns
        active_patterns = self.db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repository_id,
            FragilityPattern.status == "ACTIVE"
        ).all()

        total_p = self.db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repository_id
        ).count()

        active_p = len(active_patterns)

        stale_p = self.db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repository_id,
            FragilityPattern.status == "STALE"
        ).count()

        # 2. Collect pattern IDs and hashes, sorting deterministically
        active_pattern_ids = sorted([str(p.id) for p in active_patterns])
        pattern_hashes = sorted([p.pattern_hash for p in active_patterns if p.pattern_hash])

        # 3. Determine evidence window dynamically from active patterns
        timestamps = [p.last_seen_at for p in active_patterns if p.last_seen_at]
        if timestamps:
            start_date = min(timestamps).isoformat()
            end_date = max(timestamps).isoformat()
        else:
            now = datetime.utcnow()
            start_date = (now - timedelta(days=30)).isoformat()
            end_date = now.isoformat()

        evidence_window = {
            "start": start_date,
            "end": end_date
        }

        # 4. Generate deterministic snapshot hash
        evidence_window_str = str(sorted(evidence_window.items()))
        raw_snapshot_payload = (
            f"ids:{active_pattern_ids}|"
            f"hashes:{pattern_hashes}|"
            f"scoring:{self.SCORING_VERSION}|"
            f"gen:{self.GENERATION_VERSION}|"
            f"window:{evidence_window_str}"
        )
        snapshot_hash = hashlib.sha256(raw_snapshot_payload.encode("utf-8")).hexdigest()

        # 5. Create immutable snapshot record
        snapshot = FragilitySnapshot(
            id=uuid.uuid4(),
            repository_id=repository_id,
            recommendation_run_id=recommendation_run_id,
            snapshot_hash=snapshot_hash,
            generated_at=datetime.utcnow(),
            total_patterns=total_p,
            active_patterns=active_p,
            stale_patterns=stale_p,
            generation_version=self.GENERATION_VERSION,
            scoring_version=self.SCORING_VERSION,
            evidence_window=evidence_window,
            generation_trigger=trigger,
            snapshot_metadata={
                "total_patterns_mined": total_p,
                "active_patterns_count": active_p
            },
            active_pattern_ids=active_pattern_ids,
            pattern_hashes=pattern_hashes,
            created_at=datetime.utcnow()
        )

        self.db.add(snapshot)
        self.db.commit()

        logger.info(f"Successfully generated fragility snapshot {snapshot.id} with hash {snapshot_hash}.")
        return snapshot

    def get_snapshot_lineage(self, snapshot_id: uuid.UUID) -> Dict[str, Any]:
        """
        Resolves full historical evidence lineage for a given snapshot, querying all associated
        patterns and their underlying evidence link ledgers.
        """
        snapshot = self.db.query(FragilitySnapshot).filter(FragilitySnapshot.id == snapshot_id).first()
        if not snapshot:
            raise ValueError(f"FragilitySnapshot with ID {snapshot_id} not found.")

        # Query all associated patterns using active_pattern_ids stored in the snapshot
        # Since active_pattern_ids is a JSONB list of UUID strings:
        pattern_uuids = [uuid.UUID(pid) for pid in snapshot.active_pattern_ids]
        
        patterns = []
        if pattern_uuids:
            patterns = self.db.query(FragilityPattern).filter(FragilityPattern.id.in_(pattern_uuids)).all()

        patterns_lineage = []
        for p in patterns:
            # Query evidence links for each pattern
            evidence_links = self.db.query(FragilityEvidenceLink).filter(
                FragilityEvidenceLink.fragility_pattern_id == p.id
            ).all()

            links_list = []
            for link in evidence_links:
                links_list.append({
                    "evidence_link_id": str(link.id),
                    "evidence_type": link.evidence_type,
                    "source_test_run_id": str(link.source_test_run_id) if link.source_test_run_id else None,
                    "source_test_result_id": str(link.source_test_result_id) if link.source_test_result_id else None,
                    "source_incident_id": link.source_incident_id,
                    "source_pull_request_id": str(link.source_pull_request_id) if link.source_pull_request_id else None,
                    "evidence_summary": link.evidence_summary
                })

            patterns_lineage.append({
                "pattern_id": str(p.id),
                "pattern_type": p.pattern_type,
                "normalized_pattern_key": p.normalized_pattern_key,
                "title": p.title,
                "explanation": p.explanation,
                "fragility_score": p.fragility_score,
                "risk_level": p.risk_level,
                "evidence_count": p.evidence_count,
                "evidence_links": links_list
            })

        return {
            "snapshot_id": str(snapshot.id),
            "repository_id": str(snapshot.repository_id),
            "recommendation_run_id": str(snapshot.recommendation_run_id) if snapshot.recommendation_run_id else None,
            "snapshot_hash": snapshot.snapshot_hash,
            "generated_at": snapshot.generated_at.isoformat(),
            "total_patterns": snapshot.total_patterns,
            "active_patterns": snapshot.active_patterns,
            "stale_patterns": snapshot.stale_patterns,
            "generation_version": snapshot.generation_version,
            "scoring_version": snapshot.scoring_version,
            "evidence_window": snapshot.evidence_window,
            "generation_trigger": snapshot.generation_trigger,
            "patterns": patterns_lineage
        }
