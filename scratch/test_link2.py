"""Test installation link - capture real error."""
import sys, traceback
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')

from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.config import settings
print(f"App ID: {settings.GITHUB_APP_ID}")
key = settings.github_private_key
print(f"Private key loaded: {'YES - ' + str(len(key)) + ' chars' if key else 'NO'}")

from app.db.session import SessionLocal
from app.models.github_installation import GitHubInstallation
from app.models.user import WorkspaceMember

db = SessionLocal()
members = db.query(WorkspaceMember).all()
print(f"Workspace members: {len(members)}")

if members:
    workspace_id = members[0].workspace_id
    print(f"Workspace: {workspace_id}")

    from app.services.github_app import GitHubAppService
    service = GitHubAppService(db)
    try:
        result = service.inline_sync_repositories(workspace_id, 135363628)
        print(f"SUCCESS: {result}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()

db.close()
