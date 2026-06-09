#!/usr/bin/env python3
"""
Automated Verification Script for Veriscope Test History Upload Business Flow.
File: scratch/verify_test_history_upload_business_flow.py

This script verifies 16 business flow characteristics across backend database states,
REST API endpoints, and static contract layout scans of the frontend Next.js interface.

Business Flow Checklist Verified:
1. page loads for selected repository (API GET)
2. page blocks upload for unselected repository with clear message (API POST validation)
3. no file selected -> upload disabled with helper text (Static Scan contract check)
4. invalid file extension blocked (Static Scan contract check)
5. oversized file blocked (API POST 413 & Static Scan contract check)
6. valid JUnit XML upload succeeds (API POST 201)
7. backend creates TestRun (Database query check)
8. backend creates TestResults (Database query check)
9. evidence summary refreshes (API GET summary check)
10. readiness changes from NEEDS_TEST_HISTORY to NEEDS_COVERAGE (Database & API check)
11. success panel shows parsed stats (API return payload check)
12. Upload Coverage Report CTA appears (Static Scan contract check)
13. View Repository Readiness CTA works (Static Scan contract check)
14. Back link works according to from parameter (Static Scan contract check)
15. no dead CTAs (Static Scan contract check)
16. no alert() usage (Static Scan contract check)
"""

import os
import sys
import uuid
import json
import time
import re
from datetime import datetime
from typing import Optional, Dict, Any

# Ensure veriscope base is in path
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

import jwt
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.github_installation import GitHubInstallation
from app.models.test_result import TestRun, TestResult
from app.config import settings

API_BASE = "http://localhost:8000"
JWT_SECRET = settings.STATE_SECRET_KEY or "veriscope-state-secret-key-change-in-prod"

# Mock valid JUnit XML
VALID_JUNIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="Mocha Tests" time="15.5" tests="4" failures="1" skipped="1">
  <testsuite name="Authentication Services" tests="4" failures="1" skipped="1" errors="0" time="15.5">
    <testcase name="should sign in user with valid credentials" classname="Auth" time="3.2" />
    <testcase name="should block user with invalid password" classname="Auth" time="2.1" />
    <testcase name="should enforce password complexity" classname="Auth" time="4.0">
      <failure message="Enforcement failed: accepted weak password '123456'">
        Error: expected complexity pattern to reject '123456'
      </failure>
    </testcase>
    <testcase name="should skip MFA if session is trusted" classname="Auth" time="0.0">
      <skipped />
    </testcase>
  </testsuite>
</testsuites>
"""

# Mock invalid JUnit XML
INVALID_JUNIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="Malformed Suite" tests="3">
    <testcase name="missing_end_tag"
  </testsuite>
</testsuites>
"""

class FlowTestResult:
    def __init__(self):
        self.sections = {}
        self.current_section = "General"
        self.passed_count = 0
        self.failed_count = 0

    def add_section(self, name: str):
        self.current_section = name
        self.sections[name] = []

    def add(self, check_name: str, passed: bool, description: str = ""):
        if self.current_section not in self.sections:
            self.sections[self.current_section] = []
        self.sections[self.current_section].append((check_name, passed, description))
        if passed:
            self.passed_count += 1
            print(f"  [PASS] {check_name}")
        else:
            self.failed_count += 1
            print(f"  [FAIL] {check_name}")
            if description:
                print(f"         --> {description}")

    def print_markdown_report(self):
        print("\n" + "="*80)
        print("                  VERISCOPE BUSINESS FLOW VERIFICATION REPORT                  ")
        print("="*80 + "\n")

        for section, tests in self.sections.items():
            print(section)
            print("-" * len(section))
            for check, passed, desc in tests:
                status_text = "[PASS] SUCCESS" if passed else "[FAIL] FAILURE"
                print(f" {status_text:<18} | {check:<60}")
                if not passed and desc:
                    print(f"                    Details: {desc}")
            print()

        print("="*80)
        total = self.passed_count + self.failed_count
        print(f"Final Summary: Passed {self.passed_count}/{total} Checkpoints ({self.passed_count/total*100:.1f}%)")
        print("="*80 + "\n")

