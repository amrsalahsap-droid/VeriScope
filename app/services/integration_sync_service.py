"""
Integration Sync Service

Syncs linked work items and external test cases reliably.
Supports multiple sync modes and handles failures gracefully.
"""

import uuid
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.integration_connection import IntegrationConnection
from app.models.external_work_item import ExternalWorkItem
from app.models.external_test_case_detailed import ExternalTestCase
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.manual_test_execution import ManualTestExecution
from app.models.manual_execution_sync_event import ManualExecutionSyncEvent
from app.services.pr_work_item_linker import PRWorkItemLinker
from app.services.jira_connector import JiraConnector
from app.services.azure_devops_connector import AzureDevOpsConnector
from app.services.testrail_connector import TestRailConnector
from app.services.provider_sync.provider_registry import ProviderRegistry
from app.services.work_item_behavior_mapper import WorkItemBehaviorMapper
from app.services.external_test_case_scenario_mapper import ExternalTestCaseScenarioMapper


logger = logging.getLogger("veriscope.integration_sync_service")


class SyncMode(str, Enum):
    """Sync modes for integration sync."""
    LINKED_ONLY = "LINKED_ONLY"  # Sync only linked work items for PR recommendation
    MANUAL_REPOSITORY = "MANUAL_REPOSITORY"  # Manual full repository sync
    SCHEDULED = "SCHEDULED"  # Scheduled sync (future)


