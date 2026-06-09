import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from app.db.session import get_db
from app.models.repository import Repository
from app.models.user import Workspace, User, WorkspaceMember

db = next(get_db())
try:
    print("=== WORKSPACES ===")
    workspaces = db.query(Workspace).all()
    for w in workspaces:
        print(f"Workspace: {w.name} | ID: {w.id} | Slug: {w.slug}")

    print("\n=== USERS ===")
    users = db.query(User).all()
    for u in users:
        member = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == u.id).first()
        ws_slug = db.query(Workspace.slug).filter(Workspace.id == member.workspace_id).scalar() if member else "None"
        print(f"User: {u.name} | Email: {u.email} | Active Workspace Slug: {ws_slug}")

    print("\n=== REPOSITORIES ===")
    repos = db.query(Repository).all()
    print(f"Total repositories in DB: {len(repos)}")
    for r in repos:
        ws_slug = db.query(Workspace.slug).filter(Workspace.id == r.workspace_id).scalar()
        print(f"Repo: {r.full_name} | ID: {r.id} | Workspace Slug: {ws_slug} | is_active: {r.is_active} | selected: {r.selected_for_analysis} | installation_id: {r.installation_id}")

finally:
    db.close()
