"""Fix github_installations table schema to match the SQLAlchemy model."""
from app.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    trans = conn.begin()
    try:
        # 1. Rename organization_id -> workspace_id
        print("Renaming organization_id -> workspace_id...")
        conn.execute(text("ALTER TABLE github_installations RENAME COLUMN organization_id TO workspace_id"))
        
        # 2. Rename account_login -> github_account_login
        print("Renaming account_login -> github_account_login...")
        conn.execute(text("ALTER TABLE github_installations RENAME COLUMN account_login TO github_account_login"))
        
        # 3. Add missing columns
        print("Adding missing columns...")
        
        # installation_id (BigInteger, same as github_installation_id)
        conn.execute(text("ALTER TABLE github_installations ADD COLUMN IF NOT EXISTS installation_id BIGINT"))
        # Backfill from github_installation_id
        conn.execute(text("UPDATE github_installations SET installation_id = github_installation_id WHERE installation_id IS NULL"))
        
        # github_account_id
        conn.execute(text("ALTER TABLE github_installations ADD COLUMN IF NOT EXISTS github_account_id BIGINT"))
        
        # github_account_type
        conn.execute(text("ALTER TABLE github_installations ADD COLUMN IF NOT EXISTS github_account_type VARCHAR DEFAULT 'User'"))
        
        # permissions (JSONB)
        conn.execute(text("ALTER TABLE github_installations ADD COLUMN IF NOT EXISTS permissions JSONB"))
        
        # repository_selection
        conn.execute(text("ALTER TABLE github_installations ADD COLUMN IF NOT EXISTS repository_selection VARCHAR DEFAULT 'all'"))
        
        # installed_at
        conn.execute(text("ALTER TABLE github_installations ADD COLUMN IF NOT EXISTS installed_at TIMESTAMP DEFAULT NOW()"))
        
        # suspended_at
        conn.execute(text("ALTER TABLE github_installations ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP"))
        
        # updated_at
        conn.execute(text("ALTER TABLE github_installations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()"))
        
        # 4. Add foreign key constraint if missing
        print("Adding workspace_id foreign key...")
        conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE github_installations 
                ADD CONSTRAINT fk_github_installations_workspace_id 
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
        """))
        
        # 5. Add unique constraint if missing
        print("Adding unique constraints...")
        conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE github_installations 
                ADD CONSTRAINT uq_workspace_installation UNIQUE (workspace_id, installation_id);
            EXCEPTION
                WHEN duplicate_table THEN NULL;
            END $$;
        """))
        
        trans.commit()
        print("Schema migration complete!")
        
        # Verify
        result = conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'github_installations' ORDER BY ordinal_position"
        ))
        print("\nUpdated columns:")
        for col in result.fetchall():
            print(f"  {col[0]}: {col[1]}")
            
    except Exception as e:
        trans.rollback()
        print(f"Error: {e}")
        raise
