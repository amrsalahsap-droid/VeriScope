"""
Migration to add readiness_acknowledged column to recommendation_runs table
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from app.db.session import engine

def add_readiness_acknowledged_column():
    """Add readiness_acknowledged column to recommendation_runs table"""
    
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Check if column already exists
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'recommendation_runs' 
            AND column_name = 'readiness_acknowledged'
        """))
        
        if result.fetchone():
            print("Column readiness_acknowledged already exists")
            return
        
        # Add the column
        db.execute(text("""
            ALTER TABLE recommendation_runs 
            ADD COLUMN readiness_acknowledged BOOLEAN DEFAULT FALSE
        """))
        
        db.commit()
        print("Successfully added readiness_acknowledged column to recommendation_runs table")
        
    except Exception as e:
        print(f"Error adding column: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_readiness_acknowledged_column()
