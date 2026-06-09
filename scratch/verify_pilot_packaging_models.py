import os
import sys
import uuid
import datetime
from pathlib import Path
from sqlalchemy.exc import IntegrityError

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal, engine
from app.db.base import Base
import app.models
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pilot import (
    PilotOrganizationProfile,
    PilotRepositoryEnrollment,
    PilotReportSnapshot,
)

def cleanup_database():
    """Clean up the test DB records cleanly."""
    db = SessionLocal()
    try:
        # Snapshots and enrollments are deleted first due to cascade
        db.query(PilotRepositoryEnrollment).delete()
        db.query(PilotReportSnapshot).delete()
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
    print("STARTING VERISCOPE PHASE 7: PILOT PACKAGING MODELS VERIFICATION")
    print("======================================================================\n")

    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    profile_id = uuid.uuid4()

    try:
        # 1. Seed base organization and repository
        print("--- TEST 1: Seeding Base Organization & Repository ---")
        org = Organization(
            id=org_id,
            name="Alpha Pilot Enterprises",
            slug="alpha-pilot"
        )
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=787878,
            name="core-api",
            full_name="alpha-pilot/core-api",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()
        print("[PASSED] Base organization and repository seeded successfully.\n")

        # 2. Test PilotOrganizationProfile Check Constraints
        print("--- TEST 2: Testing PilotOrganizationProfile Check Constraints ---")
        
        # Test 2a: Invalid Pilot Status
        print("Testing invalid pilot status...")
        invalid_status_profile = PilotOrganizationProfile(
            id=uuid.uuid4(),
            organization_id=org_id,
            pilot_name="Invalid Status Pilot",
            pilot_status="SUPER_ACTIVE",  # Invalid
            pricing_model="FREE"
        )
        db.add(invalid_status_profile)
        try:
            db.commit()
            assert False, "Should have failed with IntegrityError for invalid pilot_status!"
        except IntegrityError as e:
            db.rollback()
            print("[PASSED] Correctly prevented invalid pilot_status ('SUPER_ACTIVE').")

        # Test 2b: Invalid Pricing Model
        print("Testing invalid pricing model...")
        invalid_pricing_profile = PilotOrganizationProfile(
            id=uuid.uuid4(),
            organization_id=org_id,
            pilot_name="Invalid Pricing Pilot",
            pilot_status="ACTIVE",
            pricing_model="BILLIONAIRE"  # Invalid
        )
        db.add(invalid_pricing_profile)
        try:
            db.commit()
            assert False, "Should have failed with IntegrityError for invalid pricing_model!"
        except IntegrityError as e:
            db.rollback()
            print("[PASSED] Correctly prevented invalid pricing_model ('BILLIONAIRE').")

        # Test 2c: Valid Profile Creation
        print("Creating valid pilot profile...")
        profile = PilotOrganizationProfile(
            id=profile_id,
            organization_id=org_id,
            pilot_name="Alpha Core Pilot",
            pilot_status="ACTIVE",
            pilot_start_date=datetime.datetime.utcnow(),
            pilot_end_date=datetime.datetime.utcnow() + datetime.timedelta(days=90),
            pricing_model="FIXED_MONTHLY",
            monthly_price_usd=250.00,
            repo_limit=5,
            notes="Key pilot client."
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        assert profile.pilot_name == "Alpha Core Pilot"
        assert profile.pricing_model == "FIXED_MONTHLY"
        assert profile.monthly_price_usd == 250.00
        print("[PASSED] Valid PilotOrganizationProfile created successfully!\n")

        # 3. Test PilotRepositoryEnrollment Constraints & Uniqueness
        print("--- TEST 3: Testing PilotRepositoryEnrollment Constraints & Uniqueness ---")
        
        # Test 3a: Invalid Enrollment Status
        print("Testing invalid enrollment status...")
        invalid_enrollment = PilotRepositoryEnrollment(
            id=uuid.uuid4(),
            pilot_profile_id=profile_id,
            repository_id=repo_id,
            enrollment_status="SUSPENDED"  # Invalid
        )
        db.add(invalid_enrollment)
        try:
            db.commit()
            assert False, "Should have failed with IntegrityError for invalid enrollment_status!"
        except IntegrityError as e:
            db.rollback()
            print("[PASSED] Correctly prevented invalid enrollment_status ('SUSPENDED').")

        # Test 3b: Valid Enrollment
        print("Creating valid repository enrollment...")
        enrollment = PilotRepositoryEnrollment(
            id=uuid.uuid4(),
            pilot_profile_id=profile_id,
            repository_id=repo_id,
            enrollment_status="ACTIVE",
            enrolled_at=datetime.datetime.utcnow()
        )
        db.add(enrollment)
        db.commit()
        print("[PASSED] Repository enrollment registered successfully.")

        # Test 3c: Duplicate Enrollment (Uniqueness check)
        print("Testing duplicate enrollment uniqueness constraint...")
        duplicate_enrollment = PilotRepositoryEnrollment(
            id=uuid.uuid4(),
            pilot_profile_id=profile_id,
            repository_id=repo_id,
            enrollment_status="ACTIVE"
        )
        db.add(duplicate_enrollment)
        try:
            db.commit()
            assert False, "Should have failed with IntegrityError for duplicate enrollment!"
        except IntegrityError as e:
            db.rollback()
            print("[PASSED] Correctly prevented duplicate repository enrollment via UniqueConstraint.\n")

        # 4. Test PilotReportSnapshot Immutability
        print("--- TEST 4: Testing PilotReportSnapshot Append-Only Immutability ---")
        snapshot_id = uuid.uuid4()
        snapshot = PilotReportSnapshot(
            id=snapshot_id,
            pilot_profile_id=profile_id,
            report_snapshot_hash="sha256_dummy_hash_for_phase_7",
            report_version=1,
            reporting_window_start=datetime.datetime.utcnow() - datetime.timedelta(days=30),
            reporting_window_end=datetime.datetime.utcnow(),
            generated_at=datetime.datetime.utcnow(),
            report_payload={"total_savings_usd": 1250.00, "runs_audited": 42}
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        print("[PASSED] Immutable report snapshot created and persisted.")

        # Test 4a: Attempt Mutation
        print("Attempting to mutate snapshot fields...")
        try:
            snapshot.report_version = 2
            db.commit()
            assert False, "Should have failed with RuntimeError for mutating PilotReportSnapshot!"
        except RuntimeError as e:
            assert "Forensic Immutability Violation" in str(e)
            db.rollback()
            print("[PASSED] ORM event listener correctly blocked snapshot updates.")

        # Test 4b: Attempt Deletion
        print("Attempting to delete snapshot...")
        try:
            db.delete(snapshot)
            db.commit()
            assert False, "Should have failed with RuntimeError for deleting PilotReportSnapshot!"
        except RuntimeError as e:
            assert "Forensic Immutability Violation" in str(e)
            db.rollback()
            print("[PASSED] ORM event listener correctly blocked snapshot deletions.\n")

    finally:
        db.close()

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 PILOT PACKAGING MODEL TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