def generate_token(email: str, name: str, sub: str, workspace_id: Optional[str] = None) -> str:
    payload = {
        "sub": sub,
        "email": email,
        "name": name,
        "auth_provider": "github",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    if workspace_id:
        payload["workspace_id"] = workspace_id
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def setup_test_data(db: Session):
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        email=f"test-flow-{unique_id}@veriscope.dev",
        name="Business Flow Inspector",
        auth_provider="github",
        provider_user_id=f"999999{unique_id}",
    )
    db.add(user)
    db.commit()
    
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Business Flow Workspace",
        slug=f"business-flow-workspace-{unique_id}",
        created_by_user_id=user.id,
    )
    db.add(workspace)
    db.commit()
    
    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role="OWNER",
    )
    db.add(member)
    db.commit()
    
    installation_id = int(f"9999{unique_id}", 16) % 1000000
    installation = GitHubInstallation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        installation_id=installation_id,
        github_installation_id=installation_id,
        github_account_id=999999,
        github_account_type="Organization",
        github_account_login="business-flow-org",
        repository_selection="selected",
        permissions='{"contents": "read", "pull_requests": "read"}',
        status="ACTIVE",
        installed_at=datetime.utcnow(),
    )
    db.add(installation)
    db.commit()
    
    base_repo_id = int(f"4000{unique_id}", 16) % 1000000
    now = datetime.utcnow()
    
    # 1. Enabled Repository for Analysis (NEEDS_TEST_HISTORY)
    repo_selected = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        github_repo_id=base_repo_id,
        installation_id=installation.github_installation_id,
        owner="business-flow-org",
        name="flow-repo-selected",
        full_name="business-flow-org/flow-repo-selected",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=True,
        last_synced_at=now,
        latest_sync_status="SUCCESS",
    )
    
    # 2. Unselected Repository (NOT_SELECTED)
    repo_unselected = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        github_repo_id=base_repo_id + 1,
        installation_id=installation.github_installation_id,
        owner="business-flow-org",
        name="flow-repo-unselected",
        full_name="business-flow-org/flow-repo-unselected",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=False,
        last_synced_at=now,
        latest_sync_status="SUCCESS",
    )
    
    db.add_all([repo_selected, repo_unselected])
    db.commit()
    
    return {
        "user": user,
        "workspace": workspace,
        "installation": installation,
        "repo_selected": repo_selected,
        "repo_unselected": repo_unselected,
    }

def cleanup_test_data(db: Session, test_data: Dict[str, Any]):
    try:
        # Delete related test runs/results first
        repo_ids = [test_data["repo_selected"].id, test_data["repo_unselected"].id]
        runs = db.query(TestRun).filter(TestRun.repository_id.in_(repo_ids)).all()
        run_ids = [run.id for run in runs]
        
        if run_ids:
            db.query(TestResult).filter(TestResult.test_run_id.in_(run_ids)).delete(synchronize_session=False)
            db.query(TestRun).filter(TestRun.id.in_(run_ids)).delete(synchronize_session=False)
            
        db.query(Repository).filter(Repository.id.in_(repo_ids)).delete(synchronize_session=False)
        db.query(GitHubInstallation).filter(GitHubInstallation.id == test_data["installation"].id).delete(synchronize_session=False)
        db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == test_data["workspace"].id).delete(synchronize_session=False)
        db.query(Workspace).filter(Workspace.id == test_data["workspace"].id).delete(synchronize_session=False)
        db.query(User).filter(User.id == test_data["user"].id).delete(synchronize_session=False)
        
        db.commit()
        print("Business flow test data cleaned up.")
    except Exception as e:
        print(f"Error during cleanup: {e}")
        db.rollback()

