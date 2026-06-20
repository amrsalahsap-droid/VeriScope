"""add ci_fail_on_partial to repository

Revision ID: add_ci_fail_on_partial
Revises: add_pipeline_execution_jobs
Create Date: 2026-06-17 22:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_ci_fail_on_partial'
down_revision = '9b7e3f2a2771'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('repositories', sa.Column('ci_fail_on_partial', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    op.drop_column('repositories', 'ci_fail_on_partial')
