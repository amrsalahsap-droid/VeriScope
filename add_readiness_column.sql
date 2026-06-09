-- Add readiness_acknowledged column to recommendation_runs table
-- This fixes the database error: column recommendation_runs.readiness_acknowledged does not exist

DO $$
BEGIN
    -- Check if the column already exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'recommendation_runs' 
        AND column_name = 'readiness_acknowledged'
    ) THEN
        -- Add the column
        ALTER TABLE recommendation_runs 
        ADD COLUMN readiness_acknowledged BOOLEAN DEFAULT FALSE;
        
        RAISE NOTICE 'Added readiness_acknowledged column to recommendation_runs table';
    ELSE
        RAISE NOTICE 'readiness_acknowledged column already exists';
    END IF;
END $$;
