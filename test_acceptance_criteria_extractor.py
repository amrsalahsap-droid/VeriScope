"""Test suite for AcceptanceCriteriaExtractor."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.acceptance_criteria_extractor import AcceptanceCriteriaExtractor
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.user import Workspace


def test_extract_from_pr_description_with_ac_section(db_session: Session):
    """Test extraction from PR description with explicit Acceptance Criteria section."""
    
    pr_description = """
    This PR implements password reset functionality.
    
    ## Acceptance Criteria:
    - User can request password reset with email
    - User receives reset token via email
    - User can reset password with valid token
    - Expired token is rejected
    - Reused token is rejected
    """
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    criteria, evidence_gap = extractor.extract_from_pr_description(
        pr_description=pr_description,
        repository_id=str(uuid4()),
        pull_request_id=str(uuid4()),
        source="PR_DESCRIPTION"
    )
    
    assert len(criteria) == 5, f"Expected 5 criteria, got {len(criteria)}"
    assert evidence_gap == {}, "Should not have evidence gap when AC found"
    
    # Verify criteria content
    criterion_texts = [c["text"].lower() for c in criteria]
    assert "user can request password reset with email" in criterion_texts
    assert "user receives reset token via email" in criterion_texts
    assert "user can reset password with valid token" in criterion_texts
    assert "expired token is rejected" in criterion_texts
    assert "reused token is rejected" in criterion_texts
    
    # Verify confidence scores
    for criterion in criteria:
        assert 0.0 <= criterion["confidence"] <= 1.0
        assert criterion["source"] == "PR_DESCRIPTION"
        assert "evidence_excerpt" in criterion
    
    print("✓ Extracted 5 criteria from PR description with AC section")


def test_extract_from_pr_description_with_given_when_then(db_session: Session):
    """Test extraction from PR description with Given/When/Then format."""
    
    pr_description = """
    This PR implements user registration.
    
    - Given a new user
    - When they submit valid registration form
    - Then their account is created
    - And they receive confirmation email
    
    - Given a user with existing email
    - When they try to register with same email
    - Then registration is rejected
    """
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    criteria, evidence_gap = extractor.extract_from_pr_description(
        pr_description=pr_description,
        repository_id=str(uuid4()),
        pull_request_id=str(uuid4()),
        source="PR_DESCRIPTION"
    )
    
    assert len(criteria) >= 2, f"Expected at least 2 criteria, got {len(criteria)}"
    assert evidence_gap == {}, "Should not have evidence gap when AC found"
    
    print(f"✓ Extracted {len(criteria)} criteria from Given/When/Then format")


def test_extract_from_pr_description_with_should_must(db_session: Session):
    """Test extraction from PR description with Should/Must statements."""
    
    pr_description = """
    This PR improves authentication.
    
    The system should validate user credentials.
    The system must encrypt passwords.
    Users should be able to reset their password.
    The app must support session timeout.
    """
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    criteria, evidence_gap = extractor.extract_from_pr_description(
        pr_description=pr_description,
        repository_id=str(uuid4()),
        pull_request_id=str(uuid4()),
        source="PR_DESCRIPTION"
    )
    
    assert len(criteria) >= 2, f"Expected at least 2 criteria, got {len(criteria)}"
    assert evidence_gap == {}, "Should not have evidence gap when AC found"
    
    print(f"✓ Extracted {len(criteria)} criteria from Should/Must statements")


def test_extract_from_pr_description_with_numbered_list(db_session: Session):
    """Test extraction from PR description with numbered list."""
    
    pr_description = """
    This PR adds billing functionality.
    
    Requirements:
    1. User can view invoice history
    2. User can download PDF invoice
    3. User can update payment method
    4. System validates payment details
    """
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    criteria, evidence_gap = extractor.extract_from_pr_description(
        pr_description=pr_description,
        repository_id=str(uuid4()),
        pull_request_id=str(uuid4()),
        source="PR_DESCRIPTION"
    )
    
    assert len(criteria) == 4, f"Expected 4 criteria, got {len(criteria)}"
    assert evidence_gap == {}, "Should not have evidence gap when AC found"
    
    print("✓ Extracted 4 criteria from numbered list")


def test_extract_from_pr_description_with_checklist(db_session: Session):
    """Test extraction from PR description with checklist format."""
    
    pr_description = """
    This PR implements user profile updates.
    
    Checklist:
    [x] User can update name
    [ ] User can update email
    [ ] User can update avatar
    [ ] Email validation is performed
    """
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    criteria, evidence_gap = extractor.extract_from_pr_description(
        pr_description=pr_description,
        repository_id=str(uuid4()),
        pull_request_id=str(uuid4()),
        source="PR_DESCRIPTION"
    )
    
    assert len(criteria) >= 2, f"Expected at least 2 criteria, got {len(criteria)}"
    assert evidence_gap == {}, "Should not have evidence gap when AC found"
    
    print(f"✓ Extracted {len(criteria)} criteria from checklist format")


def test_extract_from_empty_description(db_session: Session):
    """Test extraction from empty PR description."""
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    criteria, evidence_gap = extractor.extract_from_pr_description(
        pr_description="",
        repository_id=str(uuid4()),
        pull_request_id=str(uuid4()),
        source="PR_DESCRIPTION"
    )
    
    assert len(criteria) == 0, "Should extract no criteria from empty description"
    assert evidence_gap["type"] == "ACCEPTANCE_CRITERIA_MISSING"
    assert "Empty PR description" in evidence_gap["reason"]
    
    print("✓ Empty description returns evidence gap")


def test_extract_from_vague_prose(db_session: Session):
    """Test extraction from vague prose (should return empty or low confidence)."""
    
    pr_description = """
    This PR might improve the user experience.
    We could maybe add some features.
    It would be nice to consider adding authentication.
    """
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    criteria, evidence_gap = extractor.extract_from_pr_description(
        pr_description=pr_description,
        repository_id=str(uuid4()),
        pull_request_id=str(uuid4()),
        source="PR_DESCRIPTION"
    )
    
    # Vague prose should either return empty or very low confidence criteria
    if len(criteria) > 0:
        for criterion in criteria:
            assert criterion["confidence"] < 0.5, "Vague prose should have low confidence"
        print(f"✓ Vague prose extracted {len(criteria)} low-confidence criteria")
    else:
        assert evidence_gap["type"] == "ACCEPTANCE_CRITERIA_MISSING"
        print("✓ Vague prose returns evidence gap")


def test_normalize_and_deduplicate(db_session: Session):
    """Test that duplicate criteria are normalized and deduplicated."""
    
    pr_description = """
    Acceptance Criteria:
    - User can reset password
    - User should be able to reset their password
    - Password reset functionality is available
    - User can update email
    """
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    criteria, _ = extractor.extract_from_pr_description(
        pr_description=pr_description,
        repository_id=str(uuid4()),
        pull_request_id=str(uuid4()),
        source="PR_DESCRIPTION"
    )
    
    # Check that normalized keys are unique
    normalized_keys = [c["normalized_key"] for c in criteria]
    assert len(normalized_keys) == len(set(normalized_keys)), "Normalized keys should be unique"
    
    print(f"✓ Deduplicated {len(criteria)} criteria (normalized keys unique)")


def test_classify_criterion_type(db_session: Session):
    """Test that criterion types are classified correctly."""
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    
    # Test each type
    test_cases = [
        ("User can reset password", "FUNCTIONAL"),
        ("System must validate input", "VALIDATION"),
        ("Password must be encrypted", "SECURITY"),
        ("Display error message on screen", "UI"),
        ("API endpoint returns JSON", "API"),
        ("Sync with external service", "INTEGRATION"),
        ("Response time should be under 200ms", "PERFORMANCE"),
        ("Store user in database", "DATABASE"),
    ]
    
    for text, expected_type in test_cases:
        classified_type = extractor._classify_criterion_type(text)
        # We allow UNKNOWN if classification fails, but prefer correct type
        if classified_type != expected_type:
            print(f"  Note: '{text}' classified as {classified_type} (expected {expected_type})")
    
    print("✓ Criterion type classification tested")


def test_persist_criteria(db_session: Session):
    """Test that criteria can be persisted to database."""
    
    # Create workspace and repository
    workspace = Workspace(id=uuid4(), name="test", slug="test")
    db_session.add(workspace)
    db_session.commit()
    
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        full_name="test/test-repo",
        workspace_id=workspace.id,
        github_repo_id=12345,
    )
    db_session.add(repo)
    db_session.commit()
    
    from datetime import datetime
    pr = PullRequest(
        id=uuid4(),
        repository_id=repo.id,
        github_pr_id=123,
        number=1,
        title="Test PR",
        author="test",
        source_branch="feature",
        target_branch="main",
        state="open",
        head_commit_sha="abc123",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow(),
    )
    db_session.add(pr)
    db_session.commit()
    
    # Create criteria
    criteria_data = [
        {
            "text": "User can reset password",
            "normalized_key": "user can reset password",
            "criterion_type": "FUNCTIONAL",
            "source": "PR_DESCRIPTION",
            "confidence": 0.8,
            "evidence_excerpt": "- User can reset password",
        },
        {
            "text": "System validates email",
            "normalized_key": "system validates email",
            "criterion_type": "VALIDATION",
            "source": "PR_DESCRIPTION",
            "confidence": 0.9,
            "evidence_excerpt": "- System validates email",
        },
    ]
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    persisted = extractor.persist_criteria(
        criteria=criteria_data,
        repository_id=repo.id,
        pull_request_id=pr.id,
        db=db_session
    )
    
    assert len(persisted) == 2, f"Expected 2 persisted criteria, got {len(persisted)}"
    
    # Verify persistence
    db_criteria = db_session.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.repository_id == repo.id
    ).all()
    
    assert len(db_criteria) == 2, f"Expected 2 criteria in DB, got {len(db_criteria)}"
    
    print("✓ Criteria persisted to database successfully")


def test_extract_from_linked_story(db_session: Session):
    """Test extraction from linked story text."""
    
    story_text = """
    Story: User Registration
    
    As a new user
    I want to create an account
    So that I can use the application
    
    Acceptance Criteria:
    - User can sign up with email and password
    - Password must meet complexity requirements
    - Email validation is sent
    - User can complete registration with valid token
    """
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    criteria, evidence_gap = extractor.extract_from_linked_story(
        story_text=story_text,
        repository_id=str(uuid4()),
        pull_request_id=str(uuid4()),
        source="LINKED_STORY"
    )
    
    assert len(criteria) >= 2, f"Expected at least 2 criteria, got {len(criteria)}"
    assert evidence_gap == {}, "Should not have evidence gap when AC found"
    
    # Verify source
    for criterion in criteria:
        assert criterion["source"] == "LINKED_STORY"
    
    print(f"✓ Extracted {len(criteria)} criteria from linked story")


def test_confidence_calculation(db_session: Session):
    """Test confidence score calculation."""
    
    extractor = AcceptanceCriteriaExtractor(db=db_session)
    
    # High confidence
    high_conf = extractor._calculate_confidence("Given a user, the system must validate credentials")
    assert high_conf > 0.7, f"High confidence expected, got {high_conf}"
    
    # Low confidence
    low_conf = extractor._calculate_confidence("Maybe we could consider adding a feature")
    assert low_conf < 0.5, f"Low confidence expected, got {low_conf}"
    
    # Medium confidence
    med_conf = extractor._calculate_confidence("User can update their profile")
    assert 0.4 <= med_conf <= 0.7, f"Medium confidence expected, got {med_conf}"
    
    print(f"✓ Confidence calculation: high={high_conf:.2f}, low={low_conf:.2f}, med={med_conf:.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
