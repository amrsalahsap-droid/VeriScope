"""add_external_test_case_reference

Revision ID: add_external_test_case_ref
Revises: add_evidence_source
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_external_test_case_ref'
down_revision: Union[str, Sequence[str], None] = 'add_evidence_source'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'external_test_case_references',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider', sa.String(), nullable=False, index=True),
        sa.Column('external_project_id', sa.String(), nullable=False, index=True),
        sa.Column('external_test_case_id', sa.String(), nullable=False, index=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('tags', postgresql.JSONB(), nullable=True),
        sa.Column('priority', sa.String(), nullable=True),
        sa.Column('business_criticality', sa.String(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    # Create composite index for provider + external_test_case_id
    op.create_index(
        'ix_external_test_case_references_provider_external_id',
        'external_test_case_references',
        ['provider', 'external_test_case_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_external_test_case_references_provider_external_id', table_name='external_test_case_references')
    op.drop_table('external_test_case_references')
