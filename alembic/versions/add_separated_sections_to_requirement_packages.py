"""Add separated sections to requirement_packages table

Revision ID: add_separated_sections
Revises: add_pull_request_id
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_separated_sections'
down_revision = 'add_pull_request_id'
branch_labels = None
depends_on = None


def upgrade():
    # Add separated business requirement sections columns
    op.add_column('requirement_packages', sa.Column('business_change_summary', sa.Text(), nullable=True))
    op.add_column('requirement_packages', sa.Column('affected_journeys', postgresql.JSON(), nullable=True))
    op.add_column('requirement_packages', sa.Column('risk_notes', sa.Text(), nullable=True))
    op.add_column('requirement_packages', sa.Column('invalid_test_data_examples', postgresql.JSON(), nullable=True))
    op.add_column('requirement_packages', sa.Column('valid_test_data_examples', postgresql.JSON(), nullable=True))
    op.add_column('requirement_packages', sa.Column('security_notes', postgresql.JSON(), nullable=True))
    op.add_column('requirement_packages', sa.Column('integration_notes', sa.Text(), nullable=True))
    op.add_column('requirement_packages', sa.Column('out_of_scope_notes', sa.Text(), nullable=True))


def downgrade():
    # Remove separated business requirement sections columns
    op.drop_column('requirement_packages', 'out_of_scope_notes')
    op.drop_column('requirement_packages', 'integration_notes')
    op.drop_column('requirement_packages', 'security_notes')
    op.drop_column('requirement_packages', 'valid_test_data_examples')
    op.drop_column('requirement_packages', 'invalid_test_data_examples')
    op.drop_column('requirement_packages', 'risk_notes')
    op.drop_column('requirement_packages', 'affected_journeys')
    op.drop_column('requirement_packages', 'business_change_summary')
