"""Add staleness columns to recommendation_runs table in Postgres if they do not exist."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import SessionLocal

db = SessionLocal()

try:
    print("Checking and adding staleness columns to recommendation_runs table...")
    
    # Check and add input_stale column
    db.execute(text("ALTER TABLE recommendation_runs ADD COLUMN IF NOT EXISTS input_stale BOOLEAN NOT NULL DEFAULT FALSE"))
    print("Added input_stale column (or it already existed)")
    
    # Check and add stale_reason column
    db.execute(text("ALTER TABLE recommendation_runs ADD COLUMN IF NOT EXISTS stale_reason VARCHAR"))
    print("Added stale_reason column (or it already existed)")
    
    # Check and add stale_since column
    db.execute(text("ALTER TABLE recommendation_runs ADD COLUMN IF NOT EXISTS stale_since TIMESTAMP"))
    print("Added stale_since column (or it already existed)")
    
    # Check and add stale_input_types column
    db.execute(text("ALTER TABLE recommendation_runs ADD COLUMN IF NOT EXISTS stale_input_types JSONB"))
    print("Added stale_input_types column (or it already existed)")
    
    db.commit()
    print("Database transaction committed successfully.")
except Exception as e:
    db.rollback()
    print(f"Error occurred while modifying database: {e}")
finally:
    db.close()
