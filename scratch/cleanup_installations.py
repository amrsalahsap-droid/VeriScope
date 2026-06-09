"""Delete all stale github_installations rows so the real user can link fresh."""
import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.db.session import SessionLocal
from app.models.github_installation import GitHubInstallation

db = SessionLocal()
rows = db.query(GitHubInstallation).all()
print(f"Found {len(rows)} installation(s) - deleting all stale rows...")
for r in rows:
    print(f"  Deleting: ws={r.workspace_id} gh_id={r.github_installation_id}")
    db.delete(r)
db.commit()
print("Done. DB is clean.")
db.close()
