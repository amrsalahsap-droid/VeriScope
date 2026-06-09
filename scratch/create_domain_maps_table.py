import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import engine
from sqlalchemy import text

def migrate():
    print("Connecting to PostgreSQL database and creating domain_maps table...")
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Create domain_maps table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS domain_maps (
                    id UUID PRIMARY KEY,
                    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
                    domain VARCHAR NOT NULL,
                    files JSONB NOT NULL DEFAULT '[]'::jsonb,
                    modules JSONB NOT NULL DEFAULT '[]'::jsonb,
                    owners JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            # Create indexes
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_domain_maps_repository_id ON domain_maps (repository_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_domain_maps_domain ON domain_maps (domain)"))
            
            trans.commit()
            print("Table domain_maps successfully created!")
            
            # Verify columns
            result = conn.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'domain_maps'"
            ))
            rows = result.fetchall()
            print("Verified columns in domain_maps table:")
            for row in rows:
                print(f" - {row[0]}: {row[1]}")
        except Exception as e:
            trans.rollback()
            print(f"Error during migration: {e}")
            raise

if __name__ == "__main__":
    migrate()
