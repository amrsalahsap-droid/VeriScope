import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import engine
from sqlalchemy import text

def migrate():
    print("Connecting to PostgreSQL database and adding impact_graph column...")
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("ALTER TABLE recommendation_runs ADD COLUMN IF NOT EXISTS impact_graph JSONB"))
            trans.commit()
            print("Column impact_graph successfully added!")
            
            # Verify columns
            result = conn.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'recommendation_runs' AND column_name = 'impact_graph'"
            ))
            row = result.fetchone()
            if row:
                print(f"Verified: {row[0]} of type {row[1]}")
            else:
                print("Verification failed: column not found.")
        except Exception as e:
            trans.rollback()
            print(f"Error during migration: {e}")
            raise

if __name__ == "__main__":
    migrate()
