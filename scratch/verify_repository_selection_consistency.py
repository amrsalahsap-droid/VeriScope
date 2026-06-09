"""
Verification script for repository selection consistency.

This script verifies:
1. GitHub installation sync creates repositories with correct initial state
2. Repository selection through onboarding endpoint works correctly
3. Readiness states update correctly based on selection
4. Summary counts are accurate
5. Disable/enable flow preserves correct semantics
"""

import requests
import json
import sys
from typing import Dict, Any, List
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8000"
AUTH_EMAIL = "test@example.com"
AUTH_NAME = "Test User"

# Test data
TEST_REPO_COUNT = 3


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def log(message: str, color: str = ""):
    """Print a message with optional color."""
    print(f"{color}{message}{Colors.RESET}")


def log_success(message: str):
    log(f"✓ {message}", Colors.GREEN)


def log_error(message: str):
    log(f"✗ {message}", Colors.RED)


def log_info(message: str):
    log(f"ℹ {message}", Colors.BLUE)


def log_section(message: str):
    log(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    log(f"{Colors.BOLD}{message}{Colors.RESET}")
    log(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")


def get_auth_token() -> str:
    """Get or create auth token for test user."""
    # This is a placeholder - in reality you'd need to implement OAuth flow
    # For now, we'll assume the user is already authenticated
    # and we have a token from the session
    log_info("Note: This script assumes you have a valid auth token")
    log_info("Set AUTH_TOKEN environment variable or modify this script")
    
    import os
    token = os.environ.get("AUTH_TOKEN")
    if not token:
        log_error("AUTH_TOKEN environment variable not set")
        sys.exit(1)
    return token


def get_headers(token: str) -> Dict[str, str]:
    """Get headers with auth token."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def get_repositories(token: str) -> Dict[str, Any]:
    """Fetch repositories from backend."""
    response = requests.get(
        f"{BACKEND_URL}/github/repositories",
        headers=get_headers(token)
    )
    if response.status_code != 200:
        log_error(f"Failed to fetch repositories: {response.status_code}")
        log_error(response.text)
        sys.exit(1)
    return response.json()


def select_repositories(token: str, repo_ids: List[str]) -> Dict[str, Any]:
    """Select repositories via onboarding endpoint."""
    response = requests.post(
        f"{BACKEND_URL}/github/repositories/select",
        headers=get_headers(token),
        json={"repository_ids": repo_ids}
    )
    if response.status_code != 200:
        log_error(f"Failed to select repositories: {response.status_code}")
        log_error(response.text)
        sys.exit(1)
    return response.json()


def enable_repository(token: str, repo_id: str) -> Dict[str, Any]:
    """Enable a repository."""
    response = requests.post(
        f"{BACKEND_URL}/github/repositories/{repo_id}/enable",
        headers=get_headers(token)
    )
    if response.status_code != 200:
        log_error(f"Failed to enable repository: {response.status_code}")
        log_error(response.text)
        sys.exit(1)
    return response.json()


def disable_repository(token: str, repo_id: str) -> Dict[str, Any]:
    """Disable a repository."""
    response = requests.post(
        f"{BACKEND_URL}/github/repositories/{repo_id}/disable",
        headers=get_headers(token)
    )
    if response.status_code != 200:
        log_error(f"Failed to disable repository: {response.status_code}")
        log_error(response.text)
        sys.exit(1)
    return response.json()


def verify_initial_state(repositories: List[Dict[str, Any]]):
    """Verify 1-3: Initial repository state after sync."""
    log_section("VERIFICATION 1-3: Initial Repository State")
    
    if len(repositories) == 0:
        log_error("No repositories found. Please run GitHub sync first.")
        sys.exit(1)
    
    log_info(f"Found {len(repositories)} repositories")
    
    for repo in repositories:
        # Verify selected_for_analysis = false initially
        if repo.get("selected_for_analysis") != False:
            log_error(f"Repository {repo['full_name']} has selected_for_analysis={repo.get('selected_for_analysis')}, expected False")
            sys.exit(1)
        
        # Verify is_active = true (GitHub installed)
        if repo.get("is_active") != True:
            log_error(f"Repository {repo['full_name']} has is_active={repo.get('is_active')}, expected True")
            sys.exit(1)
        
        # Verify readiness = NOT_SELECTED
        if repo.get("readiness_state") != "NOT_SELECTED":
            log_error(f"Repository {repo['full_name']} has readiness_state={repo.get('readiness_state')}, expected NOT_SELECTED")
            sys.exit(1)
        
        log_success(f"Repository {repo['full_name']}: selected_for_analysis=False, is_active=True, readiness=NOT_SELECTED")
    
    log_success("All repositories have correct initial state")


def verify_selection(repositories: List[Dict[str, Any]], token: str):
    """Verify 4-5: Repository selection and readiness update."""
    log_section("VERIFICATION 4-5: Repository Selection")
    
    repo_ids = [repo["id"] for repo in repositories]
    
    log_info(f"Selecting {len(repo_ids)} repositories...")
    select_repositories(token, repo_ids)
    
    # Fetch updated repositories
    updated_repos = get_repositories(token)["repositories"]
    
    for repo in updated_repos:
        # Verify selected_for_analysis = true after selection
        if repo.get("selected_for_analysis") != True:
            log_error(f"Repository {repo['full_name']} has selected_for_analysis={repo.get('selected_for_analysis')}, expected True after selection")
            sys.exit(1)
        
        # Verify readiness = NEEDS_TEST_HISTORY (no test runs yet)
        if repo.get("readiness_state") != "NEEDS_TEST_HISTORY":
            log_error(f"Repository {repo['full_name']} has readiness_state={repo.get('readiness_state')}, expected NEEDS_TEST_HISTORY")
            sys.exit(1)
        
        # Verify NOT REMOVED_OR_INACTIVE
        if repo.get("readiness_state") == "REMOVED_OR_INACTIVE":
            log_error(f"Repository {repo['full_name']} incorrectly shows REMOVED_OR_INACTIVE after selection")
            sys.exit(1)
        
        log_success(f"Repository {repo['full_name']}: selected_for_analysis=True, readiness=NEEDS_TEST_HISTORY")
    
    log_success("All repositories selected correctly and readiness updated")


def verify_summary(data: Dict[str, Any]):
    """Verify 6: Summary counts are correct."""
    log_section("VERIFICATION 6: Summary Counts")
    
    summary = data["summary"]
    
    expected = {
        "connected_repositories": TEST_REPO_COUNT,
        "selected_repositories": TEST_REPO_COUNT,
        "needs_test_history": TEST_REPO_COUNT,
        "sync_issues": 0
    }
    
    for key, expected_value in expected.items():
        actual_value = summary.get(key, 0)
        if actual_value != expected_value:
            log_error(f"Summary {key}: expected {expected_value}, got {actual_value}")
            sys.exit(1)
        log_success(f"Summary {key}: {actual_value}")
    
    log_success("All summary counts are correct")


def verify_no_removed_state(repositories: List[Dict[str, Any]]):
    """Verify 7: No REMOVED_OR_INACTIVE state."""
    log_section("VERIFICATION 7: No REMOVED_OR_INACTIVE State")
    
    for repo in repositories:
        if repo.get("readiness_state") == "REMOVED_OR_INACTIVE":
            log_error(f"Repository {repo['full_name']} incorrectly shows REMOVED_OR_INACTIVE")
            sys.exit(1)
        if repo.get("readiness_state") == "UNKNOWN":
            log_error(f"Repository {repo['full_name']} incorrectly shows UNKNOWN")
            sys.exit(1)
    
    log_success("No repositories show REMOVED_OR_INACTIVE or UNKNOWN")


def verify_disable_enable(repositories: List[Dict[str, Any]], token: str):
    """Verify 8-9: Disable/enable flow."""
    log_section("VERIFICATION 8-9: Disable/Enable Flow")
    
    if len(repositories) == 0:
        log_error("No repositories to test disable/enable")
        sys.exit(1)
    
    test_repo = repositories[0]
    repo_id = test_repo["id"]
    repo_name = test_repo["full_name"]
    
    log_info(f"Testing disable/enable on {repo_name}")
    
    # Disable repository
    disable_repository(token, repo_id)
    
    # Fetch updated state
    updated_repos = get_repositories(token)["repositories"]
    disabled_repo = next((r for r in updated_repos if r["id"] == repo_id), None)
    
    if not disabled_repo:
        log_error("Repository not found after disable")
        sys.exit(1)
    
    # Verify NOT_SELECTED after disable
    if disabled_repo.get("readiness_state") != "NOT_SELECTED":
        log_error(f"After disable, readiness_state={disabled_repo.get('readiness_state')}, expected NOT_SELECTED")
        sys.exit(1)
    
    # Verify NOT REMOVED_OR_INACTIVE
    if disabled_repo.get("readiness_state") == "REMOVED_OR_INACTIVE":
        log_error(f"After disable, incorrectly shows REMOVED_OR_INACTIVE")
        sys.exit(1)
    
    # Verify NOT UNKNOWN
    if disabled_repo.get("readiness_state") == "UNKNOWN":
        log_error(f"After disable, incorrectly shows UNKNOWN")
        sys.exit(1)
    
    # Verify selected_for_analysis = false
    if disabled_repo.get("selected_for_analysis") != False:
        log_error(f"After disable, selected_for_analysis={disabled_repo.get('selected_for_analysis')}, expected False")
        sys.exit(1)
    
    # Verify is_active still true (not changed by disable)
    if disabled_repo.get("is_active") != True:
        log_error(f"After disable, is_active={disabled_repo.get('is_active')}, expected True (should not change)")
        sys.exit(1)
    
    log_success(f"After disable: readiness=NOT_SELECTED, selected_for_analysis=False, is_active=True")
    
    # Re-enable repository
    enable_repository(token, repo_id)
    
    # Fetch updated state
    updated_repos = get_repositories(token)["repositories"]
    enabled_repo = next((r for r in updated_repos if r["id"] == repo_id), None)
    
    if not enabled_repo:
        log_error("Repository not found after enable")
        sys.exit(1)
    
    # Verify NEEDS_TEST_HISTORY after re-enable
    if enabled_repo.get("readiness_state") != "NEEDS_TEST_HISTORY":
        log_error(f"After re-enable, readiness_state={enabled_repo.get('readiness_state')}, expected NEEDS_TEST_HISTORY")
        sys.exit(1)
    
    # Verify selected_for_analysis = true
    if enabled_repo.get("selected_for_analysis") != True:
        log_error(f"After re-enable, selected_for_analysis={enabled_repo.get('selected_for_analysis')}, expected True")
        sys.exit(1)
    
    log_success(f"After re-enable: readiness=NEEDS_TEST_HISTORY, selected_for_analysis=True")


def verify_refresh_persistence(token: str):
    """Verify 10: Page refresh preserves states."""
    log_section("VERIFICATION 10: Page Refresh Persistence")
    
    # Fetch repositories twice to simulate page refresh
    repos1 = get_repositories(token)["repositories"]
    repos2 = get_repositories(token)["repositories"]
    
    if len(repos1) != len(repos2):
        log_error(f"Repository count changed after refresh: {len(repos1)} -> {len(repos2)}")
        sys.exit(1)
    
    for repo1, repo2 in zip(repos1, repos2):
        if repo1["id"] != repo2["id"]:
            log_error("Repository IDs don't match after refresh")
            sys.exit(1)
        
        if repo1["selected_for_analysis"] != repo2["selected_for_analysis"]:
            log_error(f"selected_for_analysis changed after refresh for {repo1['full_name']}")
            sys.exit(1)
        
        if repo1["readiness_state"] != repo2["readiness_state"]:
            log_error(f"readiness_state changed after refresh for {repo1['full_name']}")
            sys.exit(1)
    
    log_success("Repository states preserved after refresh")


def main():
    """Run all verification tests."""
    log_section("REPOSITORY SELECTION CONSISTENCY VERIFICATION")
    log_info(f"Backend URL: {BACKEND_URL}")
    log_info(f"Test started at: {datetime.now().isoformat()}")
    
    # Get auth token
    token = get_auth_token()
    
    # Fetch initial repositories
    data = get_repositories(token)
    repositories = data["repositories"]
    
    # Run verifications
    verify_initial_state(repositories)
    verify_selection(repositories, token)
    
    # Re-fetch to get updated data
    data = get_repositories(token)
    repositories = data["repositories"]
    
    verify_summary(data)
    verify_no_removed_state(repositories)
    verify_disable_enable(repositories, token)
    verify_refresh_persistence(token)
    
    # Final success
    log_section("ALL VERIFICATIONS PASSED")
    log_success("Repository selection consistency verified successfully")
    log_info(f"Test completed at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
