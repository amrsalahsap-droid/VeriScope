"""
Debug GitHub Status API 422 error.
"""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.github_api_client import GitHubApiClient

REPO_OWNER = "amrsalahsap-droid"
REPO_NAME = "VeriScope"
INSTALLATION_ID = 135363628
COMMIT_SHA = "48070288954ed705ddb34e0365344becfe5fcec6"

def main():
    print("=" * 60)
    print("Debugging GitHub Status API 422 Error")
    print("=" * 60)
    
    client = GitHubApiClient()
    
    # Step 1: Verify commit exists
    print(f"\n[STEP 1] Verifying commit {COMMIT_SHA} exists...")
    try:
        token = client.get_installation_token(INSTALLATION_ID)
        print(f"[TOKEN] Installation token obtained successfully")
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits/{COMMIT_SHA}"
        print(f"[API] GET {url}")
        
        response = client.request("GET", url, headers=headers)
        print(f"[API] Status: {response.status_code}")
        
        if response.status_code == 200:
            commit_data = response.json()
            print(f"[SUCCESS] Commit exists")
            print(f"[COMMIT] SHA: {commit_data.get('sha')}")
            print(f"[COMMIT] Message: {commit_data.get('commit', {}).get('message', 'N/A')[:100]}")
            print(f"[COMMIT] Author: {commit_data.get('commit', {}).get('author', {}).get('name', 'N/A')}")
        else:
            print(f"[ERROR] Commit not found")
            print(f"[RESPONSE] {response.text}")
            return
    except Exception as e:
        print(f"[ERROR] Failed to verify commit: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: Check repository permissions
    print(f"\n[STEP 2] Checking repository permissions...")
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
        print(f"[API] GET {url}")
        
        response = client.request("GET", url, headers=headers)
        print(f"[API] Status: {response.status_code}")
        
        if response.status_code == 200:
            repo_data = response.json()
            print(f"[REPO] Permissions: {repo_data.get('permissions', {})}")
            print(f"[REPO] Private: {repo_data.get('private', False)}")
        else:
            print(f"[ERROR] Failed to get repo info")
            print(f"[RESPONSE] {response.text}")
    except Exception as e:
        print(f"[ERROR] Failed to check permissions: {e}")
    
    # Step 3: Check installation permissions
    print(f"\n[STEP 3] Checking installation permissions...")
    try:
        url = f"https://api.github.com/app/installations/{INSTALLATION_ID}"
        print(f"[API] GET {url}")
        
        # Use JWT for app-level API calls
        jwt_token = client.generate_app_jwt()
        app_headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        response = client.request("GET", url, headers=app_headers)
        print(f"[API] Status: {response.status_code}")
        
        if response.status_code == 200:
            install_data = response.json()
            print(f"[INSTALL] Permissions: {install_data.get('permissions', {})}")
            print(f"[INSTALL] Repository Selection: {install_data.get('repository_selection', 'N/A')}")
        else:
            print(f"[ERROR] Failed to get installation info")
            print(f"[RESPONSE] {response.text}")
    except Exception as e:
        print(f"[ERROR] Failed to check installation: {e}")
    
    # Step 4: Try creating status with detailed logging
    print(f"\n[STEP 4] Attempting to create commit status...")
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/statuses/{COMMIT_SHA}"
        
        payload = {
            "state": "pending",
            "description": "Test status from debug script",
            "context": "veriscope/debug"
        }
        
        print(f"[API] POST {url}")
        print(f"[PAYLOAD] {json.dumps(payload, indent=2)}")
        
        response = client.request("POST", url, headers=headers, body=payload)
        print(f"[API] Status: {response.status_code}")
        print(f"[API] Response: {response.text}")
        
        if response.status_code in [200, 201]:
            print(f"[SUCCESS] Status created")
            status_data = response.json()
            print(f"[STATUS] ID: {status_data.get('id')}")
            print(f"[STATUS] State: {status_data.get('state')}")
            print(f"[STATUS] Context: {status_data.get('context')}")
        else:
            print(f"[ERROR] Failed to create status")
            print(f"[ERROR] Status Code: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            
            # Try to parse error details
            try:
                error_data = response.json()
                print(f"[ERROR] Message: {error_data.get('message', 'N/A')}")
                print(f"[ERROR] Errors: {error_data.get('errors', [])}")
            except:
                pass
    except Exception as e:
        print(f"[ERROR] Failed to create status: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Debug Complete")
    print("=" * 60)

if __name__ == "__main__":
    main()
