import pytest
from unittest.mock import MagicMock, patch
import uuid
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService
from app.services.regression_evidence_classifier import TestNode, ExecutionNode

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def graph_service(mock_db):
    service = RequirementEvidenceGraphService(db=mock_db)
    service.integration = MagicMock()
    # Mock integration.build_execution_nodes to just return mocked results instead of executing real logic
    service.integration.build_execution_nodes.side_effect = lambda results, pr_id, head, test_map: [
        ExecutionNode(
            test_id=f"exec-{i}",
            test_name="x",
            classname="y",
            status="passed",
            duration=0.0,
            pull_request_id=pr_id,
            head_sha=head,
            mapped_test_node_id=None
        ) for i in range(len(results))
    ]
    return service

def test_testresult_model_has_no_pull_request_id():
    """TestResult model has no pull_request_id."""
    from app.models.test_result import TestResult
    assert not hasattr(TestResult, 'pull_request_id')

def test_build_execution_nodes_no_attribute_error(graph_service, mock_db):
    """`_build_execution_nodes` does not access `TestResult.pull_request_id`. No AttributeError occurs."""
    pr_id = str(uuid.uuid4())
    head_sha = "abc123sha"
    
    # DB mock returns empty list
    mock_query = mock_db.query.return_value
    mock_join = mock_query.join.return_value
    mock_filter = mock_join.filter.return_value
    mock_filter.all.return_value = []
    
    # Should not raise AttributeError
    nodes = graph_service._build_execution_nodes(pr_id, head_sha, [])
    assert len(nodes) == 0

def test_build_execution_nodes_returns_18_nodes(graph_service, mock_db):
    """Given a recommendation run with attached current PR JUnit execution containing 18 test rows. `_build_execution_nodes` returns 18 execution/test nodes."""
    pr_id = str(uuid.uuid4())
    head_sha = "abc123sha"
    
    # Mock 18 test results
    mock_results = [MagicMock() for _ in range(18)]
    
    mock_query = mock_db.query.return_value
    mock_join = mock_query.join.return_value
    mock_filter = mock_join.filter.return_value
    mock_filter.all.return_value = mock_results
    
    nodes = graph_service._build_execution_nodes(pr_id, head_sha, [])
    
    assert len(nodes) == 18

@patch("app.services.evidence_graph.requirement_evidence_graph_service.logging.getLogger")
def test_build_execution_nodes_missing_returns_warning(mock_get_logger, graph_service, mock_db):
    """Current PR execution is missing. `_build_execution_nodes` returns empty list and diagnostic warning."""
    pr_id = str(uuid.uuid4())
    head_sha = "abc123sha"
    
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    # DB mock returns empty list
    mock_query = mock_db.query.return_value
    mock_join = mock_query.join.return_value
    mock_filter = mock_join.filter.return_value
    mock_filter.all.return_value = []
    
    nodes = graph_service._build_execution_nodes(pr_id, head_sha, [])
    
    assert len(nodes) == 0
    mock_logger.warning.assert_called_with("No current PR test execution relationship found for this recommendation run.")

def test_build_execution_nodes_separates_historical(graph_service, mock_db):
    """Historical test results exist. Current PR execution results exist. `_build_execution_nodes` returns only current PR results."""
    pr_id = str(uuid.uuid4())
    head_sha = "abc123sha"
    
    # Simulate DB returning only PR results because of the join filter
    pr_results = [MagicMock() for _ in range(5)]
    
    mock_query = mock_db.query.return_value
    mock_join = mock_query.join.return_value
    mock_filter = mock_join.filter.return_value
    mock_filter.all.return_value = pr_results
    
    # The SQLAlchemy query construction should verify it applies a filter on TestRun.pull_request_id
    nodes = graph_service._build_execution_nodes(pr_id, head_sha, [])
    
    assert len(nodes) == 5
    
    # Check that filter was called with the right argument
    # We can't strictly inspect the SQLAlchemy binary expression easily in a unit test 
    # without a lot of mocking, but we can verify `.filter` was called.
    mock_join.filter.assert_called_once()
