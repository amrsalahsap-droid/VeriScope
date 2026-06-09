"""
Migration to add readiness snapshot columns to recommendation_runs table
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from app.db.session import engine

def add_readiness_snapshot_columns():
    """Add readiness snapshot columns to recommendation_runs table"""

    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    columns_to_add = [
        ("readiness_snapshot_available", "BOOLEAN DEFAULT FALSE"),
        ("readiness_score_at_generation", "FLOAT"),
        ("readiness_level_at_generation", "VARCHAR(50)"),
        ("expected_confidence_at_generation", "VARCHAR(50)"),
        ("confidence_ceiling_at_generation", "VARCHAR(50)"),
        ("confidence_reason_at_generation", "TEXT"),
        ("can_generate_at_generation", "BOOLEAN"),
        ("available_inputs_at_generation", "JSONB"),
        ("missing_inputs_at_generation", "JSONB"),
        ("blocking_inputs_at_generation", "JSONB"),
        ("confidence_limiters_at_generation", "JSONB"),
        ("evidence_summary_at_generation", "JSONB"),
        ("generated_from_repository_id", "UUID"),
        ("generated_from_pull_request_id", "UUID"),
        ("generation_context_version", "VARCHAR(50)"),
    ]

    try:
        for column_name, column_type in columns_to_add:
            # Check if column already exists
            result = db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'recommendation_runs'
                AND column_name = :column_name
            """), {"column_name": column_name})

            if result.fetchone():
                print(f"Column {column_name} already exists")
                continue

            # Add the column
            db.execute(text(f"""
                ALTER TABLE recommendation_runs
                ADD COLUMN {column_name} {column_type}
            """))
            print(f"Successfully added column {column_name}")

        db.commit()
        print("Successfully added all readiness snapshot columns to recommendation_runs table")

    except Exception as e:
        print(f"Error adding columns: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_readiness_snapshot_columns()
