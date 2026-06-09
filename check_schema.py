import os
import sys
from sqlalchemy import create_engine, text

os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/veriscope'
engine = create_engine(os.environ['DATABASE_URL'])

with engine.connect() as conn:
    result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'work_item_behavior_mappings' ORDER BY ordinal_position"))
    columns = [row[0] for row in result]
    print("Columns in work_item_behavior_mappings:")
    for col in columns:
        print(f"  - {col}")
