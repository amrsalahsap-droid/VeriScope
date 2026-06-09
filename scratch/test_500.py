"""Reproduce the backend_500 by simulating the full endpoint call."""
import sys, traceback
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')

from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

# Generate a valid JWT token matching what NextAuth produces
from jose import jwt as jose_jwt
import time

secret = "veriscope-state-secret-key-change-in-prod"
token = jose_jwt.encode({
    "sub": "12345",
    "email": "test@test.com",
    "name": "Test User",
    "image": "https://example.com/pic.jpg",
    "auth_provider": "github",
    "provider_user_id": "12345",
    "iat": int(time.time()),
    "exp": int(time.time()) + 86400
}, secret, algorithm="HS256")

print(f"Token generated: {token[:50]}...")

# Now call the endpoint via HTTP
import urllib.request, json

data = json.dumps({"installation_id": 135363628, "setup_action": "install"}).encode()
req = urllib.request.Request(
    "http://localhost:8000/github/installation/link",
    data=data,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode()
        print(f"SUCCESS {resp.status}: {body}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP ERROR {e.code}: {body}")
except Exception as e:
    print(f"Exception: {e}")
    traceback.print_exc()
