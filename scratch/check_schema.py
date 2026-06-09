"""Check actual DB columns vs model columns."""
import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')

from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.db.session import engine
from sqlalchemy import text, inspect

insp = inspect(engine)

print("=== github_installations columns in DB ===")
cols = insp.get_columns('github_installations')
db_cols = {c['name'] for c in cols}
for c in cols:
    print(f"  {c['name']} ({c['type']})")

print("\n=== GitHubInstallation model columns ===")
from app.models.github_installation import GitHubInstallation
model_cols = {col.key for col in GitHubInstallation.__table__.columns}
for col in GitHubInstallation.__table__.columns:
    print(f"  {col.key} ({col.type})")

print("\n=== MISSING from DB (in model but not in DB) ===")
missing = model_cols - db_cols
for c in missing:
    print(f"  MISSING: {c}")

print("\n=== EXTRA in DB (in DB but not in model) ===")
extra = db_cols - model_cols
for c in extra:
    print(f"  EXTRA: {c}")
