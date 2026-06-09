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
from app.models.dependency import FileDependency
from app.services.dependency_expansion_resolver import DependencyExpansionResolver


def cleanup_database():
    """Clean up seeded data safely."""
    db = SessionLocal()
    try:
        db.query(FileDependency).delete()
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
    print("STARTING DEPENDENCY EXPANSION RESOLVER INTEGRATION VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()

    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # Seed Organization and Repository
        org = Organization(id=org_id, name="Dependency Corp", slug="dependency-corp")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=333444,
            name="dependency-core",
            full_name="dependency-corp/dependency-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # ----------------------------------------------------
        # TEST 1: Missing graph check
        # ----------------------------------------------------
        print("\n--- TEST 1: Missing Graph Resolution ---")
        bundle_missing = DependencyExpansionResolver.expand_dependencies(
            db=db,
            repository_id=repo_id,
            changed_files=["src/auth.py"]
        )

        assert bundle_missing.expanded_files == []
        assert bundle_missing.dependency_state_hash is None
        assert any("no dependency graph" in r.lower() for r in bundle_missing.reasons)
        print("  - Correctly handled missing dependency graph.")

        # ----------------------------------------------------
        # TEST 2: Linear Chain Tree and Depth Resolution
        # ----------------------------------------------------
        print("\n--- TEST 2: Linear Chain Traversal by Depth (Rule 4) ---")
        # Seed linear imports: C imports B, B imports A.
        # So: B depends on A (FileDependency: file_path=B, depends_on_file_path=A)
        # C depends on B (FileDependency: file_path=C, depends_on_file_path=B)
        commit_sha = "sha_chain_111"
        dep1 = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/B.py",
            depends_on_file_path="src/A.py",
            commit_sha=commit_sha
        )
        dep2 = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/C.py",
            depends_on_file_path="src/B.py",
            commit_sha=commit_sha
        )
        db.add(dep1)
        db.add(dep2)
        db.commit()

        # A. Depth 1 (NORMAL) - Should only reach B
        bundle_d1 = DependencyExpansionResolver.expand_dependencies(
            db=db,
            repository_id=repo_id,
            changed_files=["src/A.py"],
            max_depth=1
        )
        assert bundle_d1.expanded_files == ["src/B.py"]
        assert bundle_d1.expansion_depth_reached == 1
        assert "src/A.py" in bundle_d1.expansion_edges
        assert bundle_d1.expansion_edges["src/A.py"] == ["src/B.py"]
        print("  - Depth 1 (NORMAL) traversal correctly returned directly dependent file B.")

        # B. Depth 2 (WIDENED) - Should reach B and transitively C
        bundle_d2 = DependencyExpansionResolver.expand_dependencies(
            db=db,
            repository_id=repo_id,
            changed_files=["src/A.py"],
            max_depth=2
        )
        assert bundle_d2.expanded_files == ["src/B.py", "src/C.py"]
        assert bundle_d2.expansion_depth_reached == 2
        assert bundle_d2.expansion_edges["src/A.py"] == ["src/B.py"]
        assert bundle_d2.expansion_edges["src/B.py"] == ["src/C.py"]
        print("  - Depth 2 (WIDENED) traversal correctly returned transitively dependent file C.")

        # ----------------------------------------------------
        # TEST 3: Cycle loop protection
        # ----------------------------------------------------
        print("\n--- TEST 3: Cycle Loop Termination (Rule 9) ---")
        # Add cycle: A imports C -> A depends on C (FileDependency: file_path=A, depends_on_file_path=C)
        dep_cycle = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/A.py",
            depends_on_file_path="src/C.py",
            commit_sha=commit_sha
        )
        db.add(dep_cycle)
        db.commit()

        # Starting at A, the path goes A -> B -> C -> A. BFS must terminate without looping
        bundle_cycle = DependencyExpansionResolver.expand_dependencies(
            db=db,
            repository_id=repo_id,
            changed_files=["src/A.py"],
            max_depth=3
        )
        assert bundle_cycle.expanded_files == ["src/B.py", "src/C.py"]
        assert bundle_cycle.limit_exceeded is False
        print("  - Traversal correctly completed and resolved cycles safely without infinite loops.")

        # ----------------------------------------------------
        # TEST 4: Stale graph check (Rule 7)
        # ----------------------------------------------------
        print("\n--- TEST 4: Stale Graph Degradation (Rule 7) ---")
        # Set all records' created_at to 15 days ago
        db.query(FileDependency).delete()
        db.commit()

        stale_date = datetime.datetime.utcnow() - datetime.timedelta(days=15)
        dep_stale = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/B.py",
            depends_on_file_path="src/A.py",
            commit_sha=commit_sha,
            created_at=stale_date
        )
        db.add(dep_stale)
        db.commit()

        bundle_stale = DependencyExpansionResolver.expand_dependencies(
            db=db,
            repository_id=repo_id,
            changed_files=["src/A.py"],
            max_depth=1
        )
        assert any("confidence is low" in r.lower() for r in bundle_stale.reasons)
        print("  - Stale graph correctly degrades confidence.")

        # ----------------------------------------------------
        # TEST 5: Visited nodes cap limit (Rule 8)
        # ----------------------------------------------------
        print("\n--- TEST 5: Visited Nodes limit cap ---")
        # Seed another dependent so we have: B and C depending on A
        dep_c_on_a = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/C.py",
            depends_on_file_path="src/A.py",
            commit_sha=commit_sha
        )
        db.add(dep_c_on_a)
        db.commit()

        # Constrain max_nodes to 1 popped node
        bundle_limit = DependencyExpansionResolver.expand_dependencies(
            db=db,
            repository_id=repo_id,
            changed_files=["src/A.py"],
            max_depth=3,
            max_nodes=1
        )
        # First node A popped. Visited nodes limit exceeded when A popped, so B/C neighbors are evaluated,
        # but further traversal is stopped. Limit exceeded should be True.
        assert bundle_limit.limit_exceeded is True
        assert any("limit exceeded" in r.lower() for r in bundle_limit.reasons)
        print("  - Node visit limit caps enforced and limit_exceeded successfully reported.")

    finally:
        db.close()

    print("\n======================================================================")
    print("ALL DEPENDENCY Expansion RESOLVER INTEGRATION VERIFICATIONS PASSED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
