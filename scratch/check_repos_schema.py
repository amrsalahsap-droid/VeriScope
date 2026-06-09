import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    result = db.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'repositories' ORDER BY ordinal_position"
    ))
    for r in result:
        print(f"{r[0]}: {r[1]}")
finally:
    db.close()
