"""add_defect_learning_events

Creates the ``defect_learning_events`` table — an append-only audit ledger
written by ``EscapedDefectLearner`` each time a ``RecommendationOutcome``
flagged with ``escaped_defect_detected`` or ``rollback_occurred`` is processed.

Each row captures:
  - what the PR changed (``changed_files``)
  - what Veriscope recommended vs. what CI ran (``recommended_tests``, ``executed_tests``)
  - the gap that let the defect through (``missed_tests``)
  - how many knowledge-graph edges were created or strengthened
  - a snapshot of the peak ``defect_count`` at the time of the pass

The table is intentionally append-only: application-level SQLAlchemy event
listeners raise ``RuntimeError`` on any UPDATE or DELETE attempt.

Revision ID: d3e5f7a9b1c2
Revises: c2d4f6a8b0e1
Create Date: 2026-05-29 05:32:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d3e5f7a9b1c2"
down_revision: Union[str, Sequence[str], None] = "c2d4f6a8b0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the defect_learning_events table."""
    op.create_table(
        "defect_learning_events",

        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),

        # Scoping / foreign keys
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recommendation_outcome_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recommendation_outcomes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pull_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pull_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # Trigger classification
        sa.Column("trigger_type", sa.String(), nullable=False),

        # Evidence snapshot (JSONB lists)
        sa.Column("changed_files",     postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("recommended_tests", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("executed_tests",    postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("missed_tests",      postgresql.JSONB(), nullable=False, server_default="[]"),

        # Learning counters
        sa.Column("links_created",      sa.Integer(), nullable=False, server_default="0"),
        sa.Column("links_strengthened", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("defect_count_at_time", sa.Integer(), nullable=False, server_default="0"),

        # Non-fatal error ledger
        sa.Column("errors", postgresql.JSONB(), nullable=False, server_default="[]"),

        # Temporal
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # Indexes — support "show me all learning events for this repo sorted by time"
    # and "show all events triggered by this outcome"
    op.create_index(
        "ix_defect_learning_events_repository_id",
        "defect_learning_events",
        ["repository_id"],
    )
    op.create_index(
        "ix_defect_learning_events_outcome_id",
        "defect_learning_events",
        ["recommendation_outcome_id"],
    )
    op.create_index(
        "ix_defect_learning_events_pull_request_id",
        "defect_learning_events",
        ["pull_request_id"],
    )
    op.create_index(
        "ix_defect_learning_events_repo_created_at",
        "defect_learning_events",
        ["repository_id", "created_at"],
    )


def downgrade() -> None:
    """Drop the defect_learning_events table and all associated indexes."""
    op.drop_index("ix_defect_learning_events_repo_created_at",  table_name="defect_learning_events")
    op.drop_index("ix_defect_learning_events_pull_request_id",  table_name="defect_learning_events")
    op.drop_index("ix_defect_learning_events_outcome_id",        table_name="defect_learning_events")
    op.drop_index("ix_defect_learning_events_repository_id",     table_name="defect_learning_events")
    op.drop_table("defect_learning_events")
