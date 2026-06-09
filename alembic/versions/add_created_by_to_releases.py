"""add created_by to releases

Revision ID: add_created_by_to_releases
Revises: 
Create Date: 2026-06-04 21:51:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_created_by_to_releases'
down_revision = 'add_external_context_to_snapshot'
branch_labels = None
depends_on = None


def upgrade():
    # Add created_by column to releases table
    op.add_column('releases', sa.Column('created_by', sa.String(), nullable=True))


def downgrade():
    # Remove created_by column from releases table
    op.drop_column('releases', 'created_by')
