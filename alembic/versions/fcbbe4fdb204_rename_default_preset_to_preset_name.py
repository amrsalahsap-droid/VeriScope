"""rename default_preset to preset_name

Revision ID: fcbbe4fdb204
Revises: 8d36600b36af
Create Date: 2026-06-19 04:28:06.439030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fcbbe4fdb204'
down_revision: Union[str, Sequence[str], None] = '8d36600b36af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('workspace_ci_cd_policy_defaults')]
    if 'default_preset' in columns and 'preset_name' not in columns:
        op.alter_column('workspace_ci_cd_policy_defaults', 'default_preset', new_column_name='preset_name')


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('workspace_ci_cd_policy_defaults')]
    if 'preset_name' in columns and 'default_preset' not in columns:
        op.alter_column('workspace_ci_cd_policy_defaults', 'preset_name', new_column_name='default_preset')
