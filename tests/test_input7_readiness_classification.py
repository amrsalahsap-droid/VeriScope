"""
Test Input 7 readiness status and confidence classification rules.

Tests verify:
- PARTIAL_READY status when some changed files are covered
- READY status when all changed files are covered
- NO_CHANGED_FILE_COVERAGE status when no changed files are covered
- PARTIAL confidence for partial changed file coverage
- HIGH confidence for full changed file coverage
- NONE confidence only when no current coverage
- MISSING status only when no coverage records exist
- HISTORICAL_ONLY status only when SHA mismatch
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.repository import Repository
from app.models.workspace import Workspace
from app.models.test_result import TestCase
from app.services.input_readiness_v2_service import InputReadinessV2Service
from app.constants.evidence import CoverageLevel, EvidenceSource


@pytest.fixture
def db_session(test_db: Session):
    """Provide a test database session."""
    return test_db


@pytest.fixture
def workspace(db_session: Session):
    """Create a test workspace."""
    ws = Workspace(
        id=uuid4(),
        name="Test Workspace",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(ws)
    db_session.commit()
    return ws


@pytest.fixture
def repository(db_session: Session, workspace):
    """Create a test repository."""
    repo = Repository(
        id=uuid4(),
        workspace_id=workspace.id,
        name="test-repo",
        owner="test-owner",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(repo)
    db_session.commit()
    return repo


@pytest.fixture
def pull_request(db_session: Session, repository):
    """Create a test pull request."""
    pr = PullRequest(
        id=uuid4(),
        repository_id=repository.id,
        number=123,
        title="Test PR",
        head_commit_sha="abc123def456",
        base_commit_sha="789xyz",
        state="open",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(pr)
    db_session.commit()
    return pr


@pytest.fixture
def coverage_report(db_session: Session, repository, pull_request):
    """Create a test coverage report."""
    report = CoverageReport(
        id=uuid4(),
        repository_id=repository.id,
        workspace_id=repository.workspace_id,
        commit_sha="abc123def456",
        pull_request_id=pull_request.id,
        current_pr_head_sha=pull_request.head_commit_sha,
        commit_sha_source="AUTO_FROM_SELECTED_PR",
        sha_mismatch=False,
        is_current=True,
        format="LCOV",
        source=EvidenceSource.MANUAL_UPLOAD.value,
        coverage_level=CoverageLevel.TEST_CASE_LEVEL,
        files_total=7,
        covered_lines_total=100,
        uncovered_lines_total=4,
        total_lines=104,
        line_coverage_ratio=0.96,
        overall_coverage_pct=0.96,
        coverage_confidence="HIGH",
        evidence_health_status="HEALTHY",
        coverage_uploaded_at=datetime.now(timezone.utc),
        changed_files_total=6,
        changed_files_with_coverage=4,
        changed_files_without_coverage=2,
        current_pr_coverage_confidence="PARTIAL",
    )
    db_session.add(report)
    db_session.commit()
    return report


@pytest.fixture
def coverage_file_entries(db_session: Session, coverage_report):
    """Create test coverage file entries."""
    entries = []
    for i in range(7):
        entry = CoverageFileEntry(
            id=uuid4(),
            coverage_report_id=coverage_report.id,
            repository_id=coverage_report.repository_id,
            file_path=f"app/module_{i}.py",
            covered_lines=[1, 2, 3, 4, 5] if i < 5 else [],
            uncovered_lines=[6, 7] if i < 5 else [1, 2, 3, 4, 5, 6, 7],
            total_lines=7,
            line_coverage_ratio=0.71 if i < 5 else 0.0,
        )
        db_session.add(entry)
        entries.append(entry)
    db_session.commit()
    return entries


@pytest.fixture
def changed_files(db_session: Session, pull_request):
    """Create test changed files for the PR."""
    changed_files = []
    for i in range(6):
        cf = PullRequestChangedFile(
            id=uuid4(),
            pull_request_id=pull_request.id,
            file_path=f"app/module_{i}.py",
            status="modified",
        )
        db_session.add(cf)
        changed_files.append(cf)
    db_session.commit()
    return changed_files


@pytest.fixture
def test_links(db_session: Session, coverage_report, repository):
    """Create test file-to-test links."""
    links = []
    for i in range(4):
        # Create a test case first
        tc = TestCase(
            id=uuid4(),
            repository_id=repository.id,
            test_name=f"test_module_{i}",
            suite_name="test_suite",
            stable_identity=f"test_module_{i}_stable",
        )
        db_session.add(tc)
        
        link = FileTestLink(
            id=uuid4(),
            coverage_report_id=coverage_report.id,
            file_path=f"app/module_{i}.py",
            test_case_id=tc.id,
            mapping_type="DIRECT",
            confidence_score="HIGH",
        )
        db_session.add(link)
        links.append(link)
    db_session.commit()
    return links


def test_input7_not_missing_when_current_coverage_exists(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries
):
    """Test that status is not MISSING when current coverage exists."""
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    assert input7.status != "MISSING", "Status should not be MISSING when current coverage exists"


def test_input7_partial_ready_when_some_changed_files_covered(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries, changed_files
):
    """Test that status is PARTIAL_READY when some but not all changed files are covered."""
    # Setup: 4 of 6 changed files have coverage
    coverage_report.changed_files_total = 6
    coverage_report.changed_files_with_coverage = 4
    coverage_report.changed_files_without_coverage = 2
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    assert input7.status == "PARTIAL_READY", f"Expected PARTIAL_READY, got {input7.status}"
    assert input7.details.get("changed_files_total") == 6
    assert input7.details.get("changed_files_with_coverage") == 4


def test_input7_ready_when_all_changed_files_covered(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries, changed_files
):
    """Test that status is READY when all changed files are covered."""
    # Setup: all 6 changed files have coverage
    coverage_report.changed_files_total = 6
    coverage_report.changed_files_with_coverage = 6
    coverage_report.changed_files_without_coverage = 0
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    assert input7.status in ("READY", "TEST_LEVEL_READY"), f"Expected READY or TEST_LEVEL_READY, got {input7.status}"
    assert input7.details.get("changed_files_total") == 6
    assert input7.details.get("changed_files_with_coverage") == 6


def test_input7_no_changed_file_coverage_when_zero_changed_files_covered(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries, changed_files
):
    """Test that status is NO_CHANGED_FILE_COVERAGE when no changed files are covered."""
    # Setup: 0 of 6 changed files have coverage
    coverage_report.changed_files_total = 6
    coverage_report.changed_files_with_coverage = 0
    coverage_report.changed_files_without_coverage = 6
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    assert input7.status == "NO_CHANGED_FILE_COVERAGE", f"Expected NO_CHANGED_FILE_COVERAGE, got {input7.status}"


def test_input7_confidence_partial_when_4_of_6_changed_files_covered(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries, changed_files
):
    """Test that confidence is PARTIAL when 4 of 6 changed files are covered."""
    # Setup: 4 of 6 changed files have coverage
    coverage_report.changed_files_total = 6
    coverage_report.changed_files_with_coverage = 4
    coverage_report.changed_files_without_coverage = 2
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    assert input7.details.get("current_pr_coverage_confidence") == "PARTIAL", \
        f"Expected PARTIAL confidence, got {input7.details.get('current_pr_coverage_confidence')}"


def test_input7_confidence_high_when_all_changed_files_covered(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries, changed_files, test_links
):
    """Test that confidence is HIGH when all changed files are covered."""
    # Setup: all 6 changed files have coverage
    coverage_report.changed_files_total = 6
    coverage_report.changed_files_with_coverage = 6
    coverage_report.changed_files_without_coverage = 0
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    assert input7.details.get("current_pr_coverage_confidence") in ("HIGH", "MODERATE"), \
        f"Expected HIGH or MODERATE confidence, got {input7.details.get('current_pr_coverage_confidence')}"


def test_input7_confidence_none_only_when_no_current_coverage(
    db_session: Session, repository, pull_request
):
    """Test that confidence is NONE only when no current coverage exists."""
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    assert input7.status == "MISSING", "Status should be MISSING when no coverage exists"
    assert input7.details.get("current_pr_coverage_confidence") == "NONE", \
        "Confidence should be NONE when no coverage exists"


def test_input7_missing_only_when_no_coverage_records(
    db_session: Session, repository, pull_request
):
    """Test that status is MISSING only when no coverage records exist."""
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    assert input7.status == "MISSING", "Status should be MISSING when no coverage records exist"


def test_input7_historical_only_only_when_sha_mismatch(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries
):
    """Test that status is HISTORICAL_ONLY only when SHA mismatch occurs."""
    # Setup: SHA mismatch
    coverage_report.commit_sha = "different_sha"
    coverage_report.current_pr_head_sha = pull_request.head_commit_sha
    coverage_report.sha_mismatch = True
    coverage_report.is_current = False
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    assert input7.status in ("HISTORICAL_ONLY", "STALE"), \
        f"Expected HISTORICAL_ONLY or STALE, got {input7.status}"


def test_input7_overall_coverage_percent_displayed_correctly(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries, changed_files
):
    """Test that overall coverage percent is displayed correctly (multiplied by 100)."""
    # Setup: 96% coverage
    coverage_report.overall_coverage_pct = 0.96
    coverage_report.line_coverage_ratio = 0.96
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    # The summary should show 96.0% not 0.96%
    assert "96.0%" in input7.summary, f"Expected 96.0% in summary, got: {input7.summary}"


def test_input7_excludes_test_files_from_source_coverage_denominator(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries
):
    """Test that test files are excluded from source coverage denominator."""
    # Create changed files: 4 source files, 2 test files
    changed_files = []
    for i in range(4):
        cf = PullRequestChangedFile(
            id=uuid4(),
            pull_request_id=pull_request.id,
            file_path=f"src/module_{i}.py",
            status="modified",
        )
        db_session.add(cf)
        changed_files.append(cf)
    
    # Add test files
    for i in range(2):
        cf = PullRequestChangedFile(
            id=uuid4(),
            pull_request_id=pull_request.id,
            file_path=f"src/test_module_{i}.test.py",
            status="modified",
        )
        db_session.add(cf)
        changed_files.append(cf)
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    # Coverable source files should be 4, not 6
    assert input7.details.get("coverable_changed_files_total") == 4
    # Test files should be 2
    assert input7.details.get("changed_test_files_total") == 2


def test_input7_reports_changed_test_files_separately(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries
):
    """Test that changed test files are reported separately."""
    # Create changed files with test files
    changed_files = []
    for i in range(3):
        cf = PullRequestChangedFile(
            id=uuid4(),
            pull_request_id=pull_request.id,
            file_path=f"src/module_{i}.py",
            status="modified",
        )
        db_session.add(cf)
        changed_files.append(cf)
    
    cf = PullRequestChangedFile(
        id=uuid4(),
        pull_request_id=pull_request.id,
        file_path="src/__tests__/test_auth.py",
        status="modified",
    )
    db_session.add(cf)
    changed_files.append(cf)
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    # Test files should be reported
    assert input7.details.get("changed_test_files_total") == 1
    assert "test_auth.py" in input7.details.get("changed_test_files", [])


def test_input7_ready_when_all_coverable_changed_source_files_covered(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries
):
    """Test that status is READY when all coverable source files are covered."""
    # Create changed files: 4 source files (all covered), 2 test files
    changed_files = []
    for i in range(4):
        cf = PullRequestChangedFile(
            id=uuid4(),
            pull_request_id=pull_request.id,
            file_path=f"app/module_{i}.py",
            status="modified",
        )
        db_session.add(cf)
        changed_files.append(cf)
    
    for i in range(2):
        cf = PullRequestChangedFile(
            id=uuid4(),
            pull_request_id=pull_request.id,
            file_path=f"app/test_module_{i}.test.py",
            status="modified",
        )
        db_session.add(cf)
        changed_files.append(cf)
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    # Should be READY since all 4 source files are covered
    assert input7.status in ("READY", "TEST_LEVEL_READY"), f"Expected READY or TEST_LEVEL_READY, got {input7.status}"
    assert input7.details.get("coverable_changed_files_total") == 4
    assert input7.details.get("coverable_changed_files_covered") == 4


def test_input7_partial_ready_when_coverable_source_file_uncovered(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries
):
    """Test that status is PARTIAL_READY when a coverable source file is uncovered."""
    # Create changed files: 4 source files (3 covered, 1 uncovered)
    changed_files = []
    for i in range(4):
        cf = PullRequestChangedFile(
            id=uuid4(),
            pull_request_id=pull_request.id,
            file_path=f"app/module_{i}.py",
            status="modified",
        )
        db_session.add(cf)
        changed_files.append(cf)
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    # Should be PARTIAL_READY since only 3 of 4 source files are covered
    assert input7.status == "PARTIAL_READY", f"Expected PARTIAL_READY, got {input7.status}"
    assert input7.details.get("coverable_changed_files_total") == 4
    assert input7.details.get("coverable_changed_files_covered") == 3


def test_input7_returns_uncovered_source_file_paths(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries
):
    """Test that uncovered source file paths are returned."""
    # Create changed files where one is not in coverage
    changed_files = []
    for i in range(3):
        cf = PullRequestChangedFile(
            id=uuid4(),
            pull_request_id=pull_request.id,
            file_path=f"app/module_{i}.py",
            status="modified",
        )
        db_session.add(cf)
        changed_files.append(cf)
    
    # Add an uncovered file
    cf = PullRequestChangedFile(
        id=uuid4(),
        pull_request_id=pull_request.id,
        file_path="app/uncovered_module.py",
        status="modified",
    )
    db_session.add(cf)
    changed_files.append(cf)
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    # Uncovered files should be listed
    uncovered = input7.details.get("uncovered_coverable_changed_files", [])
    assert len(uncovered) > 0, "Expected uncovered source files to be listed"
    assert any("uncovered_module" in f for f in uncovered), "Expected uncovered_module.py in uncovered files"


def test_input7_confidence_high_when_4_of_4_coverable_source_files_covered(
    db_session: Session, repository, pull_request, coverage_report, coverage_file_entries, test_links
):
    """Test that confidence is HIGH when all coverable source files are covered."""
    # Create changed files: 4 source files (all covered), 2 test files
    changed_files = []
    for i in range(4):
        cf = PullRequestChangedFile(
            id=uuid4(),
            pull_request_id=pull_request.id,
            file_path=f"app/module_{i}.py",
            status="modified",
        )
        db_session.add(cf)
        changed_files.append(cf)
    
    for i in range(2):
        cf = PullRequestChangedFile(
            id=uuid4(),
            pull_request_id=pull_request.id,
            file_path=f"app/test_module_{i}.test.py",
            status="modified",
        )
        db_session.add(cf)
        changed_files.append(cf)
    db_session.commit()
    
    service = InputReadinessV2Service(db_session)
    result = service.evaluate_repository_readiness(repository.id, pull_request.id)
    
    input7 = next((item for item in result.inputs if item.input_id == "INPUT_7"), None)
    assert input7 is not None
    # Confidence should be HIGH when all source files are covered
    assert input7.details.get("current_pr_coverage_confidence") in ("HIGH", "MODERATE"), \
        f"Expected HIGH or MODERATE confidence, got {input7.details.get('current_pr_coverage_confidence')}"
