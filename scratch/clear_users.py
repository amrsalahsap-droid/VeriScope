"""
Script to delete all users from the database.
This will cascade delete workspace memberships and set workspace.created_by_user_id to NULL.
"""

from app.db.session import SessionLocal
from app.models.user import User, WorkspaceMember, Workspace

def clear_all_users():
    db = SessionLocal()
    try:
        # Count users before deletion
        user_count = db.query(User).count()
        print(f"Found {user_count} users in database")
        
        if user_count == 0:
            print("No users to delete")
            return
        
        # Delete all workspace members (will cascade due to ondelete=CASCADE)
        member_count = db.query(WorkspaceMember).count()
        print(f"Deleting {member_count} workspace members...")
        db.query(WorkspaceMember).delete()
        
        # Set workspace.created_by_user_id to NULL
        workspace_count = db.query(Workspace).filter(Workspace.created_by_user_id.isnot(None)).count()
        print(f"Updating {workspace_count} workspaces to remove creator reference...")
        db.query(Workspace).filter(Workspace.created_by_user_id.isnot(None)).update(
            {"created_by_user_id": None}
        )
        
        # Delete all users
        print(f"Deleting {user_count} users...")
        db.query(User).delete()
        
        db.commit()
        print("✓ All users deleted successfully")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error deleting users: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_users()
