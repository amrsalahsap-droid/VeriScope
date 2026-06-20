import pytest
from unittest.mock import MagicMock, patch
import uuid
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService
from app.services.regression_evidence_classifier import CoverageNode

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def graph_service(mock_db):
    service = RequirementEvidenceGraphService(db=mock_db)
    service.integration = MagicMock()
    # Mock integration.build_coverage_nodes to just return mocked results
    service.integration.build_coverage_nodes.side_effect = lambda rep, changed, reqs: [CoverageNode(coverage_report_id=str(rep.id), file_path="x", covered_lines=[1], uncovered_lines=[2])] if rep else []
    return service

def test_coveragereport_model_has_no_head_commit_sha():
    """CoverageReport model has no head_commit_sha."""
    from app.models.coverage import CoverageReport
    assert not hasattr(CoverageReport, 'head_commit_sha')
    assert hasattr(CoverageReport, 'commit_sha')

def test_build_coverage_nodes_no_attribute_error(graph_service, mock_db):
    """`_build_coverage_nodes` does not access `CoverageReport.head_commit_sha`. No AttributeError occurs."""
    repo_id = str(uuid.uuid4())
    head_sha = "abc123sha"
    pr_id = str(uuid.uuid4())
    
    # DB mock returns empty list for PR match and sha match
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order = mock_filter.order_by.return_value
    mock_order.all.return_value = []
    
    # Should not raise AttributeError
    nodes = graph_service._build_coverage_nodes(repo_id, head_sha, [], pull_request_id=pr_id)
    assert len(nodes) == 0

def test_build_coverage_nodes_returns_nodes_from_sha(graph_service, mock_db):
    """Given CoverageReport with commit_sha matching PR head SHA. `_build_coverage_nodes` returns coverage nodes."""
    repo_id = str(uuid.uuid4())
    head_sha = "abc123sha"
    
    mock_report = MagicMock()
    mock_report.id = uuid.uuid4()
    
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order = mock_filter.order_by.return_value
    
    # Simulate query returning the mock report
    mock_order.all.return_value = [mock_report]
    
    nodes = graph_service._build_coverage_nodes(repo_id, head_sha, [], pull_request_id=None)
    
    assert len(nodes) == 1
    assert nodes[0].coverage_report_id == str(mock_report.id)

@patch("app.services.evidence_graph.requirement_evidence_graph_service.logging.getLogger")
def test_build_coverage_nodes_missing_returns_empty(mock_get_logger, graph_service, mock_db):
    """Given no coverage report. Endpoint still returns successful evidence graph with coverage unavailable diagnostic."""
    repo_id = str(uuid.uuid4())
    head_sha = "abc123sha"
    pr_id = str(uuid.uuid4())
    
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    # DB mock returns empty list
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order = mock_filter.order_by.return_value
    mock_order.all.return_value = []
    
    nodes = graph_service._build_coverage_nodes(repo_id, head_sha, [], pull_request_id=pr_id)
    
    assert len(nodes) == 0
    mock_logger.warning.assert_any_call("No current coverage report found for this recommendation run.")

@patch("app.services.evidence_graph.requirement_evidence_graph_service.logging.getLogger")
def test_build_coverage_nodes_picks_latest_multiple(mock_get_logger, graph_service, mock_db):
    """Given multiple coverage reports for the same PR/commit. Latest coverage report is selected."""
    repo_id = str(uuid.uuid4())
    head_sha = "abc123sha"
    pr_id = str(uuid.uuid4())
    
    mock_report_new = MagicMock()
    mock_report_new.id = uuid.uuid4()
    mock_report_old = MagicMock()
    
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order = mock_filter.order_by.return_value
    
    # Return two reports for PR match
    mock_order.all.return_value = [mock_report_new, mock_report_old]
    
    nodes = graph_service._build_coverage_nodes(repo_id, head_sha, [], pull_request_id=pr_id)
    
    assert len(nodes) == 1
    assert nodes[0].coverage_report_id == str(mock_report_new.id)
    mock_logger.warning.assert_any_call(f"Found 2 coverage reports for PR {pr_id}. Using the most recent.")

def test_coverage_does_not_classify_by_itself(graph_service):
    """Coverage nodes do not classify requirements as covered by themselves."""
    from app.services.regression_evidence_classifier import RequirementNode, EvidenceClassification
    req = RequirementNode(requirement_id="1", title="AC", is_real_testable_requirement=True, matched_test_ids=[], matched_execution_ids=[])
    req.match_score = 0.5
    
    cov_node = CoverageNode(coverage_report_id="123", file_path="x", covered_lines=[1], uncovered_lines=[2], related_requirement_ids=["1"])
    
    from app.services.evidence_graph.evidence_quality_policy import EvidenceQualityPolicy
    policy = EvidenceQualityPolicy(enable_partial_classification=False)
    graph_service._classify_requirements([req], [], [], [cov_node], policy=policy)
    
    # Assert it gets marked as partially covered, but NOT fully verified
    assert req.classification == EvidenceClassification.PARTIALLY_COVERED
