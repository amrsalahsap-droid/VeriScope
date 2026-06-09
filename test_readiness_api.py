import requests

# Test repository-level readiness endpoint
repo_id = '1777fdde-1d61-41e6-a7b0-1cdc2062fd56'
pr_id = '70754e80-72a7-4f66-96d5-5571a9ab1be2'

# Test PR-level readiness endpoint
response = requests.get(f'http://localhost:8000/readiness/repositories/{repo_id}/pull-requests/{pr_id}')
print(f'PR-level readiness status: {response.status_code}')
if response.status_code == 200:
    data = response.json()
    print(f'Readiness Level: {data.get("readiness_level")}')
    print(f'Expected Confidence: {data.get("expected_confidence")}')
    print(f'Readiness Score: {data.get("readiness_score")}')
    print(f'Can Generate: {data.get("can_generate")}')
    print(f'Available Inputs: {data.get("available_inputs")}')
    print(f'Missing Inputs: {data.get("missing_inputs")}')
    print(f'Blocking Inputs: {data.get("blocking_inputs")}')
else:
    print(f'Error: {response.text}')
