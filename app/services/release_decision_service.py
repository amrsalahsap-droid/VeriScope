"""Release Decision Service - Governance workflow for release approval/rejection."""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.release_decision import ReleaseDecision
from app.models.release_decision_history import ReleaseDecisionHistory
from app.models.recommendation import RecommendationRun
from app.models.user import User
from app.services.risk_based_regression.risk_scoring_service import RiskScoringService


class ReleaseDecisionService:
    """Service for managing release decision governance workflow."""

    # Health statuses that block release decisions
    BLOCKING_HEALTH_STATUSES = {
        "STALE_INPUTS",
        "INTERNAL_EVIDENCE_MODEL_INCONSISTENT",
        "REQUIRES_REGENERATION",
    }

    # Allowed health statuses for release approval
    ALLOWED_HEALTH_STATUSES = {
        "VALIDATION_PASSED_COVERAGE_INCOMPLETE",
        "VALIDATION_PASSED_TRACEABILITY_INCOMPLETE",
        "READY",
    }

    @staticmethod
    def derive_readiness_state_from_health(
        health: str,
        fallback: str | None = None
    ) -> str:
        """
        Derive readiness state from evidence health status.
        
        Maps backend health enum to readiness state for storage in ReleaseDecision.
        This ensures readiness_state is not stale when evidence_health_status changes.
        
        Args:
            health: Evidence health status from EvidenceHealthEvaluator
            fallback: Fallback readiness state if health is unknown (backward compat)
        
        Returns:
            Readiness state string (READY, NOT_READY, NEEDS_REVIEW, BLOCKED)
        """
        # Mapping from health enum to readiness state
        health_to_readiness = {
            "READY": "READY",
            "READY_WITH_GAPS": "READY",
            "READY_WITH_TRACEABILITY_ISSUES": "READY",
            "VALIDATION_PASSED_COVERAGE_INCOMPLETE": "NOT_READY",
            "VALIDATION_PASSED_TRACEABILITY_INCOMPLETE": "NOT_READY",
            "NEEDS_TRACEABILITY_REVIEW": "NEEDS_REVIEW",
            "BLOCKED_BY_FAILED_TESTS": "BLOCKED",
            "BLOCKED_BY_SKIPPED_REQUIRED_TESTS": "BLOCKED",
            "BLOCKED_BY_FAILED_OR_SKIPPED_TESTS": "BLOCKED",
            "VALIDATION_FAILED": "BLOCKED",
            "STALE_INPUTS": "BLOCKED",
            "INTERNAL_EVIDENCE_MODEL_INCONSISTENT": "BLOCKED",
            "INSUFFICIENT_INPUT": "NOT_READY",
            "BLOCKED": "BLOCKED",
        }
        
        derived = health_to_readiness.get(health)
        if derived:
            return derived
        
        # Fallback to provided fallback or default to NEEDS_REVIEW for unknown states
        return fallback if fallback else "NEEDS_REVIEW"

    @staticmethod
    def get_snapshot_hash(run: RecommendationRun) -> str:
        """Get the current evidence snapshot hash for a recommendation run."""
        return run.evidence_fingerprint or str(run.id)

    @staticmethod
    def get_release_state(db: Session, run_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get the current release decision state for a recommendation run.

        The release decision is computed from the normalized readiness input
        summary (`run.evidence_summary_at_generation["readiness_input_summary"]`)
        so it stays consistent with the readiness cards and does not drift
        because of stale stored health/status columns.

        Args:
            db: Database session
            run_id: Recommendation run ID

        Returns:
            Dict with release decision state or None if no run exists
        """
        run = db.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
        if not run:
            return None

        decision = db.query(ReleaseDecision).filter(
            ReleaseDecision.recommendation_run_id == run_id,
            ReleaseDecision.is_active == True
        ).first()

        # Prefer the authoritative normalized readiness summary. If it is missing,
        # fall back to the stored decision/health fields for backward compatibility.
        readiness_summary = (
            (run.evidence_summary_at_generation or {}).get("readiness_input_summary") or {}
        )

        total_requirements = int(readiness_summary.get("accepted_acs", 0) or 0)
        trusted_requirements = int(readiness_summary.get("trusted_ac_mappings", 0) or 0)
        requirements_requiring_action = int(
            readiness_summary.get("review_required_ac_mappings", 0) or 0
        )
        current_pr_tests_passed = int(
            readiness_summary.get("current_pr_tests_passed", 0) or 0
        )
        current_pr_tests_failed = int(
            readiness_summary.get("current_pr_tests_failed", 0) or 0
        )
        coverage_is_current = bool(readiness_summary.get("coverage_is_current", False))

        # Verification status based purely on normalized AC coverage evidence.
        if total_requirements == 0:
            verification_status = "NOT_VERIFIED"
        elif trusted_requirements == total_requirements and current_pr_tests_passed > 0:
            verification_status = "FULLY_VERIFIED"
        elif trusted_requirements > 0:
            verification_status = "PARTIALLY_VERIFIED"
        else:
            verification_status = "NOT_VERIFIED"

        # Quality gate / release blockers derived from normalized evidence.
        blockers = []
        if requirements_requiring_action > 0:
            blockers.append(
                f"{requirements_requiring_action} acceptance criteria require review"
            )
        if current_pr_tests_failed > 0:
            blockers.append(
                f"{current_pr_tests_failed} current PR tests failed"
            )
        if not coverage_is_current:
            blockers.append("Coverage is not current for the PR head commit")

        # Optional governance inputs (e.g. manual tests, business intent) are warnings,
        # not AC verification failures.
        evidence_summary = run.evidence_summary_at_generation or {}
        missing_signals = evidence_summary.get("missing_signals") or []
        optional_governance_missing = bool(missing_signals)

        if blockers:
            quality_gate = "NOT_READY"
            quality_gate_reason = "Release blocked: " + "; ".join(blockers)
        elif optional_governance_missing:
            quality_gate = "READY_WITH_WARNINGS"
            quality_gate_reason = (
                "All ACs have trusted passing evidence. "
                "Optional governance inputs may still be missing."
            )
        else:
            quality_gate = "READY"
            quality_gate_reason = "All ACs have trusted passing evidence."

        # ----------------------------------------------------------------------
        # Required Before Release / Final Release Decision gating
        # ----------------------------------------------------------------------
        # Blocker calculation is only trustworthy when the generation succeeded and
        # the run is not a stale/draft/unsafe artifact.  When it cannot be trusted
        # we surface CALCULATION_FAILED instead of falsely claiming "all clear".
        can_compute_blockers = bool(
            readiness_summary
            and not run.is_draft
            and not run.input_stale
            and not run.generation_blocked_reason
            and not run.unsafe_for_optimization
        )

        if can_compute_blockers:
            if blockers:
                required_before_release_status = "BLOCKED"
                final_release_decision = "BLOCKED"
                approve_enabled = False
                gating_reason = "Release blocked: " + "; ".join(blockers)
            elif quality_gate == "READY_WITH_WARNINGS":
                required_before_release_status = "CLEAR"
                final_release_decision = "READY_FOR_APPROVAL_WITH_WARNINGS"
                approve_enabled = True
                gating_reason = "All blockers clear; optional governance inputs may still be missing."
            elif quality_gate in ("UNKNOWN", "NOT_READY"):
                required_before_release_status = "CLEAR"
                final_release_decision = "GOVERNANCE_OVERRIDE_REQUIRED"
                approve_enabled = False
                gating_reason = "Quality gate is not ready; governance override required."
            else:
                required_before_release_status = "CLEAR"
                final_release_decision = "READY_FOR_APPROVAL"
                approve_enabled = True
                gating_reason = "All blockers clear."
        else:
            failure_reasons = []
            if not readiness_summary:
                failure_reasons.append("readiness input summary unavailable")
            if run.is_draft:
                failure_reasons.append("recommendation is a draft")
            if run.input_stale:
                failure_reasons.append("inputs are stale")
            if run.generation_blocked_reason:
                failure_reasons.append(f"generation blocked: {run.generation_blocked_reason}")
            if run.unsafe_for_optimization:
                failure_reasons.append("recommendation flagged as unsafe for optimization")

            required_before_release_status = "CALCULATION_FAILED"
            final_release_decision = "BLOCKED"
            approve_enabled = False
            gating_reason = (
                "Release blockers could not be calculated."
                if not failure_reasons
                else "Release blockers could not be calculated: " + "; ".join(failure_reasons) + "."
            )

        # Legacy stored fields kept for compatibility.
        stored_readiness = decision.readiness_state if decision else None
        stored_health = decision.evidence_health_status if decision else run.evidence_health_status

        result = {
            "decisionId": str(decision.id) if decision else None,
            "decisionStatus": decision.decision_status if decision else "PENDING_REVIEW",
            "approverId": str(decision.approver_id) if decision and decision.approver_id else None,
            "approverName": decision.approver_name if decision else None,
            "decisionNote": decision.decision_note if decision else None,
            "snapshotHash": decision.snapshot_hash if decision else ReleaseDecisionService.get_snapshot_hash(run),
            "evidenceHealthStatus": stored_health,
            "readinessState": stored_readiness,
            "verification_status": verification_status,
            "trusted_requirements": trusted_requirements,
            "total_requirements": total_requirements,
            "requirements_requiring_action": requirements_requiring_action,
            "current_pr_tests_passed": current_pr_tests_passed,
            "quality_gate": quality_gate,
            "quality_gate_reason": quality_gate_reason,
            "quality_gate_profile": "Missing",
            "evidence_readiness": "Ready" if not blockers else "Not Ready",
            "required_before_release_status": required_before_release_status,
            "blockers": blockers,
            "final_release_decision": final_release_decision,
            "approve_enabled": approve_enabled,
            "reason": gating_reason,
            "createdAt": decision.created_at.isoformat() + "Z" if decision and decision.created_at else None,
            "updatedAt": decision.updated_at.isoformat() + "Z" if decision and decision.updated_at else None,
        }
        return result

    @staticmethod
    def submit_release_decision(
        db: Session,
        run: RecommendationRun,
        data: Dict[str, Any],
        actor: User,
        live_evidence_health: str | None = None
    ) -> ReleaseDecision:
        """Submit a release decision (APPROVED, REJECTED, CONDITIONALLY_APPROVED).

        Args:
            db: Database session
            run: Recommendation run
            data: Decision data including decision_status, snapshot_hash, decision_note
            actor: User submitting the decision
            live_evidence_health: Optional live evidence health from regressionEvidence.decisionSummary.health

        Returns:
            Created or updated ReleaseDecision

        Raises:
            ValueError: If snapshot hash mismatch or health status blocks decision
        """
        decision_status = data.get("decision_status")
        submitted_snapshot_hash = data.get("snapshot_hash")
        decision_note = data.get("decision_note")

        # Validate decision status
        valid_statuses = {"APPROVED", "REJECTED", "CONDITIONALLY_APPROVED"}
        if decision_status not in valid_statuses:
            raise ValueError(f"Invalid decision status: {decision_status}. Must be one of {valid_statuses}")

        # Approval requires the computed release state to allow it.
        if decision_status in {"APPROVED", "CONDITIONALLY_APPROVED"}:
            current_state = ReleaseDecisionService.get_release_state(db, run.id)
            if current_state and not current_state.get("approve_enabled", True):
                raise ValueError(
                    f"RELEASE_DECISION_BLOCKED: Cannot approve release. "
                    f"Reason: {current_state.get('reason', 'Release blockers not cleared or calculation failed.')}"
                )

        # Validate snapshot hash
        current_snapshot_hash = ReleaseDecisionService.get_snapshot_hash(run)
        if submitted_snapshot_hash != current_snapshot_hash:
            raise ValueError(
                f"RELEASE_SNAPSHOT_MISMATCH: Submitted snapshot hash {submitted_snapshot_hash} "
                f"does not match current snapshot hash {current_snapshot_hash}. "
                f"REQUIRES_REGENERATION"
            )

        # Use live health if provided, otherwise fall back to stale DB column
        health_to_validate = live_evidence_health or run.evidence_health_status
        
        # Validate health status allows decision
        if health_to_validate in ReleaseDecisionService.BLOCKING_HEALTH_STATUSES:
            raise ValueError(
                f"RELEASE_DECISION_BLOCKED: Evidence health status {health_to_validate} "
                f"blocks release decisions. Reason: Evidence requires regeneration or has inconsistencies."
            )

        # Require note for REJECTED and CONDITIONALLY_APPROVED
        if decision_status in {"REJECTED", "CONDITIONALLY_APPROVED"} and not decision_note:
            raise ValueError(
                f"DECISION_NOTE_REQUIRED: Decision note is required for {decision_status} decisions."
            )

        # Get or create release decision
        decision = db.query(ReleaseDecision).filter(
            ReleaseDecision.recommendation_run_id == run.id,
            ReleaseDecision.is_active == True
        ).first()

        previous_status = None
        if decision:
            previous_status = decision.decision_status
        else:
            # Create new decision
            # Use live health if provided, otherwise fall back to stale DB column
            health_to_store = live_evidence_health or run.evidence_health_status
            
            decision = ReleaseDecision(
                recommendation_run_id=run.id,
                decision_status="PENDING_REVIEW",
                snapshot_hash=current_snapshot_hash,
                evidence_health_status=health_to_store,
                readiness_state=ReleaseDecisionService.derive_readiness_state_from_health(
                    health_to_store,
                    fallback=run.recommendation_readiness_state
                ),
                is_active=True
            )
            db.add(decision)
            db.flush()

        # Record history event for the transition
        event_type = decision_status.upper()
        history = ReleaseDecisionHistory(
            release_decision_id=decision.id,
            event_type=event_type,
            actor_id=str(actor.id),
            actor_name=actor.name,
            previous_status=previous_status,
            new_status=decision_status,
            note=decision_note,
            snapshot_hash=current_snapshot_hash
        )
        db.add(history)

        # Update decision
        decision.decision_status = decision_status
        decision.approver_id = str(actor.id)
        decision.approver_name = actor.name
        decision.decision_note = decision_note
        decision.snapshot_hash = current_snapshot_hash
        
        # Use live health if provided, otherwise fall back to stale DB column
        health_to_store = live_evidence_health or run.evidence_health_status
        decision.evidence_health_status = health_to_store
        decision.readiness_state = ReleaseDecisionService.derive_readiness_state_from_health(
            health_to_store,
            fallback=run.recommendation_readiness_state
        )
        decision.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(decision)

        # Record outcome signals for skipped required items when approved with override
        if decision_status == "APPROVED_WITH_OVERRIDE":
            ReleaseDecisionService._record_release_outcome(
                db,
                str(run.id),
                decision_status,
                data.get("skipped_required_items", []),
                str(run.repository_id),
                str(run.workspace_id) if run.workspace_id else None
            )

        return decision

    @staticmethod
    def _record_release_outcome(
        db: Session,
        recommendation_run_id: str,
        decision: str,
        skipped_required_items: List[str],
        repository_id: str,
        workspace_id: str
    ):
        """
        Record outcome signals for skipped items
        when approved with override.
        """
        if decision != "APPROVED_WITH_OVERRIDE":
            return
        
        from app.models.pattern_memory_v2 import PatternMemoryV2
        import uuid
        
        for ac_key in skipped_required_items:
            existing = db.query(PatternMemoryV2).filter(
                PatternMemoryV2.pattern_key == ac_key,
                PatternMemoryV2.repository_id == repository_id
            ).first()
            
            if existing:
                existing.usage_count += 1
                existing.strength = min(
                    1.0, 
                    existing.strength + 0.1
                )
            else:
                signal = PatternMemoryV2(
                    id=uuid.uuid4(),
                    repository_id=repository_id,
                    workspace_id=workspace_id,
                    pattern_key=ac_key,
                    signal_type="OVERRIDE_WARNING",
                    strength=0.3,
                    confidence=0.5,
                    usage_count=1
                )
                db.add(signal)
        
        db.commit()

    @staticmethod
    def reset_release_decision(
        db: Session,
        run: RecommendationRun,
        data: Dict[str, Any],
        actor: User,
        live_evidence_health: str | None = None
    ) -> ReleaseDecision:
        """Reset a release decision back to PENDING_REVIEW.

        Args:
            db: Database session
            run: Recommendation run
            data: Reset data including snapshot_hash
            actor: User performing the reset
            live_evidence_health: Optional live evidence health from regressionEvidence.decisionSummary.health

        Returns:
            Updated ReleaseDecision

        Raises:
            ValueError: If snapshot hash mismatch or no active decision exists
        """
        submitted_snapshot_hash = data.get("snapshot_hash")

        # Validate snapshot hash
        current_snapshot_hash = ReleaseDecisionService.get_snapshot_hash(run)
        if submitted_snapshot_hash != current_snapshot_hash:
            raise ValueError(
                f"RELEASE_SNAPSHOT_MISMATCH: Submitted snapshot hash {submitted_snapshot_hash} "
                f"does not match current snapshot hash {current_snapshot_hash}. "
                f"REQUIRES_REGENERATION"
            )

        # Get active decision
        decision = db.query(ReleaseDecision).filter(
            ReleaseDecision.recommendation_run_id == run.id,
            ReleaseDecision.is_active == True
        ).first()

        if not decision:
            raise ValueError("NO_ACTIVE_DECISION: No active release decision found to reset.")

        previous_status = decision.decision_status

        # Record history event for reset
        history = ReleaseDecisionHistory(
            release_decision_id=decision.id,
            event_type="RESET",
            actor_id=str(actor.id),
            actor_name=actor.name,
            previous_status=previous_status,
            new_status="PENDING_REVIEW",
            note=data.get("note"),
            snapshot_hash=current_snapshot_hash
        )
        db.add(history)

        # Reset decision to pending
        decision.decision_status = "PENDING_REVIEW"
        decision.approver_id = None
        decision.approver_name = None
        decision.decision_note = None
        decision.snapshot_hash = current_snapshot_hash
        
        # Use live health if provided, otherwise fall back to stale DB column
        health_to_store = live_evidence_health or run.evidence_health_status
        decision.evidence_health_status = health_to_store
        decision.readiness_state = ReleaseDecisionService.derive_readiness_state_from_health(
            health_to_store,
            fallback=run.recommendation_readiness_state
        )
        decision.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(decision)

        return decision

    @staticmethod
    def get_release_history(
        db: Session,
        run_id: uuid.UUID,
        audit_mode: bool = False
    ) -> Dict[str, Any]:
        """Get the release decision history for a recommendation run.

        Args:
            db: Database session
            run_id: Recommendation run ID
            audit_mode: If True, expose internal IDs

        Returns:
            Dict with release decision history including timeline
        """
        decision = db.query(ReleaseDecision).filter(
            ReleaseDecision.recommendation_run_id == run_id,
            ReleaseDecision.is_active == True
        ).first()

        if not decision:
            return {
                "decisionId": None,
                "decisionStatus": "PENDING_REVIEW",
                "history": [],
                "totalEvents": 0
            }

        # Get history events sorted chronologically
        history_events = db.query(ReleaseDecisionHistory).filter(
            ReleaseDecisionHistory.release_decision_id == decision.id
        ).order_by(ReleaseDecisionHistory.created_at.asc()).all()

        # Serialize history events
        serialized_events = []
        for event in history_events:
            event_data = {
                "eventType": event.event_type,
                "actorName": event.actor_name,
                "previousStatus": event.previous_status,
                "newStatus": event.new_status,
                "note": event.note,
                "createdAt": event.created_at.isoformat() + "Z" if event.created_at else None,
            }

            if audit_mode:
                event_data["historyId"] = str(event.id)
                event_data["actorId"] = str(event.actor_id) if event.actor_id else None
                event_data["snapshotHash"] = event.snapshot_hash
            else:
                event_data["historyId"] = None
                event_data["actorId"] = None
                event_data["snapshotHash"] = None

            serialized_events.append(event_data)

        return {
            "decisionId": str(decision.id),
            "decisionStatus": decision.decision_status,
            "approverName": decision.approver_name,
            "snapshotHash": decision.snapshot_hash,
            "evidenceHealthStatus": decision.evidence_health_status,
            "readinessState": decision.readiness_state,
            "history": serialized_events,
            "totalEvents": len(serialized_events),
        }

    @staticmethod
    def generate_risk_aware_recommendations(
        requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate risk-aware release decision recommendations.

        Args:
            requirements: List of requirements with risk_score, risk_band, coverage_bucket

        Returns:
            Dict with decisionRecommendations, decisionReasoning, requiredBeforeRelease
        """
        # Analyze risk profile
        high_risk_items = []
        critical_risk_items = []
        missing_critical = []
        partial_high_risk = []

        for req in requirements:
            risk_band = req.get("risk_band", "LOW")
            risk_score = req.get("risk_score", 0)
            coverage_bucket = req.get("coverage_bucket", "COVERED")
            req_id = req.get("requirement_id", "")
            title = req.get("title", "")

            # Identify critical and high-risk items
            if risk_band == "CRITICAL":
                critical_risk_items.append({
                    "requirement_id": req_id,
                    "title": title,
                    "risk_score": risk_score,
                    "risk_band": risk_band,
                    "coverage_bucket": coverage_bucket
                })
                if coverage_bucket == "MISSING":
                    missing_critical.append({
                        "requirement_id": req_id,
                        "title": title,
                        "action": f"Run {req_id} validation"
                    })
            elif risk_band == "HIGH":
                high_risk_items.append({
                    "requirement_id": req_id,
                    "title": title,
                    "risk_score": risk_score,
                    "risk_band": risk_band,
                    "coverage_bucket": coverage_bucket
                })
                if coverage_bucket == "PARTIAL":
                    partial_high_risk.append({
                        "requirement_id": req_id,
                        "title": title,
                        "action": f"Run {req_id} validation"
                    })

        # Generate decision recommendation
        decision_recommendation = "APPROVED"
        decision_reasoning = []
        required_before_release = []

        # Check for blocking conditions
        if missing_critical:
            decision_recommendation = "CONDITIONALLY_APPROVED"
            decision_reasoning.append(f"{len(missing_critical)} critical requirements missing coverage")
            required_before_release.extend(missing_critical)

        if partial_high_risk:
            if decision_recommendation == "APPROVED":
                decision_recommendation = "CONDITIONALLY_APPROVED"
            decision_reasoning.append(f"{len(partial_high_risk)} high-risk requirements with partial coverage")
            required_before_release.extend(partial_high_risk)

        if critical_risk_items:
            decision_reasoning.append(f"{len(critical_risk_items)} critical-risk requirements identified")

        if high_risk_items:
            decision_reasoning.append(f"{len(high_risk_items)} high-risk requirements identified")

        # If no issues, recommend approval
        if decision_recommendation == "APPROVED":
            decision_reasoning.append("All critical requirements have adequate coverage")
            decision_reasoning.append("No high-risk gaps detected")

        return {
            "decisionRecommendations": decision_recommendation,
            "decisionReasoning": decision_reasoning,
            "requiredBeforeRelease": required_before_release,
            "riskSummary": {
                "criticalRiskItems": len(critical_risk_items),
                "highRiskItems": len(high_risk_items),
                "missingCritical": len(missing_critical),
                "partialHighRisk": len(partial_high_risk)
            }
        }

    @staticmethod
    def get_risk_aware_release_state(
        db: Session,
        run_id: uuid.UUID,
        requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get release decision state with risk-aware recommendations.

        Args:
            db: Database session
            run_id: Recommendation run ID
            requirements: List of requirements with risk data

        Returns:
            Dict with release decision state and risk-aware recommendations
        """
        # Get current release state
        current_state = ReleaseDecisionService.get_release_state(db, run_id)

        # Generate risk-aware recommendations
        risk_recommendations = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        # Merge with current state
        if current_state:
            current_state["riskAwareRecommendations"] = risk_recommendations
        else:
            current_state = {
                "decisionId": None,
                "decisionStatus": "PENDING_REVIEW",
                "riskAwareRecommendations": risk_recommendations
            }

        return current_state
