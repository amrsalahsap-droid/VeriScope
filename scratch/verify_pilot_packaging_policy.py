import os
import sys
import uuid
import datetime
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal, engine
from app.db.base import Base
import app.models
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pilot import (
    PilotOrganizationProfile,
    PilotRepositoryEnrollment
)
from app.services.pilot_packaging_policy import PilotPackagingPolicy

def cleanup_database():
    """Clean up the test DB records cleanly."""
    db = SessionLocal()
    try:
        db.query(PilotRepositoryEnrollment).delete()
        db.query(PilotOrganizationProfile).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database cleanup successful.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_verification():
    print("======================================================================")
    print("STARTING VERISCOPE PHASE 7: PILOT PACKAGING POLICY VERIFICATION")
    print("======================================================================\n")

    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    # 1. Test Retrieve Default Configuration Rules
    print("--- TEST 1: Validating Standard Policy Config Defaults ---")
    config = PilotPackagingPolicy.get_default_packaging_config()
    
    assert config["pricing_version"] == "1.0.0"
    assert config["monthly_price_usd"] == 1500.00
    assert config["repo_limit"] == 3
    assert config["pricing_model"] == "FIXED_MONTHLY"
    assert config["pilot_status"] == "ACTIVE"
    
    features = config["features"]
    assert features["non_blocking_advisory_mode"] is True
    assert features["pr_comment_integration"] is True
    assert features["fragility_memory"] is True
    assert features["pilot_reporting"] is True
    
    print("[PASSED] Standard early paid pilot baseline configuration resolved accurately.\n")

    db = SessionLocal()
    org_id = uuid.uuid4()

    try:
        # 2. Seed base organization and repositories
        org = Organization(id=org_id, name="Pilot Labs Ltd", slug="pilot-labs")
        db.add(org)
        
        repos = []
        for i in range(4):
            repo_id = uuid.uuid4()
            repo = Repository(
                id=repo_id,
                organization_id=org_id,
                github_repo_id=404000 + i,
                name=f"service-{i}",
                full_name=f"pilot-labs/service-{i}",
                default_branch="main",
                is_active=True
            )
            db.add(repo)
            repos.append(repo)
        db.commit()

        # 3. Create Default Profile via Policy
        print("--- TEST 2: Instantiating Default Profile ---")
        profile = PilotPackagingPolicy.create_default_profile(
            db=db,
            organization_id=org_id,
            pilot_name="Beta Evaluation Pilot"
        )

        assert profile.pricing_model == "FIXED_MONTHLY"
        assert profile.monthly_price_usd == 1500.00
        assert profile.repo_limit == 3
        assert "Pricing Version: 1.0.0" in profile.notes
        print("[PASSED] Standard profile successfully created in DB using default policies.\n")

        # 4. Verify Repository Enrollment Limit guards
        print("--- TEST 3: Testing Limit Guards & Repository Enrollment Lineage ---")
        # Enrollment 1
        assert PilotPackagingPolicy.can_enroll_repository(db, profile.id) is True
        db.add(PilotRepositoryEnrollment(
            id=uuid.uuid4(), pilot_profile_id=profile.id, repository_id=repos[0].id,
            enrollment_status="ACTIVE", enrolled_at=datetime.datetime.utcnow()
        ))
        db.commit()

        # Enrollment 2
        assert PilotPackagingPolicy.can_enroll_repository(db, profile.id) is True
        db.add(PilotRepositoryEnrollment(
            id=uuid.uuid4(), pilot_profile_id=profile.id, repository_id=repos[1].id,
            enrollment_status="ACTIVE", enrolled_at=datetime.datetime.utcnow()
        ))
        db.commit()

        # Enrollment 3
        assert PilotPackagingPolicy.can_enroll_repository(db, profile.id) is True
        db.add(PilotRepositoryEnrollment(
            id=uuid.uuid4(), pilot_profile_id=profile.id, repository_id=repos[2].id,
            enrollment_status="ACTIVE", enrolled_at=datetime.datetime.utcnow()
        ))
        db.commit()

        # Enrollment 4 - MUST BE BLOCKED BY THE Standard Repository Limit!
        assert PilotPackagingPolicy.can_enroll_repository(db, profile.id) is False
        print("[PASSED] limit checks correctly blocked the 4th repository enrollment (Limit = 3).\n")

        # 5. Verify configuration flexibility (Configurable later overrides)
        print("--- TEST 4: Upgrading and Customizing Profile (Late Configuration) ---")
        # Upgrade profile repo_limit and pricing model
        profile.repo_limit = 5
        profile.monthly_price_usd = 2500.00
        profile.notes = "Upgraded to 5 repositories tier under customized packaging rules."
        db.commit()

        # Repository 4 enrollment check should now pass!
        assert PilotPackagingPolicy.can_enroll_repository(db, profile.id) is True
        db.add(PilotRepositoryEnrollment(
            id=uuid.uuid4(), pilot_profile_id=profile.id, repository_id=repos[3].id,
            enrollment_status="ACTIVE", enrolled_at=datetime.datetime.utcnow()
        ))
        db.commit()
        
        # Verify enrollment completed successfully
        active_count = db.query(PilotRepositoryEnrollment).filter(
            PilotRepositoryEnrollment.pilot_profile_id == profile.id,
            PilotRepositoryEnrollment.enrollment_status == "ACTIVE"
        ).count()
        assert active_count == 4
        print("[PASSED] Late configuration modifications applied cleanly, showing upgraded limits function perfectly.\n")

    finally:
        db.close()

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 PILOT PACKAGING POLICY VERIFICATION TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
