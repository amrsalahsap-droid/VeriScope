"""Release Audit Service - Generates complete audit records for release decisions."""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest
from app.models.release_decision import ReleaseDecision
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.pattern_memory_v2 import PatternMemoryV2


class ReleaseAuditService:
    """Service for generating release audit records."""

    @staticmethod
    def generate_release_audit_record(
        db: Session,
        recommendation_run_id: str
    ) -> Dict[str, Any]:
        """
        Generate a complete audit record for a 
        recommendation run and its release decision.
        """
        # Load the recommendation run
        run = db.query(RecommendationRun).filter(
            RecommendationRun.id == uuid.UUID(recommendation_run_id)
        ).first()
        
        if not run:
            raise ValueError(f"Recommendation run {recommendation_run_id} not found")
        
        # Load the pull request
        pr = db.query(PullRequest).filter(
            PullRequest.id == run.pr_id
        ).first()
        
        # Load the release decision
        decision = db.query(ReleaseDecision).filter(
            ReleaseDecision.recommendation_run_id == run.id,
            ReleaseDecision.is_active == True
        ).first()
        
        # Load the repository
        from app.models.repository import Repository
        repository = db.query(Repository).filter(
            Repository.id == run.repository_id
        ).first()
        
        # Build the audit record
        audit_record = {
            "audit_version": "1.0",
            "generated_at": datetime.utcnow().isoformat(),
            "recommendation_run_id": str(run.id),
            
            "release": {
                "pr_number": pr.number if pr else None,
                "pr_title": pr.title if pr else None,
                "repository": repository.full_name if repository else None,
                "branch": pr.source_branch if pr else None,
                "head_commit_sha": pr.head_commit_sha if pr else None,
                "pr_author": pr.author if pr else None,
                "pr_opened_at": pr.github_created_at.isoformat() if pr and pr.github_created_at else None
            },
            
            "decision": {
                "status": decision.decision_status if decision else "PENDING",
                "decided_by": decision.approver_name if decision else None,
                "decided_at": decision.updated_at.isoformat() if decision and decision.updated_at else None,
                "override_reason": decision.decision_note if decision else None,
                "quality_gate": run.evidence_health_status or "UNKNOWN",
                "confidence_score": None,  # Would need to compute from scope
                "confidence_label": None  # Would need to compute from scope
            },
            
            "scope_summary": {
                "total_requirements": 0,  # Would need to load from scope
                "already_verified": 0,
                "required_executed": 0,
                "required_pending": 0,
                "safe_to_skip": 0,
                "execution_reduction_pct": 0.0
            },
            
            "required_items": [],
            "already_verified_items": [],
            "skipped_items": [],
            "risk_overrides": [],
            "changed_files": [],
            "outcome_learning_signals": []
        }
        
        # Load changed files
        if pr:
            from app.models.pull_request import PullRequestChangedFile
            changed_files = db.query(PullRequestChangedFile).filter(
                PullRequestChangedFile.pull_request_id == pr.id
            ).all()
            audit_record["changed_files"] = [f.file_path for f in changed_files]
        
        # Load outcome learning signals
        pattern_memories = db.query(PatternMemoryV2).filter(
            PatternMemoryV2.repository_id == run.repository_id
        ).all()
        
        for pm in pattern_memories:
            audit_record["outcome_learning_signals"].append({
                "pattern_key": pm.pattern_key,
                "signal_type": pm.signal_type,
                "strength": pm.strength,
                "influenced_scope": False  # Would need to check against scope items
            })
        
        # Load scope items if available from regression scope snapshot
        if run.requirement_evidence_snapshot_json:
            import json
            snapshot = json.loads(run.requirement_evidence_snapshot_json)
            
            # Extract scope summary
            counts = snapshot.get("counts", {})
            audit_record["scope_summary"] = {
                "total_requirements": counts.get("totalRequirements", 0),
                "already_verified": counts.get("verifiedTests", 0),
                "required_executed": 0,  # Would need execution data
                "required_pending": counts.get("missingAutomatedCoverage", 0),
                "safe_to_skip": 0,
                "execution_reduction_pct": 0.0
            }
            
            # Extract AC traceability
            traceability = snapshot.get("acTraceability", [])
            
            for trace in traceability:
                ac_id = trace.get("requirementId")
                title = trace.get("requirementText", "")
                coverage_status = trace.get("coverageStatus", "MISSING")
                
                if coverage_status == "COVERED":
                    audit_record["already_verified_items"].append({
                        "ac_id": ac_id,
                        "title": title,
                        "verified_at": None,  # Would need execution timestamp
                        "evidence_sha": None,
                        "covered_files": trace.get("linkedExistingTests", [])
                    })
                elif coverage_status == "MISSING":
                    audit_record["required_items"].append({
                        "ac_id": ac_id,
                        "title": title,
                        "status": "PENDING",
                        "reason_required": "Missing automated coverage",
                        "evidence_sha": None,
                        "evidence_freshness": "UNKNOWN",
                        "risk_band": "HIGH",
                        "verified_at": None
                    })
        
        return audit_record
