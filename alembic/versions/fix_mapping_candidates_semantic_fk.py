"""fix_mapping_candidates_semantic_fk

Revision ID: fix_mapping_candidates_semantic_fk
Revises: update_github_installation
Create Date: 2026-07-25 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm1n2o3p4q5r6'
down_revision: Union[str, Sequence[str], None] = 'update_github_installation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the existing foreign key constraint on semantic_best_match_ac_id
    op.drop_constraint('mapping_candidates_semantic_best_match_ac_id_fkey', 'mapping_candidates', type_='foreignkey')
    
    # Re-add the constraint without ON DELETE CASCADE
    op.create_foreign_key(
        'mapping_candidates_semantic_best_match_ac_id_fkey',
        'mapping_candidates',
        'acceptance_criteria',
        ['semantic_best_match_ac_id'],
        ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the constraint without CASCADE
    op.drop_constraint('mapping_candidates_semantic_best_match_ac_id_fkey', 'mapping_candidates', type_='foreignkey')
    
    # Re-add the constraint with ON DELETE CASCADE
    op.create_foreign_key(
        'mapping_candidates_semantic_best_match_ac_id_fkey',
        'mapping_candidates',
        'acceptance_criteria',
        ['semantic_best_match_ac_id'],
        ['id'],
        ondelete='CASCADE'
    )
