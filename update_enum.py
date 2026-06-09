import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'app'))
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import create_engine, text

database_url = os.getenv('DATABASE_URL')
engine = create_engine(database_url)

with engine.connect() as conn:
    # Drop and recreate the enum with all values
    conn.execute(text('DROP TYPE IF EXISTS scope_item_type_enum CASCADE;'))
    conn.commit()
    conn.execute(text("CREATE TYPE scope_item_type_enum AS ENUM ('AUTOMATED_TEST', 'MANUAL_TEST', 'SUGGESTED_SCENARIO', 'COVERAGE_GAP');"))
    conn.commit()
    print('Updated scope_item_type_enum')
