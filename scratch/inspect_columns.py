import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.session import get_db
from sqlalchemy import text

db_gen = get_db()
db = next(db_gen)
try:
    result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'pull_requests'"))
    columns = [row[0] for row in result.fetchall()]
    print("pull_requests columns:", columns)
finally:
    db.close()
