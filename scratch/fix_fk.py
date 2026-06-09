"""Fix the FK constraint on github_installations to point to workspaces instead of organizations."""
import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.db.session import engine
from sqlalchemy import text, inspect

insp = inspect(engine)

# Check existing FKs on github_installations
print("=== FKs on github_installations ===")
fks = insp.get_foreign_keys('github_installations')
for fk in fks:
    print(f"  name={fk['name']} constrained={fk['constrained_columns']} referred_table={fk['referred_table']}")

# Check if organizations table exists
print("\n=== Tables in DB ===")
tables = insp.get_table_names()
for t in sorted(tables):
    print(f"  {t}")

# Check if real user's workspace exists in organizations
print("\n=== Checking organizations table ===")
with engine.connect() as conn:
    try:
        rows = conn.execute(text("SELECT id FROM organizations LIMIT 5")).fetchall()
        print(f"  Organizations: {[str(r[0]) for r in rows]}")
    except Exception as e:
        print(f"  organizations table error: {e}")

# Fix: drop old FK and add new one pointing to workspaces
print("\n=== Applying FK fix ===")
with engine.begin() as conn:
    try:
        # Drop old FK
        conn.execute(text("ALTER TABLE github_installations DROP CONSTRAINT IF EXISTS github_installations_organization_id_fkey"))
        conn.execute(text("ALTER TABLE github_installations DROP CONSTRAINT IF EXISTS github_installations_workspace_id_fkey"))
        print("  Dropped old FK constraints")
        
        # Add correct FK to workspaces
        conn.execute(text("""
            ALTER TABLE github_installations 
            ADD CONSTRAINT github_installations_workspace_id_fkey 
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        """))
        print("  Added new FK: github_installations.workspace_id -> workspaces.id")
    except Exception as e:
        print(f"  Error fixing FK: {e}")

print("\nDone.")
