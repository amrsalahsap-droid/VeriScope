import urllib.request, json
import jwt as pyjwt
from datetime import datetime, timedelta

BASE = 'http://localhost:8000'
secret = 'veriscope-state-secret-key-change-in-prod'

real_token = pyjwt.encode({
    'sub': 'real_user', 'email': 'amrsalah.sap@gmail.com',
    'name': 'Amr', 'image': None, 'auth_provider': 'github',
    'provider_user_id': 'real_user',
    'iat': int(datetime.utcnow().timestamp()),
    'exp': int((datetime.utcnow() + timedelta(hours=24)).timestamp()),
}, secret, algorithm='HS256')

# Step 1: Get list of repos
req = urllib.request.Request(
    f'{BASE}/github/repositories',
    headers={'Authorization': 'Bearer ' + real_token}
)
resp = urllib.request.urlopen(req, timeout=10)
body = json.loads(resp.read())
repos = body.get('repositories', [])
print(f'Found {len(repos)} repos')

for repo in repos:
    repo_id = repo['id']
    full_name = repo['full_name']
    print(f'\n=== Fetching detail for {full_name} ({repo_id}) ===')

    # Step 2: Fetch detail for each repo
    req2 = urllib.request.Request(
        f'{BASE}/github/repositories/{repo_id}',
        headers={'Authorization': 'Bearer ' + real_token}
    )
    try:
        resp2 = urllib.request.urlopen(req2, timeout=10)
        detail = json.loads(resp2.read())
        print(f'  Status: 200')
        print(f'  Keys: {list(detail.keys())}')
        has_evidence = 'evidence' in detail
        has_health = 'health' in detail
        has_readiness = 'readiness_state' in detail
        print(f'  evidence: {has_evidence} | health: {has_health} | readiness_state: {has_readiness}')
        print(f'  readiness_state: {detail.get("readiness_state")} | next_action: {detail.get("next_action")}')
    except urllib.error.HTTPError as e:
        err_body = json.loads(e.read())
        print(f'  HTTP Error {e.code}: {err_body}')
    except Exception as e:
        print(f'  Error: {type(e).__name__}: {e}')
