"""Add governance access review tables

Revision ID: add_governance_access_review_tables
Revises: 8d36600b36af
Create Date: 2026-06-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_governance_access_review_tables'
down_revision = '8d36600b36af'
branch_labels = None
depends_on = None


def upgrade():
    # Create governance_access_reviews table
    op.create_table(
        'governance_access_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('review_name', sa.String(100), nullable=False),
        sa.Column('review_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='DRAFT'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('summary_json', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    )
    
    # Create governance_access_review_items table
    op.create_table(
        'governance_access_review_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('review_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('scope_type', sa.String(50), nullable=False),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('assignment_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('risk_level', sa.String(50), nullable=False),
        sa.Column('finding_type', sa.String(100), nullable=False),
        sa.Column('finding_message', sa.String(500), nullable=False),
        sa.Column('recommendation', sa.String(500), nullable=False),
        sa.Column('review_status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('decision_reason', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['review_id'], ['governance_access_reviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assignment_id'], ['governance_role_assignments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    )


def downgrade():
    op.drop_table('governance_access_review_items')
    op.drop_table('governance_access_reviews')
