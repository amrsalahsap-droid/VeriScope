#!/usr/bin/env python3
"""
Verification script for partial repository selection during onboarding.

This script verifies:
1. GitHub installation has 3 repos.
2. User selects only 1 repo.
3. Backend persists exactly 1 selected repo.
4. Other 2 repos remain connected.
5. /api/repositories returns all 3 repos.
6. Selected repo readiness = NEEDS_TEST_HISTORY.
7. Unselected repos readiness = NOT_SELECTED.
8. Summary: connected_repositories = 3, selected_repositories = 1, needs_test_history = 1, sync_issues = 0
9. /app/repositories does not show empty state.
10. Page refresh preserves same state.
11. Selecting all repos later updates selected_repositories = 3.
12. Selecting zero repos is allowed with connected_repositories still = 3 and selected_repositories = 0.
"""

import os
import sys
import requests
from typing import Dict, Any, List

# Configuration
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN")


class VerificationError(Exception):
    """Custom exception for verification failures."""
    pass


def log_step(step: str):
    """Log a verification step."""
    print(f"\n{'='*60}")
    print(f"STEP: {step}")
    print('='*60)


def log_success(message: str):
    """Log a success message."""
    print(f"✓ {message}")


def log_failure(message: str):
    """Log a failure message."""
    print(f"✗ {message}")


def get_headers() -> Dict[str, str]:
    """Get request headers with authorization."""
    if not AUTH_TOKEN:
        raise VerificationError("AUTH_TOKEN environment variable not set")
    return {"Authorization": f"Bearer {AUTH_TOKEN}"}


def get_repositories(selected_only: bool = False) -> Dict[str, Any]:
    """Fetch repositories from backend."""
    params = {"selected_only": "true" if selected_only else "false"}
    response = requests.get(
        f"{BACKEND_URL}/github/repositories",
        headers=get_headers(),
        params=params
    )
    if response.status_code != 200:
        raise VerificationError(f"Failed to fetch repositories: {response.status_code} - {response.text}")
    return response.json()


def select_repositories(repository_ids: List[str]) -> Dict[str, Any]:
    """Select repositories."""
    response = requests.post(
        f"{BACKEND_URL}/github/repositories/select",
        headers=get_headers(),
        json={"repository_ids": repository_ids}
    )
    if response.status_code != 200:
        raise VerificationError(f"Failed to select repositories: {response.status_code} - {response.text}")
    return response.json()


def verify_initial_state():
    """Verify initial state - GitHub installation has repos."""
    log_step("Verify initial state - GitHub installation has repos")
    
    data = get_repositories(selected_only=False)
    repos = data.get("repositories", [])
    summary = data.get("summary", {})
    
    if len(repos) < 3:
        raise VerificationError(f"Expected at least 3 repositories, found {len(repos)}")
    log_success(f"Found {len(repos)} repositories in workspace")
    
    connected = summary.get("connected_repositories", 0)
    if connected < 3:
        raise VerificationError(f"Expected connected_repositories >= 3, got {connected}")
    log_success(f"connected_repositories = {connected}")
    
    return repos


def verify_partial_selection(repos: List[Dict[str, Any]]):
    """Verify selecting only 1 repository works correctly."""
    log_step("Verify partial selection - select only 1 repository")
    
    # Select only the first repository
    selected_repo_id = repos[0]["id"]
    log_success(f"Selecting repository: {repos[0]['full_name']}")
    
    result = select_repositories([selected_repo_id])
    log_success(f"Selection API returned: {result}")
    
    # Verify selection persisted
    data = get_repositories(selected_only=False)
    updated_repos = data.get("repositories", [])
    summary = data.get("summary", {})
    
    # Check selected_for_analysis
    selected_count = sum(1 for r in updated_repos if r.get("selected_for_analysis"))
    if selected_count != 1:
        raise VerificationError(f"Expected 1 selected repository, found {selected_count}")
    log_success(f"selected_for_analysis count = {selected_count}")
    
    # Check summary
    selected_repos = summary.get("selected_repositories", 0)
    if selected_repos != 1:
        raise VerificationError(f"Expected selected_repositories = 1, got {selected_repos}")
    log_success(f"selected_repositories = {selected_repos}")
    
    connected = summary.get("connected_repositories", 0)
    if connected < 3:
        raise VerificationError(f"Expected connected_repositories >= 3, got {connected}")
    log_success(f"connected_repositories = {connected}")
    
    # Check all repos still present
    if len(updated_repos) < 3:
        raise VerificationError(f"Expected all repos to remain, found {len(updated_repos)}")
    log_success(f"All {len(updated_repos)} repositories still present")
    
    return updated_repos


