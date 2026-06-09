import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/veriscope_dev")
print("Connecting to:", db_url)
engine = create_engine(db_url)
inspector = inspect(engine)
tables = inspector.get_table_names()
print("Tables in DB:")
for t in sorted(tables):
    print(f"  - {t}")
