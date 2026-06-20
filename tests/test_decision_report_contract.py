import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import uuid

from app.main import app as fastapi_app
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_workspace
from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest
from app.services.regression_evidence_classifier import EvidenceClassification

client = TestClient(fastapi_app)

class TestDecisionReportContract:

    @patch("app.routers.recommendation.get_db")
    @patch("app.routers.recommendation.RequirementEvidenceGraphService")
    def test_regression_evidence_contract_structure(self, mock_graph_service_class, mock_get_db):
        """Test that the /regression-evidence endpoint adheres to the new decision report contract."""
        mock_db = MagicMock()
        
        run_id = uuid.uuid4()
        pr_id = uuid.uuid4()
        
        mock_run = MagicMock(spec=RecommendationRun)
        mock_run.id = run_id
        mock_run.pull_request_id = pr_id
        mock_run.repository_id = uuid.uuid4()
        mock_run.input_snapshot = MagicMock(changed_files=[{"filename": "test.py"}])
        
        mock_pr = MagicMock(spec=PullRequest)
        mock_pr.id = pr_id
        mock_pr.head_commit_sha = "abc123sha"
        mock_pr.description = "AC-01 minimum password length"
        
        # Configure DB mock
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
        
        # Create mocked requirement nodes that match our counts (16 verified, 2 partial, 7 missing)
        requirements = []
        
        # 16 verified requirements
        for i in range(16):
            req = MagicMock()
            req.node_type = "PARENT_REQUIREMENT"
            req.requirement_id = f"req-verified-{i}"
            req.readable_id = f"AC-V{i}"
            req.title = f"Verified AC {i}"
            req.flow = "flow-v"
            req.risk_level = "MUST"
            req.classification = EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION
            req.match_score = 0.95
            req.source_hash = f"hash-v-{i}"
            req.match_diagnostics = {"JUNIT_AC_ID_MISMATCH": False}
            requirements.append(req)
            
        # 2 partial requirements
        for i in range(2):
            req = MagicMock()
            req.node_type = "PARENT_REQUIREMENT"
            req.requirement_id = f"req-partial-{i}"
            req.readable_id = f"AC-P{i}"
            req.title = f"Partial AC {i}"
            req.flow = "flow-p"
            req.risk_level = "RECOMMENDED"
            req.classification = EvidenceClassification.PARTIALLY_COVERED
            req.match_score = 0.75
            req.source_hash = f"hash-p-{i}"
            req.match_diagnostics = {"context_mismatch": True}
            requirements.append(req)
            
        # 7 missing requirements
        for i in range(7):
            req = MagicMock()
            req.node_type = "PARENT_REQUIREMENT"
            req.requirement_id = f"req-missing-{i}"
            req.readable_id = f"AC-M{i}"
            req.title = f"Missing AC {i}"
            req.flow = "flow-m"
            req.risk_level = "MUST"
            req.classification = EvidenceClassification.MISSING_AUTOMATED_COVERAGE
            req.match_score = 0.0
            req.source_hash = f"hash-m-{i}"
            req.match_diagnostics = {}
            requirements.append(req)
            
        # Mock view model
        mock_view_model = MagicMock()
        mock_view_model.health = "VALIDATION_PASSED_COVERAGE_INCOMPLETE"
        mock_view_model.can_render_recommendation = True
        mock_view_model.requirements = requirements
        mock_view_model.counts = {
            "uploadedPrTestsTotal": 18,
            "uploadedPrTestsPassed": 18,
            "uploadedPrTestsFailed": 0,
            "uploadedPrTestsSkipped": 0
        }
        mock_view_model.decision_copy = MagicMock()
        mock_view_model.decision_copy.headline = "Headline"
        mock_view_model.decision_copy.explanation = "Explanation"
        mock_view_model.decision_copy.next_action = "Next Action"
        mock_view_model.decision_copy.primary_cta = "Primary CTA"
        mock_view_model.decision_copy.secondary_cta = "Secondary CTA"
        mock_view_model.verified_by_current_pr = []
        mock_view_model.match_table = []
        mock_view_model.diagnostics = {}
        
        mock_graph_service_instance = MagicMock()
        mock_graph_service_instance.build_evidence_graph.return_value = mock_view_model
        mock_graph_service_class.return_value = mock_graph_service_instance
        
        fastapi_app.dependency_overrides[get_db] = lambda: mock_db
        fastapi_app.dependency_overrides[get_current_user] = lambda: MagicMock()
        fastapi_app.dependency_overrides[get_current_workspace] = lambda: MagicMock()
        
        # Call normal mode (audit=False)
        response = client.get(f"/api/recommendations/{run_id}/regression-evidence")
        assert response.status_code == 200
        data = response.json()
        
        # Verify contract sections exist
        assert "decisionSummary" in data
        assert "buckets" in data
        assert "scopeRecommendation" in data
        
        # Assert counts
        summary = data["decisionSummary"]
        assert summary["totalCurrentPrTests"] == 18
        assert summary["passedCurrentPrTests"] == 18
        assert summary["totalParentRequirements"] == 25
        assert summary["coveredByPassedPrTests"] == 16
        assert summary["partiallySupported"] == 2
        assert summary["missingAutomatedCoverage"] == 7
        assert summary["traceabilityReviewNeeded"] == 0
        
        # Health checks (must be limited / passed coverage incomplete)
        assert summary["health"] == "VALIDATION_PASSED_COVERAGE_INCOMPLETE"
        # Since coverage is incomplete, health cannot show READY, primary CTA must be Review Missing & Partial Coverage
        assert summary["primaryCta"] == "Review Missing & Partial Coverage"
        
        # Normal mode: must NOT contain internal IDs in buckets or scope
        for bucket_name, items in data["buckets"].items():
            for item in items:
                assert "diagnostics" not in item
                
        # Assert scope recommendations
        scope = data["scopeRecommendation"]
        assert len(scope["requiredItems"]) == 7
        assert len(scope["reviewItems"]) == 2
        assert len(scope["excludedAlreadyVerified"]) == 16  # verified reqs (no tests mocked)
        
        # Call audit mode (audit=True)
        response_audit = client.get(f"/api/recommendations/{run_id}/regression-evidence?audit=true")
        assert response_audit.status_code == 200
        data_audit = response_audit.json()
        
        # Audit mode: must contain diagnostics with internal IDs, match scores, source hashes
        for bucket_name, items in data_audit["buckets"].items():
            for item in items:
                assert "diagnostics" in item
                assert "internalId" in item["diagnostics"]
                assert "matchScore" in item["diagnostics"]
                assert "sourceHash" in item["diagnostics"]
                
        fastapi_app.dependency_overrides.clear()