class SyncStatus(str, Enum):
    """Sync status."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILURE = "FAILURE"
    SKIPPED = "SKIPPED"


@dataclass
class SyncResult:
    """Result of integration sync operation."""
    sync_status: SyncStatus
    work_items_synced: int
    test_cases_synced: int
    work_item_mappings_created: int
    test_case_mappings_created: int
    errors: List[str]
    warnings: List[str]
    evidence_gaps: List[str]


class IntegrationSyncService:
    """
    Syncs linked work items and external test cases reliably.
    
    Rules:
    - Retry transient failures
    - Store sync status
    - Do not block recommendation on sync failure
    - Add evidence gap if integration unavailable
    - Idempotent upserts
    """
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 2
    
    def __init__(self, db: Session):
        """Initialize the sync service with database session."""
        self.db = db
    
    def sync_for_pr_recommendation(
        self,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID
    ) -> SyncResult:
        """
        Sync linked work items for PR recommendation (linked-only mode).
        
        Args:
            repository_id: Repository ID
            pull_request_id: Pull request ID
            
        Returns:
            SyncResult with sync status and statistics
        """
        logger.info(f"Starting linked-only sync for PR {pull_request_id}")
        
        errors = []
        warnings = []
        evidence_gaps = []
        
        # Get pull request
        pr = self.db.query(PullRequest).filter(
            PullRequest.id == pull_request_id
        ).first()
        
        if not pr:
            errors.append(f"Pull request {pull_request_id} not found")
            return SyncResult(
                sync_status=SyncStatus.FAILURE,
                work_items_synced=0,
                test_cases_synced=0,
                work_item_mappings_created=0,
                test_case_mappings_created=0,
                errors=errors,
                warnings=warnings,
                evidence_gaps=evidence_gaps
            )
        
        # Detect linked work item keys from PR
        work_item_keys = self._detect_linked_work_items(pr)
        
        if not work_item_keys:
            warnings.append("No linked work item keys detected from PR")
            return SyncResult(
                sync_status=SyncStatus.SKIPPED,
                work_items_synced=0,
                test_cases_synced=0,
                work_item_mappings_created=0,
                test_case_mappings_created=0,
                errors=errors,
                warnings=warnings,
                evidence_gaps=evidence_gaps
            )
        
        logger.info(f"Detected {len(work_item_keys)} linked work item keys: {work_item_keys}")
        
        # Get integration connections for the repository
        connections = self.db.query(IntegrationConnection).filter(
            IntegrationConnection.repository_id == repository_id,
            IntegrationConnection.is_active == True
        ).all()
        
        if not connections:
            evidence_gaps.append("No active integration connections found - external context unavailable")
            return SyncResult(
                sync_status=SyncStatus.SKIPPED,
                work_items_synced=0,
                test_cases_synced=0,
                work_item_mappings_created=0,
                test_case_mappings_created=0,
                errors=errors,
                warnings=warnings,
                evidence_gaps=evidence_gaps
            )
        
        # Sync work items
        work_items_synced = 0
        test_cases_synced = 0
        work_item_mappings_created = 0
        test_case_mappings_created = 0
        
        for connection in connections:
            try:
                # Sync work items for this connection
                sync_result = self._sync_work_items_for_connection(
                    connection=connection,
                    work_item_keys=work_item_keys,
                    repository_id=repository_id
                )
                
                work_items_synced += sync_result["work_items_synced"]
                test_cases_synced += sync_result["test_cases_synced"]
                work_item_mappings_created += sync_result["work_item_mappings_created"]
                test_case_mappings_created += sync_result["test_case_mappings_created"]
                warnings.extend(sync_result["warnings"])
                
            except Exception as e:
                logger.error(f"Failed to sync work items for connection {connection.provider}: {e}")
                errors.append(f"Failed to sync {connection.provider}: {str(e)}")
                # Continue with other connections
        
        # Determine overall sync status
        if errors:
            if work_items_synced > 0 or test_cases_synced > 0:
                sync_status = SyncStatus.PARTIAL_SUCCESS
            else:
                sync_status = SyncStatus.FAILURE
        else:
            sync_status = SyncStatus.SUCCESS
        
        logger.info(
            f"Sync completed: status={sync_status}, work_items={work_items_synced}, "
            f"test_cases={test_cases_synced}, mappings={work_item_mappings_created + test_case_mappings_created}"
        )
        
        return SyncResult(
            sync_status=sync_status,
            work_items_synced=work_items_synced,
            test_cases_synced=test_cases_synced,
            work_item_mappings_created=work_item_mappings_created,
            test_case_mappings_created=test_case_mappings_created,
            errors=errors,
            warnings=warnings,
            evidence_gaps=evidence_gaps
        )
    
    def _detect_linked_work_items(self, pr: PullRequest) -> List[str]:
        """
        Detect linked work item keys from PR.
        
        Args:
            pr: PullRequest
            
        Returns:
            List of work item keys
        """
        linker = PRWorkItemLinker(self.db)
        
        # Detect work item keys from PR metadata
        detected = linker._detect_all_keys(
            pull_request=pr,
            commits=[]
        )
        
        return list(detected.keys())
    
    def _sync_work_items_for_connection(
        self,
        connection: IntegrationConnection,
        work_item_keys: List[str],
        repository_id: uuid.UUID
    ) -> Dict[str, int]:
        """
        Sync work items for a specific integration connection.
        
        Args:
            connection: IntegrationConnection
            work_item_keys: List of work item keys to sync
            repository_id: Repository ID
            
        Returns:
            Dictionary with sync statistics
        """
        warnings = []
        work_items_synced = 0
        test_cases_synced = 0
        work_item_mappings_created = 0
        test_case_mappings_created = 0
        
        # Get connector based on provider
        connector = self._get_connector(connection)
        
        if not connector:
            warnings.append(f"No connector available for provider {connection.provider}")
            return {
                "work_items_synced": 0,
                "test_cases_synced": 0,
                "work_item_mappings_created": 0,
                "test_case_mappings_created": 0,
                "warnings": warnings
            }
        
        # Fetch work items with retry
        work_items = self._fetch_work_items_with_retry(
            connector=connector,
            work_item_keys=work_item_keys
        )
        
        if not work_items:
            warnings.append(f"No work items fetched from {connection.provider}")
            return {
                "work_items_synced": 0,
                "test_cases_synced": 0,
                "work_item_mappings_created": 0,
                "test_case_mappings_created": 0,
                "warnings": warnings
            }
        
        # Upsert work items
        work_item_mapper = WorkItemBehaviorMapper(self.db)
        
        for work_item_data in work_items:
            try:
                # Upsert external work item
                external_work_item = self._upsert_external_work_item(
                    connection=connection,
                    work_item_data=work_item_data,
                    repository_id=repository_id
                )
                
                work_items_synced += 1
                
                # Map work item to behaviors/journeys
                mapping_result = work_item_mapper.map_work_item(
                    work_item=external_work_item,
                    repository_id=repository_id
                )
                
                work_item_mapper.save_mapping(external_work_item, mapping_result)
                work_item_mappings_created += 1
                
                # Fetch linked test cases if available
                if connection.provider in ("TESTRAIL", "XRAY", "ZEPHYR"):
                    test_cases = self._fetch_linked_test_cases(
                        connector=connector,
                        work_item_key=work_item_data.get("key")
                    )
                    
                    for test_case_data in test_cases:
                        # Upsert external test case
                        external_test_case = self._upsert_external_test_case(
                            connection=connection,
                            test_case_data=test_case_data,
                            repository_id=repository_id,
                            linked_work_item_key=work_item_data.get("key")
                        )
                        
                        test_cases_synced += 1
                        
                        # Map test case to scenarios
                        test_case_mapper = ExternalTestCaseScenarioMapper(self.db)
                        scenario_mapping_result = test_case_mapper.map_test_case(
                            test_case=external_test_case,
                            repository_id=repository_id
                        )
                        
                        test_case_mapper.save_mapping(external_test_case, scenario_mapping_result)
                        test_case_mappings_created += 1
                
            except Exception as e:
                logger.error(f"Failed to sync work item {work_item_data.get('key')}: {e}")
                warnings.append(f"Failed to sync work item {work_item_data.get('key')}: {str(e)}")
        
        return {
            "work_items_synced": work_items_synced,
            "test_cases_synced": test_cases_synced,
            "work_item_mappings_created": work_item_mappings_created,
            "test_case_mappings_created": test_case_mappings_created,
            "warnings": warnings
        }
    
    def _get_connector(self, connection: IntegrationConnection):
        """
        Get connector instance based on provider.
        
        Args:
            connection: IntegrationConnection
            
        Returns:
            Connector instance or None
        """
        config = connection.config or {}
        
        if connection.provider == "JIRA":
            return JiraConnector(
                base_url=config.get("base_url"),
                api_token=config.get("api_token"),
                username=config.get("username")
            )
        elif connection.provider == "AZURE_DEVOPS":
            return AzureDevOpsConnector(
                organization_url=config.get("organization_url"),
                project=config.get("project"),
                pat_token=config.get("pat_token")
            )
        elif connection.provider == "TESTRAIL":
            return TestRailConnector(
                base_url=config.get("base_url"),
                username=config.get("username"),
                api_key=config.get("api_key")
            )
        else:
            logger.warning(f"Unsupported provider: {connection.provider}")
            return None
    
    def _fetch_work_items_with_retry(
        self,
        connector,
        work_item_keys: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch work items with retry logic.
        
        Args:
            connector: Connector instance
            work_item_keys: List of work item keys
            
        Returns:
            List of work item data
        """
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                work_items = []
                
                for key in work_item_keys:
                    try:
                        work_item = connector.fetch_work_item(key)
                        if work_item:
                            work_items.append(work_item)
                    except Exception as e:
                        logger.warning(f"Failed to fetch work item {key} (attempt {attempt + 1}): {e}")
                        if attempt == self.MAX_RETRIES - 1:
                            last_error = e
                
                return work_items
                
            except Exception as e:
                last_error = e
                logger.warning(f"Fetch attempt {attempt + 1} failed: {e}")
                
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY_SECONDS)
        
        logger.error(f"Failed to fetch work items after {self.MAX_RETRIES} attempts: {last_error}")
        return []
    
    def _fetch_linked_test_cases(
        self,
        connector,
        work_item_key: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch linked test cases for a work item.
        
        Args:
            connector: Connector instance
            work_item_key: Work item key
            
        Returns:
            List of test case data
        """
        try:
            # TestRail-specific: fetch cases by reference
            if hasattr(connector, 'fetch_cases_by_reference'):
                test_cases = connector.fetch_cases_by_reference(work_item_key)
                return test_cases
        except Exception as e:
            logger.warning(f"Failed to fetch linked test cases for {work_item_key}: {e}")
        
        return []
    
    def _upsert_external_work_item(
        self,
        connection: IntegrationConnection,
        work_item_data: Dict[str, Any],
        repository_id: uuid.UUID
    ) -> ExternalWorkItem:
        """
        Upsert external work item (idempotent).
        
        Args:
            connection: IntegrationConnection
            work_item_data: Work item data from connector
            repository_id: Repository ID
            
        Returns:
            ExternalWorkItem
        """
        # Check for existing work item
        existing = self.db.query(ExternalWorkItem).filter(
            ExternalWorkItem.external_key == work_item_data.get("key"),
            ExternalWorkItem.provider == connection.provider,
            ExternalWorkItem.repository_id == repository_id
        ).first()
        
        if existing:
            # Update existing
            existing.title = work_item_data.get("title", existing.title)
            existing.description = work_item_data.get("description", existing.description)
            existing.status = work_item_data.get("status", existing.status)
            existing.work_item_type = work_item_data.get("work_item_type", existing.work_item_type)
            existing.acceptance_criteria = work_item_data.get("acceptance_criteria", existing.acceptance_criteria)
            existing.raw_payload = work_item_data
            existing.last_synced_at = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            return existing
        else:
            # Create new
            work_item = ExternalWorkItem(
                id=uuid.uuid4(),
                workspace_id=connection.workspace_id,
                repository_id=repository_id,
                integration_connection_id=connection.id,
                provider=connection.provider,
                external_id=work_item_data.get("id"),
                external_key=work_item_data.get("key"),
                title=work_item_data.get("title"),
                description=work_item_data.get("description"),
                status=work_item_data.get("status"),
                work_item_type=work_item_data.get("work_item_type"),
                acceptance_criteria=work_item_data.get("acceptance_criteria", []),
                raw_payload=work_item_data,
                last_synced_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(work_item)
            self.db.commit()
            return work_item
    
    def _upsert_external_test_case(
        self,
        connection: IntegrationConnection,
        test_case_data: Dict[str, Any],
        repository_id: uuid.UUID,
        linked_work_item_key: Optional[str]
    ) -> ExternalTestCase:
        """
        Upsert external test case (idempotent).
        
        Args:
            connection: IntegrationConnection
            test_case_data: Test case data from connector
            repository_id: Repository ID
            linked_work_item_key: Linked work item key
            
        Returns:
            ExternalTestCase
        """
        # Check for existing test case
        existing = self.db.query(ExternalTestCase).filter(
            ExternalTestCase.external_key == test_case_data.get("key"),
            ExternalTestCase.provider == connection.provider,
            ExternalTestCase.repository_id == repository_id
        ).first()
        
        if existing:
            # Update existing
            existing.title = test_case_data.get("title", existing.title)
            existing.description = test_case_data.get("description", existing.description)
            existing.priority = test_case_data.get("priority", existing.priority)
            existing.test_type = test_case_data.get("test_type", existing.test_type)
            existing.preconditions = test_case_data.get("preconditions", existing.preconditions)
            existing.steps = test_case_data.get("steps", existing.steps)
            existing.expected_result = test_case_data.get("expected_result", existing.expected_result)
            existing.tags = test_case_data.get("tags", existing.tags)
            existing.linked_work_item_keys = [linked_work_item_key] if linked_work_item_key else existing.linked_work_item_keys
            existing.raw_payload = test_case_data
            existing.last_synced_at = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            return existing
        else:
            # Create new
            test_case = ExternalTestCase(
                id=uuid.uuid4(),
                workspace_id=connection.workspace_id,
                repository_id=repository_id,
                integration_connection_id=connection.id,
                provider=connection.provider,
                external_id=test_case_data.get("id"),
                external_key=test_case_data.get("key"),
                title=test_case_data.get("title"),
                description=test_case_data.get("description"),
                priority=test_case_data.get("priority"),
                test_type=test_case_data.get("test_type"),
                preconditions=test_case_data.get("preconditions", []),
                steps=test_case_data.get("steps", []),
                expected_result=test_case_data.get("expected_result"),
                tags=test_case_data.get("tags", []),
                linked_work_item_keys=[linked_work_item_key] if linked_work_item_key else [],
                automation_status=test_case_data.get("automation_status", "MANUAL"),
                url=test_case_data.get("url"),
                raw_payload=test_case_data,
                last_synced_at=datetime.utcnow(),
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(test_case)
            self.db.commit()
            return test_case
    
    def sync_manual_execution_to_provider(
        self,
        execution_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Sync manual test execution result to external provider (TestRail).
        
        Flow:
        1. Find execution
        2. Find linked ExternalTestCase
        3. Find IntegrationConnection
        4. Get connector
        5. Push result
        6. Update execution sync fields
        7. Create sync event audit trail
        
        Args:
            execution_id: ManualTestExecution ID
            
        Returns:
            Dictionary with sync result
        """
        # Find execution
        execution = self.db.query(ManualTestExecution).filter(
            ManualTestExecution.id == execution_id
        ).first()
        
        if not execution:
            return {
                'success': False,
                'status': 'FAILED',
                'error': f'Execution {execution_id} not found'
            }
        
        # Find linked ExternalTestCase
        external_test_case = self.db.query(ExternalTestCase).filter(
            ExternalTestCase.id == execution.external_test_case_id
        ).first()
        
        if not external_test_case:
            return {
                'success': False,
                'status': 'FAILED',
                'error': f'External test case {execution.external_test_case_id} not found'
            }
        
        # Check provider sync capability via registry (replaces hardcoded TESTRAIL guard)
        registry = ProviderRegistry()
        provider = external_test_case.provider

        if not registry.is_execution_sync_supported(provider):
            cap = registry.get_capability(provider)
            if cap is None:
                error_msg = f'Provider {provider} is not registered in the sync framework'
            else:
                error_msg = (
                    f'Provider {provider} does not support execution sync '
                    f'(supports_execution_sync=False)'
                )
            return {
                'success': False,
                'status': 'FAILED',
                'error': error_msg
            }

        # Find IntegrationConnection
        connection = self.db.query(IntegrationConnection).filter(
            IntegrationConnection.id == external_test_case.integration_connection_id
        ).first()

        if not connection:
            return {
                'success': False,
                'status': 'FAILED',
                'error': f'Integration connection {external_test_case.integration_connection_id} not found'
            }

        # Get sync connector via registry (provider-agnostic)
        config = connection.config or {}
        connector = registry.get_connector(provider, config)

        if not connector:
            return {
                'success': False,
                'status': 'FAILED',
                'error': f'No sync connector available for provider {provider}'
            }
        
        # Prepare test case reference with run_id from provider metadata
        test_case_reference = {
            'external_id': external_test_case.external_id,
            'external_key': external_test_case.external_key,
            'run_id': connection.provider_metadata.get('default_test_run_id') if connection.provider_metadata else None
        }
        
        # Prepare execution data
        execution_data = {
            'outcome': execution.outcome,
            'notes': execution.notes,
            'executed_by': execution.executed_by_name,
            'executed_at': execution.executed_at.isoformat() if execution.executed_at else None
        }
        
        # Sanitize request payload to ensure no credentials are persisted
        from app.services.security.credential_encryption_service import get_credential_encryption_service
        try:
            encryption_service = get_credential_encryption_service()
            sanitized_request_payload = encryption_service.redact({
                'test_case_reference': test_case_reference,
                'execution': execution_data
            })
        except Exception:
            # If encryption service fails, still sanitize with basic redaction
            sanitized_request_payload = {
                'test_case_reference': test_case_reference,
                'execution': execution_data
            }
        
        # Create sync event record (PENDING)
        sync_event = ManualExecutionSyncEvent(
            id=uuid.uuid4(),
            execution_id=execution_id,
            provider=connection.provider,
            status='PENDING',
            request_payload=sanitized_request_payload,
            response_payload=None,
            error_message=None,
            external_run_id=None,
            external_execution_id=None,
            created_at=datetime.utcnow(),
            attempt_count=0,
            max_attempts=3
        )
        self.db.add(sync_event)
        self.db.commit()
        
        return {
            'success': True,
            'status': 'PENDING',
            'sync_event_id': str(sync_event.id)
        }
    
    def enqueue_manual_execution_sync(self, execution_id: uuid.UUID) -> Dict[str, Any]:
        """
        Enqueue a manual execution for sync (called by manual execution creation).
        
        Args:
            execution_id: ID of the manual execution to sync
            
        Returns:
            Enqueue result
        """
        # Get execution
        execution = self.db.query(ManualTestExecution).filter(
            ManualTestExecution.id == execution_id
        ).first()
        
        if not execution:
            logger.error(f"Execution {execution_id} not found for enqueue")
            return {
                'success': False,
                'status': 'FAILED',
                'error': f'Execution {execution_id} not found'
            }
        
        # Get external test case
        external_test_case = self.db.query(ExternalTestCase).filter(
            ExternalTestCase.id == execution.external_test_case_id
        ).first()
        
        if not external_test_case:
            logger.error(f"External test case {execution.external_test_case_id} not found")
            return {
                'success': False,
                'status': 'FAILED',
                'error': 'External test case not found'
            }
        
        # Get connection
        connection = self.db.query(IntegrationConnection).filter(
            IntegrationConnection.id == external_test_case.integration_connection_id
        ).first()
        
        if not connection:
            logger.error(f"Integration connection {external_test_case.integration_connection_id} not found")
            return {
                'success': False,
                'status': 'FAILED',
                'error': 'Integration connection not found'
            }
        
        # Check if provider supports execution sync
        from app.services.provider_sync.provider_registry import ProviderRegistry
        registry = ProviderRegistry()
        if not registry.is_execution_sync_supported(connection.provider):
            logger.info(f"Provider {connection.provider} does not support execution sync, skipping enqueue")
            return {
                'success': True,
                'status': 'SKIPPED',
                'error': 'Provider does not support execution sync'
            }
        
        # Prepare test case reference
        test_case_reference = {
            'external_id': external_test_case.external_id,
            'external_key': external_test_case.external_key,
            'run_id': connection.provider_metadata.get('default_test_run_id') if connection.provider_metadata else None
        }
        
        # Prepare execution data
        execution_data = {
            'outcome': execution.outcome,
            'notes': execution.notes,
            'executed_by': execution.executed_by_name,
            'executed_at': execution.executed_at.isoformat() if execution.executed_at else None
        }
        
        # Sanitize request payload
        from app.services.security.credential_encryption_service import get_credential_encryption_service
        try:
            encryption_service = get_credential_encryption_service()
            sanitized_request_payload = encryption_service.redact({
                'test_case_reference': test_case_reference,
                'execution': execution_data
            })
        except Exception:
            sanitized_request_payload = {
                'test_case_reference': test_case_reference,
                'execution': execution_data
            }
        
        # Create sync event record (PENDING)
        sync_event = ManualExecutionSyncEvent(
            id=uuid.uuid4(),
            execution_id=execution_id,
            provider=connection.provider,
            status='PENDING',
            request_payload=sanitized_request_payload,
            response_payload=None,
            error_message=None,
            external_run_id=None,
            external_execution_id=None,
            created_at=datetime.utcnow(),
            attempt_count=0,
            max_attempts=3
        )
        self.db.add(sync_event)
        self.db.commit()
        
        logger.info(f"Enqueued sync event {sync_event.id} for execution {execution_id}")
        
        return {
            'success': True,
            'status': 'PENDING',
            'sync_event_id': str(sync_event.id)
        }
    
    def process_sync_event(self, sync_event_id: uuid.UUID) -> Dict[str, Any]:
        """
        Process a sync event (called by queue worker).
        
        Args:
            sync_event_id: ID of the sync event to process
            
        Returns:
            Sync result
        """
        # Get sync event
        sync_event = self.db.query(ManualExecutionSyncEvent).filter(
            ManualExecutionSyncEvent.id == sync_event_id
        ).first()
        
        if not sync_event:
            logger.error(f"Sync event {sync_event_id} not found")
            return {
                'success': False,
                'status': 'FAILED',
                'error': f'Sync event {sync_event_id} not found'
            }
        
        # Mark as IN_PROGRESS
        sync_event.status = 'IN_PROGRESS'
        sync_event.locked_at = datetime.utcnow()
        self.db.commit()
        
        # Get execution
        execution = self.db.query(ManualTestExecution).filter(
            ManualTestExecution.id == sync_event.execution_id
        ).first()
        
        if not execution:
            logger.error(f"Execution {sync_event.execution_id} not found")
            sync_event.status = 'FAILED'
            sync_event.last_error = 'Execution not found'
            sync_event.locked_at = None
            self.db.commit()
            return {
                'success': False,
                'status': 'FAILED',
                'error': 'Execution not found'
            }
        
        # Get connection
        external_test_case = self.db.query(ExternalTestCase).filter(
            ExternalTestCase.id == execution.external_test_case_id
        ).first()
        
        if not external_test_case:
            logger.error(f"External test case {execution.external_test_case_id} not found")
            sync_event.status = 'FAILED'
            sync_event.last_error = 'External test case not found'
            sync_event.locked_at = None
            self.db.commit()
            return {
                'success': False,
                'status': 'FAILED',
                'error': 'External test case not found'
            }
        
        connection = self.db.query(IntegrationConnection).filter(
            IntegrationConnection.id == external_test_case.integration_connection_id
        ).first()
        
        if not connection:
            logger.error(f"Integration connection {external_test_case.integration_connection_id} not found")
            sync_event.status = 'FAILED'
            sync_event.last_error = 'Integration connection not found'
            sync_event.locked_at = None
            self.db.commit()
            return {
                'success': False,
                'status': 'FAILED',
                'error': 'Integration connection not found'
            }
        
        # Get sync connector
        provider = connection.provider
        registry = ProviderRegistry()
        config = {}
        
        # Decrypt credentials
        try:
            encryption_service = get_credential_encryption_service()
            config = encryption_service.decrypt(connection.encrypted_credentials)
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for {provider}: {e}")
            sync_event.status = 'FAILED'
            sync_event.last_error = f'Failed to decrypt credentials: {e}'
            sync_event.locked_at = None
            self.db.commit()
            return {
                'success': False,
                'status': 'FAILED',
                'error': f'Failed to decrypt credentials: {e}'
            }
        
        connector = registry.get_connector(provider, config)
        
        if not connector:
            logger.error(f"No sync connector available for provider {provider}")
            sync_event.status = 'FAILED'
            sync_event.last_error = f'No sync connector available for provider {provider}'
            sync_event.locked_at = None
            self.db.commit()
            return {
                'success': False,
                'status': 'FAILED',
                'error': f'No sync connector available for provider {provider}'
            }
        
        # Prepare test case reference
        test_case_reference = {
            'external_id': external_test_case.external_id,
            'external_key': external_test_case.external_key,
            'run_id': connection.provider_metadata.get('default_test_run_id') if connection.provider_metadata else None
        }
        
        # Prepare execution data
        execution_data = {
            'outcome': execution.outcome,
            'notes': execution.notes,
            'executed_by': execution.executed_by_name,
            'executed_at': execution.executed_at.isoformat() if execution.executed_at else None
        }
        
        # Push result
        try:
            sync_result = connector.push_execution_result(test_case_reference, execution_data)
            
            # Sanitize response payload
            try:
                encryption_service = get_credential_encryption_service()
                sanitized_response_payload = encryption_service.redact(sync_result)
            except Exception:
                sanitized_response_payload = sync_result
            
            # Update sync event
            sync_event.status = sync_result.get('status', 'FAILED')
            sync_event.response_payload = sanitized_response_payload
            sync_event.error_message = sync_result.get('error')
            sync_event.external_run_id = sync_result.get('external_run_id')
            sync_event.external_execution_id = sync_result.get('external_execution_id')
            sync_event.locked_at = None
            sync_event.locked_by = None
            
            if sync_event.status == 'SYNCED':
                sync_event.completed_at = datetime.utcnow()
            
            # Update execution sync fields
            execution.external_system = connection.provider
            execution.external_run_id = sync_result.get('external_run_id')
            execution.external_execution_id = sync_result.get('external_execution_id')
            execution.sync_status = sync_result.get('status')
            execution.last_synced_at = datetime.utcnow()
            
            self.db.commit()
            
            return {
                'success': sync_result.get('success', False),
                'status': sync_result.get('status'),
                'external_run_id': sync_result.get('external_run_id'),
                'external_execution_id': sync_result.get('external_execution_id'),
                'error': sync_result.get('error')
            }
            
        except Exception as e:
            error_msg = f'Failed to sync execution: {str(e)}'
            logger.error(error_msg)
            
            # Update sync event as failed
            sync_event.status = 'FAILED'
            sync_event.error_message = error_msg
            
            # Update execution sync fields
            execution.sync_status = 'FAILED'
            execution.last_synced_at = datetime.utcnow()
            
            self.db.commit()
            
            return {
                'success': False,
                'status': 'FAILED',
                'error': error_msg
            }
