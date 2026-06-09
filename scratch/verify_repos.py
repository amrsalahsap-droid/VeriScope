import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')
from app.db.session import SessionLocal
from app.models.repository import Repository

db = SessionLocal()
repos = db.query(Repository).all()
for r in repos:
    print(f"{r.full_name}")
    print(f"  owner={r.owner}  visibility={r.visibility}  installation_id={r.installation_id}")
    print(f"  is_active={r.is_active}  selected_for_analysis={r.selected_for_analysis}")
    print(f"  last_synced_at={r.last_synced_at}  latest_sync_status={r.latest_sync_status}")
    print(f"  sync_error={r.sync_error}  workspace_id={r.workspace_id}")
    print()
db.close()
