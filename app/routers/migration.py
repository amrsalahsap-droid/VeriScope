"""
Temporary migration router to fix database schema issues
"""

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from app.db.session import engine

router = APIRouter(prefix="/migration", tags=["migration"])

@router.post("/add-readiness-acknowledged")
async def add_readiness_acknowledged_column():
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
            return {"message": "readiness_acknowledged column already exists", "status": "already_exists"}
        
        # Add the column
        db.execute(text("""
            ALTER TABLE recommendation_runs 
            ADD COLUMN readiness_acknowledged BOOLEAN DEFAULT FALSE
        """))
        
        db.commit()
        return {"message": "Successfully added readiness_acknowledged column", "status": "success"}
        
    except Exception as e:
        db.rollback()
        return {"error": str(e), "status": "error"}
    finally:
        db.close()
