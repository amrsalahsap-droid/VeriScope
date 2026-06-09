"""Check database schema for github_installations table."""
from app.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Check if table exists
    result = conn.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'github_installations' ORDER BY ordinal_position"
    ))
    cols = result.fetchall()
    if cols:
        print("github_installations columns:")
        for col in cols:
            print(f"  {col[0]}: {col[1]}")
    else:
        print("github_installations table does NOT exist")
    
    print()
    
    # Check all tables
    result = conn.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    ))
    tables = result.fetchall()
    print("All tables:")
    for t in tables:
        print(f"  {t[0]}")
