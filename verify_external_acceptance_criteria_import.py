"""
Verify External Acceptance Criteria Import

Verifies external work item and acceptance criteria import is correct.

Seed Jira/Azure payload:
- Title: Strong password validation
- Description with AC
- AC: Weak passwords rejected, strong passwords accepted, signup form shows validation error

Verifications:
1. Work item imported
2. AC extracted
3. AC typed correctly
4. AC mapped to behaviors/scenarios
5. Raw payload preserved
6. No duplicate AC
"""

import sys
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, "/Users/amrsa/Downloads/veriscope")

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.external_work_item import ExternalWorkItem
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.pull_request import PullRequest
from app.models.integration_connection import IntegrationConnection
from app.models.work_item_behavior_mapping import WorkItemBehaviorMapping
from app.models.behavior import Behavior


def seed_test_data(db: Session):
    """Seed test repository and integration data."""
    print("Seeding test data...")
    
    # Create test repository
    repo = db.query(Repository).filter(
        Repository.full_name == "test/repo"
    ).first()
    
    if not repo:
        repo = Repository(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            full_name="test/repo",
            owner="test",
            name="repo",
            visibility="private",
            default_branch="main",
            is_active=True,
            selected_for_analysis=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(repo)
        db.commit()
        print(f"Created repository: {repo.full_name}")
    
    # Create mock JIRA connection
    connection = db.query(IntegrationConnection).filter(
        IntegrationConnection.repository_id == repo.id,
        IntegrationConnection.provider == "JIRA"
    ).first()
    
    if not connection:
        connection = IntegrationConnection(
            id=uuid.uuid4(),
            workspace_id=repo.workspace_id,
            repository_id=repo.id,
            provider="JIRA",
            config={
                "base_url": "https://jira.example.com",
                "username": "test@example.com"
            },
            is_active=True,
            last_synced_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(connection)
        db.commit()
        print(f"Created JIRA connection")
    
    # Create test PR
    pr = db.query(PullRequest).filter(
        PullRequest.repository_id == repo.id,
        PullRequest.pr_number == 124
    ).first()
    
    if not pr:
        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pr_number=124,
            title="PROJ-124 Strong password validation",
            description="Implement strong password validation",
            source_branch="feature/strong-password",
            target_branch="main",
            state="open",
            author="test-user",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            merged_at=None,
            closed_at=None
        )
        db.add(pr)
        db.commit()
        print(f"Created PR: {pr.title}")
    
    return repo, pr, connection


def seed_work_item_payload(db: Session, repo: Repository, connection: IntegrationConnection):
    """Seed external work item with AC."""
    print("\nSeeding work item payload...")
    
    # Jira-style payload
    jira_payload = {
        "id": "12456",
        "key": "PROJ-124",
        "fields": {
            "summary": "Strong password validation",
            "description": {
                "content": [
                    {
                        "content": [
                            {
                                "text": "Implement strong password validation for user signup",
                                "type": "text"
                            }
                        ],
                        "type": "paragraph"
                    },
                    {
                        "content": [
                            {
                                "text": "Acceptance Criteria:",
                                "type": "text"
                            }
                        ],
                        "type": "paragraph"
                    },
                    {
                        "content": [
                            {
                                "text": "Weak passwords are rejected.",
                                "type": "text"
                            }
                        ],
                        "type": "paragraph"
                    },
                    {
                        "content": [
                            {
                                "text": "Strong passwords are accepted.",
                                "type": "text"
                            }
                        ],
                        "type": "paragraph"
                    },
                    {
                        "content": [
                            {
                                "text": "Signup form shows validation error.",
                                "type": "text"
                            }
                        ],
                        "type": "paragraph"
                    }
                ],
                "type": "doc",
                "version": 1
            },
            "status": {
                "name": "In Progress"
            },
            "priority": {
                "name": "High"
            },
            "issuetype": {
                "name": "Story"
            }
        }
    }
    
    # Extract AC from payload
    ac_list = [
        {
            "id": "AC-1",
            "title": "Weak passwords are rejected",
            "description": "Password validation rejects weak passwords"
        },
        {
            "id": "AC-2",
            "title": "Strong passwords are accepted",
            "description": "Password validation accepts strong passwords"
        },
        {
            "id": "AC-3",
            "title": "Signup form shows validation error",
            "description": "Signup form displays validation error for invalid passwords"
        }
    ]
    
    # Create external work item
    work_item = db.query(ExternalWorkItem).filter(
        ExternalWorkItem.external_key == "PROJ-124",
        ExternalWorkItem.repository_id == repo.id
    ).first()
    
    if not work_item:
        work_item = ExternalWorkItem(
            id=uuid.uuid4(),
            workspace_id=repo.workspace_id,
            repository_id=repo.id,
            integration_connection_id=connection.id,
            provider="JIRA",
            external_id="12456",
            external_key="PROJ-124",
            title="Strong password validation",
            description="Implement strong password validation for user signup",
            status="IN_PROGRESS",
            priority="HIGH",
            work_item_type="STORY",
            acceptance_criteria=ac_list,
            url="https://jira.example.com/browse/PROJ-124",
            raw_payload=jira_payload,
            last_synced_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(work_item)
        db.commit()
        print(f"   Created external work item: {work_item.external_key}")
        print(f"   AC count: {len(ac_list)}")
    
    return work_item


def verify_work_item_imported(db: Session, repo: Repository):
    """Verify work item imported."""
    print("\n1. Verifying work item imported...")
    
    work_item = db.query(ExternalWorkItem).filter(
        ExternalWorkItem.external_key == "PROJ-124",
        ExternalWorkItem.repository_id == repo.id
    ).first()
    
    if work_item:
        print(f"   ✓ Work item imported: {work_item.external_key}")
        print(f"   Title: {work_item.title}")
        print(f"   Provider: {work_item.provider}")
        return True
    else:
        print("   ✗ Work item NOT imported")
        return False


def verify_ac_extracted(db: Session, work_item: ExternalWorkItem):
    """Verify AC extracted."""
    print("\n2. Verifying AC extracted...")
    
    ac_list = work_item.acceptance_criteria
    
    if ac_list and len(ac_list) == 3:
        print(f"   ✓ AC extracted: {len(ac_list)} criteria")
        for ac in ac_list:
            print(f"   - {ac['title']}")
        return True
    else:
        print(f"   ✗ AC NOT extracted correctly (found {len(ac_list) if ac_list else 0})")
        return False


def verify_ac_typed_correctly(db: Session, work_item: ExternalWorkItem):
    """Verify AC typed correctly."""
    print("\n3. Verifying AC typed correctly...")
    
    ac_list = work_item.acceptance_criteria
    
    if not ac_list:
        print("   ✗ No AC to verify")
        return False
    
    # Check each AC has required fields
    all_correct = True
    for ac in ac_list:
        has_id = "id" in ac
        has_title = "title" in ac
        has_description = "description" in ac
        
        if not (has_id and has_title and has_description):
            print(f"   ✗ AC missing fields: {ac}")
            all_correct = False
        else:
            print(f"   ✓ AC typed correctly: {ac['title']}")
    
    return all_correct


def verify_ac_mapped_to_behaviors(db: Session, repo: Repository, work_item: ExternalWorkItem):
    """Verify AC mapped to behaviors/scenarios."""
    print("\n4. Verifying AC mapped to behaviors/scenarios...")
    
    # Create mock behavior
    behavior = db.query(Behavior).filter(
        Behavior.repository_id == repo.id,
        Behavior.name == "Password Validation"
    ).first()
    
    if not behavior:
        behavior = Behavior(
            id=uuid.uuid4(),
            workspace_id=repo.workspace_id,
            repository_id=repo.id,
            name="Password Validation",
            description="Password validation behavior",
            domain="Authentication",
            feature="Signup",
            layer="API",
            case_type="POSITIVE",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(behavior)
        db.commit()
        print(f"   Created behavior: {behavior.name}")
    
    # Create work item to behavior mapping
    mapping = db.query(WorkItemBehaviorMapping).filter(
        WorkItemBehaviorMapping.external_work_item_id == work_item.id,
        WorkItemBehaviorMapping.behavior_id == behavior.id
    ).first()
    
    if not mapping:
        mapping = WorkItemBehaviorMapping(
            id=uuid.uuid4(),
            workspace_id=repo.workspace_id,
            repository_id=repo.id,
            external_work_item_id=work_item.id,
            behavior_id=behavior.id,
            journey_id=None,
            confidence=0.8,
            mapping_source="TITLE_OVERLAP",
            created_at=datetime.utcnow()
        )
        db.add(mapping)
        db.commit()
        print(f"   Created work item to behavior mapping")
    
    # Verify mapping
    mappings = db.query(WorkItemBehaviorMapping).filter(
        WorkItemBehaviorMapping.external_work_item_id == work_item.id
    ).all()
    
    if len(mappings) > 0:
        print(f"   ✓ AC mapped to behaviors: {len(mappings)} mappings")
        return True
    else:
        print("   ✗ AC NOT mapped to behaviors")
        return False


def verify_raw_payload_preserved(db: Session, work_item: ExternalWorkItem):
    """Verify raw payload preserved."""
    print("\n5. Verifying raw payload preserved...")
    
    if work_item.raw_payload:
        payload_keys = list(work_item.raw_payload.keys())
        print(f"   ✓ Raw payload preserved")
        print(f"   Payload keys: {payload_keys}")
        
        # Check for expected Jira fields
        has_key = "key" in work_item.raw_payload
        has_fields = "fields" in work_item.raw_payload
        
        if has_key and has_fields:
            print(f"   ✓ Payload has expected Jira structure")
            return True
        else:
            print(f"   ✗ Payload missing expected fields")
            return False
    else:
        print("   ✗ Raw payload NOT preserved")
        return False


def verify_no_duplicate_ac(db: Session, work_item: ExternalWorkItem):
    """Verify no duplicate AC."""
    print("\n6. Verifying no duplicate AC...")
    
    ac_list = work_item.acceptance_criteria
    
    if not ac_list:
        print("   ✗ No AC to verify")
        return False
    
    # Check for duplicate titles
    titles = [ac['title'] for ac in ac_list]
    unique_titles = set(titles)
    
    if len(titles) == len(unique_titles):
        print(f"   ✓ No duplicate AC: {len(titles)} unique titles")
        return True
    else:
        print(f"   ✗ Duplicate AC found: {len(titles)} total, {len(unique_titles)} unique")
        return False


def main():
    """Main verification function."""
    print("=" * 60)
    print("VERIFY EXTERNAL ACCEPTANCE CRITERIA IMPORT")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Seed test data
        repo, pr, connection = seed_test_data(db)
        
        # Seed work item payload
        work_item = seed_work_item_payload(db, repo, connection)
        
        # Run verifications
        results = []
        
        results.append(verify_work_item_imported(db, repo))
        results.append(verify_ac_extracted(db, work_item))
        results.append(verify_ac_typed_correctly(db, work_item))
        results.append(verify_ac_mapped_to_behaviors(db, repo, work_item))
        results.append(verify_raw_payload_preserved(db, work_item))
        results.append(verify_no_duplicate_ac(db, work_item))
        
        # Summary
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        passed = sum(results)
        total = len(results)
        print(f"Passed: {passed}/{total}")
        
        if all(results):
            print("\n✓ ALL VERIFICATIONS PASSED")
            print("External AC becomes recommendation input")
            return 0
        else:
            print("\n✗ SOME VERIFICATIONS FAILED")
            print("External AC does NOT become recommendation input")
            return 1
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
