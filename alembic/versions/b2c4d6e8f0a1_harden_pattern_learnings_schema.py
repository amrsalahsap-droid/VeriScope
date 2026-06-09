"""harden_pattern_learnings_schema

Revision ID: b2c4d6e8f0a1
Revises: a9f3c1d2e8b5
Create Date: 2026-05-30

Hardens the pattern_learnings schema per Requirement 7.7:
- Converts `source` column from plain String to a PostgreSQL native enum type
- Converts `strength` and `confidence` from Float to NUMERIC
- Adds CHECK constraints ensuring strength and confidence are in [0.0, 1.0]
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c4d6e8f0a1'
down_revision = 'a9f3c1d2e8b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create the PostgreSQL native enum type for source
    op.execute(
        "CREATE TYPE pattern_learning_source AS ENUM "
        "('ESCAPED_DEFECT', 'MANUAL_OVERRIDE', 'FOLLOWED', 'HEURISTIC')"
    )

    # 2. Alter source column to use the new enum type
    op.execute(
        "ALTER TABLE pattern_learnings "
        "ALTER COLUMN source TYPE pattern_learning_source "
        "USING source::pattern_learning_source"
    )

    # 3. Alter strength column from Float to NUMERIC
    op.execute(
        "ALTER TABLE pattern_learnings "
        "ALTER COLUMN strength TYPE NUMERIC"
    )

    # 4. Alter confidence column from Float to NUMERIC
    op.execute(
        "ALTER TABLE pattern_learnings "
        "ALTER COLUMN confidence TYPE NUMERIC"
    )

    # 5. Add CHECK constraint for strength
    op.create_check_constraint(
        "chk_pattern_learning_strength",
        "pattern_learnings",
        "strength >= 0.0 AND strength <= 1.0",
    )

    # 6. Add CHECK constraint for confidence
    op.create_check_constraint(
        "chk_pattern_learning_confidence",
        "pattern_learnings",
        "confidence >= 0.0 AND confidence <= 1.0",
    )


def downgrade() -> None:
    # 1. Drop CHECK constraint for confidence
    op.drop_constraint(
        "chk_pattern_learning_confidence",
        "pattern_learnings",
        type_="check",
    )

    # 2. Drop CHECK constraint for strength
    op.drop_constraint(
        "chk_pattern_learning_strength",
        "pattern_learnings",
        type_="check",
    )

    # 3. Alter confidence back to Float
    op.execute(
        "ALTER TABLE pattern_learnings "
        "ALTER COLUMN confidence TYPE FLOAT"
    )

    # 4. Alter strength back to Float
    op.execute(
        "ALTER TABLE pattern_learnings "
        "ALTER COLUMN strength TYPE FLOAT"
    )

    # 5. Alter source back to String (VARCHAR)
    op.execute(
        "ALTER TABLE pattern_learnings "
        "ALTER COLUMN source TYPE VARCHAR "
        "USING source::VARCHAR"
    )

    # 6. Drop the enum type
    op.execute("DROP TYPE pattern_learning_source")
