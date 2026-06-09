"""Test the installation link endpoint and capture the real error."""
import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')

# Load env
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.db.session import SessionLocal
from app.services.github_app import GitHubAppService
from app.models.github_installation import GitHubInstallation
from app.models.user import WorkspaceMember
from sqlalchemy import text

db = SessionLocal()

print("=== DB Check ===")
# Check workspace members
members = db.query(WorkspaceMember).all()
print(f"Workspace members: {len(members)}")
for m in members:
    print(f"  user_id={m.user_id}, workspace_id={m.workspace_id}")

# Check existing installations
installations = db.query(GitHubInstallation).all()
print(f"\nExisting installations: {len(installations)}")
for i in installations:
    print(f"  id={i.id}, workspace_id={i.workspace_id}, github_installation_id={i.github_installation_id}, status={i.status}")

if members:
    workspace_id = members[0].workspace_id
    print(f"\n=== Testing inline_sync for workspace {workspace_id} ===")
    
    # First ensure installation record exists
    inst = db.query(GitHubInstallation).filter(
        GitHubInstallation.workspace_id == workspace_id
    ).first()
    
    if not inst:
        from app.models.github_installation import GitHubInstallation
        from datetime import datetime
        inst = GitHubInstallation(
            workspace_id=workspace_id,
            installation_id=135363628,
            github_installation_id=135363628,
            github_account_login="unknown",
            github_account_type="User",
            repository_selection="all",
            status="ACTIVE",
            installed_at=datetime.utcnow()
        )
        db.add(inst)
        db.commit()
        print("Created installation record")
    
    # Test inline sync
    service = GitHubAppService(db)
    try:
        result = service.inline_sync_repositories(workspace_id, 135363628)
        print(f"Sync result: {result}")
    except Exception as e:
        print(f"Sync error: {type(e).__name__}: {e}")
    
    # Test private key loading
    from app.config import settings
    key = settings.github_private_key
    if key:
        print(f"\nPrivate key loaded: YES ({len(key)} chars)")
        print(f"Starts with: {key[:30]}")
    else:
        print("\nPrivate key: NOT LOADED")
    print(f"App ID: {settings.GITHUB_APP_ID}")

db.close()
