"""
Fetch real PR data from amrsalahsap-droid/VeriScope for Phase 8.6E validation.
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

def main():
    print("=" * 60)
    print("Fetching Real PR Data from GitHub")
    print("=" * 60)
    
    client = GitHubApiClient()
    
    try:
        # List open PRs
        print(f"\n[FETCH] Listing PRs for {REPO_OWNER}/{REPO_NAME}...")
        prs = client.list_pull_requests(INSTALLATION_ID, REPO_OWNER, REPO_NAME, state="all")
        
        print(f"[FETCH] Found {len(prs)} PRs")
        
        if not prs:
            print("[ERROR] No PRs found in repository")
            return
        
        # Get the most recent PR
        pr = prs[0]
        print(f"\n[FETCH] Using PR #{pr['number']}: {pr['title']}")
        print(f"[FETCH] State: {pr['state']}")
        print(f"[FETCH] Head SHA: {pr['head']['sha']}")
        print(f"[FETCH] Base SHA: {pr['base']['sha']}")
        print(f"[FETCH] Head Ref: {pr['head']['ref']}")
        print(f"[FETCH] Base Ref: {pr['base']['ref']}")
        print(f"[FETCH] Changed Files: {pr.get('changed_files', 'N/A')}")
        
        # Get detailed PR info
        print(f"\n[FETCH] Fetching detailed PR info...")
        pr_detail = client.get_pull_request(INSTALLATION_ID, REPO_OWNER, REPO_NAME, pr['number'])
        
        print(f"[FETCH] PR Detail - Additions: {pr_detail.get('additions', 'N/A')}")
        print(f"[FETCH] PR Detail - Deletions: {pr_detail.get('deletions', 'N/A')}")
        print(f"[FETCH] PR Detail - Changed Files: {pr_detail.get('changed_files', 'N/A')}")
        
        # Get changed files
        print(f"\n[FETCH] Fetching changed files...")
        files, _, _, _, _ = client.get_pull_request_files(INSTALLATION_ID, REPO_OWNER, REPO_NAME, pr['number'])
        
        print(f"[FETCH] Found {len(files)} changed files")
        for i, f in enumerate(files[:10]):  # Show first 10
            print(f"[FETCH]   - {f['filename']} ({f['status']})")
        
        # Save to file
        output = {
            "pr_number": pr['number'],
            "pr_title": pr['title'],
            "pr_state": pr['state'],
            "head_sha": pr['head']['sha'],
            "base_sha": pr['base']['sha'],
            "head_ref": pr['head']['ref'],
            "base_ref": pr['base']['ref'],
            "changed_files_count": pr.get('changed_files', len(files)),
            "additions": pr_detail.get('additions', 0),
            "deletions": pr_detail.get('deletions', 0),
            "changed_files": [{"filename": f['filename'], "status": f['status']} for f in files]
        }
        
        output_file = "real_pr_data.json"
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n[SUCCESS] Saved PR data to {output_file}")
        print(f"\n" + "=" * 60)
        print("Real PR Data Summary")
        print("=" * 60)
        print(f"PR Number: {output['pr_number']}")
        print(f"Head SHA: {output['head_sha']}")
        print(f"Base SHA: {output['base_sha']}")
        print(f"Changed Files: {output['changed_files_count']}")
        print("=" * 60)
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch PR data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
