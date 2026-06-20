"""
Add ci_cd_governance_review_snapshots table

Revision ID: f1g2h3i4j5k6
Revises: e0f1g2h3i4j5
Create Date: 2026-06-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f1g2h3i4j5k6'
down_revision = 'e0f1g2h3i4j5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ci_cd_governance_review_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('total_repositories', sa.Integer(), nullable=False, default=0),
        sa.Column('compliance_score', sa.Integer(), nullable=False, default=0),
        sa.Column('critical_count', sa.Integer(), nullable=False, default=0),
        sa.Column('high_risk_count', sa.Integer(), nullable=False, default=0),
        sa.Column('drifted_count', sa.Integer(), nullable=False, default=0),
        sa.Column('compliant_count', sa.Integer(), nullable=False, default=0),
        sa.Column('snapshot_json', postgresql.JSON(), nullable=True),
    )


def downgrade():
    op.drop_table('ci_cd_governance_review_snapshots')
