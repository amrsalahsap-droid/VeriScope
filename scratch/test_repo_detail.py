import sys, json, time, urllib.request, urllib.error
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')
from jose import jwt as jose_jwt

secret = "veriscope-state-secret-key-change-in-prod"
token = jose_jwt.encode({
    "sub": "amrsalahsap-droid",
    "email": "amrsalah.sap@gmail.com",
    "name": "amrsalahsap-droid",
    "auth_provider": "github",
    "provider_user_id": "amrsalahsap-droid",
    "iat": int(time.time()),
    "exp": int(time.time()) + 300
}, secret, algorithm="HS256")

# Test repository ID
repo_id = "1777fdde-1d61-41e6-a7b0-1cdc2062fd56"

req = urllib.request.Request(
    f"http://localhost:8000/github/repositories/{repo_id}",
    headers={"Authorization": f"Bearer {token}"},
    method="GET"
)

try:
    print(f"Calling GET /github/repositories/{repo_id}...")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    print("Status: 200")
    print(json.dumps(data, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
