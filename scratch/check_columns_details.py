import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app'))

from sqlalchemy import text
from app.db.session import engine

with engine.connect() as conn:
    # 1. Print all tables in public schema
    res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
    print("Tables in public schema:")
    for row in res:
        print(f"  - {row[0]}")
        
    # 2. Print columns of work_item_behavior_mappings
    print("\nColumns in work_item_behavior_mappings:")
    try:
        res = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'work_item_behavior_mappings'"))
        for row in res:
            print(f"  - {row[0]}: {row[1]}")
    except Exception as e:
        print(f"  Error getting columns: {e}")

    # 3. Print alembic versions
    print("\nAlembic version table:")
    try:
        res = conn.execute(text("SELECT * FROM alembic_version"))
        for row in res:
            print(f"  - Version: {row[0]}")
    except Exception as e:
        print(f"  Error getting alembic version: {e}")
