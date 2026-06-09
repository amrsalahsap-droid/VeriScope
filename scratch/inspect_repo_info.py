import sys
from app.db.session import SessionLocal
from app.models import Repository, GitHubInstallation, Workspace, User, WorkspaceMember

db = SessionLocal()
try:
    print("--- WORKSPACES ---")
    workspaces = db.query(Workspace).all()
    for w in workspaces:
        print(f"ID: {w.id}, Name: {w.name}")
        
    print("\n--- USERS ---")
    users = db.query(User).all()
    for u in users:
        print(f"ID: {u.id}, Email: {u.email}")
        
    print("\n--- WORKSPACE MEMBERS ---")
    members = db.query(WorkspaceMember).all()
    for m in members:
        print(f"Workspace ID: {m.workspace_id}, User ID: {m.user_id}, Role: {m.role}")

    print("\n--- REPOSITORIES ---")
    repos = db.query(Repository).all()
    for r in repos:
        if r.full_name == "amrsalahsap-droid/trustdesk":
            print(f"ID: {r.id}, Name: {r.name}, Full Name: {r.full_name}, Workspace ID: {r.workspace_id}, installation_id: {getattr(r, 'installation_id', 'N/A')}")
finally:
    db.close()
