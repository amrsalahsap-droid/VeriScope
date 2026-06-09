"""add_risk_assessments_table

Revision ID: a3c7e9f12b04
Revises: fedd9b1c0ace
Create Date: 2026-05-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a3c7e9f12b04'
down_revision: Union[str, Sequence[str], None] = 'fedd9b1c0ace'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create risk_assessments table."""
    op.create_table(
        'risk_assessments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'repository_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('repositories.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'pull_request_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('pull_requests.id', ondelete='CASCADE'),
            nullable=True,
        ),
        sa.Column('impact_profile', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('risk_level', sa.String(), nullable=False),
        sa.Column('risk_areas', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('risk_reasons', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('engine_version', sa.String(), nullable=False, server_default='v1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_risk_assessments_repository_id', 'risk_assessments', ['repository_id'])
    op.create_index('ix_risk_assessments_pull_request_id', 'risk_assessments', ['pull_request_id'])


def downgrade() -> None:
    """Drop risk_assessments table."""
    op.drop_index('ix_risk_assessments_pull_request_id', table_name='risk_assessments')
    op.drop_index('ix_risk_assessments_repository_id', table_name='risk_assessments')
    op.drop_table('risk_assessments')
