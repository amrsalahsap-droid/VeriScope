"""Test the enhanced /github/repositories endpoint."""
import sys, json, time, urllib.request, urllib.error
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')
from jose import jwt as jose_jwt

secret = "veriscope-state-secret-key-change-in-prod"
token = jose_jwt.encode({
    "sub": "12345",
    "email": "test@test.com",
    "name": "Test User",
    "auth_provider": "github",
    "provider_user_id": "12345",
    "iat": int(time.time()),
    "exp": int(time.time()) + 300
}, secret, algorithm="HS256")

req = urllib.request.Request(
    "http://localhost:8000/github/repositories",
    headers={"Authorization": f"Bearer {token}"},
    method="GET"
)

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    print("Status: 200")
    print(f"Summary: {json.dumps(data['summary'], indent=2)}")
    print(f"Repos: {len(data['repositories'])}")
    if data['repositories']:
        repo = data['repositories'][0]
        print(f"\nFirst repo: {repo['full_name']}")
        print(f"  readiness_state:   {repo['readiness_state']}")
        print(f"  readiness_reasons: {repo['readiness_reasons']}")
        print(f"  next_action:       {repo['next_action']}")
        print(f"  active_pr_count:   {repo['active_pr_count']}")
        print(f"  test_runs_count:   {repo['test_runs_count']}")
        print(f"  coverage_reports:  {repo['coverage_reports_count']}")
        print(f"  visibility:        {repo['visibility']}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}")
