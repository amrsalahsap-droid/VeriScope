"""
Migration script to add missing columns matched_terms and reason
to mapping tables in the active PostgreSQL database.
"""
import os
import sys
from sqlalchemy import text

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import engine

def run_migration():
    print("Connecting to database...")
    with engine.connect() as conn:
        print("Adding missing columns to work_item_behavior_mappings...")
        conn.execute(text("ALTER TABLE work_item_behavior_mappings ADD COLUMN IF NOT EXISTS matched_terms JSONB;"))
        conn.execute(text("ALTER TABLE work_item_behavior_mappings ADD COLUMN IF NOT EXISTS reason TEXT;"))
        
        print("Adding missing columns to external_test_scenario_mappings...")
        conn.execute(text("ALTER TABLE external_test_scenario_mappings ADD COLUMN IF NOT EXISTS matched_terms JSONB;"))
        conn.execute(text("ALTER TABLE external_test_scenario_mappings ADD COLUMN IF NOT EXISTS reason TEXT;"))
        
        # Commit transaction (in case of non-autocommit connection)
        conn.commit()
        print("Migration complete!")

if __name__ == "__main__":
    run_migration()
