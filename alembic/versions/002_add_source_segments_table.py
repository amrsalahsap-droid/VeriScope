"""Add source_segments table.

Revision ID: 002_add_source_segments
Revises: 001_add_source_fields
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import enum

# revision identifiers, used by Alembic.
revision = '002_add_source_segments'
down_revision = '001_add_source_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Create source_segments table using String for disposition (avoid enum issues)
    op.create_table(
        'source_segments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id'), nullable=True, index=True),
        sa.Column('pull_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pull_requests.id'), nullable=True, index=True),
        sa.Column('raw_artifact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('raw_artifacts.id'), nullable=True, index=True),
        sa.Column('source_section', sa.String(100), nullable=True),
        sa.Column('source_index', sa.Integer(), nullable=True),
        sa.Column('source_number', sa.Integer(), nullable=True, index=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('normalized_text', sa.Text(), nullable=True),
        sa.Column('disposition', sa.String(50), nullable=False, index=True),
        sa.Column('source_hash', sa.String(64), nullable=True, index=True),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    # Drop source_segments table
    op.drop_table('source_segments')
    
    # Drop SegmentDisposition enum
    postgresql.ENUM(name='segmentdisposition').drop(op.get_bind())
