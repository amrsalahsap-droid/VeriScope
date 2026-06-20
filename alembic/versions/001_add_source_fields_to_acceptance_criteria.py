"""Add source_section and source_number to acceptance_criteria.

Revision ID: 001_add_source_fields
Revises: c7b5ac125e37
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_source_fields'
down_revision = 'c7b5ac125e37'
branch_labels = None
depends_on = None


def upgrade():
    # Add source_section column
    op.add_column('acceptance_criteria', sa.Column('source_section', sa.String(100), nullable=True, index=True))
    
    # Add source_number column
    op.add_column('acceptance_criteria', sa.Column('source_number', sa.Integer(), nullable=True, index=True))


def downgrade():
    # Remove source_number column
    op.drop_column('acceptance_criteria', 'source_number')
    
    # Remove source_section column
    op.drop_column('acceptance_criteria', 'source_section')
