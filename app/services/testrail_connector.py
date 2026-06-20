"""
TestRail Connector V1

Imports managed test cases from TestRail for Veriscope.
Supports fetching by reference key (linked to work items) or by project.
"""

import httpx
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.services.test_management_connector import TestManagementConnector
from app.constants.test_management import map_veriscope_to_testrail_outcome


logger = logging.getLogger("veriscope.testrail_connector")


@dataclass
class TestRailTestCase:
    """Normalized TestRail test case data."""
    external_id: str
    external_key: str
    title: str
    description: Optional[str]
    preconditions: List[str]
    steps: List[Dict[str, str]]
    expected_result: Optional[str]
    priority: Optional[str]
    test_type: Optional[str]
    automation_status: str
    tags: List[str]
    linked_work_item_keys: List[str]
    url: str
    raw_payload: Dict[str, Any]


class TestRailConnector(TestManagementConnector):
    """
    TestRail connector for importing test cases.
    
    V1 Scope:
    - Fetch test cases by reference key (linked to work items) first
    - Support project-based fetching (with caution for large projects)
    - Extract steps, preconditions, expected results
    - Handle auth failures gracefully
    - Preserve raw payload
    - Manual test cases ≠ executed tests
    """
    
    def __init__(self, base_url: str, username: str, api_key: str):
        """
        Initialize TestRail connector.
        
        Args:
            base_url: TestRail instance URL (e.g., "https://company.testrail.io")
            username: TestRail username
            api_key: TestRail API key
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.api_key = api_key
        self.client = httpx.Client(timeout=30.0)
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "TESTRAIL"
    
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        Establish connection to TestRail.
        
        Args:
            credentials: Dict with base_url, username, api_key
            
        Returns:
            True if connection successful, False otherwise
        """
        self.base_url = credentials.get('base_url', '').rstrip('/')
        self.username = credentials.get('username', '')
        self.api_key = credentials.get('api_key', '')
        
        # Validate connection
        return self.validate_credentials(credentials)
    
    def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate credentials without establishing a full connection.
        
        Args:
            credentials: Dict with base_url, username, api_key
            
        Returns:
            True if credentials are valid, False otherwise
        """
        base_url = credentials.get('base_url', '').rstrip('/')
        username = credentials.get('username', '')
        api_key = credentials.get('api_key', '')
        
        if not all([base_url, username, api_key]):
            return False
        
        try:
            # Test connection with a simple API call
            response = self.client.get(
                f"{base_url}/index.php?/api/v2/get_users",
                auth=(username, api_key),
                headers={"Accept": "application/json"}
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"TestRail credential validation failed: {e}")
            return False
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """
        List available projects in TestRail.
        
        Returns:
            List of project dictionaries
        """
        try:
            response = self.client.get(
                f"{self.base_url}/index.php?/api/v2/get_projects",
                auth=(self.username, self.api_key),
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"TestRail API error listing projects: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error listing TestRail projects: {e}")
            return []
    
    def list_test_cases(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List test cases for a given project.
        
        NOTE: Use with caution for large projects. Prefer fetch_cases_by_reference.
        
        Args:
            project_id: TestRail project ID
            
        Returns:
            List of test case dictionaries
        """
        return self.fetch_cases_by_project(project_id)
    
    def list_test_runs(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List test runs for a given project.
        
        NOTE: Not used in V1 - V1 focuses on test case structure, not execution.
        
        Returns:
            List of test run dictionaries
        """
        # V1: Not implemented - focus on test case structure
        return []
    
    def fetch_cases_by_project(self, project_id: str) -> List[TestRailTestCase]:
        """
        Fetch test cases for a given project.
        
        WARNING: Use with caution for large projects. This may return many cases.
        
        Args:
            project_id: TestRail project ID
            
        Returns:
            List of TestRailTestCase objects
        """
        try:
            response = self.client.get(
                f"{self.base_url}/index.php?/api/v2/get_cases/{project_id}",
                auth=(self.username, self.api_key),
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 401:
                logger.error("TestRail authentication failed")
                return []
            
            if response.status_code != 200:
                logger.warning(f"TestRail API error for project {project_id}: {response.status_code}")
                return []
            
            payload = response.json()
            cases = []
            
            for case_data in payload:
                normalized = self.normalize_test_case(case_data)
                cases.append(normalized)
            
            return cases
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching TestRail cases for project {project_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching TestRail cases for project {project_id}: {e}")
            return []
    
    def fetch_cases_by_reference(self, reference_key: str) -> List[TestRailTestCase]:
        """
        Fetch test cases by reference key (e.g., Jira issue key).
        
        This is the preferred method in V1 as it targets specific cases
        linked to work items rather than entire projects.
        
        Args:
            reference_key: Reference key (e.g., "PROJ-123")
            
        Returns:
            List of TestRailTestCase objects
        """
        try:
            # TestRail API doesn't have a direct "get by reference" endpoint
            # We need to search using the get_cases endpoint with a filter
            # However, TestRail API v2 doesn't support filtering by refs directly
            # As a fallback, we'll fetch all cases and filter client-side
            # This is not ideal but is the only way with TestRail API v2
            
            # For V1, we'll implement a placeholder that logs the limitation
            logger.warning(
                f"TestRail API v2 does not support direct reference filtering. "
                f"Cannot fetch cases by reference key '{reference_key}' without project ID. "
                f"Use fetch_cases_by_project instead."
            )
            return []
            
        except Exception as e:
            logger.error(f"Error fetching TestRail cases by reference {reference_key}: {e}")
            return []
    
    def normalize_test_case(self, payload: Dict[str, Any]) -> TestRailTestCase:
        """
        Normalize TestRail API payload to TestRailTestCase format.
        
        Args:
            payload: Raw TestRail API response
            
        Returns:
            Normalized TestRailTestCase
        """
        # Extract basic fields
        external_id = str(payload.get('id', ''))
        external_key = str(payload.get('id', ''))  # TestRail uses numeric IDs
        title = payload.get('title', '')
        description = payload.get('custom_description', '')
        
        # Extract preconditions
        preconditions = []
        custom_preconds = payload.get('custom_preconds', '')
        if custom_preconds:
            preconditions = [line.strip() for line in custom_preconds.split('\n') if line.strip()]
        
        # Extract steps
        steps = []
        custom_steps = payload.get('custom_steps', '')
        if custom_steps:
            # TestRail stores steps as custom field with specific format
            # Format: "Step 1\nExpected 1\n\nStep 2\nExpected 2"
            step_lines = custom_steps.split('\n')
            current_step = None
            for line in step_lines:
                line = line.strip()
                if line:
                    if current_step is None:
                        current_step = {'step': line, 'expected': ''}
                    else:
                        current_step['expected'] = line
                        steps.append(current_step)
                        current_step = None
        
        # Extract expected result (if not in steps)
        expected_result = payload.get('custom_expected_result', '')
        if not expected_result and steps:
            # Use the last step's expected result as overall expected result
            expected_result = steps[-1].get('expected', '')
        
        # Extract priority
        priority_id = payload.get('priority_id')
        priority = self._map_priority(priority_id)
        
        # Extract test type
        type_id = payload.get('type_id')
        test_type = self._map_test_type(type_id)
        
        # Extract automation status
        custom_automation = payload.get('custom_automation', '')
        automation_status = self._map_automation_status(custom_automation)
        
        # Extract tags
        tags = []
        # TestRail doesn't have a standard tags field in the case object
        # Tags might be in custom fields
        custom_tags = payload.get('custom_tags', '')
        if custom_tags:
            tags = [tag.strip() for tag in custom_tags.split(',') if tag.strip()]
        
        # Extract linked work item keys from refs
        refs = payload.get('refs', '')
        linked_work_item_keys = []
        if refs:
            # Parse refs for Jira-like keys
            import re
            jira_keys = re.findall(r'[A-Z]+-\d+', refs)
            linked_work_item_keys.extend(jira_keys)
        
        # Build URL
        url = f"{self.base_url}/index.php?/cases/view/{external_id}"
        
        return TestRailTestCase(
            external_id=external_id,
            external_key=external_key,
            title=title,
            description=description,
            preconditions=preconditions,
            steps=steps,
            expected_result=expected_result,
            priority=priority,
            test_type=test_type,
            automation_status=automation_status,
            tags=tags,
            linked_work_item_keys=linked_work_item_keys,
            url=url,
            raw_payload=payload
        )
    
    def _map_priority(self, priority_id: Optional[int]) -> Optional[str]:
        """
        Map TestRail priority ID to readable priority.
        
        Args:
            priority_id: TestRail priority ID
            
        Returns:
            Priority string or None
        """
        # TestRail priority IDs (default):
        # 1: Critical, 2: High, 3: Medium, 4: Low
        if priority_id is None:
            return None
        
        priority_map = {
            1: "Critical",
            2: "High",
            3: "Medium",
            4: "Low"
        }
        return priority_map.get(priority_id, "Unknown")
    
    def _map_test_type(self, type_id: Optional[int]) -> Optional[str]:
        """
        Map TestRail type ID to readable test type.
        
        Args:
            type_id: TestRail type ID
            
        Returns:
            Test type string or None
        """
        # TestRail type IDs (default):
        # Common types vary by instance
        if type_id is None:
            return None
        
        # This is a simplified mapping - actual IDs vary by TestRail instance
        type_map = {
            1: "Functional",
            2: "UI",
            3: "API",
            4: "Performance",
            5: "Security",
            6: "Integration"
        }
        return type_map.get(type_id, "Unknown")
    
    def _map_automation_status(self, custom_automation: str) -> str:
        """
        Map custom automation field to automation status.
        
        Args:
            custom_automation: Custom automation field value
            
        Returns:
            Automation status string
        """
        if not custom_automation:
            return "UNKNOWN"
        
        automation_lower = custom_automation.lower()
        
        if 'manual' in automation_lower:
            return "MANUAL"
        elif 'automated' in automation_lower:
            return "AUTOMATED"
        elif 'partial' in automation_lower or 'semi' in automation_lower:
            return "PARTIALLY_AUTOMATED"
        else:
            return "UNKNOWN"
    
    def push_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Push execution result to TestRail.
        
        Args:
            test_case_reference: Test case reference with external_id, external_key
            execution: Execution data with outcome, notes, executed_by, executed_at
            
        Returns:
            Dictionary with sync result including external_run_id, external_execution_id
        """
        try:
            # Map Veriscope outcome to TestRail status
            veriscope_outcome = execution.get('outcome', 'PASSED')
            testrail_status = map_veriscope_to_testrail_outcome(veriscope_outcome)
            
            # Resolve TestRail case ID
            testrail_case_id = test_case_reference.get('external_id')
            if not testrail_case_id:
                raise ValueError("TestRail case ID not found in test case reference")
            
            # Resolve target run ID from provider metadata or request
            # For MVP, we'll require run_id to be passed in test_case_reference
            run_id = test_case_reference.get('run_id')
            if not run_id:
                raise ValueError("TestRail run ID not found - cannot push result without target run")
            
            # Prepare TestRail API payload
            payload = {
                'status_id': self._get_status_id_from_name(testrail_status),
                'comment': execution.get('notes', ''),
                'elapsed': None,  # Could be calculated from execution time
                'assignedto_id': None,  # Could map executed_by
            }
            
            # Make API call to add result
            response = self.client.post(
                f"{self.base_url}/index.php?/api/v2/add_result_for_case/{run_id}/{testrail_case_id}",
                auth=(self.username, self.api_key),
                headers={"Content-Type": "application/json"},
                json=payload
            )
            
            if response.status_code == 200:
                result_data = response.json()
                return {
                    'success': True,
                    'external_run_id': str(run_id),
                    'external_execution_id': str(result_data.get('id', '')),
                    'status': 'SYNCED',
                    'error': None,
                    'httpStatus': None,
                    'retryAfterSeconds': None,
                    'errorType': None
                }
            else:
                error_msg = f"TestRail API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                
                # Extract retry-after header if present
                retry_after = response.headers.get('Retry-After')
                retry_after_seconds = None
                if retry_after:
                    try:
                        retry_after_seconds = int(retry_after)
                    except ValueError:
                        pass
                
                # Classify error type based on status code
                error_type = self._classify_error(response.status_code, response.text)
                
                return {
                    'success': False,
                    'external_run_id': None,
                    'external_execution_id': None,
                    'status': 'FAILED',
                    'error': error_msg,
                    'httpStatus': response.status_code,
                    'retryAfterSeconds': retry_after_seconds,
                    'errorType': error_type
                }
                
        except Exception as e:
            error_msg = f"Failed to push execution result to TestRail: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'external_run_id': None,
                'external_execution_id': None,
                'status': 'FAILED',
                'error': error_msg,
                'httpStatus': None,
                'retryAfterSeconds': None,
                'errorType': 'UNKNOWN_FAILURE'
            }
    
    def _classify_error(self, status_code: int, response_text: str) -> str:
        """
        Classify error type based on HTTP status code and response text.
        
        Args:
            status_code: HTTP status code
            response_text: Response body text
            
        Returns:
            Error type string (RATE_LIMITED, AUTHENTICATION_FAILED, etc.)
        """
        if status_code == 429:
            return 'RATE_LIMITED'
        elif status_code in (401, 403):
            return 'AUTHENTICATION_FAILED'
        elif status_code == 404:
            return 'PERMANENT_PROVIDER_FAILURE'
        elif status_code >= 500:
            return 'TEMPORARY_PROVIDER_FAILURE'
        elif status_code == 400:
            # Check if it's a configuration error
            if any(keyword in response_text.lower() for keyword in [
                'missing', 'required', 'invalid', 'configuration', 'config'
            ]):
                return 'CONFIGURATION_ERROR'
        
        return 'UNKNOWN_FAILURE'
    
    def _get_status_id_from_name(self, status_name: str) -> int:
        """
        Get TestRail status ID from status name.
        
        TestRail uses numeric status IDs:
        - 1: Passed
        - 2: Blocked
        - 3: Untested
        - 4: Retest
        - 5: Failed
        
        Args:
            status_name: Status name (passed, failed, blocked, retest)
            
        Returns:
            Status ID as integer
        """
        status_map = {
            'passed': 1,
            'blocked': 2,
            'retest': 4,
            'failed': 5
        }
        return status_map.get(status_name.lower(), 5)  # Default to failed if unknown
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
