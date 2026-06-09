import os
import sys
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.dependency import FileDependency
from app.services.dependency_extraction import DependencyService

client = TestClient(app)

def cleanup_database():
    """Clean up test records to ensure fresh validation runs."""
    db = SessionLocal()
    try:
        db.query(FileDependency).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database clean up successful.")
    except Exception as e:
        db.rollback()
        print(f"Error during database cleanup: {e}")
    finally:
        db.close()

def create_mock_workspace() -> str:
    """Creates a temporary workspace with standard JS/TS files containing import/export/require patterns."""
    temp_dir = tempfile.mkdtemp(prefix="veriscope_test_workspace_")
    
    # Define file structures
    files = {
        "src/index.ts": """
import { Button } from './components/Button';
import { Card } from './components/Card';
import * as React from 'react'; // Third-party: should be skipped
export { default as layout } from './layout';
""",
        "src/components/Button.tsx": """
import { useTheme } from '../hooks/useTheme';
const helper = require('./helper');
""",
        "src/components/Card.tsx": """
import { useTheme } from '../hooks/useTheme';
""",
        "src/components/helper.js": """
// Regular helper function
export const val = 42;
""",
        "src/hooks/useTheme.ts": """
export const theme = 'dark';
""",
        "src/layout/index.ts": """
export const layout = {};
"""
    }

    for rel_path, content in files.items():
        abs_path = os.path.join(temp_dir, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content.strip())
            
    print(f"Mock workspace created at: {temp_dir}")
    return temp_dir

