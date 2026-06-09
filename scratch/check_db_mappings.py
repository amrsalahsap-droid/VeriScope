import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    for table_name in ['work_item_behavior_mappings', 'external_test_scenario_mappings']:
        print(f"\nColumns in {table_name}:")
        res = db.execute(text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'"))
        for row in res:
            print(f"  {row[0]}: {row[1]}")
finally:
    db.close()

