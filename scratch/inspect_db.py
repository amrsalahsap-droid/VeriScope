import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.session import get_db
from app.models.repository import Repository
from app.models.github_installation import GitHubInstallation

db_gen = get_db()
db = next(db_gen)
try:
    repos = db.query(Repository).filter(Repository.full_name.like('%trustdesk%')).all()
    print("REPOSITORIES:")
    for r in repos:
        print(f"ID: {r.id}, full_name: {r.full_name}, owner: {r.owner}, name: {r.name}, is_active: {r.is_active}")
        print(f"  github_repository_id: {r.github_repo_id}, github_installation_id: {r.installation_id}")
        print(f"  workspace_id: {r.workspace_id}")
        print(f"  latest_pr_synced_at: {r.latest_pr_synced_at}, sync_error: {r.sync_error}")

    installations = db.query(GitHubInstallation).all()
    print("\nINSTALLATIONS:")
    for inst in installations:
        print(f"ID: {inst.id}, github_installation_id: {inst.github_installation_id}, account_login: {inst.github_account_login}, status: {inst.status}, workspace_id: {inst.workspace_id}")
finally:
    db.close()
