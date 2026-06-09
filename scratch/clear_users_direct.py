"""
Direct SQL execution script to delete all users.
Uses raw SQL execution without requiring full app imports.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from sqlalchemy import create_engine, text
    from app.config import settings
    
    def clear_all_users():
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Count before
                user_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
                member_count = conn.execute(text("SELECT COUNT(*) FROM workspace_members")).scalar()
                workspace_count = conn.execute(text("SELECT COUNT(*) FROM workspaces WHERE created_by_user_id IS NOT NULL")).scalar()
                
                print(f"Before deletion:")
                print(f"  Users: {user_count}")
                print(f"  Workspace members: {member_count}")
                print(f"  Workspaces with creator: {workspace_count}")
                
                if user_count == 0:
                    print("No users to delete")
                    trans.rollback()
                    return
                
                # Delete workspace members
                print("Deleting workspace members...")
                conn.execute(text("DELETE FROM workspace_members"))
                
                # Update workspaces
                print("Updating workspaces...")
                conn.execute(text("UPDATE workspaces SET created_by_user_id = NULL WHERE created_by_user_id IS NOT NULL"))
                
                # Delete users
                print("Deleting users...")
                conn.execute(text("DELETE FROM users"))
                
                # Count after
                user_count_after = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
                member_count_after = conn.execute(text("SELECT COUNT(*) FROM workspace_members")).scalar()
                workspace_count_after = conn.execute(text("SELECT COUNT(*) FROM workspaces WHERE created_by_user_id IS NOT NULL")).scalar()
                
                print(f"After deletion:")
                print(f"  Users: {user_count_after}")
                print(f"  Workspace members: {member_count_after}")
                print(f"  Workspaces with creator: {workspace_count_after}")
                
                trans.commit()
                print("✓ All users deleted successfully")
                
            except Exception as e:
                trans.rollback()
                print(f"✗ Error: {e}")
                raise
    
    if __name__ == "__main__":
        clear_all_users()
        
except ImportError as e:
    print(f"Import error: {e}")
    print("\nPlease install dependencies first:")
    print("pip install sqlalchemy pydantic-settings")
