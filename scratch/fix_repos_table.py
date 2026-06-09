"""Fix repositories table: make organization_id nullable."""
import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.db.session import engine
from sqlalchemy import text, inspect

insp = inspect(engine)

print("=== repositories columns ===")
cols = insp.get_columns('repositories')
for c in cols:
    print(f"  {c['name']} nullable={c['nullable']} default={c.get('default')}")

print("\n=== Applying fix ===")
with engine.begin() as conn:
    # Make organization_id nullable
    try:
        conn.execute(text("ALTER TABLE repositories ALTER COLUMN organization_id DROP NOT NULL"))
        print("  organization_id is now nullable")
    except Exception as e:
        print(f"  organization_id fix: {e}")

    # Also fix FK if it references organizations
    fks = insp.get_foreign_keys('repositories')
    for fk in fks:
        if fk['referred_table'] == 'organizations':
            print(f"  Found FK to organizations: {fk['name']} on columns {fk['constrained_columns']}")
            try:
                conn.execute(text(f"ALTER TABLE repositories DROP CONSTRAINT IF EXISTS {fk['name']}"))
                print(f"  Dropped FK {fk['name']}")
            except Exception as e:
                print(f"  Could not drop FK {fk['name']}: {e}")

print("\nDone.")
