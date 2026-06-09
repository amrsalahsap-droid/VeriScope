"""Check alembic current revision and DB columns on repositories table."""
import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.db.session import engine
from sqlalchemy import text, inspect

insp = inspect(engine)

# Current alembic revision
with engine.connect() as conn:
    try:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        print(f"Current alembic revision: {row[0] if row else 'none'}")
    except Exception as e:
        print(f"Could not read alembic_version: {e}")

# Repositories columns
print("\n=== repositories columns ===")
for c in insp.get_columns('repositories'):
    print(f"  {c['name']:35s} nullable={c['nullable']} type={c['type']}")

# Repositories constraints
print("\n=== repositories unique constraints ===")
for uc in insp.get_unique_constraints('repositories'):
    print(f"  {uc}")

print("\n=== repositories indexes ===")
for idx in insp.get_indexes('repositories'):
    print(f"  {idx['name']:50s} cols={idx['column_names']} unique={idx['unique']}")
