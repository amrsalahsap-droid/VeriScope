"""add_override_count_to_test_coverage_links

Adds an explicit ``override_count`` column to ``test_coverage_links``.

Background
----------
``ManualOverrideLearner`` previously derived "how many times an engineer
manually added this test" from ``run_count``.  That conflated two distinct
counters:

* ``run_count`` — incremented on every ``upsert_link`` call, regardless of
  discovery source (STATIC, DYNAMIC, HEURISTIC, MANUAL_OVERRIDE, …).
* ``override_count`` — should only count deliberate engineer additions
  (``source=MANUAL_OVERRIDE``).

This migration adds the dedicated ``override_count`` column so the semantics
are explicit and the promotion query ("tests added ≥ N times should surface
as future recommendations") can be expressed unambiguously.

Revision ID: c2d4f6a8b0e1
Revises: a9f1e2b3c4d5
Create Date: 2026-05-29 05:23:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2d4f6a8b0e1"
down_revision: Union[str, Sequence[str], None] = "a9f1e2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add override_count column to test_coverage_links."""
    op.add_column(
        "test_coverage_links",
        sa.Column(
            "override_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment=(
                "Number of times an engineer manually added this test "
                "(source=MANUAL_OVERRIDE upserts only). "
                "Distinct from run_count which counts all sources."
            ),
        ),
    )


def downgrade() -> None:
    """Remove override_count column from test_coverage_links."""
    op.drop_column("test_coverage_links", "override_count")
