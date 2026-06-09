import os
import sys
import uuid
import datetime
import hashlib
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.test_result import TestCase
from app.services.path_heuristic_resolver import PathHeuristicResolver


def cleanup_database():
    """Clean up seeded data safely."""
    db = SessionLocal()
    try:
        db.query(TestCase).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database cleaned up successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()


def run_verification():
    print("======================================================================")
    print("STARTING PATH HEURISTIC RESOLVER INTEGRATION VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()

    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # Seed Organization and Repository
        org = Organization(id=org_id, name="Heuristic Corp", slug="heuristic-corp")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=222333,
            name="heuristic-core",
            full_name="heuristic-corp/heuristic-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed test cases matching different heuristic types for stem "auth"
        # 1. SAME_STEM
        tc_exact = TestCase(
            id=uuid.uuid4(),
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="auth",
            stable_identity="auth_suite::auth",
            canonical_identity_hash=hashlib.sha256(b"auth_suite::auth").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"auth_suite::auth").hexdigest()
        )
        # 2. TEST_PREFIX_SUFFIX
        tc_suffix = TestCase(
            id=uuid.uuid4(),
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="auth_test",
            stable_identity="auth_suite::auth_test",
            canonical_identity_hash=hashlib.sha256(b"auth_suite::auth_test").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"auth_suite::auth_test").hexdigest()
        )
        # 3. MODULE_NAME_MATCH
        tc_module = TestCase(
            id=uuid.uuid4(),
            repository_id=repo_id,
            suite_name="auth_controllers_suite",
            test_name="verify_tokens",
            stable_identity="auth_controllers_suite::verify_tokens",
            canonical_identity_hash=hashlib.sha256(b"auth_controllers_suite::verify_tokens").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"auth_controllers_suite::verify_tokens").hexdigest()
        )
        # 4. SAME_DIRECTORY (parent dir of src/controllers/user.py is controllers)
        tc_dir = TestCase(
            id=uuid.uuid4(),
            repository_id=repo_id,
            suite_name="controllers_suite",
            test_name="test_endpoints",
            stable_identity="controllers_suite::test_endpoints",
            canonical_identity_hash=hashlib.sha256(b"controllers_suite::test_endpoints").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"controllers_suite::test_endpoints").hexdigest()
        )

        db.add(tc_exact)
        db.add(tc_suffix)
        db.add(tc_module)
        db.add(tc_dir)
        db.commit()

        # ----------------------------------------------------
        # TEST 1: Heuristic Match Type and Confidence Resolution
        # ----------------------------------------------------
        print("\n--- TEST 1: Match Type and Confidence Resolution ---")
        bundle = PathHeuristicResolver.resolve_path_heuristics(
            db=db,
            repository_id=repo_id,
            changed_files=["src/auth.py"]
        )

        assert len(bundle.heuristic_test_candidates) == 3
        # Candidate types should be matched
        types = {c.heuristic_type for c in bundle.heuristic_test_candidates}
        assert "SAME_STEM" in types
        assert "TEST_PREFIX_SUFFIX" in types
        assert "MODULE_NAME_MATCH" in types

        # Check exact stem mapping
        c_exact = [c for c in bundle.heuristic_test_candidates if c.heuristic_type == "SAME_STEM"][0]
        assert c_exact.confidence_score == "MODERATE"
        assert c_exact.stable_identity == "auth_suite::auth"

        # Check prefix/suffix mapping
        c_suffix = [c for c in bundle.heuristic_test_candidates if c.heuristic_type == "TEST_PREFIX_SUFFIX"][0]
        assert c_suffix.confidence_score == "MODERATE"
        assert c_suffix.stable_identity == "auth_suite::auth_test"

        # Check module matching
        c_module = [c for c in bundle.heuristic_test_candidates if c.heuristic_type == "MODULE_NAME_MATCH"][0]
        assert c_module.confidence_score == "LOW"
        assert c_module.stable_identity == "auth_controllers_suite::verify_tokens"
        print("  - Heuristic match types resolved correctly.")
        print("  - Correct confidence levels applied (MODERATE for stems, LOW for module).")

        # ----------------------------------------------------
        # TEST 2: Parent Directory hierarchy matching (SAME_DIRECTORY)
        # ----------------------------------------------------
        print("\n--- TEST 2: Parent Directory matching ---")
        bundle_dir = PathHeuristicResolver.resolve_path_heuristics(
            db=db,
            repository_id=repo_id,
            changed_files=["src/controllers/user.py"]
        )

        assert len(bundle_dir.heuristic_test_candidates) == 2
        candidate_identities = {c.stable_identity for c in bundle_dir.heuristic_test_candidates}
        assert "controllers_suite::test_endpoints" in candidate_identities
        assert "auth_controllers_suite::verify_tokens" in candidate_identities
        print("  - Parent directory matches correctly resolved (SAME_DIRECTORY).")

        # ----------------------------------------------------
        # TEST 3: Capped Heuristic Limits (MAX_HEURISTIC_TESTS_PER_FILE = 5)
        # ----------------------------------------------------
        print("\n--- TEST 3: Safety Limits and Sorting ---")
        # Add 6 additional test cases matching the stem "auth" to exceed the cap of 5
        for i in range(6):
            tc_extra = TestCase(
                id=uuid.uuid4(),
                repository_id=repo_id,
                suite_name="auth_suite",
                test_name=f"test_auth_extra_{i}",
                stable_identity=f"auth_suite::test_auth_extra_{i}",
                canonical_identity_hash=hashlib.sha256(f"auth_suite::test_auth_extra_{i}".encode("utf-8")).hexdigest(),
                identity_lineage_root_hash=hashlib.sha256(f"auth_suite::test_auth_extra_{i}".encode("utf-8")).hexdigest()
            )
            db.add(tc_extra)
        db.commit()

        bundle_cap = PathHeuristicResolver.resolve_path_heuristics(
            db=db,
            repository_id=repo_id,
            changed_files=["src/auth.py"]
        )

        # Maximum of 5 candidates should be returned for a single file
        assert len(bundle_cap.heuristic_test_candidates) == 5

        # Check sorted order: MODERATE before LOW, alphabetical by stable_identity
        candidates = bundle_cap.heuristic_test_candidates
        # Stems/prefix are MODERATE, so they must be first
        for i in range(len(candidates) - 1):
            c_curr = candidates[i]
            c_next = candidates[i + 1]
            if c_curr.confidence_score == "LOW":
                assert c_next.confidence_score == "LOW"
            if c_curr.confidence_score == c_next.confidence_score:
                assert c_curr.stable_identity < c_next.stable_identity
        print("  - Safety limits successfully applied (maximum 5 candidates returned).")
        print("  - Candidates sorted deterministically (confidence desc, stable_identity asc).")

        # ----------------------------------------------------
        # TEST 4: Unresolved files
        # ----------------------------------------------------
        print("\n--- TEST 4: Tracking Unresolved Files ---")
        bundle_unresolved = PathHeuristicResolver.resolve_path_heuristics(
            db=db,
            repository_id=repo_id,
            changed_files=["src/auth.py", "src/unmatched_module.py"]
        )

        assert "src/unmatched_module.py" in bundle_unresolved.unresolved_files
        assert "src/auth.py" not in bundle_unresolved.unresolved_files
        print("  - Unresolved files accurately cataloged.")

    finally:
        db.close()

    print("\n======================================================================")
    print("ALL PATH HEURISTIC RESOLVER INTEGRATION VERIFICATIONS PASSED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