def run_tests():
    print("Starting Veriscope Lightweight Dependency Extraction & Impacted-File Expansion Tests...\n")
    
    # 1. Create Mock Workspace
    checkout_dir = create_mock_workspace()
    
    # 2. Setup database entities
    db = SessionLocal()
    org_id = uuid4()
    repo_id = uuid4()
    commit_sha = "abc123commitsha"
    
    try:
        org = Organization(id=org_id, name="Test Org", slug="test-org")
        db.add(org)
        db.commit()
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=123456,
            name="test-repo",
            full_name="test-org/test-repo",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()
        print(f"Registered organization {org_id} and repository {repo_id} in database.")
        
        # ----------------------------------------------------
        # 3. Test Static AST Extractor & Heuristics Resolution
        # ----------------------------------------------------
        print("\n--- 3. Testing Tree-Sitter AST & Heuristic Path Resolver ---")
        
        # Test individual file specifier extraction
        index_content = """
        import { Button } from './components/Button';
        export { default as layout } from './layout';
        """
        specifiers = DependencyService.extract_specifiers_from_content(index_content, "src/index.ts")
        assert len(specifiers) == 2
        assert ("./components/Button", "import") in specifiers
        assert ("./layout", "export") in specifiers
        print("Success: AST Extractor correctly matched import/export statements.")

        # Test require and dynamic import extraction
        btn_content = """
        import { useTheme } from '../hooks/useTheme';
        const helper = require('./helper');
        """
        specifiers_btn = DependencyService.extract_specifiers_from_content(btn_content, "src/components/Button.tsx")
        assert len(specifiers_btn) == 2
        assert ("../hooks/useTheme", "import") in specifiers_btn
        assert ("./helper", "require") in specifiers_btn
        print("Success: AST Extractor correctly matched require statements.")

        # Test relative path resolution heuristics
        # Fuzzy extension matching (.tsx)
        res_button = DependencyService.resolve_specifier(checkout_dir, "src/index.ts", "./components/Button")
        assert res_button == "src/components/Button.tsx", f"Expected src/components/Button.tsx, got {res_button}"
        
        # Directory index matching
        res_layout = DependencyService.resolve_specifier(checkout_dir, "src/index.ts", "./layout")
        assert res_layout == "src/layout/index.ts", f"Expected src/layout/index.ts, got {res_layout}"

        # Relative escape safety (must block escaping checkout_dir)
        res_escaped = DependencyService.resolve_specifier(checkout_dir, "src/index.ts", "../../../escape")
        assert res_escaped == "", f"Expected empty string for escaped path, got {res_escaped}"
        
        # Non-relative imports (like 'react') must be ignored
        res_external = DependencyService.resolve_specifier(checkout_dir, "src/index.ts", "react")
        assert res_external == "", f"Expected empty string for external package, got {res_external}"

        print("Success: Heuristic resolution successfully handled extensions, index files, external packages, and safety constraints.")

        # ----------------------------------------------------
        # 4. Ingestion & Idempotency Persistence Tests
        # ----------------------------------------------------
        print("\n--- 4. Testing Dependency Ingestion & Idempotency ---")
        
        # Persist first time
        edges_count = DependencyService.extract_and_persist_dependencies(db, repo_id, commit_sha, checkout_dir)
        print(f"Persisted {edges_count} dependency edges to database.")
        
        # Verify 6 expected edges
        db_edges = db.query(FileDependency).filter(
            FileDependency.repository_id == repo_id,
            FileDependency.commit_sha == commit_sha
        ).all()
        assert len(db_edges) == 6, f"Expected 6 edges in database, found {len(db_edges)}"
        
        # Check specific edge contents
        edge_map = {(e.file_path, e.depends_on_file_path): e.dependency_type for e in db_edges}
        assert ("src/index.ts", "src/components/Button.tsx") in edge_map
        assert edge_map[("src/index.ts", "src/components/Button.tsx")] == "import"
        assert ("src/index.ts", "src/layout/index.ts") in edge_map
        assert edge_map[("src/index.ts", "src/layout/index.ts")] == "export"
        assert ("src/components/Button.tsx", "src/components/helper.js") in edge_map
        assert edge_map[("src/components/Button.tsx", "src/components/helper.js")] == "require"
        print("Success: Database correctly populated with expected edges and types.")

        # Idempotency re-run check
        edges_count_2 = DependencyService.extract_and_persist_dependencies(db, repo_id, commit_sha, checkout_dir)
        assert edges_count_2 == 6
        db_edges_2 = db.query(FileDependency).filter(
            FileDependency.repository_id == repo_id,
            FileDependency.commit_sha == commit_sha
        ).all()
        assert len(db_edges_2) == 6, f"Idempotency check failed: expected 6 edges, found {len(db_edges_2)}"
        print("Success: Idempotent overwrite works flawlessly (clears prior data, no duplicate edges).")

        # ----------------------------------------------------
        # 5. Impacted-File Expansion Tests
        # ----------------------------------------------------
        print("\n--- 5. Testing Impacted-File Expansion (Conservative Scope) ---")
        
        # Test Case 1: Changed leaf file useTheme.ts (should expand to its incoming dependents: Button and Card)
        expansion_theme = DependencyService.expand_impacted_files(db, repo_id, commit_sha, ["src/hooks/useTheme.ts"])
        assert "src/components/Button.tsx" in expansion_theme["directly_dependent_files"]
        assert "src/components/Card.tsx" in expansion_theme["directly_dependent_files"]
        assert len(expansion_theme["imported_neighbors"]) == 0
        print("Success: Expansion for leaf node returned correct dependent files (incoming edges).")

        # Test Case 2: Changed middle file Button.tsx (should expand to its incoming: index.ts, and outgoing: useTheme, helper)
        expansion_btn = DependencyService.expand_impacted_files(db, repo_id, commit_sha, ["src/components/Button.tsx"])
        assert expansion_btn["directly_dependent_files"] == ["src/index.ts"]
        assert "src/hooks/useTheme.ts" in expansion_btn["imported_neighbors"]
        assert "src/components/helper.js" in expansion_btn["imported_neighbors"]
        print("Success: Expansion for middle node returned both incoming dependents and outgoing imported neighbors.")

        # ----------------------------------------------------
        # 6. Diagnostic API Endpoint Tests
        # ----------------------------------------------------
        print("\n--- 6. Testing GET /internal/dependencies/{repo_id}/debug Diagnostic API ---")
        
        # Fetch debug audit info
        response = client.get(f"/internal/dependencies/{repo_id}/debug")
        assert response.status_code == 200, f"Debug endpoint failed: {response.text}"
        debug_data = response.json()
        assert debug_data["raw_inputs"] is not None
        assert debug_data["telemetry"]["latest_commit_sha"] == commit_sha
        assert debug_data["raw_inputs"]["total_dependency_edges"] == 6
        assert len(debug_data["derived_relationships"]["edges"]) == 6
        print("Success: Debug endpoint returned correct summary, latest commit SHA, and total edge counts.")

        # Test pagination (limit & offset)
        response_paginated = client.get(f"/internal/dependencies/{repo_id}/debug?limit=2&offset=1")
        assert response_paginated.status_code == 200
        paginated_data = response_paginated.json()
        assert paginated_data["raw_inputs"] is not None
        assert paginated_data["raw_inputs"]["total_dependency_edges"] == 6
        assert len(paginated_data["derived_relationships"]["edges"]) == 6
        print("Success: Pagination limit and offset constraints validated successfully.")

    finally:
        db.close()
        # Clean up workspace folder
        shutil.rmtree(checkout_dir, ignore_errors=True)

    print("\n=======================================================")
    # Print nice UI table of extracted edges for auditability
    print("ALL DEPENDENCY EXTRACTION INTEGRATION TESTS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_tests()
    finally:
        cleanup_database()
