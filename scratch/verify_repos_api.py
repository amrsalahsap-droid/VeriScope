import urllib.request, json, sys
import jwt as pyjwt
from datetime import datetime, timedelta

BASE = 'http://localhost:8000'

def req(url, token=None):
    headers = {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    r = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(r, timeout=10)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return None, str(e)

secret = 'veriscope-state-secret-key-change-in-prod'

def make_token(email, name):
    return pyjwt.encode({
        'sub': name, 'email': email,
        'name': name, 'image': None, 'auth_provider': 'github',
        'provider_user_id': name,
        'iat': int(datetime.utcnow().timestamp()),
        'exp': int((datetime.utcnow() + timedelta(hours=24)).timestamp()),
    }, secret, algorithm='HS256')

real_token = make_token('amrsalah.sap@gmail.com', 'Amr')
gate_token = make_token('gate_test@example.com', 'Gate')

print('=== TEST 1: No auth (dev mode fallback) ===')
status, body = req(f'{BASE}/github/repositories')
repos = body.get('repositories', []) if isinstance(body, dict) else []
print(f'Status: {status} | Repos: {len(repos)}')

print()
print('=== TEST 2: Real user auth, all repos ===')
status, body = req(f'{BASE}/github/repositories', real_token)
repos = body.get('repositories', []) if isinstance(body, dict) else []
summary = body.get('summary') if isinstance(body, dict) else None
print(f'Status: {status} | Repos: {len(repos)} | Summary: {summary}')
for r in repos:
    print(f'  - {r["full_name"]} | selected={r["selected_for_analysis"]} | is_active={r["is_active"]} | readiness={r["readiness_state"]}')

print()
print('=== TEST 3: selected_only=true (backward compat) ===')
status, body = req(f'{BASE}/github/repositories?selected_only=true', real_token)
repos = body.get('repositories', []) if isinstance(body, dict) else []
print(f'Status: {status} | Repos: {len(repos)}')

print()
print('=== TEST 4: Empty workspace (no real repos) ===')
status, body = req(f'{BASE}/github/repositories', gate_token)
repos = body.get('repositories', []) if isinstance(body, dict) else []
msg = body.get('message') if isinstance(body, dict) else None
print(f'Status: {status} | Repos: {len(repos)} | Message: {msg}')

print()
print('=== DONE ===')
