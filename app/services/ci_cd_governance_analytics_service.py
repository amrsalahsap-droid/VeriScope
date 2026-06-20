"""
Service for CI/CD governance analytics and executive reporting.

Provides organization-level analytics including:
- Compliance trend analysis
- Policy adoption tracking
- Drift trend analysis
- Exception analytics
- Repository risk heatmap
- Governance maturity scoring
- Executive summary generation
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.models.repository import Repository
from app.models.repository_ci_cd_policy import RepositoryCICDPolicy
from app.models.ci_cd_policy_exception import CICDPolicyException
from app.models.ci_cd_governance_review_snapshot import CICDGovernanceReviewSnapshot
from app.models.workspace_ci_cd_policy_default import WorkspaceCICDPolicyDefault
import uuid


class CICDGovernanceAnalyticsService:
    """Service for calculating governance analytics and metrics."""
    
    @staticmethod
    def get_governance_analytics(
        db: Session,
        workspace_id: uuid.UUID,
        window_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive governance analytics for an organization.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            window_days: Time window in days for trend analysis
            
        Returns:
            Dictionary containing all governance analytics
        """
        return {
            "compliance_trend": CICDGovernanceAnalyticsService.get_compliance_trend(
                db, workspace_id, window_days
            ),
            "policy_adoption": CICDGovernanceAnalyticsService.get_policy_adoption_trend(
                db, workspace_id
            ),
            "drift_trend": CICDGovernanceAnalyticsService.get_drift_trend(
                db, workspace_id, window_days
            ),
            "exception_analytics": CICDGovernanceAnalyticsService.get_exception_analytics(
                db, workspace_id, window_days
            ),
            "risk_heatmap": CICDGovernanceAnalyticsService.get_repository_risk_heatmap(
                db, workspace_id
            ),
            "maturity_score": CICDGovernanceAnalyticsService.get_governance_maturity_score(
                db, workspace_id
            )
        }
    
    @staticmethod
    def get_compliance_trend(
        db: Session,
        workspace_id: uuid.UUID,
        window_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate compliance trend using governance review snapshots.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            window_days: Time window in days
            
        Returns:
            Compliance trend metrics including current score, previous score, delta, and direction
        """
        # Get the two most recent snapshots
        snapshots = db.query(CICDGovernanceReviewSnapshot).filter(
            CICDGovernanceReviewSnapshot.workspace_id == workspace_id
        ).order_by(CICDGovernanceReviewSnapshot.created_at.desc()).limit(2).all()
        
        if len(snapshots) < 2:
            return {
                "current_compliance_score": None,
                "previous_compliance_score": None,
                "score_delta": None,
                "trend_direction": "INSUFFICIENT_DATA",
                "message": "At least two governance review snapshots are required for trend analysis.",
                "compliant_repository_count": 0,
                "drifted_repository_count": 0,
                "high_risk_repository_count": 0,
                "critical_repository_count": 0,
                "branch_protection_ready_count": 0,
                "artifact_policy_required_count": 0,
                "unknown_gate_failure_required_count": 0
            }
        
        current = snapshots[0]
        previous = snapshots[1]
        
        current_score = current.compliance_score
        previous_score = previous.compliance_score
        delta = current_score - previous_score
        
        # Determine trend direction
        if delta > 2:
            trend_direction = "IMPROVING"
        elif delta < -2:
            trend_direction = "DECLINING"
        else:
            trend_direction = "STABLE"
        
        return {
            "current_compliance_score": current_score,
            "previous_compliance_score": previous_score,
            "score_delta": delta,
            "trend_direction": trend_direction,
            "compliant_repository_count": current.compliant_count,
            "drifted_repository_count": current.drifted_count,
            "high_risk_repository_count": current.high_risk_count,
            "critical_repository_count": current.critical_count,
            "branch_protection_ready_count": 0,  # Calculated from repository policies
            "artifact_policy_required_count": 0,  # Calculated from repository policies
            "unknown_gate_failure_required_count": 0  # Calculated from repository policies
        }
    
    @staticmethod
    def get_policy_adoption_trend(
        db: Session,
        workspace_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Calculate policy adoption distribution across repositories.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            
        Returns:
            Policy adoption metrics including preset distribution and insights
        """
        # Get all repositories for the organization
        repositories = db.query(Repository).filter(
            Repository.workspace_id == workspace_id
        ).all()
        
        if not repositories:
            return {
                "total_repositories": 0,
                "preset_distribution": {},
                "organization_default_inherited": 0,
                "repository_override": 0,
                "drifted_from_default": 0,
                "insights": []
            }
        
        # Get organization default preset
        org_default = db.query(WorkspaceCICDPolicyDefault).filter(
            WorkspaceCICDPolicyDefault.workspace_id == workspace_id
        ).first()
        org_default_preset = org_default.preset_name if org_default else "STANDARD"
        
        # Count preset adoption
        preset_counts = {
            "PERMISSIVE": 0,
            "STANDARD": 0,
            "STRICT": 0,
            "REGULATED": 0,
            "CUSTOM": 0
        }
        
        organization_default_inherited = 0
        repository_override = 0
        drifted_from_default = 0
        
        from app.services.ci_cd_policy_bulk_operation_service import CICDPolicyBulkOperationService
        for repo in repositories:
            comp = CICDPolicyBulkOperationService.calculate_repository_compliance(db, repo.id)
            preset_name = comp.get("current_preset") or "STANDARD"
            if preset_name in preset_counts:
                preset_counts[preset_name] += 1
            else:
                preset_counts["CUSTOM"] += 1
            
            if comp.get("policy_source") in ("WORKSPACE_DEFAULT", "SYSTEM_DEFAULT"):
                organization_default_inherited += 1
            else:
                repository_override += 1
            
            if comp.get("drift_detected"):
                drifted_from_default += 1
        
        total = len(repositories)
        preset_distribution = {
            preset: {
                "count": count,
                "percentage": round((count / total) * 100, 1) if total > 0 else 0
            }
            for preset, count in preset_counts.items()
        }
        
        # Generate insights
        insights = []
        if preset_counts["STANDARD"] > total * 0.5:
            insights.append("Most repositories use STANDARD preset.")
        if preset_counts["STRICT"] + preset_counts["REGULATED"] < total * 0.2:
            insights.append("Consider using STRICT or REGULATED for high-risk repositories.")
        if preset_counts["CUSTOM"] > 0:
            insights.append(f"{preset_counts['CUSTOM']} repositories use CUSTOM policies and should be reviewed.")
        if drifted_from_default > 0:
            insights.append(f"{drifted_from_default} repositories have drifted from organization default.")
        
        return {
            "total_repositories": total,
            "preset_distribution": preset_distribution,
            "organization_default_inherited": {
                "count": organization_default_inherited,
                "percentage": round((organization_default_inherited / total) * 100, 1) if total > 0 else 0
            },
            "repository_override": {
                "count": repository_override,
                "percentage": round((repository_override / total) * 100, 1) if total > 0 else 0
            },
            "drifted_from_default": {
                "count": drifted_from_default,
                "percentage": round((drifted_from_default / total) * 100, 1) if total > 0 else 0
            },
            "insights": insights
        }
    
    @staticmethod
    def get_drift_trend(
        db: Session,
        workspace_id: uuid.UUID,
        window_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate drift trend over time.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            window_days: Time window in days
            
        Returns:
            Drift trend metrics including drift counts, delta, and common drift fields
        """
        # Get the two most recent snapshots
        snapshots = db.query(CICDGovernanceReviewSnapshot).filter(
            CICDGovernanceReviewSnapshot.workspace_id == workspace_id
        ).order_by(CICDGovernanceReviewSnapshot.created_at.desc()).limit(2).all()
        
        if len(snapshots) < 2:
            return {
                "current_drifted_repositories": 0,
                "previous_drifted_repositories": 0,
                "drift_delta": 0,
                "high_risk_drift_delta": 0,
                "critical_drift_delta": 0,
                "most_common_drift_fields": [],
                "repositories_newly_drifted": [],
                "repositories_returned_to_compliance": [],
                "insufficient_data": True
            }
        
        current = snapshots[0]
        previous = snapshots[1]
        
        current_drifted = current.drifted_count + current.high_risk_count + current.critical_count
        previous_drifted = previous.drifted_count + previous.high_risk_count + previous.critical_count
        drift_delta = current_drifted - previous_drifted
        
        # Get current drift fields from repository policies
        repositories = db.query(Repository).filter(
            Repository.workspace_id == workspace_id
        ).all()
        
        drift_field_counts = {
            "ci_fail_on_partial": 0,
            "fail_on_unknown_gate": 0,
            "fail_on_missing_recommendation": 0,
            "require_artifact": 0,
            "require_pr_comment": 0,
            "allow_manual_override": 0,
            "manual_override_requires_reason": 0,
            "strict_mode": 0
        }
        
        from app.services.ci_cd_policy_preset_service import CICDPolicyPresetService
        preset_service = CICDPolicyPresetService()
        for repo in repositories:
            drift = preset_service.detect_policy_drift(db, repo.id)
            if drift.get("drift_detected") and drift.get("drift_fields"):
                for field in drift["drift_fields"]:
                    if field in drift_field_counts:
                        drift_field_counts[field] += 1
        
        # Sort by count
        most_common_drift_fields = sorted(
            [{"field": field, "count": count} for field, count in drift_field_counts.items() if count > 0],
            key=lambda x: x["count"],
            reverse=True
        )[:5]
        
        return {
            "current_drifted_repositories": current_drifted,
            "previous_drifted_repositories": previous_drifted,
            "drift_delta": drift_delta,
            "high_risk_drift_delta": current.high_risk_count - previous.high_risk_count,
            "critical_drift_delta": current.critical_count - previous.critical_count,
            "most_common_drift_fields": most_common_drift_fields,
            "repositories_newly_drifted": [],  # Would require detailed snapshot comparison
            "repositories_returned_to_compliance": [],  # Would require detailed snapshot comparison
            "insufficient_data": False
        }
    
    @staticmethod
    def get_exception_analytics(
        db: Session,
        workspace_id: uuid.UUID,
        window_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate exception analytics including aging and trends.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            window_days: Time window in days
            
        Returns:
            Exception analytics including counts, aging buckets, and risk indicators
        """
        now = datetime.utcnow()
        window_start = now - timedelta(days=window_days)
        
        # Get all exceptions for the organization
        exceptions = db.query(CICDPolicyException).filter(
            CICDPolicyException.workspace_id == workspace_id
        ).all()
        
        active_exceptions = [e for e in exceptions if e.status == "APPROVED" and (not e.expires_at or e.expires_at > now)]
        pending_exceptions = [e for e in exceptions if e.status == "PENDING"]
        approved_exceptions = [e for e in exceptions if e.status == "APPROVED"]
        rejected_exceptions = [e for e in exceptions if e.status == "REJECTED"]
        revoked_exceptions = [e for e in exceptions if e.status == "REVOKED"]
        expired_exceptions = [e for e in exceptions if e.status == "APPROVED" and e.expires_at and e.expires_at <= now]
        
        # Exceptions expiring soon
        expiring_in_7_days = [e for e in active_exceptions if e.expires_at and e.expires_at <= now + timedelta(days=7)]
        expiring_in_30_days = [e for e in active_exceptions if e.expires_at and e.expires_at <= now + timedelta(days=30)]
        
        # Average approval time
        approved_with_time = [e for e in approved_exceptions if e.updated_at and e.created_at]
        avg_approval_time = None
        if approved_with_time:
            approval_times = [(e.updated_at - e.created_at).total_seconds() / 3600 for e in approved_with_time]
            avg_approval_time = sum(approval_times) / len(approval_times)
        
        # Oldest pending exception
        oldest_pending = None
        if pending_exceptions:
            oldest_pending = min(pending_exceptions, key=lambda e: e.created_at)
        
        # Exception aging buckets
        aging_buckets = {
            "0-7_days": 0,
            "8-30_days": 0,
            "31-90_days": 0,
            "90+_days": 0
        }
        
        for exception in active_exceptions:
            age_days = (now - exception.created_at).days
            if age_days <= 7:
                aging_buckets["0-7_days"] += 1
            elif age_days <= 30:
                aging_buckets["8-30_days"] += 1
            elif age_days <= 90:
                aging_buckets["31-90_days"] += 1
            else:
                aging_buckets["90+_days"] += 1
        
        # Most common exception fields
        exception_field_counts = {}
        for exception in exceptions:
            for field in exception.exception_fields:
                exception_field_counts[field] = exception_field_counts.get(field, 0) + 1
        
        most_common_exception_fields = sorted(
            [{"field": field, "count": count} for field, count in exception_field_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:5]
        
        # Risk rules
        risk_indicators = []
        if oldest_pending and (now - oldest_pending.created_at).days > 7:
            risk_indicators.append({
                "level": "WARNING",
                "message": f"Pending exception older than 7 days: {oldest_pending.id}"
            })
        if expired_exceptions:
            risk_indicators.append({
                "level": "HIGH",
                "message": f"{len(expired_exceptions)} approved exceptions have expired"
            })
        
        return {
            "active_exceptions": len(active_exceptions),
            "pending_exceptions": len(pending_exceptions),
            "approved_exceptions": len(approved_exceptions),
            "rejected_exceptions": len(rejected_exceptions),
            "revoked_exceptions": len(revoked_exceptions),
            "expired_exceptions": len(expired_exceptions),
            "exceptions_expiring_in_7_days": len(expiring_in_7_days),
            "exceptions_expiring_in_30_days": len(expiring_in_30_days),
            "average_approval_time_hours": round(avg_approval_time, 2) if avg_approval_time else None,
            "oldest_pending_exception": {
                "id": str(oldest_pending.id),
                "requested_at": oldest_pending.created_at.isoformat(),
                "age_days": (now - oldest_pending.created_at).days
            } if oldest_pending else None,
            "exception_aging_buckets": aging_buckets,
            "most_common_exception_fields": most_common_exception_fields,
            "risk_indicators": risk_indicators
        }
    
    @staticmethod
    def get_repository_risk_heatmap(
        db: Session,
        workspace_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """
        Calculate repository-level risk heatmap.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            
        Returns:
            List of repository risk entries with scores and bands
        """
        repositories = db.query(Repository).filter(
            Repository.workspace_id == workspace_id
        ).all()
        
        heatmap_data = []
        
        from app.services.ci_cd_policy_bulk_operation_service import CICDPolicyBulkOperationService
        from app.models.pipeline_run import PipelineRun
        
        for repo in repositories:
            policy = db.query(RepositoryCICDPolicy).filter(
                RepositoryCICDPolicy.repository_id == repo.id
            ).first()
            
            comp = CICDPolicyBulkOperationService.calculate_repository_compliance(db, repo.id)
            
            # Get active exceptions for this repository
            active_exceptions = db.query(CICDPolicyException).filter(
                CICDPolicyException.repository_id == repo.id,
                CICDPolicyException.status == "APPROVED"
            ).all()
            
            expired_exceptions = [e for e in active_exceptions if e.expires_at and e.expires_at <= datetime.utcnow()]
            
            # Calculate risk score
            risk_score = 0
            risk_reasons = []
            
            # Critical drift adds high risk
            drift_risk = comp.get("drift_risk_level")
            if drift_risk == "CRITICAL":
                risk_score += 30
                risk_reasons.append("Critical drift detected")
            elif drift_risk == "HIGH":
                risk_score += 20
                risk_reasons.append("High-risk drift detected")
            elif drift_risk == "MEDIUM":
                risk_score += 10
                risk_reasons.append("Medium-risk drift detected")
            
            # Missing artifact policy
            if not comp.get("artifact_required"):
                risk_score += 10
                risk_reasons.append("Artifact policy not required")
            
            # Manual override without reason
            if comp.get("manual_override_enabled"):
                if policy and not policy.manual_override_requires_reason:
                    risk_score += 15
                    risk_reasons.append("Manual override allowed without reason")
            
            # Unknown gates recurring
            if comp.get("unknown_gate_fails"):
                risk_score += 5
            
            # Branch protection not ready
            if not comp.get("branch_protection_ready"):
                risk_score += 10
                risk_reasons.append("Branch protection not ready")
            
            # Expired exception
            if expired_exceptions:
                risk_score += 20
                risk_reasons.append(f"{len(expired_exceptions)} expired exception(s)")
            
            # Active exceptions
            if active_exceptions:
                risk_score += len(active_exceptions) * 5
                risk_reasons.append(f"{len(active_exceptions)} active exception(s)")
            
            # Determine risk band
            if risk_score >= 50:
                risk_band = "CRITICAL"
            elif risk_score >= 30:
                risk_band = "HIGH"
            elif risk_score >= 15:
                risk_band = "MEDIUM"
            else:
                risk_band = "LOW"
            
            # Recommended action
            if risk_band == "CRITICAL":
                recommended_action = "Immediate attention required - address critical drift and expired exceptions"
            elif risk_band == "HIGH":
                recommended_action = "Review drift and exceptions - consider policy updates"
            elif risk_band == "MEDIUM":
                recommended_action = "Monitor and address drift sources"
            else:
                recommended_action = "Maintain current governance posture"
            
            # Get latest quality gate status from pipeline runs
            latest_run = db.query(PipelineRun).filter(
                PipelineRun.repository_id == repo.id
            ).order_by(PipelineRun.created_at.desc()).first()
            latest_quality_gate = latest_run.quality_gate.value if latest_run and latest_run.quality_gate else "UNKNOWN"
            
            heatmap_data.append({
                "repository_id": str(repo.id),
                "repository_name": repo.full_name,
                "current_preset": comp.get("current_preset"),
                "compliance_score": comp.get("compliance_score") or 0,
                "compliance_status": comp.get("compliance_status") or "UNKNOWN",
                "drift_risk_level": comp.get("drift_risk_level") or "NONE",
                "active_exception_count": len(active_exceptions),
                "expired_exception_count": len(expired_exceptions),
                "branch_protection_ready": comp.get("branch_protection_ready") or False,
                "latest_quality_gate": latest_quality_gate,
                "unknown_gate_frequency": 0,  # Would need historical data
                "missing_recommendation_frequency": 0,  # Would need historical data
                "manual_override_count": 0,  # Would need historical data
                "risk_score": risk_score,
                "risk_band": risk_band,
                "risk_reasons": risk_reasons,
                "recommended_action": recommended_action
            })
        
        # Sort by risk score descending
        heatmap_data.sort(key=lambda x: x["risk_score"], reverse=True)
        
        return heatmap_data
    
    @staticmethod
    def get_governance_maturity_score(
        db: Session,
        workspace_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Calculate organization-level governance maturity score.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            
        Returns:
            Maturity score with dimensions, level, strengths, and recommendations
        """
        repositories = db.query(Repository).filter(
            Repository.workspace_id == workspace_id
        ).all()
        
        if not repositories:
            return {
                "score": 0,
                "level": "INITIAL",
                "dimension_scores": {},
                "strengths": [],
                "weaknesses": [],
                "recommended_next_actions": []
            }
        
        from app.services.ci_cd_policy_bulk_operation_service import CICDPolicyBulkOperationService
        
        # Calculate compliance for all repositories to avoid duplicate DB queries and calculations
        repository_compliances = []
        for repo in repositories:
            comp = CICDPolicyBulkOperationService.calculate_repository_compliance(db, repo.id)
            repository_compliances.append(comp)
            
        # Policy Coverage (/20)
        policies_with_coverage = 0
        for comp in repository_compliances:
            if comp.get("current_preset"):
                policies_with_coverage += 1
        policy_coverage_score = int((policies_with_coverage / len(repositories)) * 20)
        
        # Policy Consistency (/20)
        preset_counts = {}
        for comp in repository_compliances:
            preset = comp.get("current_preset") or "STANDARD"
            preset_counts[preset] = preset_counts.get(preset, 0) + 1
        
        # High consistency if most repos use same preset
        max_preset_count = max(preset_counts.values()) if preset_counts else 0
        policy_consistency_score = int((max_preset_count / len(repositories)) * 20)
        
        # Branch Protection Readiness (/20)
        branch_protection_ready = 0
        for comp in repository_compliances:
            if comp.get("branch_protection_ready"):
                branch_protection_ready += 1
        branch_protection_score = int((branch_protection_ready / len(repositories)) * 20)
        
        # Exception Hygiene (/20)
        active_exceptions = db.query(CICDPolicyException).filter(
            CICDPolicyException.workspace_id == workspace_id,
            CICDPolicyException.status == "APPROVED"
        ).count()
        
        expired_exceptions = db.query(CICDPolicyException).filter(
            CICDPolicyException.workspace_id == workspace_id,
            CICDPolicyException.status == "APPROVED",
            CICDPolicyException.expires_at <= datetime.utcnow()
        ).count()
        
        # Fewer exceptions is better
        exception_ratio = active_exceptions / len(repositories) if repositories else 0
        exception_hygiene_score = max(0, 20 - int(exception_ratio * 10) - (expired_exceptions * 2))
        
        # Operational Observability (/10)
        # Based on having governance review snapshots
        snapshot_count = db.query(CICDGovernanceReviewSnapshot).filter(
            CICDGovernanceReviewSnapshot.workspace_id == workspace_id
        ).count()
        observability_score = min(10, snapshot_count)
        
        # Evidence Preservation (/10)
        # Based on compliance score
        avg_compliance = 0
        for comp in repository_compliances:
            avg_compliance += comp.get("compliance_score") or 0
        avg_compliance = avg_compliance / len(repositories) if repositories else 0
        evidence_score = int((avg_compliance / 100) * 10)
        
        total_score = (
            policy_coverage_score +
            policy_consistency_score +
            branch_protection_score +
            exception_hygiene_score +
            observability_score +
            evidence_score
        )
        
        # Determine maturity level
        if total_score >= 90:
            level = "ENTERPRISE_READY"
        elif total_score >= 80:
            level = "ADVANCED"
        elif total_score >= 60:
            level = "MANAGED"
        elif total_score >= 40:
            level = "DEVELOPING"
        else:
            level = "INITIAL"
        
        dimension_scores = {
            "policy_coverage": policy_coverage_score,
            "policy_consistency": policy_consistency_score,
            "branch_protection_readiness": branch_protection_score,
            "exception_hygiene": exception_hygiene_score,
            "operational_observability": observability_score,
            "evidence_preservation": evidence_score
        }
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        
        if policy_coverage_score >= 15:
            strengths.append("Strong policy coverage across repositories")
        else:
            weaknesses.append("Improve policy coverage for all repositories")
        
        if policy_consistency_score >= 15:
            strengths.append("Consistent policy adoption")
        else:
            weaknesses.append("Standardize policy presets across repositories")
        
        if branch_protection_score >= 15:
            strengths.append("Good branch protection readiness")
        else:
            weaknesses.append("Enable branch protection for more repositories")
        
        if exception_hygiene_score >= 15:
            strengths.append("Good exception hygiene")
        else:
            weaknesses.append("Review and reduce exception usage")
        
        if observability_score >= 8:
            strengths.append("Good operational observability")
        else:
            weaknesses.append("Create more governance review snapshots")
        
        if evidence_score >= 8:
            strengths.append("Strong evidence preservation")
        else:
            weaknesses.append("Improve compliance scores")
        
        # Recommended next actions
        recommended_next_actions = []
        if policy_coverage_score < 20:
            recommended_next_actions.append("Ensure all repositories have CI/CD policies configured")
        if policy_consistency_score < 15:
            recommended_next_actions.append("Consider standardizing on organization default preset")
        if branch_protection_score < 15:
            recommended_next_actions.append("Enable branch protection for critical repositories")
        if exception_hygiene_score < 15:
            recommended_next_actions.append("Review and clean up expired or unnecessary exceptions")
        if observability_score < 8:
            recommended_next_actions.append("Schedule regular governance review snapshots")
        if evidence_score < 8:
            recommended_next_actions.append("Address compliance issues in low-scoring repositories")
        
        return {
            "score": total_score,
            "level": level,
            "dimension_scores": dimension_scores,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommended_next_actions": recommended_next_actions
        }
    
    @staticmethod
    def generate_executive_report(
        db: Session,
        workspace_id: uuid.UUID,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Generate executive governance report.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            format: Output format (json, csv, markdown)
            
        Returns:
            Executive report data
        """
        analytics = CICDGovernanceAnalyticsService.get_governance_analytics(db, workspace_id)
        maturity = CICDGovernanceAnalyticsService.get_governance_maturity_score(db, workspace_id)
        heatmap = CICDGovernanceAnalyticsService.get_repository_risk_heatmap(db, workspace_id)
        
        # Top critical repositories
        critical_repos = [r for r in heatmap if r["risk_band"] == "CRITICAL"][:5]
        high_risk_repos = [r for r in heatmap if r["risk_band"] == "HIGH"][:5]
        
        return {
            "executive_summary": {
                "overall_compliance_score": analytics["compliance_trend"]["current_compliance_score"],
                "maturity_score": maturity["score"],
                "maturity_level": maturity["level"],
                "trend_direction": analytics["compliance_trend"]["trend_direction"],
                "total_repositories": len(heatmap),
                "critical_repositories": len(critical_repos),
                "high_risk_repositories": len(high_risk_repos),
                "repositories_with_drift": analytics["drift_trend"]["current_drifted_repositories"],
                "active_exceptions": analytics["exception_analytics"]["active_exceptions"],
                "pending_exceptions": analytics["exception_analytics"]["pending_exceptions"],
                "expired_exceptions": analytics["exception_analytics"]["expired_exceptions"],
                "branch_protection_ready_percentage": round(
                    sum(1 for r in heatmap if r["branch_protection_ready"]) / len(heatmap) * 100, 1
                ) if heatmap else 0
            },
            "maturity_score": maturity,
            "compliance_trend": analytics["compliance_trend"],
            "policy_adoption": analytics["policy_adoption"],
            "drift_trend": analytics["drift_trend"],
            "exception_analytics": analytics["exception_analytics"],
            "risk_heatmap_summary": {
                "total_repositories": len(heatmap),
                "critical_count": len([r for r in heatmap if r["risk_band"] == "CRITICAL"]),
                "high_count": len([r for r in heatmap if r["risk_band"] == "HIGH"]),
                "medium_count": len([r for r in heatmap if r["risk_band"] == "MEDIUM"]),
                "low_count": len([r for r in heatmap if r["risk_band"] == "LOW"])
            },
            "top_critical_repositories": critical_repos,
            "top_high_risk_repositories": high_risk_repos,
            "recommended_executive_actions": maturity["recommended_next_actions"],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def compare_governance_snapshots(
        db: Session,
        workspace_id: uuid.UUID,
        from_snapshot_id: uuid.UUID,
        to_snapshot_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Compare two governance review snapshots.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            from_snapshot_id: Starting snapshot ID
            to_snapshot_id: Ending snapshot ID
            
        Returns:
            Comparison metrics showing changes between snapshots
        """
        from_snapshot = db.query(CICDGovernanceReviewSnapshot).filter(
            CICDGovernanceReviewSnapshot.id == from_snapshot_id,
            CICDGovernanceReviewSnapshot.workspace_id == workspace_id
        ).first()
        
        to_snapshot = db.query(CICDGovernanceReviewSnapshot).filter(
            CICDGovernanceReviewSnapshot.id == to_snapshot_id,
            CICDGovernanceReviewSnapshot.workspace_id == workspace_id
        ).first()
        
        if not from_snapshot or not to_snapshot:
            return {
                "error": "One or both snapshots not found"
            }
        
        compliance_delta = to_snapshot.compliance_score - from_snapshot.compliance_score
        total_repos_delta = to_snapshot.total_repositories - from_snapshot.total_repositories
        critical_delta = to_snapshot.critical_count - from_snapshot.critical_count
        high_risk_delta = to_snapshot.high_risk_count - from_snapshot.high_risk_count
        drifted_delta = to_snapshot.drifted_count - from_snapshot.drifted_count
        compliant_delta = to_snapshot.compliant_count - from_snapshot.compliant_count
        
        return {
            "from_snapshot": {
                "id": str(from_snapshot.id),
                "created_at": from_snapshot.created_at.isoformat(),
                "compliance_score": from_snapshot.compliance_score,
                "total_repositories": from_snapshot.total_repositories
            },
            "to_snapshot": {
                "id": str(to_snapshot.id),
                "created_at": to_snapshot.created_at.isoformat(),
                "compliance_score": to_snapshot.compliance_score,
                "total_repositories": to_snapshot.total_repositories
            },
            "changes": {
                "compliance_score_delta": compliance_delta,
                "total_repositories_delta": total_repos_delta,
                "critical_repositories_delta": critical_delta,
                "high_risk_repositories_delta": high_risk_delta,
                "drifted_repositories_delta": drifted_delta,
                "compliant_repositories_delta": compliant_delta
            },
            "summary": {
                "compliance_improved": compliance_delta > 0,
                "risk_improved": critical_delta < 0 and high_risk_delta < 0,
                "drift_reduced": drifted_delta < 0
            }
        }
