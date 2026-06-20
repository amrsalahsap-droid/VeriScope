"""
GitHub Real Publishing Service Tests

Tests for GitHub status/check and PR comment publishing service.
Mock HTTP calls but exercise the real service implementation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.github_check_service import GitHubCheckService
from app.models.pipeline_run import QualityGateStatus


class TestGitHubStatusCheckPublishing:
    """Tests for GitHub status/check publishing."""
    
    @patch('app.services.github_check_service.requests.post')
    def test_pending_commit_status_created_on_trigger(self, mock_post):
        """Test that pending commit status is created on trigger."""
        mock_post.return_value = Mock(status_code=201, json=lambda: {"id": 123})
        
        service = GitHubCheckService(github_token="test_token")
        response = service.create_commit_status(
            owner="testowner",
            repo="testrepo",
            commit_sha="abc123",
            state="pending",
            description="Quality gate analysis in progress"
        )
        
        assert response is not None
        mock_post.assert_called_once()
        
        # Verify the call was made with pending state
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['state'] == 'pending'
    
    @patch('app.services.github_check_service.requests.post')
    def test_final_status_updated_by_worker(self, mock_post):
        """Test that final status is updated by worker."""
        mock_post.return_value = Mock(status_code=201, json=lambda: {"id": 124})
        
        service = GitHubCheckService(github_token="test_token")
        response = service.create_commit_status(
            owner="testowner",
            repo="testrepo",
            commit_sha="abc123",
            state="success",
            description="Quality gate passed"
        )
        
        assert response is not None
        mock_post.assert_called_once()
        
        # Verify the call was made with success state
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['state'] == 'success'
    
    def test_passed_maps_to_success(self):
        """Test that PASSED quality gate maps to success status."""
        service = GitHubCheckService(github_token="test_token")
        status = service.map_quality_gate_to_status(QualityGateStatus.PASSED)
        assert status == 'success'
    
    def test_partial_maps_to_neutral_when_ci_fail_on_partial_false(self):
        """Test that PARTIAL maps to neutral when ciFailOnPartial=false."""
        service = GitHubCheckService(github_token="test_token", ci_fail_on_partial=False)
        status = service.map_quality_gate_to_status(QualityGateStatus.PARTIAL)
        assert status == 'neutral'
    
    def test_partial_maps_to_failure_when_ci_fail_on_partial_true(self):
        """Test that PARTIAL maps to failure when ciFailOnPartial=true."""
        service = GitHubCheckService(github_token="test_token", ci_fail_on_partial=True)
        status = service.map_quality_gate_to_status(QualityGateStatus.PARTIAL)
        assert status == 'failure'
    
    def test_failed_maps_to_failure(self):
        """Test that FAILED quality gate maps to failure status."""
        service = GitHubCheckService(github_token="test_token")
        status = service.map_quality_gate_to_status(QualityGateStatus.FAILED)
        assert status == 'failure'
    
    def test_blocked_maps_to_failure(self):
        """Test that BLOCKED quality gate maps to failure status."""
        service = GitHubCheckService(github_token="test_token")
        status = service.map_quality_gate_to_status(QualityGateStatus.BLOCKED)
        assert status == 'failure'
    
    def test_unknown_maps_to_pending(self):
        """Test that UNKNOWN quality gate maps to pending status."""
        service = GitHubCheckService(github_token="test_token")
        status = service.map_quality_gate_to_status(QualityGateStatus.UNKNOWN)
        assert status == 'pending'


