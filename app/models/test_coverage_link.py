"""
app/models/test_coverage_link.py
=================================

ORM model for the TestCoverageLink knowledge-graph edge.

One row represents a directed relationship between a test identifier and a
source-file path within a single repository.  The row is the foundation for
future coverage learning — no ML/heuristic population is implemented here.

Rules enforced by the schema
-----------------------------
* One row per (repository_id, test_identifier, file_path) — enforced by
  UniqueConstraint at the DB level.
* Counters (run_count, success_count, failure_count) must never go negative.
  Application code is responsible for this invariant; the model does not add
  database-level CHECK constraints so that the migration stays portable.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class TestCoverageLink(Base):
    """Directed knowledge-graph edge: test_identifier → file_path.

    Attributes
    ----------
    id:
        Surrogate UUID primary key.
    workspace_id:
        Workspace that owns this repository (CASCADE-deleted with workspace).
    repository_id:
        Repository this edge belongs to (CASCADE-deleted with repository).
    test_identifier:
        Stable string identity of the test, e.g. ``"suite::test_name"`` or a
        canonical hash.  Matches the ``stable_identity`` convention used in
        ``TestCase`` but is stored as a plain string so the link can be created
        independently of a ``TestCase`` row.
    file_path:
        Normalised source-file path within the repository, e.g.
        ``"app/services/foo.py"``.
    link_strength:
        Numerical weight in [0, 1] expressing how strongly the test covers this
        file.  ``None`` until computed by a coverage-learning job.
    confidence:
        Confidence in the ``link_strength`` value, in [0, 1].
        ``None`` until a learning job has run.
    source:
        How this link was discovered.  Expected values (not enforced as an
        enum here to keep the migration simple):
        ``STATIC``, ``DYNAMIC``, ``HEURISTIC``, ``MANUAL``.
    run_count:
        Total number of test executions observed since this link was created
        (incremented on every ``upsert_link`` call regardless of source).
    success_count:
        Number of passing executions.
    failure_count:
        Number of failing executions.
    override_count:
        Number of times an engineer **manually added** this test beyond
        Veriscope's recommendation (``source=MANUAL_OVERRIDE`` upserts only).
        Distinct from ``run_count``.  Used to promote frequently-added tests
        into future recommendations.
    defect_count:
        Number of times a production defect **escaped** while this test was
        NOT executed for this file (``source=ESCAPED_DEFECT`` upserts only).
        Distinct from both ``run_count`` and ``override_count``.  Used to
        identify the highest-risk file-test gaps for conservative future
        recommendations.
    first_seen_at:
        Timestamp of the first execution that produced this link.
    last_seen_at:
        Timestamp of the most recent execution.
    created_at:
        Row-creation timestamp (UTC).
    updated_at:
        Last-modification timestamp (UTC), updated by the application layer.
    """

    __tablename__ = "test_coverage_links"

    # ------------------------------------------------------------------ #
    #  Primary key                                                         #
    # ------------------------------------------------------------------ #
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ------------------------------------------------------------------ #
    #  Scoping                                                             #
    # ------------------------------------------------------------------ #
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ------------------------------------------------------------------ #
    #  Knowledge-graph edge identity                                       #
    # ------------------------------------------------------------------ #
    test_identifier = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

    # ------------------------------------------------------------------ #
    #  Edge quality signals                                                #
    # ------------------------------------------------------------------ #
    link_strength = Column(Float, nullable=True)   # 0.0 – 1.0
    confidence    = Column(Float, nullable=True)   # 0.0 – 1.0
    source        = Column(String, nullable=True)  # STATIC | DYNAMIC | HEURISTIC | MANUAL

    # ------------------------------------------------------------------ #
    #  Execution telemetry counters                                        #
    # ------------------------------------------------------------------ #
    run_count      = Column(Integer, nullable=False, default=0, server_default="0")
    success_count  = Column(Integer, nullable=False, default=0, server_default="0")
    failure_count  = Column(Integer, nullable=False, default=0, server_default="0")
    # Tracks how many times an engineer manually added this test (MANUAL_OVERRIDE source only).
    # Separate from run_count so promotion queries are unambiguous.
    override_count = Column(Integer, nullable=False, default=0, server_default="0")
    # Tracks how many times a production defect escaped while this test was NOT run (ESCAPED_DEFECT only).
    # Separate from override_count — both semantically and for independent querying.
    defect_count   = Column(Integer, nullable=False, default=0, server_default="0")

    # ------------------------------------------------------------------ #
    #  Temporal tracking                                                   #
    # ------------------------------------------------------------------ #
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at  = Column(DateTime, nullable=True)

    # ------------------------------------------------------------------ #
    #  Row lifecycle                                                       #
    # ------------------------------------------------------------------ #
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # ------------------------------------------------------------------ #
    #  Relationships                                                       #
    # ------------------------------------------------------------------ #
    workspace  = relationship("Workspace")
    repository = relationship("Repository", back_populates="test_coverage_links")

    # ------------------------------------------------------------------ #
    #  Constraints and indexes                                             #
    # ------------------------------------------------------------------ #
    __table_args__ = (
        # Uniqueness: one edge per (repository, test, file)
        UniqueConstraint(
            "repository_id",
            "test_identifier",
            "file_path",
            name="uq_test_coverage_links_repo_test_file",
        ),
        # Composite lookup by file path within a repo
        Index("ix_test_coverage_links_repo_file", "repository_id", "file_path"),
        # Composite lookup by test identifier within a repo
        Index("ix_test_coverage_links_repo_test", "repository_id", "test_identifier"),
        # Full composite covering the unique edge identity (supports range scans)
        Index(
            "ix_test_coverage_links_repo_file_test",
            "repository_id",
            "file_path",
            "test_identifier",
        ),
    )

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:
        return (
            f"<TestCoverageLink id={self.id} "
            f"repo={self.repository_id} "
            f"test={self.test_identifier!r} "
            f"file={self.file_path!r}>"
        )
