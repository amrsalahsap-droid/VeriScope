"""Test the detailed readiness API endpoints."""
import requests
import json

def test_api_endpoints():
    """Test the new detailed readiness API endpoints."""
    base_url = "http://localhost:8000"
    
    # Test repository readiness endpoint
    repository_id = "a5de7396-88ca-49f5-af9d-8937aecfcfab"
    pull_request_id = "805e8062-b20f-4831-81aa-f6e7d0e796fd"
    
    print(f"Testing API endpoints...")
    
    try:
        # Test repository readiness
        repo_url = f"{base_url}/api/repositories/{repository_id}/readiness"
        print(f"\nTesting: {repo_url}")
        
        response = requests.get(repo_url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Readiness Level: {data.get('readiness_level')}")
            print(f"Readiness Score: {data.get('readiness_score')}")
            print(f"Can Generate: {data.get('can_generate')}")
            print(f"Available Signals: {len(data.get('available_signals', []))}")
            print(f"Missing Signals: {len(data.get('missing_signals', []))}")
            print(f"Recommended Actions: {len(data.get('recommended_actions', []))}")
        else:
            print(f"Error: {response.text}")
        
        # Test pull request readiness
        pr_url = f"{base_url}/api/repositories/{repository_id}/pull-requests/{pull_request_id}/readiness"
        print(f"\nTesting: {pr_url}")
        
        response = requests.get(pr_url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Readiness Level: {data.get('readiness_level')}")
            print(f"Readiness Score: {data.get('readiness_score')}")
            print(f"Can Generate: {data.get('can_generate')}")
        else:
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Make sure the backend is running.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api_endpoints()
