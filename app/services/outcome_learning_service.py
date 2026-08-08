"""
Outcome Learning Service

Handles post-decision outcome event ingestion, label management, summary recomputations, and analytics.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.outcome_event import OutcomeEvent
from app.models.outcome_label import OutcomeLabel
from app.models.recommendation_outcome_summary import RecommendationOutcomeSummary
from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest
from app.models.pipeline_run import PipelineRun
from app.models.repository import Repository
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService
from app.schemas.outcome_learning import OutcomeEventCreate, OutcomeLabelCreate


# Recursive secret scrubbing keys
REDACT_KEYS = {
    "token", "authorization", "password", "secret", "key", "jwt", 
    "apikey", "api_key", "pwd", "auth", "signature", "credential",
    "connection", "private"
}


class OutcomeLearningService:
    """Service for Outcome Learning events, labels, summaries, and metrics."""

    @staticmethod
    def redact_metadata(data: Any) -> Any:
        """Recursively redact credentials, headers, and secrets before persistence."""
        if isinstance(data, dict):
            redacted = {}
            for k, v in data.items():
                k_lower = k.lower()
                if any(rk in k_lower for rk in REDACT_KEYS):
                    redacted[k] = "***REDACTED***"
                else:
                    redacted[k] = OutcomeLearningService.redact_metadata(v)
            return redacted
        elif isinstance(data, list):
            return [OutcomeLearningService.redact_metadata(item) for item in data]
        else:
            return data

    @staticmethod
    def check_idempotency(
        db: Session,
        workspace_id: UUID,
        repository_id: UUID,
        event_in: OutcomeEventCreate
    ) -> Optional[OutcomeEvent]:
        """Check if an event with the same signature or external event ID already exists."""
        if event_in.external_event_id:
            existing = db.query(OutcomeEvent).filter(
                OutcomeEvent.workspace_id == workspace_id,
                OutcomeEvent.repository_id == repository_id,
                OutcomeEvent.external_event_id == event_in.external_event_id
            ).first()
            if existing:
                return existing

        # Stable signature deduplication
        query = db.query(OutcomeEvent).filter(
            OutcomeEvent.workspace_id == workspace_id,
            OutcomeEvent.repository_id == repository_id,
            OutcomeEvent.event_type == event_in.event_type,
            OutcomeEvent.event_source == event_in.event_source
        )
        if event_in.pull_request_id:
            query = query.filter(OutcomeEvent.pull_request_id == event_in.pull_request_id)
        if event_in.pipeline_run_id:
            query = query.filter(OutcomeEvent.pipeline_run_id == event_in.pipeline_run_id)
        if event_in.commit_sha:
            query = query.filter(OutcomeEvent.commit_sha == event_in.commit_sha)
        if event_in.occurred_at:
            query = query.filter(OutcomeEvent.occurred_at == event_in.occurred_at)

        return query.first()

    @staticmethod
    def ingest_event(
        db: Session,
        workspace_id: UUID,
        repository_id: UUID,
        event_in: OutcomeEventCreate,
        actor_user_id: Optional[UUID] = None
    ) -> OutcomeEvent:
        """
        Ingest a post-decision outcome event, applying strict linking and idempotency rules.
        """
        # Redact secrets before database write
        scrubbed_metadata = OutcomeLearningService.redact_metadata(event_in.metadata_json or {})

        # 1. Idempotency Check
        existing_event = OutcomeLearningService.check_idempotency(db, workspace_id, repository_id, event_in)
        if existing_event:
            return existing_event

        # 2. Strict Linking Rules
        linked_run_id = None
        unresolved_reason = None
        
        # Determine candidate recommendation runs
        run_candidates_query = db.query(RecommendationRun).filter(
            RecommendationRun.workspace_id == workspace_id,
            RecommendationRun.repository_id == repository_id
        )

        # Build candidate filter criteria
        filters = []
        if event_in.commit_sha:
            # Match commit SHA
            filters.append(RecommendationRun.recommendation_snapshot_hash == event_in.commit_sha)
        
        if event_in.pull_request_id:
            filters.append(RecommendationRun.pull_request_id == event_in.pull_request_id)
        elif event_in.github_pr_number:
            # Resolve pull request ID first
            pr = db.query(PullRequest).filter(
                PullRequest.workspace_id == workspace_id,
                PullRequest.repository_id == repository_id,
                PullRequest.number == event_in.github_pr_number
            ).first()
            if pr:
                filters.append(RecommendationRun.pull_request_id == pr.id)

        # Apply matching filters
        if filters:
            for f in filters:
                run_candidates_query = run_candidates_query.filter(f)
            
            candidates = run_candidates_query.all()
            
            if len(candidates) == 1:
                linked_run_id = candidates[0].id
            elif len(candidates) > 1:
                unresolved_reason = "Ambiguous match: multiple matching recommendation runs found."
            else:
                unresolved_reason = "No matching recommendation runs found for the provided PR/commit filters."
        else:
            unresolved_reason = "Insufficient details to perform recommendation run linking."

        # Audit unresolved reason if link is ambiguous or missing
        audit_reason = "Resolved and linked" if linked_run_id else f"Unresolved: {unresolved_reason}"

        # 3. Create OutcomeEvent
        event = OutcomeEvent(
            workspace_id=workspace_id,
            repository_id=repository_id,
            pull_request_id=event_in.pull_request_id,
            pipeline_run_id=event_in.pipeline_run_id,
            recommendation_run_id=linked_run_id,
            github_pr_number=event_in.github_pr_number,
            commit_sha=event_in.commit_sha,
            event_type=event_in.event_type,
            event_source=event_in.event_source,
            event_status=event_in.event_status,
            severity=event_in.severity,
            occurred_at=event_in.occurred_at or datetime.utcnow(),
            detected_at=datetime.utcnow(),
            external_event_id=event_in.external_event_id,
            metadata_json=scrubbed_metadata
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # 4. Log Audit Event
        WorkspaceGovernanceAuditService.log_outcome_learning_event(
            db=db,
            workspace_id=workspace_id,
            actor_id=actor_user_id or workspace_id, # Fallback to workspace UUID if system
            event_type="OUTCOME_EVENT_CREATED",
            repository_id=repository_id,
            recommendation_run_id=linked_run_id,
            pipeline_run_id=event_in.pipeline_run_id,
            reason=audit_reason,
            metadata=scrubbed_metadata
        )

        # 5. Recompute summary if linked
        if linked_run_id:
            OutcomeLearningService.recompute_summary(db, linked_run_id)

        return event

    @staticmethod
    def create_label(
        db: Session,
        workspace_id: UUID,
        repository_id: UUID,
        recommendation_run_id: UUID,
        label_in: OutcomeLabelCreate,
        creator_id: Optional[UUID] = None
    ) -> OutcomeLabel:
        """
        Create or update a human/system label for a recommendation run.
        """
        # Verify run exists and belongs to workspace/repository
        run = db.query(RecommendationRun).filter(
            RecommendationRun.id == recommendation_run_id,
            RecommendationRun.workspace_id == workspace_id,
            RecommendationRun.repository_id == repository_id
        ).first()
        if not run:
            # Audit and raise exception
            WorkspaceGovernanceAuditService.log_outcome_learning_event(
                db=db,
                workspace_id=workspace_id,
                actor_id=creator_id or workspace_id,
                event_type="OUTCOME_LABEL_REJECTED",
                repository_id=repository_id,
                recommendation_run_id=recommendation_run_id,
                decision="REJECTED",
                reason="Recommendation run not found or scoping isolation mismatch"
            )
            raise ValueError("Recommendation run not found or does not belong to the workspace/repository context.")

        # Scrub metadata json
        scrubbed_metadata = OutcomeLearningService.redact_metadata(label_in.metadata_json or {})

        # Handle duplicate labels: version by updating in-place (latest version decision)
        label = db.query(OutcomeLabel).filter(
            OutcomeLabel.recommendation_run_id == recommendation_run_id,
            OutcomeLabel.label_type == label_in.label_type,
            OutcomeLabel.source == "human"
        ).first()

        if label:
            # Update existing label
            label.label_value = label_in.label_value
            label.confidence = label_in.confidence
            label.created_by_user_id = creator_id
            label.created_at = datetime.utcnow()
            label.metadata_json = scrubbed_metadata
        else:
            # Create new label
            label = OutcomeLabel(
                workspace_id=workspace_id,
                repository_id=repository_id,
                recommendation_run_id=recommendation_run_id,
                label_type=label_in.label_type,
                label_value=label_in.label_value,
                confidence=label_in.confidence,
                source="human",
                created_by_user_id=creator_id,
                created_at=datetime.utcnow(),
                metadata_json=scrubbed_metadata
            )
            db.add(label)

        db.commit()
        db.refresh(label)

        # Log Audit Event
        WorkspaceGovernanceAuditService.log_outcome_learning_event(
            db=db,
            workspace_id=workspace_id,
            actor_id=creator_id or workspace_id,
            event_type="OUTCOME_LABEL_CREATED",
            repository_id=repository_id,
            recommendation_run_id=recommendation_run_id,
            label_type=label_in.label_type,
            decision=label_in.label_value,
            reason="Outcome label created or updated",
            metadata=scrubbed_metadata
        )

        # Recompute summary
        OutcomeLearningService.recompute_summary(db, recommendation_run_id)

        return label

    @staticmethod
    def recompute_summary(db: Session, recommendation_run_id: UUID) -> Optional[RecommendationOutcomeSummary]:
        """
        Recompute the outcome summary for a specific recommendation run.
        Does not mutate the original RecommendationRun evidence.
        """
        run = db.query(RecommendationRun).filter(RecommendationRun.id == recommendation_run_id).first()
        if not run:
            return None

        # Fetch events and labels
        events = db.query(OutcomeEvent).filter(OutcomeEvent.recommendation_run_id == recommendation_run_id).all()
        labels = db.query(OutcomeLabel).filter(OutcomeLabel.recommendation_run_id == recommendation_run_id).all()

        # Derived fields
        merged = any(e.event_type == "PR_MERGED" for e in events)
        reverted = any(e.event_type == "PR_REVERTED" for e in events)
        deployment_failed = any(e.event_type == "DEPLOYMENT_FAILED" for e in events)
        incident_found = any(e.event_type == "INCIDENT_REPORTED" for e in events)
        bug_found = any(e.event_type == "BUG_REPORTED" for e in events)
        regression_found = any(e.event_type == "REGRESSION_FOUND" for e in events)
        
        # Check missed tests
        missed_critical = any(
            (e.event_type == "TEST_FAILURE_FOUND" and e.severity == "CRITICAL") or
            (l.label_type == "missed_required_test" and l.label_value == "true")
            for e in events for l in labels
        ) or any(l.label_type == "missed_required_test" and l.label_value == "true" for l in labels)
        
        missed_high = any(
            (e.event_type == "TEST_FAILURE_FOUND" and e.severity == "HIGH") or
            (l.label_type == "missed_high_test" and l.label_value == "true")
            for e in events for l in labels
        ) or any(l.label_type == "missed_high_test" and l.label_value == "true" for l in labels)

        # Classifications from labels
        scope_accuracy = None
        for l in labels:
            if l.label_type in ("regression_scope_accurate", "regression_scope_too_large", "regression_scope_too_small"):
                if l.label_value == "true":
                    scope_accuracy = l.label_type.replace("regression_scope_", "")
                elif l.label_type == "regression_scope_accurate" and l.label_value == "accurate":
                    scope_accuracy = "accurate"
                elif l.label_type == "regression_scope_too_large" and l.label_value == "too_large":
                    scope_accuracy = "too_large"
                elif l.label_type == "regression_scope_too_small" and l.label_value == "too_small":
                    scope_accuracy = "too_small"
        
        quality_gate_accuracy = None
        for l in labels:
            if l.label_type in ("quality_gate_correct", "quality_gate_incorrect"):
                if l.label_value == "true":
                    quality_gate_accuracy = l.label_type.replace("quality_gate_", "")
                elif l.label_value in ("correct", "incorrect"):
                    quality_gate_accuracy = l.label_value

        # Find or create summary
        summary = db.query(RecommendationOutcomeSummary).filter(
            RecommendationOutcomeSummary.recommendation_run_id == recommendation_run_id
        ).first()

        # Resolve pipeline run ID
        pipeline_run_id = None
        pr_event = next((e for e in events if e.pipeline_run_id), None)
        if pr_event:
            pipeline_run_id = pr_event.pipeline_run_id
        else:
            # Try finding a PipelineRun linked to PR or Commit
            pipe = db.query(PipelineRun).filter(
                PipelineRun.repository_id == run.repository_id,
                PipelineRun.commit_sha == run.recommendation_snapshot_hash
            ).first()
            if pipe:
                pipeline_run_id = pipe.id

        if not summary:
            summary = RecommendationOutcomeSummary(
                recommendation_run_id=recommendation_run_id,
                pipeline_run_id=pipeline_run_id,
                workspace_id=run.workspace_id,
                repository_id=run.repository_id,
                pull_request_id=run.pull_request_id,
                github_pr_number=run.pull_request.number if run.pull_request else None,
                commit_sha=run.recommendation_snapshot_hash,
                merged=merged,
                reverted=reverted,
                deployment_failed=deployment_failed,
                incident_found=incident_found,
                bug_found=bug_found,
                regression_found=regression_found,
                missed_critical_test=missed_critical,
                missed_high_test=missed_high,
                scope_accuracy=scope_accuracy,
                quality_gate_accuracy=quality_gate_accuracy,
                learning_status="PROCESSED"
            )
            db.add(summary)
        else:
            summary.pipeline_run_id = pipeline_run_id or summary.pipeline_run_id
            summary.merged = merged
            summary.reverted = reverted
            summary.deployment_failed = deployment_failed
            summary.incident_found = incident_found
            summary.bug_found = bug_found
            summary.regression_found = regression_found
            summary.missed_critical_test = missed_critical
            summary.missed_high_test = missed_high
            summary.scope_accuracy = scope_accuracy or summary.scope_accuracy
            summary.quality_gate_accuracy = quality_gate_accuracy or summary.quality_gate_accuracy
            summary.learning_status = "PROCESSED"

        db.commit()
        db.refresh(summary)

        # Log summary recomputed audit event
        WorkspaceGovernanceAuditService.log_outcome_learning_event(
            db=db,
            workspace_id=run.workspace_id,
            actor_id=run.workspace_id,
            event_type="OUTCOME_SUMMARY_RECOMPUTED",
            repository_id=run.repository_id,
            recommendation_run_id=recommendation_run_id,
            decision="PROCESSED",
            reason="Summary recomputation completed deterministically"
        )

        return summary

    @staticmethod
    def get_analytics(db: Session, workspace_id: UUID) -> Dict[str, float]:
        """
        Calculate outcome learning metrics for a workspace.
        """
        summaries = db.query(RecommendationOutcomeSummary).filter(
            RecommendationOutcomeSummary.workspace_id == workspace_id
        ).all()
        
        labels = db.query(OutcomeLabel).filter(
            OutcomeLabel.workspace_id == workspace_id
        ).all()

        total_runs = len(summaries)
        if total_runs == 0:
            return {
                "recommendation_accuracy": 1.0,  # Safe default when no data
                "quality_gate_accuracy": 1.0,
                "regression_scope_accuracy": 1.0,
                "safe_to_skip_accuracy": 1.0,
                "post_merge_failure_rate": 0.0,
                "post_deployment_failure_rate": 0.0,
                "revert_rate": 0.0,
                "incident_linked_rate": 0.0
            }

        # 1. Recommendation Accuracy
        # (Total - Incorrect) / Total
        # Incorrect is runs linked to incident/bug/revert, or explicitly labeled recommendation_too_strict / recommendation_too_lenient.
        incorrect_runs = 0
        for s in summaries:
            if s.incident_found or s.bug_found or s.reverted:
                incorrect_runs += 1
            elif s.quality_gate_accuracy == "incorrect":
                incorrect_runs += 1
        
        # Double check labels
        too_strict_count = sum(1 for l in labels if l.label_type == "recommendation_too_strict" and l.label_value == "true")
        too_lenient_count = sum(1 for l in labels if l.label_type == "recommendation_too_lenient" and l.label_value == "true")
        
        total_incorrect = max(incorrect_runs, too_strict_count + too_lenient_count)
        recommendation_accuracy = max(0.0, (total_runs - total_incorrect) / total_runs)

        # 2. Quality Gate Accuracy
        correct_qg = sum(1 for l in labels if l.label_type == "quality_gate_correct" and l.label_value in ("true", "correct"))
        incorrect_qg = sum(1 for l in labels if l.label_type == "quality_gate_incorrect" and l.label_value in ("true", "incorrect"))
        total_qg = correct_qg + incorrect_qg
        quality_gate_accuracy = correct_qg / total_qg if total_qg > 0 else 1.0

        # 3. Regression Scope Accuracy
        accurate_scope = sum(1 for l in labels if l.label_type == "regression_scope_accurate" and l.label_value in ("true", "accurate"))
        too_large_scope = sum(1 for l in labels if l.label_type == "regression_scope_too_large" and l.label_value in ("true", "too_large"))
        too_small_scope = sum(1 for l in labels if l.label_type == "regression_scope_too_small" and l.label_value in ("true", "too_small"))
        total_scope = accurate_scope + too_large_scope + too_small_scope
        regression_scope_accuracy = accurate_scope / total_scope if total_scope > 0 else 1.0

        # 4. Safe-to-Skip Accuracy
        safe_correct = sum(1 for l in labels if l.label_type == "safe_to_skip_correct" and l.label_value in ("true", "correct"))
        safe_incorrect = sum(1 for l in labels if l.label_type == "safe_to_skip_incorrect" and l.label_value in ("true", "incorrect"))
        total_safe = safe_correct + safe_incorrect
        safe_to_skip_accuracy = safe_correct / total_safe if total_safe > 0 else 1.0

        # 5. Post-Merge Failure Rate
        merged_runs = [s for s in summaries if s.merged]
        total_merged = len(merged_runs)
        failures_post_merge = sum(1 for s in merged_runs if s.deployment_failed or s.incident_found or s.bug_found)
        post_merge_failure_rate = failures_post_merge / total_merged if total_merged > 0 else 0.0

        # 6. Post-Deployment Failure Rate
        # Estimated based on deployment failed events divided by total merge events that deployed
        total_deployments = sum(1 for s in summaries if s.merged or s.deployment_failed)
        failures_post_deploy = sum(1 for s in summaries if s.deployment_failed)
        post_deployment_failure_rate = failures_post_deploy / total_deployments if total_deployments > 0 else 0.0

        # 7. Revert Rate
        reverted_count = sum(1 for s in merged_runs if s.reverted)
        revert_rate = reverted_count / total_merged if total_merged > 0 else 0.0

        # 8. Incident-linked Rate
        incidents_count = sum(1 for s in summaries if s.incident_found)
        incident_linked_rate = incidents_count / total_runs

        return {
            "recommendation_accuracy": round(recommendation_accuracy, 4),
            "quality_gate_accuracy": round(quality_gate_accuracy, 4),
            "regression_scope_accuracy": round(regression_scope_accuracy, 4),
            "safe_to_skip_accuracy": round(safe_to_skip_accuracy, 4),
            "post_merge_failure_rate": round(post_merge_failure_rate, 4),
            "post_deployment_failure_rate": round(post_deployment_failure_rate, 4),
            "revert_rate": round(revert_rate, 4),
            "incident_linked_rate": round(incident_linked_rate, 4)
        }
