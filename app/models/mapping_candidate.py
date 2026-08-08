"""Mapping Candidate evidence model for storing candidate AC -> Test mapping proposals and audit trails."""
from sqlalchemy import Column, String, Text, DateTime, Float, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base


class MappingCandidate(Base):
    """
    Represents an evidence-backed candidate proposal for mapping an Acceptance Criterion to a TestCase.
    Acts as audit evidence before elevation to trusted/confirmed coverage.
    """

    __tablename__ = "mapping_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=True, index=True)
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    acceptance_criterion_id = Column(UUID(as_uuid=True), ForeignKey("acceptance_criteria.id", ondelete="CASCADE"), nullable=True, index=True)
    requirement_package_id = Column(UUID(as_uuid=True), ForeignKey("requirement_packages.id", ondelete="SET NULL"), nullable=True, index=True)
    primary_status = Column(String(50), nullable=True, index=True)
    coverage_type = Column(String(20), nullable=False, default="none")
    execution_status = Column(String(20), nullable=False, default="unknown")

    declared_ac_ref = Column(String(100), nullable=True)
    declared_ac_text_snapshot = Column(Text, nullable=True)
    declared_ac_id = Column(UUID(as_uuid=True), ForeignKey("acceptance_criteria.id", ondelete="SET NULL"), nullable=True)
    declared_ac_display_ref = Column(String(100), nullable=True)
    semantic_ac_display_ref = Column(String(100), nullable=True)
    semantic_ac_text_snapshot = Column(Text, nullable=True)
    semantic_best_match_ac_id = Column(UUID(as_uuid=True), ForeignKey("acceptance_criteria.id"), nullable=True)
    semantic_best_match_score = Column(Float, nullable=False, default=0.0)

    candidate_source = Column(String(100), nullable=False)
    confidence_score = Column(Float, nullable=False, default=0.0)
    confidence_label = Column(String(50), nullable=True)

    # Allowed review_status values:
    # VERIFIED | SUGGESTED_STRONG | SUGGESTED_WEAK | CONFLICTED | AMBIGUOUS | UNRESOLVED | USER_CONFIRMED | USER_REJECTED
    review_status = Column(String(50), nullable=False, default="UNRESOLVED", index=True)

    conflict_detected = Column(Boolean, nullable=False, default=False)
    conflict_type = Column(String(100), nullable=True)
    conflict_reason = Column(Text, nullable=True)

    evidence_json = Column(JSON, nullable=False, default=dict)
    ai_decision_json = Column(JSON, nullable=True)
    safety_gate_json = Column(JSON, nullable=True)
    created_by = Column(String(20), nullable=False, default="system")
    user_decision = Column(String(30), nullable=False, default="none")
    user_decision_at = Column(DateTime, nullable=True)
    user_decision_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    audit_comment = Column(Text, nullable=True)
    partial_support_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    repository = relationship("Repository")
    pull_request = relationship("PullRequest")
    test_case = relationship("TestCase")
    acceptance_criterion = relationship("AcceptanceCriterion", foreign_keys=[acceptance_criterion_id])
    declared_ac = relationship("AcceptanceCriterion", foreign_keys=[declared_ac_id])
    semantic_best_match_ac = relationship("AcceptanceCriterion", foreign_keys=[semantic_best_match_ac_id])


    @property
    def can_count_as_confirmed_coverage(self) -> bool:
        """
        Returns True only if this candidate's review_status represents
        user-confirmed coverage per current product policy.

        Product policy (v1):
          - USER_CONFIRMED => True  (human explicitly approved)
          - VERIFIED => True  (equivalent to user-confirmed in legacy flows)
          - VERISCOPE_KEY_VERIFIED => False by default (configurable in future)
          - EVIDENCE_VERIFIED_ALIGNED => False (strong auto-evidence, not user-confirmed)
          - METADATA_CONFLICT_SEMANTIC_MATCH => False (conflict requires user resolution)
          - PARTIAL_SUPPORT => False (partial evidence, not full confirmed coverage)
          - SUGGESTED_STRONG | SUGGESTED_WEAK => False (awaiting user review)
          - NO_CANDIDATE => False (no test support)
          - USER_REJECTED | REJECTED => False (explicitly rejected)
          - Any other state => False (safe default)
        """
        return self.review_status in ("USER_CONFIRMED", "VERIFIED")

    def __repr__(self):
        return (
            f"<MappingCandidate(id={self.id}, tc={self.test_case_id}, ac={self.acceptance_criterion_id}, "
            f"ref={self.declared_ac_ref}, status={self.review_status}, conflict={self.conflict_detected})>"
        )