def run_flow_verification():
    results = FlowTestResult()
    db = SessionLocal()
    test_data = None

    try:
        print("Preparing mock database environment for business flow verification...")
        test_data = setup_test_data(db)
        
        token = generate_token(
            test_data["user"].email,
            test_data["user"].name,
            str(test_data["user"].id),
            str(test_data["workspace"].id)
        )
        
        # Initialize ASGI TestClient
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}
        
        # ----------------------------------------------------
        # SECTION A: BACKEND INTEGRATION & STATE ENFORCEMENT
        # ----------------------------------------------------
        results.add_section("SECTION A: BACKEND INTEGRATION & INGESTION STATE MACHINE")

        # 1. Page Loads for Selected Repository (Verify endpoint fetch status)
        print("\nVerifying SELECTED repository detail load...")
        res = client.get(f"/github/repositories/{test_data['repo_selected'].id}", headers=headers)
        results.add(
            "Page loads for selected repository",
            res.status_code == 200,
            f"Expected status 200, got {res.status_code}: {res.json()}"
        )

        # 2. Page blocks upload for unselected repository with clear message
        print("\nVerifying UNSELECTED repository blocks manual upload...")
        files = {"file": ("junit.xml", VALID_JUNIT_XML, "application/xml")}
        res_block = client.post(
            f"/github/repositories/{test_data['repo_unselected'].id}/test-history/upload",
            headers=headers,
            files=files,
            data={"source": "MANUAL_UPLOAD"}
        )
        has_block_message = "not enabled" in (res_block.json().get("detail", "")).lower()
        results.add(
            "Page blocks upload for unselected repository with clear message",
            res_block.status_code == 400 and has_block_message,
            f"Expected 400 with 'not enabled' validation, got {res_block.status_code}: {res_block.json()}"
        )

        # 3. Oversized file blocked by backend (Limit validation checks)
        print("\nVerifying oversized XML ingestion limits (>10MB)...")
        huge_xml = VALID_JUNIT_XML + ("<!-- Padding -->\n" * 1650000) # Exceeds 25MB easily
        files_huge = {"file": ("huge_junit.xml", huge_xml, "application/xml")}
        res_huge = client.post(
            f"/github/repositories/{test_data['repo_selected'].id}/test-history/upload",
            headers=headers,
            files=files_huge,
            data={"source": "MANUAL_UPLOAD"}
        )
        results.add(
            "Oversized file blocked by backend size limits (10MB)",
            res_huge.status_code == 413,
            f"Expected 413 Payload Too Large, got {res_huge.status_code}: {res_huge.text}"
        )

        # 4. Valid JUnit XML upload succeeds
        print("\nVerifying ingestion of valid JUnit XML...")
        files_valid = {"file": ("junit.xml", VALID_JUNIT_XML, "application/xml")}
        res_valid = client.post(
            f"/github/repositories/{test_data['repo_selected'].id}/test-history/upload",
            headers=headers,
            files=files_valid,
            data={
                "source": "MANUAL_UPLOAD",
                "commit_sha": "5d5be5a27bd6f2122",
                "branch": "main",
                "run_name": "Integration Regression Flow Run"
            }
        )
        results.add(
            "Valid JUnit XML upload succeeds",
            res_valid.status_code == 201 or res_valid.status_code == 200,
            f"Expected 201/200, got {res_valid.status_code}: {res_valid.text}"
        )
        
        valid_response_data = res_valid.json() if res_valid.status_code in [200, 201] else {}

        # 5. Backend creates TestRun entry
        print("\nVerifying TestRun creation in database...")
        db.refresh(test_data["repo_selected"])
        test_run = db.query(TestRun).filter(TestRun.repository_id == test_data["repo_selected"].id).first()
        results.add(
            "Backend creates TestRun database record",
            test_run is not None,
            "No TestRun entry found in database for the repository"
        )

        # 6. Backend creates TestResults rows
        print("\nVerifying TestResults rows creation in database...")
        results_count = 0
        if test_run:
            results_count = db.query(TestResult).filter(TestResult.test_run_id == test_run.id).count()
        results.add(
            "Backend creates TestResult rows in database",
            results_count == 4,  # Our valid XML has 4 testcases
            f"Expected 4 TestResult database records, found {results_count}"
        )

        # 7. Evidence summary refreshes
        print("\nVerifying repository test history summary updates...")
        res_summary = client.get(
            f"/github/repositories/{test_data['repo_selected'].id}/test-history/summary",
            headers=headers
        )
        summary_data = res_summary.json() if res_summary.status_code == 200 else {}
        summary_ok = (
            res_summary.status_code == 200 and 
            summary_data.get("test_runs_count") == 1 and 
            summary_data.get("test_results_count") == 4
        )
        results.add(
            "Evidence summary refreshes and counts runs/results correctly",
            summary_ok,
            f"Summary response verification failed: {summary_data}"
        )

        # 8. Readiness changes from NEEDS_TEST_HISTORY to NEEDS_COVERAGE
        print("\nVerifying repository readiness transition...")
        # Since we just uploaded test history but have NO coverage report, state should transition to NEEDS_COVERAGE
        readiness_state = valid_response_data.get("repository_readiness", {}).get("readiness_state")
        results.add(
            "Readiness changes from NEEDS_TEST_HISTORY to NEEDS_COVERAGE",
            readiness_state == "NEEDS_COVERAGE",
            f"Expected readiness NEEDS_COVERAGE, got {readiness_state}"
        )

        # 9. Success panel returns parsed stats
        print("\nVerifying success payload contains parsed stats...")
        stats_ok = (
            valid_response_data.get("tests_total") == 4 and
            valid_response_data.get("tests_passed") == 2 and
            valid_response_data.get("tests_failed") == 1 and
            valid_response_data.get("tests_skipped") == 1 and
            valid_response_data.get("evidence_health_status") == "HEALTHY"
        )
        results.add(
            "Success payload returns correct parsed statistics",
            stats_ok,
            f"Stats mismatch in upload payload response: {valid_response_data}"
        )

        # ----------------------------------------------------
        # SECTION B: FRONTEND STATIC CONTRACT SCANNING
        # ----------------------------------------------------
        results.add_section("SECTION B: FRONTEND STATIC INTERFACE CONTRACT SCANNING")

        page_path = r"c:\Users\amrsa\Downloads\veriscope\landing-page\app\app\repositories\[repositoryId]\test-history\page.tsx"
        if not os.path.exists(page_path):
            results.add("Frontend page component page.tsx exists", False, f"Not found at {page_path}")
            return
            
        with open(page_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 10. No alert() usage
        has_alert = "alert(" in content or "window.alert" in content
        results.add(
            "No browser alert() usage (uses custom Toasts & inline errors)",
            not has_alert,
            "Browser alert() call found in page.tsx! Always use Toast/Sonner instead."
        )

        # 11. No file selected -> upload disabled with helper text
        # Checks that the deterministic CTA helper instructions are in content
        has_no_file_helper = "Select a JUnit XML file before uploading." in content
        results.add(
            "No file selected -> Upload disabled with clear helper text",
            has_no_file_helper,
            "Missing 'Select a JUnit XML file before uploading.' disabled helper instruction state."
        )

        # 12. Invalid file extension blocked client-side
        has_ext_helper = "Only JUnit XML files are supported here." in content
        results.add(
            "Invalid file extension blocked with dedicated validation warning",
            has_ext_helper,
            "Missing advisory client-side extension validation warning message."
        )

        # 13. Oversized file blocked client-side
        has_oversize_helper = "File size exceeds the 10MB limit." in content or "File Oversized (>10MB)" in content
        results.add(
            "Oversized file blocked with client-side validation limit (10MB)",
            has_oversize_helper,
            "Missing client-side file size validation warning message."
        )

        # 14. Upload Coverage Report CTA appears
        # Checks that the redirect path for NEEDS_COVERAGE redirects to coverage upload with query param
        has_coverage_redirect = "Upload Coverage Report" in content and "coverage?from=test-history" in content
        results.add(
            "Upload Coverage Report CTA appears (direct link with source context)",
            has_coverage_redirect,
            "Missing Upload Coverage redirect context 'coverage?from=test-history'."
        )

        # 15. View Repository Readiness CTA works
        has_readiness_link = "View Repository Readiness" in content and "`/app/repositories/${repositoryId}`" in content
        results.add(
            "View Repository Readiness CTA works (routes to dashboard details)",
            has_readiness_link,
            "Missing view readiness routing action link."
        )

        # 16. Back link works according to from parameter
        has_back_link = "fromParam === \"repositories\"" in content or "fromParam === 'repositories'" in content
        results.add(
            "Back link works dynamically based on from parameter",
            has_back_link,
            "Missing dynamic back-link layout handling based on query from parameters."
        )

        # 17. No dead CTAs (Buttons are disabled, handle action clicks, or route to defined pages)
        # Check that there are no empty onClick handlers that do nothing
        has_empty_handlers = re.search(r'onClick=\{\s*\(\)\s*=>\s*\{\s*\}\s*\}', content)
        results.add(
            "All CTAs and buttons have active bindings (No dead stubs)",
            has_empty_handlers is None,
            "Found empty onClick={() => {}} stubs!"
        )

        # Print detailed report
        results.print_markdown_report()

    except Exception as e:
        print(f"Unexpected execution failure during flow tests: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if test_data:
            cleanup_test_data(db, test_data)
        db.close()

if __name__ == "__main__":
    run_flow_verification()
