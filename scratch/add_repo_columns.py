import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("Altering repositories table...")
    db.execute(text("ALTER TABLE repositories ADD COLUMN IF NOT EXISTS source VARCHAR NOT NULL DEFAULT 'GITHUB_APP'"))
    db.execute(text("ALTER TABLE repositories ADD COLUMN IF NOT EXISTS connection_status VARCHAR NOT NULL DEFAULT 'CONNECTED'"))
    db.commit()
    print("Columns added successfully!")
finally:
    db.close()
