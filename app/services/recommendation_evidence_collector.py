import uuid
from datetime import datetime
from typing import Any, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.pull_request import PullRequest, PullRequestChangedFile, PullRequestSnapshot
from app.schemas.recommendation import ChangedFile, PREvidenceBundle


class RecommendationEvidenceCollector:
    @staticmethod
    def collect_pr_evidence(db: Session, repository_id: uuid.UUID, pull_request_id: Any) -> PREvidenceBundle:
        """
        Collect changed files and PR evidence safely from local database.
        Detects insufficient PR evidence, returns changed files deterministically sorted,
        and evaluates safety flags and readiness diagnostics.
        """
        db_pr = None

        # 1. Try UUID lookup if possible
        if isinstance(pull_request_id, uuid.UUID):
            db_pr = db.query(PullRequest).filter(
                PullRequest.repository_id == repository_id,
                PullRequest.id == pull_request_id
            ).first()
        elif isinstance(pull_request_id, str):
            try:
                pr_uuid = uuid.UUID(pull_request_id)
                db_pr = db.query(PullRequest).filter(
                    PullRequest.repository_id == repository_id,
                    PullRequest.id == pr_uuid
                ).first()
            except ValueError:
                pass

        # 2. Fallback lookups by number/head SHA
        if not db_pr:
            if isinstance(pull_request_id, int):
                db_pr = db.query(PullRequest).filter(
                    PullRequest.repository_id == repository_id,
                    PullRequest.number == pull_request_id
                ).first()
            elif isinstance(pull_request_id, str):
                if pull_request_id.isdigit():
                    db_pr = db.query(PullRequest).filter(
                        PullRequest.repository_id == repository_id,
                        PullRequest.number == int(pull_request_id)
                    ).first()
                if not db_pr:
                    db_pr = db.query(PullRequest).filter(
                        PullRequest.repository_id == repository_id,
                        PullRequest.head_commit_sha == pull_request_id
                    ).first()

        # If pull request is not found, raise a clean HTTPException
        if not db_pr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pull Request with ID/number/SHA '{pull_request_id}' not found."
            )

        # Retrieve changed files sorted deterministically by file_path
        changed_files_db = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == db_pr.id
        ).order_by(PullRequestChangedFile.file_path.asc()).all()

        changed_files = [
            ChangedFile(
                file_path=f.file_path,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                previous_filename=f.previous_filename
            )
            for f in changed_files_db
        ]

        # Rule 5: Fetch latest PR snapshot if available to bind its ID
        latest_snapshot = db.query(PullRequestSnapshot).filter(
            PullRequestSnapshot.pull_request_id == db_pr.id
        ).order_by(PullRequestSnapshot.created_at.desc()).first()

        pr_snapshot_id = latest_snapshot.id if latest_snapshot else None

        # Gather safety properties and readiness diagnostics
        unsafe_for_optimization = db_pr.unsafe_for_optimization or False
        readiness_reasons = []

        # Rule 1: If PullRequest.sync_integrity_status is FAILED or PARTIAL_FAILURE
        if db_pr.sync_integrity_status in ("FAILED", "PARTIAL_FAILURE"):
            readiness_reasons.append(f"PR sync integrity is {db_pr.sync_integrity_status}.")
            if not changed_files:
                unsafe_for_optimization = True
                readiness_reasons.append("Changed files are missing due to sync integrity failure.")

        # Rule 2: If PullRequest.evidence_health_status is INSUFFICIENT
        if db_pr.evidence_health_status == "INSUFFICIENT":
            readiness_reasons.append("PR evidence health status is INSUFFICIENT.")

        # Rule 3: If changed files list is empty
        if not changed_files:
            unsafe_for_optimization = True
            if "No changed files available from PR evidence." not in readiness_reasons:
                readiness_reasons.append("No changed files available from PR evidence.")

        # Rule 4: If evidence_truncated is True
        if db_pr.evidence_truncated:
            unsafe_for_optimization = True
            trunc_reason = db_pr.truncation_reason or "Unknown truncation reason"
            readiness_reasons.append(f"PR evidence is truncated. Reason: {trunc_reason}")

        # fresh snapshot expiration check
        is_stale = False
        if latest_snapshot:
            if latest_snapshot.evidence_expires_at and latest_snapshot.evidence_expires_at < datetime.utcnow():
                is_stale = True
                readiness_reasons.append("Pull request snapshot evidence is stale and expired.")
            if db_pr.head_commit_sha != latest_snapshot.head_commit_sha:
                readiness_reasons.append("Snapshot head SHA does not match current PR head SHA.")

        if db_pr.evidence_consistency_status == "PARTIALLY_INCONSISTENT":
            readiness_reasons.append("Evidence is partially inconsistent: missing coverage mapping for changed files.")
        elif db_pr.evidence_consistency_status == "BROKEN":
            readiness_reasons.append("Evidence consistency verification is broken.")

        # Resolve overall state
        if db_pr.evidence_health_status == "INSUFFICIENT" or unsafe_for_optimization or db_pr.sync_integrity_status in ("FAILED", "UNKNOWN") or db_pr.evidence_consistency_status == "BROKEN":
            recommendation_readiness_state = "NOT_READY"
        elif db_pr.evidence_health_status == "DEGRADED" or is_stale or db_pr.sync_integrity_status == "PARTIAL_FAILURE" or db_pr.evidence_consistency_status == "PARTIALLY_INCONSISTENT":
            recommendation_readiness_state = "READY_WITH_WARNINGS"
        else:
            recommendation_readiness_state = "READY"

        return PREvidenceBundle(
            pull_request_id=db_pr.id,
            repository_id=db_pr.repository_id,
            head_commit_sha=db_pr.head_commit_sha,
            changed_files=changed_files,
            pr_snapshot_id=pr_snapshot_id,
            sync_integrity_status=db_pr.sync_integrity_status,
            evidence_health_status=db_pr.evidence_health_status,
            unsafe_for_optimization=unsafe_for_optimization,
            recommendation_readiness_state=recommendation_readiness_state,
            readiness_reasons=readiness_reasons
        )
