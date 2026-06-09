import requests
import json

repo_id = '5d10f067-820c-4fcc-9150-501a4fd2b893'
response = requests.get(f'http://localhost:8000/readiness/repositories/{repo_id}')
print(f"Status code: {response.status_code}")
if response.status_code == 200:
    print(json.dumps(response.json(), indent=2))
else:
    print(response.text)
