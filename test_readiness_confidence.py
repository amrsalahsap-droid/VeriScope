import requests
import json

# Test the readiness endpoint with the TrustDesk repository
repo_id = '5d10f067-820c-4fcc-9150-501a4fd2b893'
response = requests.get(f'http://localhost:8000/readiness/repositories/{repo_id}')
print(f'Status: {response.status_code}')
if response.status_code == 200:
    data = response.json()
    print(f'Readiness Level: {data.get("readiness_level")}')
    print(f'Expected Confidence: {data.get("expected_confidence")}')
    print(f'Readiness Score: {data.get("readiness_score")}')
    print(f'Confidence Reason: {data.get("confidence_reason")}')
    print(f'Confidence Ceiling: {data.get("confidence_ceiling")}')
    print(f'Confidence Blockers: {data.get("confidence_blockers")}')
    print(f'Confidence Limiters: {data.get("confidence_limiters")}')
    print(f'Blocking Inputs: {[inp.get("key") for inp in data.get("blocking_inputs", [])]}')
    print(f'Available Inputs: {len(data.get("available_inputs", []))}')
    print(f'Missing Inputs: {len(data.get("missing_inputs", []))}')
    print(f'Missing Input Keys: {[inp.get("key") for inp in data.get("missing_inputs", [])]}')
else:
    print(f'Error: {response.text}')
