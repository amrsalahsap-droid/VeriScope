"""merge phase 8.1 heads

Revision ID: 9b7e3f2a2771
Revises: add_provider_cooldown, add_repository_ci_tokens, add_sync_scalability_indexes, b1c2d3e4f5g6, fix_pr_github_pr_id_unique_scope
Create Date: 2026-06-17 05:53:38.330060

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b7e3f2a2771'
down_revision: Union[str, Sequence[str], None] = ('add_provider_cooldown', 'add_repository_ci_tokens', 'add_sync_scalability_indexes', 'b1c2d3e4f5g6', 'fix_pr_github_pr_id_unique_scope')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
