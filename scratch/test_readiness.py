"""Verify RepositoryReadinessService against real workspace repos."""
import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from uuid import UUID
from app.db.session import SessionLocal
from app.models.repository import Repository
from app.services.repository_readiness import RepositoryReadinessService

REAL_WORKSPACE_ID = UUID("6869aac6-51c5-4d2e-8e3e-8f74bb0acc10")

db = SessionLocal()
repos = db.query(Repository).filter(Repository.workspace_id == REAL_WORKSPACE_ID).all()
print(f"Repos found: {len(repos)}\n")

svc = RepositoryReadinessService(db)
results = svc.calculate_readiness_bulk(repos, REAL_WORKSPACE_ID)

for repo in repos:
    r = results[repo.id]
    print(f"{repo.full_name}")
    print(f"  state:      {r.readiness_state}")
    print(f"  reasons:    {r.readiness_reasons}")
    print(f"  next_action:{r.next_action}")
    print()

# Also verify single-repo method produces identical result
print("=== Single-repo verification ===")
for repo in repos:
    single = svc.calculate_readiness(repo.id, REAL_WORKSPACE_ID)
    bulk   = results[repo.id]
    match  = single.readiness_state == bulk.readiness_state
    print(f"  {repo.name}: single={single.readiness_state}  bulk={bulk.readiness_state}  match={match}")

db.close()
