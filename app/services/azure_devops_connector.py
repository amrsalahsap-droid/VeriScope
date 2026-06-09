"""
Azure DevOps Connector V1

Imports linked Azure Boards work items for Veriscope.
Fetches only specific work item IDs mentioned in PRs, no broad project crawl.
"""

import httpx
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.services.test_management_connector import TestManagementConnector


logger = logging.getLogger("veriscope.azure_devops_connector")


@dataclass
class AzureWorkItem:
    """Normalized Azure DevOps work item data."""
    external_id: str
    external_key: str
    title: str
    description: Optional[str]
    work_item_type: str
    status: str
    priority: Optional[str]
    tags: List[str]
    acceptance_criteria: List[str]
    url: str
    raw_payload: Dict[str, Any]


class AzureDevOpsConnector(TestManagementConnector):
    """
    Azure DevOps connector for importing work items and acceptance criteria.
    
    V1 Scope:
    - Fetch only specific work item IDs from PRs (no project crawl)
    - Extract acceptance criteria from description/custom fields
    - Handle auth failures gracefully
    - Preserve raw payload
    - Do not fail recommendations if Azure DevOps unavailable
    """
    
    def __init__(self, organization: str, project: str, pat_token: str):
        """
        Initialize Azure DevOps connector.
        
        Args:
            organization: Azure DevOps organization name (e.g., "myorg")
            project: Azure DevOps project name (e.g., "myproject")
            pat_token: Personal Access Token for authentication
        """
        self.organization = organization
        self.project = project
        self.pat_token = pat_token
        self.base_url = f"https://dev.azure.com/{organization}/{project}"
        self.client = httpx.Client(timeout=30.0)
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "AZURE_DEVOPS"
    
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        Establish connection to Azure DevOps.
        
        Args:
            credentials: Dict with organization, project, pat_token
            
        Returns:
            True if connection successful, False otherwise
        """
        self.organization = credentials.get('organization', '')
        self.project = credentials.get('project', '')
        self.pat_token = credentials.get('pat_token', '')
        self.base_url = f"https://dev.azure.com/{self.organization}/{self.project}"
        
        # Validate connection
        return self.validate_credentials(credentials)
    
    def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate credentials without establishing a full connection.
        
        Args:
            credentials: Dict with organization, project, pat_token
            
        Returns:
            True if credentials are valid, False otherwise
        """
        organization = credentials.get('organization', '')
        project = credentials.get('project', '')
        pat_token = credentials.get('pat_token', '')
        
        if not all([organization, project, pat_token]):
            return False
        
        try:
            # Test connection with a simple API call
            response = self.client.get(
                f"https://dev.azure.com/{organization}/_apis/projects/{project}",
                auth=('', pat_token),
                headers={"Accept": "application/json"}
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Azure DevOps credential validation failed: {e}")
            return False
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """
        List available projects in Azure DevOps.
        
        NOTE: Not used in V1 - V1 only fetches specific work item IDs.
        
        Returns:
            List of project dictionaries
        """
        # V1: Not implemented - no project crawl
        return []
    
    def list_test_cases(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List test cases for a given project.
        
        NOTE: Not used in V1 - V1 only fetches specific work item IDs.
        
        Returns:
            List of test case dictionaries
        """
        # V1: Not implemented - no project crawl
        return []
    
    def list_test_runs(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List test runs for a given project.
        
        NOTE: Not used in V1 - V1 only fetches specific work item IDs.
        
        Returns:
            List of test run dictionaries
        """
        # V1: Not implemented - no project crawl
        return []
    
    def fetch_work_item(self, work_item_id: str) -> Optional[AzureWorkItem]:
        """
        Fetch a single Azure DevOps work item by ID.
        
        Args:
            work_item_id: Azure DevOps work item ID (numeric string)
            
        Returns:
            AzureWorkItem if found, None otherwise
        """
        try:
            # Azure DevOps API requires $expand for field values
            response = self.client.get(
                f"{self.base_url}/_apis/wit/workitems/{work_item_id}?$expand=all",
                auth=('', self.pat_token),
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 404:
                logger.info(f"Azure DevOps work item {work_item_id} not found")
                return None
            
            if response.status_code == 401 or response.status_code == 403:
                logger.error(f"Azure DevOps authentication failed for work item {work_item_id}")
                return None
            
            if response.status_code != 200:
                logger.warning(f"Azure DevOps API error for work item {work_item_id}: {response.status_code}")
                return None
            
            payload = response.json()
            return self.normalize_work_item(payload)
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching Azure DevOps work item {work_item_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching Azure DevOps work item {work_item_id}: {e}")
            return None
    
    def fetch_linked_work_items(self, work_item_ids: List[str]) -> List[AzureWorkItem]:
        """
        Fetch multiple Azure DevOps work items by IDs.
        
        Args:
            work_item_ids: List of Azure DevOps work item IDs
            
        Returns:
            List of AzureWorkItem objects (excluding failures)
        """
        work_items = []
        
        for work_item_id in work_item_ids:
            work_item = self.fetch_work_item(work_item_id)
            if work_item:
                work_items.append(work_item)
        
        return work_items
    
    def normalize_work_item(self, payload: Dict[str, Any]) -> AzureWorkItem:
        """
        Normalize Azure DevOps API payload to AzureWorkItem format.
        
        Args:
            payload: Raw Azure DevOps API response
            
        Returns:
            Normalized AzureWorkItem
        """
        fields = payload.get('fields', {})
        
        # Extract basic fields
        external_id = str(payload.get('id', ''))
        external_key = str(payload.get('id', ''))  # Azure uses numeric IDs
        title = fields.get('System.Title', '')
        description = fields.get('System.Description', '')
        
        # Extract work item type
        work_item_type_name = fields.get('System.WorkItemType', '')
        work_item_type = self._map_work_item_type(work_item_type_name)
        
        # Extract state
        status = fields.get('System.State', 'UNKNOWN')
        
        # Extract priority
        priority = fields.get('Microsoft.VSTS.Common.Priority', None)
        if priority is not None:
            priority = str(priority)
        
        # Extract tags
        tags_str = fields.get('System.Tags', '')
        tags = [tag.strip() for tag in tags_str.split(';') if tag.strip()] if tags_str else []
        
        # Extract acceptance criteria
        acceptance_criteria = self._extract_acceptance_criteria(fields, description)
        
        # Build URL
        url = f"{self.base_url}/_workitems/edit/{external_id}"
        
        return AzureWorkItem(
            external_id=external_id,
            external_key=external_key,
            title=title,
            description=description,
            work_item_type=work_item_type,
            status=status,
            priority=priority,
            tags=tags,
            acceptance_criteria=acceptance_criteria,
            url=url,
            raw_payload=payload
        )
    
    def _map_work_item_type(self, azure_type: str) -> str:
        """
        Map Azure DevOps work item type to Veriscope work item type.
        
        Args:
            azure_type: Azure DevOps work item type name
            
        Returns:
            Veriscope work item type
        """
        azure_type_lower = azure_type.lower()
        
        if 'user story' in azure_type_lower or 'story' in azure_type_lower:
            return 'STORY'
        elif 'bug' in azure_type_lower or 'defect' in azure_type_lower:
            return 'BUG'
        elif 'task' in azure_type_lower:
            return 'TASK'
        elif 'feature' in azure_type_lower:
            return 'EPIC'
        elif 'requirement' in azure_type_lower or 'spec' in azure_type_lower:
            return 'REQUIREMENT'
        elif 'epic' in azure_type_lower:
            return 'EPIC'
        else:
            return 'UNKNOWN'
    
    def _extract_acceptance_criteria(
        self,
        fields: Dict[str, Any],
        description: Optional[str]
    ) -> List[str]:
        """
        Extract acceptance criteria from Azure DevOps fields.
        
        Args:
            fields: Azure DevOps work item fields
            description: Description text
            
        Returns:
            List of acceptance criteria strings
        """
        criteria = []
        
        # Try custom field for acceptance criteria
        # Common field names in Azure DevOps
        custom_field_names = [
            'Microsoft.VSTS.Common.AcceptanceCriteria',
            'Custom.AcceptanceCriteria',
            'Acceptance Criteria',
        ]
        
        for field_name in custom_field_names:
            if field_name in fields:
                ac_value = fields[field_name]
                if ac_value:
                    if isinstance(ac_value, str):
                        criteria.append(ac_value)
                    elif isinstance(ac_value, list):
                        criteria.extend(ac_value)
        
        # If no custom field, try to extract from description
        if not criteria and description:
            criteria = self._extract_ac_from_description(description)
        
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
