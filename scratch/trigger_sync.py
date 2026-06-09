"""Trigger inline sync for the real user's installation."""
import sys, traceback
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.db.session import SessionLocal
from app.models.github_installation import GitHubInstallation
from app.services.github_app import GitHubAppService

db = SessionLocal()
installations = db.query(GitHubInstallation).all()
print(f"Found {len(installations)} installation(s)")
for inst in installations:
    print(f"  ws={inst.workspace_id} gh_id={inst.github_installation_id} status={inst.status}")
    service = GitHubAppService(db)
    try:
        result = service.inline_sync_repositories(inst.workspace_id, inst.github_installation_id)
        print(f"  Sync result: {result}")
    except Exception as e:
        print(f"  Sync error: {type(e).__name__}: {e}")
        traceback.print_exc()

from app.models.repository import Repository
repos = db.query(Repository).all()
print(f"\nRepositories in DB: {len(repos)}")
for r in repos[:5]:
    print(f"  {r.full_name} (active={r.is_active})")

db.close()
