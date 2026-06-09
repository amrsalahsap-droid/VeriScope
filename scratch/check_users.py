"""Check users and workspaces in DB."""
import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.db.session import SessionLocal
from app.models.user import User, Workspace, WorkspaceMember

db = SessionLocal()

print("=== Users ===")
users = db.query(User).all()
for u in users:
    print(f"  id={u.id}, email={u.email}, provider_user_id={u.provider_user_id}")

print("\n=== Workspaces ===")
workspaces = db.query(Workspace).all()
for w in workspaces:
    print(f"  id={w.id}, slug={w.slug}, name={w.name}")

print("\n=== WorkspaceMembers ===")
members = db.query(WorkspaceMember).all()
for m in members:
    print(f"  user_id={m.user_id}, workspace_id={m.workspace_id}, role={m.role}")

db.close()
