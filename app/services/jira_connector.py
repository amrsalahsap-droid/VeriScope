"""
Jira Connector V1

Imports linked Jira issues and acceptance criteria for Veriscope.
Fetches only specific issue keys mentioned in PRs, no broad project crawl.
"""

import httpx
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.services.test_management_connector import TestManagementConnector


logger = logging.getLogger("veriscope.jira_connector")


@dataclass
class JiraWorkItem:
    """Normalized Jira work item data."""
    external_id: str
    external_key: str
    title: str
    description: Optional[str]
    work_item_type: str
    status: str
    priority: Optional[str]
    labels: List[str]
    acceptance_criteria: List[str]
    url: str
    raw_payload: Dict[str, Any]


class JiraConnector(TestManagementConnector):
    """
    Jira connector for importing work items and acceptance criteria.
    
    V1 Scope:
    - Fetch only specific issue keys from PRs (no project crawl)
    - Extract acceptance criteria from description/custom fields
    - Handle auth failures gracefully
    - Preserve raw payload
    - Do not fail recommendations if Jira unavailable
    """
    
    def __init__(self, base_url: str, email: str, api_token: str):
        """
        Initialize Jira connector.
        
        Args:
            base_url: Jira instance URL (e.g., "https://company.atlassian.net")
            email: Jira user email
            api_token: Jira API token
        """
        self.base_url = base_url.rstrip('/')
        self.email = email
        self.api_token = api_token
        self.client = httpx.Client(timeout=30.0)
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "JIRA"
    
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        Establish connection to Jira.
        
        Args:
            credentials: Dict with base_url, email, api_token
            
        Returns:
            True if connection successful, False otherwise
        """
        self.base_url = credentials.get('base_url', '').rstrip('/')
        self.email = credentials.get('email', '')
        self.api_token = credentials.get('api_token', '')
        
        # Validate connection
        return self.validate_credentials(credentials)
    
    def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate credentials without establishing a full connection.
        
        Args:
            credentials: Dict with base_url, email, api_token
            
        Returns:
            True if credentials are valid, False otherwise
        """
        base_url = credentials.get('base_url', '').rstrip('/')
        email = credentials.get('email', '')
        api_token = credentials.get('api_token', '')
        
        if not all([base_url, email, api_token]):
            return False
        
        try:
            # Test connection with a simple API call
            response = self.client.get(
                f"{base_url}/rest/api/3/myself",
                auth=(email, api_token),
                headers={"Accept": "application/json"}
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Jira credential validation failed: {e}")
            return False
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """
        List available projects in Jira.
        
        NOTE: Not used in V1 - V1 only fetches specific issue keys.
        
        Returns:
            List of project dictionaries
        """
        # V1: Not implemented - no project crawl
        return []
    
    def list_test_cases(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List test cases for a given project.
        
        NOTE: Not used in V1 - V1 only fetches specific issue keys.
        
        Returns:
            List of test case dictionaries
        """
        # V1: Not implemented - no project crawl
        return []
    
    def list_test_runs(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List test runs for a given project.
        
        NOTE: Not used in V1 - V1 only fetches specific issue keys.
        
        Returns:
            List of test run dictionaries
        """
        # V1: Not implemented - no project crawl
        return []
    
    def fetch_work_item(self, issue_key: str) -> Optional[JiraWorkItem]:
        """
        Fetch a single Jira work item by key.
        
        Args:
            issue_key: Jira issue key (e.g., "PROJ-123")
            
        Returns:
            JiraWorkItem if found, None otherwise
        """
        try:
            response = self.client.get(
                f"{self.base_url}/rest/api/3/issue/{issue_key}",
                auth=(self.email, self.api_token),
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 404:
                logger.info(f"Jira issue {issue_key} not found")
                return None
            
            if response.status_code == 401:
                logger.error(f"Jira authentication failed for {issue_key}")
                return None
            
            if response.status_code != 200:
                logger.warning(f"Jira API error for {issue_key}: {response.status_code}")
                return None
            
            payload = response.json()
            return self.normalize_work_item(payload)
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching Jira issue {issue_key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching Jira issue {issue_key}: {e}")
            return None
    
    def fetch_linked_work_items(self, issue_keys: List[str]) -> List[JiraWorkItem]:
        """
        Fetch multiple Jira work items by keys.
        
        Args:
            issue_keys: List of Jira issue keys
            
        Returns:
            List of JiraWorkItem objects (excluding failures)
        """
        work_items = []
        
        for issue_key in issue_keys:
            work_item = self.fetch_work_item(issue_key)
            if work_item:
                work_items.append(work_item)
        
        return work_items
    
    def normalize_work_item(self, payload: Dict[str, Any]) -> JiraWorkItem:
        """
        Normalize Jira API payload to JiraWorkItem format.
        
        Args:
            payload: Raw Jira API response
            
        Returns:
            Normalized JiraWorkItem
        """
        fields = payload.get('fields', {})
        
        # Extract basic fields
        external_id = str(payload.get('id', ''))
        external_key = payload.get('key', '')
        title = fields.get('summary', '')
        description = fields.get('description', {})
        
        # Handle description (can be Atlassian Document Format)
        if isinstance(description, dict):
            # Extract text from Atlassian Document Format
            description_text = self._extract_text_from_adf(description)
        else:
            description_text = str(description) if description else None
        
        # Extract issue type
        issue_type = fields.get('issuetype', {})
        work_item_type = self._map_issue_type(issue_type.get('name', ''))
        
        # Extract status
        status = fields.get('status', {})
        status_name = status.get('name', 'UNKNOWN')
        
        # Extract priority
        priority = fields.get('priority', {})
        priority_name = priority.get('name', None)
        
        # Extract labels
        labels = fields.get('labels', [])
        
        # Extract acceptance criteria
        acceptance_criteria = self._extract_acceptance_criteria(fields, description_text)
        
        # Build URL
        url = f"{self.base_url}/browse/{external_key}"
        
        return JiraWorkItem(
            external_id=external_id,
            external_key=external_key,
            title=title,
            description=description_text,
            work_item_type=work_item_type,
            status=status_name,
            priority=priority_name,
            labels=labels,
            acceptance_criteria=acceptance_criteria,
            url=url,
            raw_payload=payload
        )
    
    def _extract_text_from_adf(self, adf: Dict[str, Any]) -> str:
        """
        Extract plain text from Atlassian Document Format.
        
        Args:
            adf: Atlassian Document Format JSON
            
        Returns:
            Plain text string
        """
        if not adf:
            return ""
        
        text_parts = []
        
        def extract_from_node(node):
            if isinstance(node, dict):
                node_type = node.get('type', '')
                
                if node_type == 'text':
                    text_parts.append(node.get('text', ''))
                elif node_type == 'paragraph':
                    for child in node.get('content', []):
                        extract_from_node(child)
                    text_parts.append('\n')
                elif node_type == 'bulletList' or node_type == 'orderedList':
                    for child in node.get('content', []):
                        extract_from_node(child)
                elif node_type == 'listItem':
                    for child in node.get('content', []):
                        extract_from_node(child)
                    text_parts.append('\n')
                elif 'content' in node:
                    for child in node.get('content', []):
                        extract_from_node(child)
            elif isinstance(node, list):
                for item in node:
                    extract_from_node(item)
        
        extract_from_node(adf)
        return ''.join(text_parts).strip()
    
    def _map_issue_type(self, jira_type: str) -> str:
        """
        Map Jira issue type to Veriscope work item type.
        
        Args:
            jira_type: Jira issue type name
            
        Returns:
            Veriscope work item type
        """
        jira_type_lower = jira_type.lower()
        
        if 'story' in jira_type_lower or 'feature' in jira_type_lower:
            return 'STORY'
        elif 'bug' in jira_type_lower or 'defect' in jira_type_lower:
            return 'BUG'
        elif 'task' in jira_type_lower or 'sub-task' in jira_type_lower:
            return 'TASK'
        elif 'epic' in jira_type_lower:
            return 'EPIC'
        elif 'requirement' in jira_type_lower or 'spec' in jira_type_lower:
            return 'REQUIREMENT'
        else:
            return 'UNKNOWN'
    
    def _extract_acceptance_criteria(
        self,
        fields: Dict[str, Any],
        description_text: Optional[str]
    ) -> List[str]:
        """
        Extract acceptance criteria from Jira fields.
        
        Args:
            fields: Jira issue fields
            description_text: Plain text description
            
        Returns:
            List of acceptance criteria strings
        """
        criteria = []
        
        # Try custom field for acceptance criteria
        # Common field names: "Acceptance Criteria", "AC", "Acceptance Criteria (AC)"
        custom_field_names = [
            'Acceptance Criteria',
            'AC',
            'Acceptance Criteria (AC)',
            'customfield_10006',  # Common Jira custom field ID
        ]
        
        for field_name in custom_field_names:
            if field_name in fields:
                ac_value = fields[field_name]
                if ac_value:
                    if isinstance(ac_value, str):
                        criteria.append(ac_value)
                    elif isinstance(ac_value, list):
                        criteria.extend(ac_value)
                    elif isinstance(ac_value, dict):
                        # Handle Atlassian Document Format
                        text = self._extract_text_from_adf(ac_value)
                        if text:
                            criteria.append(text)
        
        # If no custom field, try to extract from description
        if not criteria and description_text:
            criteria = self._extract_ac_from_description(description_text)
        
        return criteria
    
    def _extract_ac_from_description(self, description: str) -> List[str]:
        """
        Extract acceptance criteria from description text.
        
        Args:
            description: Plain text description
            
        Returns:
            List of acceptance criteria strings
        """
        criteria = []
        
        # Look for AC section
        ac_patterns = [
            r'acceptance criteria[:\s*\n](.*?)(?=\n\n|\n#{1,3}|\Z)',
            r'ac[:\s*\n](.*?)(?=\n\n|\n#{1,3}|\Z)',
            r'criteria[:\s*\n](.*?)(?=\n\n|\n#{1,3}|\Z)',
        ]
        
        import re
        for pattern in ac_patterns:
            match = re.search(pattern, description, re.IGNORECASE | re.DOTALL)
            if match:
                ac_text = match.group(1).strip()
                # Split by list items
                lines = ac_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('*') or re.match(r'^\d+\.', line)):
                        # Remove list marker
                        clean_line = re.sub(r'^[-*]\s+|^\d+\.\s+', '', line)
                        if clean_line:
                            criteria.append(clean_line)
                break
        
        return criteria
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
