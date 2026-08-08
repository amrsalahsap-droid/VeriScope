"""add semantic classification fields

Revision ID: 9e8d7c6b5a4a
Revises: 56c568c7ba28
Create Date: 2026-07-11 04:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9e8d7c6b5a4a'
down_revision: Union[str, Sequence[str], None] = '56c568c7ba28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Columns for test_cases table
    op.add_column('test_cases', sa.Column('product_area', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('business_flow', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('behavior_key', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('scenario_intent', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('scenario_type', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('validation_target', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('risk_dimensions', sa.JSON(), nullable=True))
    op.add_column('test_cases', sa.Column('regression_role', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('must_run_condition', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('semantic_classification_json', sa.JSON(), nullable=True))
    op.add_column('test_cases', sa.Column('classification_source', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('classification_confidence', sa.Float(), nullable=True))
    op.add_column('test_cases', sa.Column('classification_review_status', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('classified_at', sa.DateTime(), nullable=True))
    op.add_column('test_cases', sa.Column('classified_by', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('semantic_classifier_version', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('behavior_mapping_status', sa.String(), nullable=True))

    # Columns for recommended_tests table
    # Standard SQLite schema updates do not support if_not_exists natively easily in migrations, so we just add columns.
    op.add_column('recommended_tests', sa.Column('candidate_status', sa.String(), nullable=True))
    op.add_column('recommended_tests', sa.Column('active_action', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('recommended_tests', 'active_action')
    op.drop_column('recommended_tests', 'candidate_status')

    op.drop_column('test_cases', 'behavior_mapping_status')
    op.drop_column('test_cases', 'semantic_classifier_version')
    op.drop_column('test_cases', 'classified_by')
    op.drop_column('test_cases', 'classified_at')
    op.drop_column('test_cases', 'classification_review_status')
    op.drop_column('test_cases', 'classification_confidence')
    op.drop_column('test_cases', 'classification_source')
    op.drop_column('test_cases', 'semantic_classification_json')
    op.drop_column('test_cases', 'must_run_condition')
    op.drop_column('test_cases', 'regression_role')
    op.drop_column('test_cases', 'risk_dimensions')
    op.drop_column('test_cases', 'validation_target')
    op.drop_column('test_cases', 'scenario_type')
    op.drop_column('test_cases', 'scenario_intent')
    op.drop_column('test_cases', 'behavior_key')
    op.drop_column('test_cases', 'business_flow')
    op.drop_column('test_cases', 'product_area')
