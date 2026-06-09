"""
Test Management System Connector Interface.

This module defines the abstract interface for test management system integrations.
Future integrations (TestRail, Xray, Zephyr, Jira) will implement this interface
to import test metadata without changing core ingestion models.

Note: This is a foundation for future integrations. No external API calls are made yet.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.constants.evidence import TestManagementProvider


class TestManagementConnector(ABC):
    """
    Abstract base class for test management system connectors.
    
    Implementations of this interface will:
    - Connect to test management systems (TestRail, Xray, Zephyr, Jira)
    - Validate credentials
    - List projects, test cases, and test runs
    - Import test metadata into Veriscope
    
    Important: JUnit/CI evidence remains the source of execution truth.
    Test management tools provide metadata and business context only.
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'TestRail', 'Xray')."""
        pass
    
    @abstractmethod
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        Establish connection to the test management system.
        
        Args:
            credentials: Provider-specific credentials (API key, URL, etc.)
            
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate credentials without establishing a full connection.
        
        Args:
            credentials: Provider-specific credentials
            
        Returns:
            True if credentials are valid, False otherwise
        """
        pass
    
    @abstractmethod
    def list_projects(self) -> List[Dict[str, Any]]:
        """
        List available projects in the test management system.
        
        Returns:
            List of project dictionaries with at least 'id' and 'name' keys
        """
        pass
    
    @abstractmethod
    def list_test_cases(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List test cases for a given project.
        
        Args:
            project_id: External project identifier
            
        Returns:
            List of test case dictionaries with metadata
        """
        pass
    
    @abstractmethod
    def list_test_runs(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List test runs for a given project.
        
        Args:
            project_id: External project identifier
            
        Returns:
            List of test run dictionaries with metadata
        """
        pass
    
    @abstractmethod
    def import_metadata(
        self,
        repository_id: UUID,
        project_id: str,
        test_case_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Import test metadata into Veriscope.
        
        This method should:
        - Fetch test case metadata from the provider
        - Store it in ExternalTestCaseReference model
        - Map external test cases to internal TestCase entities if possible
        - NOT replace JUnit execution evidence
        
        Args:
            repository_id: Veriscope repository ID
            project_id: External project identifier
            test_case_ids: Optional list of specific test case IDs to import
            
        Returns:
            Dictionary with import results (count, errors, etc.)
        """
        pass
    
    @abstractmethod
    def fetch_test_cases_by_issue_key(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Fetch test cases linked to a specific work item/issue key.
        
        This method is used for targeted imports based on linked work items
        (e.g., Jira issues, Azure work items) rather than broad project imports.
        
        Args:
            issue_key: Work item/issue key (e.g., "PROJ-123", "AB#123")
            
        Returns:
            List of test case dictionaries with metadata
        """
        pass
    
    @abstractmethod
    def fetch_test_cases_by_project(self, project_key: str) -> List[Dict[str, Any]]:
        """
        Fetch test cases for a specific project.
        
        Args:
            project_key: Project identifier (key or ID)
            
        Returns:
            List of test case dictionaries with metadata
        """
        pass
    
    @abstractmethod
    def normalize_test_case(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize provider-specific test case payload to standard format.
        
        The normalized format should include:
        - external_id: Provider's test case ID
        - external_key: Provider's test case key (if applicable)
        - title: Test case title
        - description: Test case description
        - preconditions: List of preconditions
        - steps: List of step dictionaries with 'step' and 'expected' keys
        - expected_result: Overall expected result
        - priority: Priority level
        - test_type: Test type (Functional, UI, API, etc.)
        - automation_status: MANUAL, AUTOMATED, PARTIALLY_AUTOMATED, UNKNOWN
        - tags: List of tags
        - linked_work_item_keys: List of linked work item keys
        - url: URL to view test case in provider
        - raw_payload: Complete raw payload
        
        Args:
            payload: Provider-specific test case payload
            
        Returns:
            Normalized test case dictionary
        """
        pass


class ManualTestConnector(TestManagementConnector):
    """
    Manual test management connector for manually entered test metadata.
    
    This connector allows users to manually specify test metadata without
    connecting to an external test management system.
    """
    
    @property
    def provider_name(self) -> str:
        return "Manual"
    
    def connect(self, credentials: Dict[str, Any]) -> bool:
        # Manual connector doesn't require connection
        return True
    
    def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        # Manual connector doesn't validate credentials
        return True
    
    def list_projects(self) -> List[Dict[str, Any]]:
        # Manual connector has no projects
        return []
    
    def list_test_cases(self, project_id: str) -> List[Dict[str, Any]]:
        # Manual connector has no test cases
        return []
    
    def list_test_runs(self, project_id: str) -> List[Dict[str, Any]]:
        # Manual connector has no test runs
        return []
    
    def import_metadata(
        self,
        repository_id: UUID,
        project_id: str,
        test_case_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        # Manual connector imports are handled via direct API calls
        return {
            "success": False,
            "error": "Manual metadata import not implemented via connector"
        }
    
    def fetch_test_cases_by_issue_key(self, issue_key: str) -> List[Dict[str, Any]]:
        # Manual connector has no external test cases
        return []
    
    def fetch_test_cases_by_project(self, project_key: str) -> List[Dict[str, Any]]:
        # Manual connector has no external test cases
        return []
    
    def normalize_test_case(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Manual connector doesn't normalize external payloads
        return {}
