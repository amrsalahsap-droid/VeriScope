"""add_intelligence_run_score_partial_columns

Revision ID: 88c5779ff440
Revises: add_input2_req_pkg_snapshots
Create Date: 2026-07-08 00:59:19.160444

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '88c5779ff440'
down_revision: Union[str, Sequence[str], None] = 'add_input2_req_pkg_snapshots'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('repository_intelligence_runs', sa.Column('score', sa.Float(), nullable=True))
    op.add_column('repository_intelligence_runs', sa.Column('max_score', sa.Float(), nullable=True))
    op.add_column('repository_intelligence_runs', sa.Column('partial_errors_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('repository_intelligence_runs', sa.Column('completed_steps_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('repository_intelligence_runs', sa.Column('failed_steps_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('repository_intelligence_runs', 'failed_steps_json')
    op.drop_column('repository_intelligence_runs', 'completed_steps_json')
    op.drop_column('repository_intelligence_runs', 'partial_errors_json')
    op.drop_column('repository_intelligence_runs', 'max_score')
    op.drop_column('repository_intelligence_runs', 'score')
