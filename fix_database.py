"""
Direct database fix to add readiness_acknowledged column
"""

import psycopg2
import os
from urllib.parse import urlparse

def get_database_connection():
    """Get database connection from DATABASE_URL"""
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/veriscope')
    
    # Parse the database URL
    parsed = urlparse(database_url)
    
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path[1:],  # Remove leading slash
        user=parsed.username,
        password=parsed.password
    )

def add_readiness_acknowledged_column():
    """Add the missing readiness_acknowledged column"""
    
    conn = get_database_connection()
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'recommendation_runs' 
            AND column_name = 'readiness_acknowledged'
        """)
        
        if cursor.fetchone():
            print("✅ readiness_acknowledged column already exists")
            return
        
        # Add the column
        cursor.execute("""
            ALTER TABLE recommendation_runs 
            ADD COLUMN readiness_acknowledged BOOLEAN DEFAULT FALSE
        """)
        
        conn.commit()
        print("✅ Successfully added readiness_acknowledged column to recommendation_runs table")
        
    except Exception as e:
        print(f"❌ Error adding column: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_readiness_acknowledged_column()
