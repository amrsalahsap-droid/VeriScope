"""
Test the actual frontend API call to see what it returns.
"""

import requests
import json

REPOSITORY_ID = "017ba58f-f192-4655-81ea-781f1955de0e"
PULL_REQUEST_ID = "f553f0c3-7493-462d-9453-d50f4c15cecc"

# Test the readiness endpoint directly
url = f"http://127.0.0.1:8000/readiness/repositories/{REPOSITORY_ID}/pull-requests/{PULL_REQUEST_ID}"

print(f"Testing API endpoint: {url}")
print()

try:
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    print()
    
    if response.status_code == 200:
        data = response.json()
        print("Response:")
        print(json.dumps(data, indent=2))
        
        # Check AC status
        available = [s.get("key") for s in data.get("available_inputs", [])]
        missing = [s.get("key") for s in data.get("missing_inputs", [])]
        
        print()
        print("="*80)
        print("AC STATUS")
        print("="*80)
        print(f"AC in available_inputs: {'acceptance_criteria' in available}")
        print(f"AC in missing_inputs: {'acceptance_criteria' in missing}")
        print(f"Score: {data.get('readiness_score')}")
        print(f"Available keys: {sorted(available)}")
        print(f"Missing keys: {sorted(missing)}")
    else:
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"Exception: {e}")