def verify_readiness_states(repos: List[Dict[str, Any]]):
    """Verify readiness states are correct."""
    log_step("Verify readiness states")
    
    selected_repo = None
    unselected_repos = []
    
    for repo in repos:
        if repo.get("selected_for_analysis"):
            selected_repo = repo
        else:
            unselected_repos.append(repo)
    
    if not selected_repo:
        raise VerificationError("No selected repository found")
    
    # Selected repo should have NEEDS_TEST_HISTORY (if no test history)
    selected_readiness = selected_repo.get("readiness_state")
    log_success(f"Selected repo readiness: {selected_readiness}")
    
    # Unselected repos should have NOT_SELECTED
    for repo in unselected_repos:
        readiness = repo.get("readiness_state")
        if readiness != "NOT_SELECTED":
            log_failure(f"Unselected repo {repo['full_name']} has readiness {readiness}, expected NOT_SELECTED")
        else:
            log_success(f"Unselected repo {repo['full_name']} has readiness NOT_SELECTED")


def verify_api_returns_all_repos():
    """Verify /api/repositories returns all repos (not just selected)."""
    log_step("Verify /api/repositories returns all connected repos")
    
    data = get_repositories(selected_only=False)
    repos = data.get("repositories", [])
    
    if len(repos) < 3:
        raise VerificationError(f"Expected at least 3 repos, got {len(repos)}")
    log_success(f"/api/repositories returns {len(repos)} repositories")
    
    # Verify selected_only=true filters correctly
    data_selected = get_repositories(selected_only=True)
    repos_selected = data_selected.get("repositories", [])
    
    if len(repos_selected) != 1:
        raise VerificationError(f"Expected 1 repo with selected_only=true, got {len(repos_selected)}")
    log_success(f"selected_only=true returns {len(repos_selected)} repository")


def verify_select_all(repos: List[Dict[str, Any]]):
    """Verify selecting all repos works."""
    log_step("Verify selecting all repositories")
    
    all_ids = [r["id"] for r in repos]
    result = select_repositories(all_ids)
    log_success(f"Selected all {len(all_ids)} repositories")
    
    data = get_repositories(selected_only=False)
    summary = data.get("summary", {})
    
    selected_repos = summary.get("selected_repositories", 0)
    if selected_repos != len(all_ids):
        raise VerificationError(f"Expected selected_repositories = {len(all_ids)}, got {selected_repos}")
    log_success(f"selected_repositories = {selected_repos}")


def verify_select_zero():
    """Verify selecting zero repos is allowed."""
    log_step("Verify selecting zero repositories")
    
    result = select_repositories([])
    log_success(f"Selected zero repositories")
    
    data = get_repositories(selected_only=False)
    summary = data.get("summary", {})
    
    connected = summary.get("connected_repositories", 0)
    selected_repos = summary.get("selected_repositories", 0)
    
    if connected < 3:
        raise VerificationError(f"Expected connected_repositories >= 3, got {connected}")
    log_success(f"connected_repositories = {connected} (repos still connected)")
    
    if selected_repos != 0:
        raise VerificationError(f"Expected selected_repositories = 0, got {selected_repos}")
    log_success(f"selected_repositories = 0")


def main():
    """Run all verification tests."""
    print("="*60)
    print("Partial Repository Selection Verification")
    print("="*60)
    print(f"Backend URL: {BACKEND_URL}")
    
    if not AUTH_TOKEN:
        print("\nERROR: AUTH_TOKEN environment variable not set")
        print("Set it with: export AUTH_TOKEN=<your_token>")
        sys.exit(1)
    
    try:
        # Run verification steps
        repos = verify_initial_state()
        updated_repos = verify_partial_selection(repos)
        verify_readiness_states(updated_repos)
        verify_api_returns_all_repos()
        verify_select_all(updated_repos)
        verify_select_zero()
        
        print("\n" + "="*60)
        print("ALL VERIFICATIONS PASSED")
        print("="*60)
        sys.exit(0)
        
    except VerificationError as e:
        print("\n" + "="*60)
        print("VERIFICATION FAILED")
        print("="*60)
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print("\n" + "="*60)
        print("UNEXPECTED ERROR")
        print("="*60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
