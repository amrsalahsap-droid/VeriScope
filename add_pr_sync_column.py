from app.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text('ALTER TABLE repositories ADD COLUMN IF NOT EXISTS latest_pr_synced_at TIMESTAMP'))
    conn.commit()
    print('Column added successfully')
