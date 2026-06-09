"""Alter recommendation_test_outcomes.test_case_id to be nullable."""
from app.db.session import engine
from sqlalchemy import text

sql = text("""
ALTER TABLE recommendation_test_outcomes 
ALTER COLUMN test_case_id DROP NOT NULL;
""")

with engine.connect() as conn:
    conn.execute(sql)
    conn.commit()
    print("test_case_id column is now nullable in recommendation_test_outcomes")
