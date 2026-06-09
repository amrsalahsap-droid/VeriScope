#!/usr/bin/env python3
"""Test script for JUnit XML upload endpoint."""

import requests
import os
from pathlib import Path

# Configuration
BACKEND_URL = "http://localhost:8000"
AUTH_TOKEN = os.environ.get("AUTH_TOKEN")

# Sample valid JUnit XML
VALID_JUNIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="test_suite_1" tests="3" failures="1" skipped="0" time="5.0">
    <testcase name="test_login" classname="tests.auth" time="1.0">
      <failure message="Authentication failed">
        Expected 200 but got 401
      </failure>
    </testcase>
    <testcase name="test_logout" classname="tests.auth" time="0.5"/>
    <testcase name="test_register" classname="tests.auth" time="0.5"/>
  </testsuite>
</testsuites>
"""

# Invalid XML
INVALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="test_suite_1" tests="3">
    <testcase name="test_login">
  </testsuite>
</testsuites>
"""

def test_upload(repository_id: str, xml_content: str, filename: str = "junit.xml"):
    """Test uploading JUnit XML to the repository."""
    if not AUTH_TOKEN:
        print("ERROR: AUTH_TOKEN environment variable not set")
        return
    
    url = f"{BACKEND_URL}/github/repositories/{repository_id}/test-history/upload"
    
    files = {"file": (filename, xml_content, "application/xml")}
    data = {
        "source": "MANUAL_UPLOAD",
        "commit_sha": "abc123def456",
        "branch": "main"
    }
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }
    
    print(f"\nTesting upload to: {url}")
    print(f"File: {filename}")
    print(f"Size: {len(xml_content)} bytes")
    
    try:
        response = requests.post(url, files=files, data=data, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    # Get repository ID from environment or use a default
    repository_id = os.environ.get("REPOSITORY_ID", "770c08f4-96ce-48ee-a110-e77f8eab6205")
    
    print("=" * 60)
    print("JUnit XML Upload Test")
    print("=" * 60)
    print(f"Repository ID: {repository_id}")
    print(f"Backend URL: {BACKEND_URL}")
    
    # Test 1: Valid XML
    print("\n" + "=" * 60)
    print("TEST 1: Valid JUnit XML")
    print("=" * 60)
    test_upload(repository_id, VALID_JUNIT_XML, "valid_junit.xml")
    
    # Test 2: Invalid XML
    print("\n" + "=" * 60)
    print("TEST 2: Invalid XML")
    print("=" * 60)
    test_upload(repository_id, INVALID_XML, "invalid_junit.xml")
    
    # Test 3: Duplicate upload (should be idempotent)
    print("\n" + "=" * 60)
    print("TEST 3: Duplicate Upload (Idempotency)")
    print("=" * 60)
    test_upload(repository_id, VALID_JUNIT_XML, "valid_junit.xml")
    
    print("\n" + "=" * 60)
    print("Tests Complete")
    print("=" * 60)

if __name__ == "__main__":
    main()
