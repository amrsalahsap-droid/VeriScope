import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')
from app.db.session import SessionLocal
from app.models.github_installation import GitHubInstallation
db = SessionLocal()
rows = db.query(GitHubInstallation).all()
for r in rows:
    print(f"id={r.id} ws={r.workspace_id} gh_id={r.github_installation_id} inst_id={r.installation_id} status={r.status}")
print(f"Total: {len(rows)}")
db.close()
