"""Integration Metrics Service

Provides provider-level metrics for integration sync monitoring.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case
from app.models.manual_execution_sync_event import ManualExecutionSyncEvent
from app.models.manual_test_execution import ManualTestExecution
from app.models.integration_provider_cooldown import IntegrationProviderCooldown


class IntegrationMetricsService:
    """Service for calculating integration sync metrics."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_provider_metrics(
        self,
        repository_id: str,
        provider: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict:
        """
        Get metrics for a specific provider or all providers.
        
        Args:
            repository_id: Repository UUID (string or UUID)
            provider: Optional provider filter (e.g., "TESTRAIL")
            from_date: Optional start date for filtering
            to_date: Optional end date for filtering
        
        Returns:
            Dictionary with provider metrics
        """
        # Convert repository_id to UUID if it's a string
        from uuid import UUID
        if isinstance(repository_id, str):
            repository_id = UUID(repository_id)
        
        # Build base query with join to execution for repository filtering
        query = self.db.query(
            ManualExecutionSyncEvent.provider,
            func.count(ManualExecutionSyncEvent.id).label('total_syncs'),
            func.sum(
                case(
                    (ManualExecutionSyncEvent.status == 'SYNCED', 1),
                    else_=0
                )
            ).label('successful_syncs'),
            func.sum(
                case(
                    (ManualExecutionSyncEvent.status == 'FAILED', 1),
                    else_=0
                )
            ).label('failed_syncs'),
            func.sum(
                case(
                    (ManualExecutionSyncEvent.status == 'RETRY_PENDING', 1),
                    else_=0
                )
            ).label('retry_pending_syncs'),
            func.sum(
                case(
                    (ManualExecutionSyncEvent.status == 'DEAD_LETTER', 1),
                    else_=0
                )
            ).label('dead_letter_syncs'),
            func.sum(ManualExecutionSyncEvent.attempt_count).label('total_attempts'),
            func.max(
                case(
                    (ManualExecutionSyncEvent.status == 'SYNCED', ManualExecutionSyncEvent.created_at),
                    else_=None
                )
            ).label('last_success_at'),
            func.max(
                case(
                    (ManualExecutionSyncEvent.status.in_(['FAILED', 'DEAD_LETTER']), ManualExecutionSyncEvent.created_at),
                    else_=None
                )
            ).label('last_failure_at')
        ).join(
            ManualTestExecution,
            ManualExecutionSyncEvent.execution_id == ManualTestExecution.id
        ).filter(
            ManualTestExecution.repository_id == repository_id
        )
        
        if provider:
            query = query.filter(ManualExecutionSyncEvent.provider == provider.upper())
        
        if from_date:
            query = query.filter(ManualExecutionSyncEvent.created_at >= from_date)
        
        if to_date:
            query = query.filter(ManualExecutionSyncEvent.created_at <= to_date)
        
        # Group by provider
        results = query.group_by(ManualExecutionSyncEvent.provider).all()
        
        # Build metrics response
        providers_metrics = []
        overall_total = 0
        overall_successful = 0
        overall_failed = 0
        overall_retry_pending = 0
        overall_dead_letter = 0
        overall_attempts = 0
        
        for row in results:
            total_syncs = row.total_syncs or 0
            successful_syncs = row.successful_syncs or 0
            failed_syncs = row.failed_syncs or 0
            retry_pending_syncs = row.retry_pending_syncs or 0
            dead_letter_syncs = row.dead_letter_syncs or 0
            total_attempts = row.total_attempts or 0
            
            success_rate = (successful_syncs / total_syncs * 100) if total_syncs > 0 else 0
            failure_rate = (failed_syncs / total_syncs * 100) if total_syncs > 0 else 0
            average_attempts = (total_attempts / total_syncs) if total_syncs > 0 else 0
            
            provider_metric = {
                "provider": row.provider,
                "totalSyncs": total_syncs,
                "successfulSyncs": successful_syncs,
                "failedSyncs": failed_syncs,
                "retryPendingSyncs": retry_pending_syncs,
                "deadLetterSyncs": dead_letter_syncs,
                "successRate": round(success_rate, 1),
                "failureRate": round(failure_rate, 1),
                "averageAttempts": round(average_attempts, 1),
                "lastSuccessAt": row.last_success_at.isoformat() if row.last_success_at else None,
                "lastFailureAt": row.last_failure_at.isoformat() if row.last_failure_at else None
            }
            
            providers_metrics.append(provider_metric)
            
            # Update overall totals
            overall_total += total_syncs
            overall_successful += successful_syncs
            overall_failed += failed_syncs
            overall_retry_pending += retry_pending_syncs
            overall_dead_letter += dead_letter_syncs
            overall_attempts += total_attempts
        
        # Calculate overall metrics
        overall_success_rate = (overall_successful / overall_total * 100) if overall_total > 0 else 0
        overall_failure_rate = (overall_failed / overall_total * 100) if overall_total > 0 else 0
        overall_average_attempts = (overall_attempts / overall_total) if overall_total > 0 else 0
        
        return {
            "providers": providers_metrics,
            "overall": {
                "totalSyncs": overall_total,
                "successfulSyncs": overall_successful,
                "failedSyncs": overall_failed,
                "retryPendingSyncs": overall_retry_pending,
                "deadLetterSyncs": overall_dead_letter,
                "successRate": round(overall_success_rate, 1),
                "failureRate": round(overall_failure_rate, 1),
                "averageAttempts": round(overall_average_attempts, 1)
            }
        }
    
    def get_alerts(
        self,
        repository_id: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Generate alert states based on metrics.
        
        Args:
            repository_id: Repository UUID (string or UUID)
            from_date: Optional start date for filtering
            to_date: Optional end date for filtering
        
        Returns:
            List of alert dictionaries
        """
        # Convert repository_id to UUID if it's a string
        from uuid import UUID
        if isinstance(repository_id, str):
            repository_id = UUID(repository_id)
        
        alerts = []
        
        # Default to last 24 hours if no date range provided
        if not from_date:
            from_date = datetime.utcnow() - timedelta(hours=24)
        if not to_date:
            to_date = datetime.utcnow()
        
        # Get metrics for the period
        metrics = self.get_provider_metrics(repository_id, from_date=from_date, to_date=to_date)
        
        # Check for high failure rate (> 20%)
        if metrics["overall"]["failureRate"] > 20:
            alerts.append({
                "code": "HIGH_FAILURE_RATE",
                "severity": "HIGH",
                "message": f"Overall failure rate is {metrics['overall']['failureRate']}% over the selected period."
            })
        
        # Check for dead-letter presence
        if metrics["overall"]["deadLetterSyncs"] > 0:
            alerts.append({
                "code": "DEAD_LETTER_PRESENT",
                "severity": "HIGH",
                "message": f"{metrics['overall']['deadLetterSyncs']} sync events are in dead-letter status."
            })
        
        # Check for no recent success (last 24 hours)
        last_success = None
        for provider in metrics["providers"]:
            if provider["lastSuccessAt"]:
                provider_last_success = datetime.fromisoformat(provider["lastSuccessAt"])
                if not last_success or provider_last_success > last_success:
                    last_success = provider_last_success
        
        if last_success and (datetime.utcnow() - last_success) > timedelta(hours=24):
            alerts.append({
                "code": "NO_RECENT_SUCCESS",
                "severity": "MEDIUM",
                "message": f"No successful syncs in the last 24 hours. Last success was at {last_success.isoformat()}."
            })
        
        # Check for growing backlog (retry pending > 10% of total)
        if metrics["overall"]["totalSyncs"] > 0:
            backlog_ratio = (metrics["overall"]["retryPendingSyncs"] / metrics["overall"]["totalSyncs"]) * 100
            if backlog_ratio > 10:
                alerts.append({
                    "code": "SYNC_BACKLOG_GROWING",
                    "severity": "MEDIUM",
                    "message": f"{metrics['overall']['retryPendingSyncs']} sync events are pending retry ({round(backlog_ratio, 1)}% of total)."
                })
        
        # Check for active provider cooldowns
        active_cooldowns = self.db.query(IntegrationProviderCooldown).filter(
            IntegrationProviderCooldown.repository_id == repository_id,
            IntegrationProviderCooldown.cooldown_until > datetime.utcnow()
        ).all()
        
        if active_cooldowns:
            providers_with_cooldown = [c.provider for c in active_cooldowns]
            alerts.append({
                "code": "PROVIDER_COOLDOWN_ACTIVE",
                "severity": "LOW",
                "message": f"Provider cooldown active for: {', '.join(providers_with_cooldown)}."
            })
        
        return alerts
