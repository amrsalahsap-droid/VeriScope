import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import uuid

from app.main import app as fastapi_app
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_workspace
from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest
from app.services.regression_evidence_classifier import ScenarioSignatureGenerator, ScenarioSignature

client = TestClient(fastapi_app)

class TestRegressionEvidenceAPI:

    @patch("app.routers.recommendation.get_db")
    @patch("app.routers.recommendation.RequirementEvidenceGraphService")
    def test_regression_evidence_endpoint_no_crash_missing_changed_files(self, mock_graph_service_class, mock_get_db):
        """Test endpoint does not crash when changed_files missing."""
        mock_db = MagicMock()
        
        run_id = uuid.uuid4()
        pr_id = uuid.uuid4()
        
        mock_run = MagicMock(spec=RecommendationRun)
        mock_run.id = run_id
        mock_run.pull_request_id = pr_id
        mock_run.repository_id = uuid.uuid4()
        
        # Missing or empty changed_files in snapshot
        mock_snapshot = MagicMock()
        mock_snapshot.changed_files = None
        mock_run.input_snapshot = mock_snapshot
        
        mock_pr = MagicMock(spec=PullRequest)
        mock_pr.id = pr_id
        mock_pr.head_commit_sha = "abc123sha"
        # No description attribute natively
        
        # Configure DB mock to return our mocks dynamically
        def mock_query(model):
            q = MagicMock()
            if model == RecommendationRun:
                q.filter().first.return_value = mock_run
            elif model == PullRequest:
                q.filter().first.return_value = mock_pr
            else:
                q.filter().first.return_value = MagicMock()
            return q
        mock_db.query = mock_query
        
        # Configure graph service
        mock_graph_service_instance = MagicMock()
        mock_view_model = MagicMock()
        mock_view_model.health = "HEALTHY"
        mock_view_model.counts = {"verifiedTests": 1, "failedTests": 0, "missingTests": 0, "totalTests": 1, "coverageGaps": 0}
        mock_view_model.requirements = []
        mock_view_model.verified_by_current_pr = []
        mock_view_model.match_table = []
        mock_view_model.decision_copy = MagicMock()
        mock_view_model.decision_copy.headline = "Headline"
        mock_view_model.decision_copy.explanation = "Explanation"
        mock_view_model.decision_copy.next_action = "Next Action"
        mock_view_model.decision_copy.primary_cta = "Primary CTA"
        mock_view_model.decision_copy.secondary_cta = "Secondary CTA"
        mock_graph_service_instance.build_evidence_graph.return_value = mock_view_model
        mock_graph_service_class.return_value = mock_graph_service_instance
        
        fastapi_app.dependency_overrides[get_db] = lambda: mock_db
        fastapi_app.dependency_overrides[get_current_user] = lambda: MagicMock()
        fastapi_app.dependency_overrides[get_current_workspace] = lambda: MagicMock()
        
        response = client.get(f"/api/recommendations/{run_id}/regression-evidence")
        
        assert response.status_code == 200, response.json()
        data = response.json()
        assert data["decisionSummary"]["health"] == "HEALTHY"
        
        # Verify it passed [] for changed_files
        mock_graph_service_instance.build_evidence_graph.assert_called_once()
        call_kwargs = mock_graph_service_instance.build_evidence_graph.call_args.kwargs
        assert call_kwargs["changed_files"] == []
        
        fastapi_app.dependency_overrides.clear()

    @patch("app.routers.recommendation.get_db")
    @patch("app.routers.recommendation.RequirementEvidenceGraphService")
    def test_regression_evidence_endpoint_no_crash_missing_pr_description(self, mock_graph_service_class, mock_get_db):
        """Test endpoint does not crash when pr.description missing."""
        mock_db = MagicMock()
        
        run_id = uuid.uuid4()
        pr_id = uuid.uuid4()
        
        mock_run = MagicMock(spec=RecommendationRun)
        mock_run.id = run_id
        mock_run.pull_request_id = pr_id
        mock_run.repository_id = uuid.uuid4()
        mock_run.input_snapshot = MagicMock(changed_files=[{"filename": "test.py"}])
        
        # Explicitly ensure no description field
        class MockPR:
            def __init__(self):
                self.id = pr_id
                self.head_commit_sha = "abc123sha"
        
        mock_pr = MockPR()
        
        # Configure DB mock to return our mocks dynamically
        def mock_query(model):
            q = MagicMock()
            if model == RecommendationRun:
                q.filter().first.return_value = mock_run
            elif model == PullRequest:
                q.filter().first.return_value = mock_pr
            else:
                q.filter().first.return_value = MagicMock()
            return q
        mock_db.query = mock_query
        
        mock_graph_service_instance = MagicMock()
        mock_view_model = MagicMock()
        mock_view_model.health = "HEALTHY"
        mock_view_model.counts = {"verifiedTests": 1, "failedTests": 0, "missingTests": 0, "totalTests": 1, "coverageGaps": 0}
        mock_view_model.requirements = []
        mock_view_model.verified_by_current_pr = []
        mock_view_model.match_table = []
        mock_view_model.decision_copy = MagicMock()
        mock_view_model.decision_copy.headline = "Headline"
        mock_view_model.decision_copy.explanation = "Explanation"
        mock_view_model.decision_copy.next_action = "Next Action"
        mock_view_model.decision_copy.primary_cta = "Primary CTA"
        mock_view_model.decision_copy.secondary_cta = "Secondary CTA"
        mock_graph_service_instance.build_evidence_graph.return_value = mock_view_model
        mock_graph_service_class.return_value = mock_graph_service_instance
        
        fastapi_app.dependency_overrides[get_db] = lambda: mock_db
        fastapi_app.dependency_overrides[get_current_user] = lambda: MagicMock()
        fastapi_app.dependency_overrides[get_current_workspace] = lambda: MagicMock()
        
        response = client.get(f"/api/recommendations/{run_id}/regression-evidence")
        
        assert response.status_code == 200
        
        # Verify it passed empty string for pr_description
        call_kwargs = mock_graph_service_instance.build_evidence_graph.call_args.kwargs
        assert call_kwargs["pr_description"] == ""
        
        fastapi_app.dependency_overrides.clear()

    @patch("app.routers.recommendation.get_db")
    @patch("app.routers.recommendation.RequirementEvidenceGraphService")
    def test_regression_evidence_endpoint_structured_error_on_exception(self, mock_graph_service_class, mock_get_db):
        """Test endpoint returns structured error if graph service raises unexpected exception."""
        mock_db = MagicMock()
        
        run_id = uuid.uuid4()
        pr_id = uuid.uuid4()
        
        mock_run = MagicMock(spec=RecommendationRun)
        mock_run.id = run_id
        mock_run.pull_request_id = pr_id
        mock_run.repository_id = uuid.uuid4()
        mock_run.input_snapshot = MagicMock(changed_files=[])
        
        mock_pr = MagicMock(spec=PullRequest)
        mock_pr.id = pr_id
        mock_pr.head_commit_sha = "abc123sha"
        
        # Configure DB mock to return our mocks dynamically
        def mock_query(model):
            q = MagicMock()
            if model == RecommendationRun:
                q.filter().first.return_value = mock_run
            elif model == PullRequest:
                q.filter().first.return_value = mock_pr
            else:
                q.filter().first.return_value = MagicMock()
            return q
        mock_db.query = mock_query
        
        # Configure graph service to raise exception
        mock_graph_service_instance = MagicMock()
        mock_graph_service_instance.build_evidence_graph.side_effect = Exception("Graph build failure")
        mock_graph_service_class.return_value = mock_graph_service_instance
        
        fastapi_app.dependency_overrides[get_db] = lambda: mock_db
        fastapi_app.dependency_overrides[get_current_user] = lambda: MagicMock()
        fastapi_app.dependency_overrides[get_current_workspace] = lambda: MagicMock()
        
        response = client.get(f"/api/recommendations/{run_id}/regression-evidence")
        
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "ERROR"
        assert data["error_code"] == "REGRESSION_EVIDENCE_BUILD_FAILED"
        assert data["message"] == "Graph build failure"
        assert data["recommendationRunId"] == str(run_id)
        assert data["canRenderRecommendation"] is False
        
        fastapi_app.dependency_overrides.clear()

    def test_scenario_signature_generator_returns_valid_signature_using_subject(self):
        """ScenarioSignatureGenerator.generate_signature returns a valid ScenarioSignature using subject."""
        text = "Expired password reset token should be rejected"
        signature = ScenarioSignatureGenerator.generate_signature(text)
        
        assert isinstance(signature, ScenarioSignature)
        assert hasattr(signature, "subject")
        assert signature.subject == "password"
        assert not hasattr(signature, "entity")
