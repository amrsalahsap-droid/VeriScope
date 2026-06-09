"""add_defect_count_to_test_coverage_links

Adds an explicit ``defect_count`` column to ``test_coverage_links``.

Background
----------
``defect_count`` tracks how many times a production defect escaped while this
specific test was NOT executed for this specific file — i.e., how many times
this (test, file) pair represented a dangerous gap in coverage that allowed a
regression to reach production.

Semantics are distinct from the existing counters:

* ``run_count``     — incremented on every ``upsert_link`` call, all sources.
* ``override_count`` — incremented only on MANUAL_OVERRIDE upserts.
* ``defect_count``  — incremented only on ESCAPED_DEFECT upserts.

This column powers ``get_high_risk_links(repository_id, min_defect_count)``,
which surfaces the highest-risk file-test gaps for conservative future
recommendation generation.

Revision ID: e4f6a8b0c1d2
Revises: d3e5f7a9b1c2
Create Date: 2026-05-29 05:32:30.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f6a8b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d3e5f7a9b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add defect_count column to test_coverage_links."""
    op.add_column(
        "test_coverage_links",
        sa.Column(
            "defect_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment=(
                "Number of times a production defect escaped while this test "
                "was NOT executed for this file (ESCAPED_DEFECT source only). "
                "Distinct from run_count and override_count."
            ),
        ),
    )


def downgrade() -> None:
    """Remove defect_count column from test_coverage_links."""
    op.drop_column("test_coverage_links", "defect_count")
