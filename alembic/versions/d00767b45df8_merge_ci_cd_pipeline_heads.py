"""merge ci/cd pipeline heads

Revision ID: d00767b45df8
Revises: add_ci_fail_on_partial, add_ci_token_audit_events, add_pipeline_execution_jobs
Create Date: 2026-06-18 04:31:03.485144

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd00767b45df8'
down_revision: Union[str, Sequence[str], None] = ('add_ci_fail_on_partial', 'add_ci_token_audit_events', 'add_pipeline_execution_jobs')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
