-- SQL script to delete all users from the database
-- This will cascade delete workspace memberships and set workspace.created_by_user_id to NULL

-- Start a transaction
BEGIN;

-- Display count before deletion
SELECT COUNT(*) as user_count FROM users;
SELECT COUNT(*) as member_count FROM workspace_members;
SELECT COUNT(*) as workspace_with_creator FROM workspaces WHERE created_by_user_id IS NOT NULL;

-- Delete all workspace members (will cascade due to ondelete=CASCADE)
DELETE FROM workspace_members;

-- Set workspace.created_by_user_id to NULL
UPDATE workspaces SET created_by_user_id = NULL WHERE created_by_user_id IS NOT NULL;

-- Delete all users
DELETE FROM users;

-- Display count after deletion
SELECT COUNT(*) as user_count_after FROM users;
SELECT COUNT(*) as member_count_after FROM workspace_members;
SELECT COUNT(*) as workspace_with_creator_after FROM workspaces WHERE created_by_user_id IS NOT NULL;

-- Commit the transaction
COMMIT;
