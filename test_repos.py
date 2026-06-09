import requests

response = requests.get('http://localhost:8000/github/repositories')
print(f'Status: {response.status_code}')
data = response.json()
print(f'Repositories count: {len(data.get("repositories", []))}')
for repo in data.get("repositories", []):
    if 'trustdesk' in repo.get('full_name', '').lower():
        print(f'TrustDesk repo: {repo}')
