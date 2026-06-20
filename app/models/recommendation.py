import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Boolean, Integer, event
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, object_session
from app.db.base import Base

class RecommendationRun(Base):
    """Immutable record of every recommendation generation."""
    __tablename__ = "recommendation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pr_id = Column(String, nullable=False, index=True)
    triggered_by = Column(String, nullable=False) # e.g. "github-webhook" or "engineer-manual"
    
    # Replaced Float coverage_confidence to avoid false precision
    evidence_quality = Column(String, nullable=False) # e.g., "HIGH", "MODERATE", "LOW", "UNKNOWN"
    
    # Replayability & Versioning Fields
    engine_version = Column(String, nullable=False) # e.g., "v1.2.0"
    recommendation_engine_version = Column(String, nullable=True) # e.g., "v1.2.0"
    ruleset_version = Column(String, nullable=False) # e.g., "rules-v1"
    degradation_policy_version = Column(String, nullable=False) # e.g., "policy-v1"
    fallback_policy_version = Column(String, nullable=True)
    dependency_expansion_strategy_version = Column(String, nullable=True)

    recommendation_reasoning_summary = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Provenance and Lineage safety (Architectural future-proofing)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True)
    pr_snapshot_id = Column(UUID(as_uuid=True), ForeignKey("pull_request_snapshots.id", ondelete="SET NULL"), nullable=True)
    pr_sync_job_id = Column(UUID(as_uuid=True), ForeignKey("pull_request_sync_jobs.id", ondelete="SET NULL"), nullable=True)
    evidence_health_status = Column(String, nullable=True)
    recommendation_readiness_state = Column(String, nullable=True)
    evidence_consistency_status = Column(String, nullable=True)
    readiness_dimensions = Column(JSONB, nullable=True)
    evidence_fingerprint = Column(String, nullable=True)
    readiness_acknowledged = Column(Boolean, nullable=False, default=False)
    readiness_acknowledged_at = Column(DateTime, nullable=True)
    readiness_acknowledged_missing_inputs = Column(JSONB, nullable=True)
    readiness_decision = Column(String, nullable=True)

    # Generation-time readiness snapshot (immutable)
    readiness_snapshot_available = Column(Boolean, nullable=False, default=False)
    readiness_score_at_generation = Column(Float, nullable=True)
    readiness_level_at_generation = Column(String, nullable=True)
    expected_confidence_at_generation = Column(String, nullable=True)
    confidence_ceiling_at_generation = Column(String, nullable=True)
    confidence_reason_at_generation = Column(String, nullable=True)
    can_generate_at_generation = Column(Boolean, nullable=True)
    available_inputs_at_generation = Column(JSONB, nullable=True)
    missing_inputs_at_generation = Column(JSONB, nullable=True)
    blocking_inputs_at_generation = Column(JSONB, nullable=True)
    confidence_limiters_at_generation = Column(JSONB, nullable=True)
    evidence_summary_at_generation = Column(JSONB, nullable=True)
    generated_from_repository_id = Column(UUID(as_uuid=True), nullable=True)
    generated_from_pull_request_id = Column(UUID(as_uuid=True), nullable=True)
    generation_context_version = Column(String, nullable=True)

    # Detailed safety, lineage, and runtime columns
    coverage_report_id = Column(UUID(as_uuid=True), ForeignKey("coverage_reports.id", ondelete="SET NULL"), nullable=True)
    dependency_state_hash = Column(String, nullable=True)
    test_history_window_start = Column(DateTime, nullable=True)
    test_history_window_end = Column(DateTime, nullable=True)
    flakiness_profile_hash = Column(String, nullable=True)

    recommendation_mode = Column(String, nullable=True) # NORMAL / WIDENED / SAFE_FALLBACK / FULL_REGRESSION
    optimization_allowed = Column(Boolean, nullable=False, default=True)
    unsafe_for_optimization = Column(Boolean, nullable=False, default=False)
    evidence_quality_reasons = Column(JSONB, nullable=True)

    skipped_reason_summary = Column(String, nullable=True)
    skipped_count = Column(Integer, nullable=False, default=0)
    top_skipped_examples = Column(JSONB, nullable=True)

    estimated_runtime_seconds = Column(Float, nullable=False, default=0.0)
    full_suite_runtime_seconds = Column(Float, nullable=True)
    runtime_confidence = Column(String, nullable=True) # HIGH / MODERATE / LOW
    runtime_source = Column(String, nullable=True) # historical_average / fallback_default / mixed

    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    input_snapshot_hash = Column(String, nullable=True)
    recommendation_snapshot_hash = Column(String, nullable=True)
    risk_level = Column(String, nullable=True)
    recommended_tests_count = Column(Integer, nullable=True)
    impact_profile = Column(JSONB, nullable=True)
    impact_graph = Column(JSONB, nullable=True)

    input_stale = Column(Boolean, nullable=False, default=False)
    stale_reason = Column(String, nullable=True)
    stale_since = Column(DateTime, nullable=True)
    stale_input_types = Column(JSONB, nullable=True)

    # Requirement Evidence Graph Snapshot (for audit/debug)
    requirement_evidence_snapshot_json = Column(JSONB, nullable=True)
    ac_traceability_snapshot_json = Column(JSONB, nullable=True)
    missing_test_mapping_snapshot_json = Column(JSONB, nullable=True)
    execution_mapping_snapshot_json = Column(JSONB, nullable=True)

    # Relationships
    repository = relationship("Repository", back_populates="recommendation_runs")
    pull_request = relationship("PullRequest")
    pr_snapshot = relationship("PullRequestSnapshot")
    pr_sync_job = relationship("PullRequestSyncJob")
    tests = relationship("RecommendationTest", back_populates="recommendation_run", cascade="all, delete-orphan")
    recommended_tests = relationship("RecommendedTest", back_populates="recommendation_run", cascade="all, delete-orphan")
    pipeline_runs = relationship("PipelineRun", back_populates="recommendation_run", cascade="all, delete-orphan")
    outcome = relationship("RecommendationOutcome", back_populates="recommendation_run", uselist=False, cascade="all, delete-orphan")
    reasoning_entries = relationship("RecommendationReasoningEntry", back_populates="recommendation_run", cascade="all, delete-orphan")
    input_snapshot = relationship("RecommendationInputSnapshot", back_populates="recommendation_run", uselist=False, cascade="all, delete-orphan")
    explanations = relationship("RecommendationExplanation", back_populates="recommendation_run", cascade="all, delete-orphan")
    suggested_scenarios = relationship("SuggestedTestScenario", back_populates="recommendation_run", cascade="all, delete-orphan")
    journey_intelligence_snapshot = relationship("JourneyIntelligenceSnapshot", back_populates="recommendation_run", uselist=False, cascade="all, delete-orphan")
    behavior_impact_run = relationship("BehaviorImpactRun", back_populates="recommendation_run", uselist=False, cascade="all, delete-orphan")
    behavior_scenario_coverages = relationship("BehaviorScenarioCoverage", back_populates="recommendation_run", cascade="all, delete-orphan")

    @property
    def pr(self):
        return self.pr_id

    @pr.setter
    def pr(self, value):
        self.pr_id = value

    @property
    def generated_tests(self):
        return self.tests

    @property
    def rationale(self):
        return self.recommendation_reasoning_summary

    @rationale.setter
    def rationale(self, value):
        self.recommendation_reasoning_summary = value

    @property
    def generated_at(self):
        return self.created_at

    @generated_at.setter
    def generated_at(self, value):
        self.created_at = value

    @property
    def coverage_confidence(self):
        return self.evidence_quality

    @coverage_confidence.setter
    def coverage_confidence(self, value):
        self.evidence_quality = value

    @property
    def correlation_id(self) -> str:
        return self.evidence_fingerprint or str(self.id)


class RecommendationTest(Base):
    """Stores exactly WHY every specific test was recommended."""
    __tablename__ = "recommendation_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_case_id = Column(String, nullable=False, index=True)
    scenario_intent_id = Column(UUID(as_uuid=True), ForeignKey("scenario_intents.id", ondelete="SET NULL"), nullable=True, index=True)
    reason_type = Column(String, nullable=False) # e.g., "historical_fragility", "dependency_expansion", "direct_file_mapping"
    reason_details = Column(JSONB, nullable=False)
    priority_score = Column(Float, nullable=False)

    # Relationships
    recommendation_run = relationship("RecommendationRun", back_populates="tests")
    scenario_intent = relationship("ScenarioIntent")


class RecommendedTest(Base):
    """Durable representation of a single recommended test inside a run."""
    __tablename__ = "recommended_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_identifier = Column(String, nullable=False, index=True)
    test_name = Column(String, nullable=False)
    class_name = Column(String, nullable=True)
    priority = Column(Float, nullable=False)
    confidence = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    source_signal = Column(String, nullable=False)
    estimated_duration_seconds = Column(Float, nullable=True)
    included = Column(Boolean, nullable=False, default=True)
    warning = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    recommendation_run = relationship("RecommendationRun", back_populates="recommended_tests")

class RecommendationOutcome(Base):
    """Tracks developer alignment, actual CI execution, and overrides."""
    __tablename__ = "recommendation_outcomes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    recommendation_snapshot_hash = Column(String, nullable=False)
    fragility_snapshot_hash = Column(String, nullable=True)
    
    # outcome_status: SHOWN, ACCEPTED, PARTIALLY_ACCEPTED, IGNORED, SUPERSEDED, UNKNOWN
    outcome_status = Column(String, nullable=False, default="SHOWN")
    
    # user_feedback: USEFUL, NOT_USEFUL, MISSING_TESTS, TOO_BROAD, TOO_NARROW, NOT_REVIEWED
    user_feedback = Column(String, nullable=True)
    feedback_comment = Column(String, nullable=True)
    ignored_reason = Column(String, nullable=True)
    
    escaped_defect_detected = Column(Boolean, nullable=False, default=False)
    rollback_occurred = Column(Boolean, nullable=False, default=False)
    production_incident_url = Column(String, nullable=True)
    
    created_by = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Legacy database columns kept for backward compatibility (non-destructive)
    executed_tests_legacy = Column("executed_tests", JSONB, nullable=True)
    manually_added_tests_legacy = Column("manually_added_tests", JSONB, nullable=True)
    manually_removed_tests_legacy = Column("manually_removed_tests", JSONB, nullable=True)
    was_followed_legacy = Column("was_followed", Boolean, nullable=True)
    override_reason_legacy = Column("override_reason", String, nullable=True)
    feedback_legacy = Column("feedback", String, nullable=True)
    escaped_defect_legacy = Column("escaped_defect", Boolean, nullable=True)
    feedback_reason = Column(String, nullable=True)
    engineer_feedback = Column(String, nullable=True)
    recommendation_presented_at = Column(DateTime, nullable=True)
    recommendation_acknowledged_at = Column(DateTime, nullable=True)
    recommendation_ignored_at = Column(DateTime, nullable=True)
    deployment_completed_at = Column(DateTime, nullable=True)
    outcome_confidence = Column(String, nullable=True)

    # Relationships
    recommendation_run = relationship("RecommendationRun", back_populates="outcome")
    test_outcomes = relationship("RecommendationTestOutcome", back_populates="outcome", cascade="all, delete-orphan")
    feedbacks = relationship("RecommendationEngineerFeedback", back_populates="outcome", cascade="all, delete-orphan")
    override_record = relationship("RecommendationOverrideRecord", back_populates="outcome", uselist=False, cascade="all, delete-orphan")
    evidences = relationship("RecommendationOutcomeEvidence", back_populates="outcome", cascade="all, delete-orphan")
    snapshot = relationship("RecommendationOutcomeSnapshot", back_populates="outcome", uselist=False, cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        # Extract and set legacy properties to prevent declarative constructor errors
        executed_tests_val = kwargs.pop("executed_tests", None)
        manually_added_tests_val = kwargs.pop("manually_added_tests", None)
        manually_removed_tests_val = kwargs.pop("manually_removed_tests", None)
        was_followed_val = kwargs.pop("was_followed", None)
        override_reason_val = kwargs.pop("override_reason", None)
        feedback_val = kwargs.pop("feedback", None)
        escaped_defect_val = kwargs.pop("escaped_defect", None)

        # Set default values for new mandatory fields if not provided
        if "outcome_status" not in kwargs:
            kwargs["outcome_status"] = "SHOWN"
        if "recommendation_snapshot_hash" not in kwargs:
            kwargs["recommendation_snapshot_hash"] = "legacy_hash"
        if "user_feedback" not in kwargs:
            kwargs["user_feedback"] = "NOT_REVIEWED"
        if "escaped_defect_detected" not in kwargs:
            kwargs["escaped_defect_detected"] = False
        if "rollback_occurred" not in kwargs:
            kwargs["rollback_occurred"] = False

        super().__init__(**kwargs)

        if executed_tests_val is not None:
            self.executed_tests = executed_tests_val
        if manually_added_tests_val is not None:
            self.manually_added_tests = manually_added_tests_val
        if manually_removed_tests_val is not None:
            self.manually_removed_tests = manually_removed_tests_val
        if was_followed_val is not None:
            self.was_followed = was_followed_val
        if override_reason_val is not None:
            self.override_reason = override_reason_val
        if feedback_val is not None:
            self.feedback = feedback_val
        if escaped_defect_val is not None:
            self.escaped_defect = escaped_defect_val

    @property
    def recommended_tests(self):
        return [t.test_case_id for t in self.recommendation_run.tests] if self.recommendation_run else []

    @property
    def executed_tests(self) -> List[str]:
        if self.test_outcomes:
            return [t.test_case.stable_identity for t in self.test_outcomes if t.actually_executed and t.test_case]
        return self.executed_tests_legacy or []

    @executed_tests.setter
    def executed_tests(self, value: List[str]):
        self.executed_tests_legacy = value

    @property
    def manually_added_tests(self) -> List[str]:
        if self.test_outcomes:
            return [t.test_case.stable_identity for t in self.test_outcomes if t.manually_added and t.test_case]
        return self.manually_added_tests_legacy or []

    @manually_added_tests.setter
    def manually_added_tests(self, value: List[str]):
        self.manually_added_tests_legacy = value

    @property
    def manually_removed_tests(self) -> List[str]:
        if self.test_outcomes:
            return [t.test_case.stable_identity for t in self.test_outcomes if t.manually_removed and t.test_case]
        return self.manually_removed_tests_legacy or []

    @manually_removed_tests.setter
    def manually_removed_tests(self, value: List[str]):
        self.manually_removed_tests_legacy = value

    @property
    def was_followed(self) -> bool:
        if self.was_followed_legacy is not None:
            return self.was_followed_legacy
        if self.outcome_status:
            return self.outcome_status in ("FOLLOWED", "PARTIALLY_FOLLOWED", "PENDING", "ACKNOWLEDGED")
        return True

    @was_followed.setter
    def was_followed(self, value: bool):
        self.was_followed_legacy = value
        if value:
            self.outcome_status = "FOLLOWED"
        else:
            self.outcome_status = "OVERRIDDEN"

    @property
    def escaped_defect(self) -> bool:
        return self.escaped_defect_detected

    @escaped_defect.setter
    def escaped_defect(self, value: bool):
        self.escaped_defect_detected = value
        self.escaped_defect_legacy = value

    @property
    def override_reason(self) -> Optional[str]:
        return self.feedback_reason or self.override_reason_legacy

    @override_reason.setter
    def override_reason(self, value: Optional[str]):
        self.feedback_reason = value
        self.override_reason_legacy = value

    @property
    def feedback_state(self):
        if self.feedback_legacy or self.engineer_feedback:
            return self.feedback_legacy or self.engineer_feedback
        if self.feedbacks:
            return self.feedbacks[-1].feedback_type.upper()
        return None

    @feedback_state.setter
    def feedback_state(self, value):
        self.feedback_legacy = value
        self.engineer_feedback = value
        if self.feedbacks:
            self.feedbacks[0].feedback_type = value
        else:
            self.feedbacks = [RecommendationEngineerFeedback(feedback_type=value)]

    @property
    def feedback(self) -> Optional[str]:
        if self.feedbacks:
            fb = self.feedbacks[-1]
            if fb.feedback_text:
                return f"{fb.feedback_type.lower()}: {fb.feedback_text}"
            return fb.feedback_type.lower()
        return self.feedback_legacy or self.engineer_feedback

    @feedback.setter
    def feedback(self, value: Optional[str]):
        self.feedback_legacy = value
        self.engineer_feedback = value
        if not value:
            self.feedbacks = []
            return

        # Parse feedback_type and feedback_text
        feedback_type = "USEFUL"
        feedback_text = None

        if ":" in value:
            parts = value.split(":", 1)
            t_part = parts[0].strip().lower()
            text_part = parts[1].strip()
            if t_part in ("useful", "not_useful", "missing_tests", "too_many_tests", "unclear_reasoning"):
                feedback_type = t_part.upper()
                feedback_text = text_part
            else:
                # Substring matching to find if a valid type is contained
                found = False
                for t in ("not_useful", "missing_tests", "too_many_tests", "unclear_reasoning", "useful"):
                    if t in t_part:
                        feedback_type = t.upper()
                        feedback_text = text_part
                        found = True
                        break
                if not found:
                    feedback_text = value
        else:
            t_part = value.strip().lower()
            if t_part in ("useful", "not_useful", "missing_tests", "too_many_tests", "unclear_reasoning"):
                feedback_type = t_part.upper()
            else:
                found = False
                for t in ("not_useful", "missing_tests", "too_many_tests", "unclear_reasoning", "useful"):
                    if t in t_part:
                        feedback_type = t.upper()
                        found = True
                        break
                if not found:
                    feedback_text = value

        if self.feedbacks:
            self.feedbacks[0].feedback_type = feedback_type
            self.feedbacks[0].feedback_text = feedback_text
        else:
            self.feedbacks = [
                RecommendationEngineerFeedback(
                    feedback_type=feedback_type,
                    feedback_text=feedback_text
                )
            ]

    @property
    def classification(self) -> str:
        """
        Dynamically compute the developer alignment classification:
        - trusted: The executed tests match the recommended tests exactly.
        - ignored: Zero recommended tests were executed (shares no common elements).
        - widened: All recommended tests were executed, plus some manually added ones.
        - narrowed: A strict non-empty subset of recommended tests were executed, with no manually added ones.
        - overridden: Any other custom mix of additions and removals.
        """
        from app.services.recommendation_ignore_detector import RecommendationIgnoreDetector

        rec_set = set(self.recommended_tests)
        exec_set = set(self.executed_tests)

        if not rec_set:
            if not exec_set:
                return "trusted"
            return "widened"

        if rec_set == exec_set:
            return "trusted"

        if RecommendationIgnoreDetector.detect(rec_set, exec_set)["status"] == "IGNORED":
            return "ignored"

        if rec_set.issubset(exec_set):
            return "widened"

        if exec_set.issubset(rec_set):
            return "narrowed"

        return "overridden"


class RecommendationTestOutcome(Base):
    """Tracks the granular outcome of a recommended or custom-run test case."""
    __tablename__ = "recommendation_test_outcomes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_outcome_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_outcomes.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    recommended_test_id = Column(UUID(as_uuid=True), ForeignKey("recommended_tests.id", ondelete="SET NULL"), nullable=True, index=True)
    test_identifier = Column(String, nullable=False, index=True)
    
    # recommendation_action: RUN_EXISTING_TEST, SKIP, OPTIONAL_MONITOR
    recommendation_action = Column(String, nullable=False, default="RUN_EXISTING_TEST")
    
    # execution_status: NOT_RUN, PASSED, FAILED, SKIPPED, UNKNOWN
    execution_status = Column(String, nullable=False, default="NOT_RUN")
    
    # engineer_decision: KEPT, REMOVED, NOT_DECIDED
    engineer_decision = Column(String, nullable=False, default="NOT_DECIDED")
    
    actual_test_result_id = Column(UUID(as_uuid=True), ForeignKey("test_results.id", ondelete="SET NULL"), nullable=True)
    actual_test_run_id = Column(UUID(as_uuid=True), ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    failure_message = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Legacy database columns kept for backward compatibility (non-destructive)
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=True, index=True)
    recommendation_reason = Column(String, nullable=True)
    recommended_by_veriscope = Column(Boolean, nullable=False, default=False)
    actually_executed = Column(Boolean, nullable=False, default=False)
    manually_added = Column(Boolean, nullable=False, default=False)
    manually_removed = Column(Boolean, nullable=False, default=False)
    execution_result = Column(String, nullable=True)
    execution_duration_seconds = Column(Float, nullable=True)
    flaky_influence = Column(Boolean, nullable=False, default=False)
    quarantine_status = Column(String, nullable=True)
    execution_presence_status = Column(String, nullable=True)

    # Relationships
    outcome = relationship("RecommendationOutcome", back_populates="test_outcomes")
    test_case = relationship("TestCase")

    def __init__(self, **kwargs):
        # Set default values for new mandatory fields if not provided
        if "recommendation_action" not in kwargs:
            kwargs["recommendation_action"] = "RUN_EXISTING_TEST"
        if "execution_status" not in kwargs:
            kwargs["execution_status"] = "NOT_RUN"
        if "engineer_decision" not in kwargs:
            kwargs["engineer_decision"] = "NOT_DECIDED"
        super().__init__(**kwargs)


class RecommendationOverrideRecord(Base):
    """
    Captures the override lineage of a recommendation run.

    One record per RecommendationOutcome. Records what was manually added or
    removed relative to what Veriscope recommended, including counts of
    critical tests removed and flaky tests manually restored.

    This model stores EVIDENCE, not judgment:
    - It does NOT classify overrides as good or bad.
    - It does NOT infer engineer intent.
    - It IS deterministic and replayable.
    """
    __tablename__ = "recommendation_override_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Unique link — one override record per outcome
    recommendation_outcome_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recommendation_outcomes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Denormalized for direct querying without joins
    recommendation_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recommendation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Detection timestamp — immutable once set
    detected_at = Column(DateTime, nullable=False)

    # Override counts
    total_manually_added = Column(Integer, nullable=False, default=0)
    total_manually_removed = Column(Integer, nullable=False, default=0)

    # override_ratio = (added + removed) / max(total_recommended, 1)
    # Range: 0.0 = no overrides, 1.0 = every recommended test was overridden
    override_ratio = Column(Float, nullable=False, default=0.0)

    # Severity-augmented counts
    # critical_tests_removed: tests removed that had evidence_priority=CRITICAL reasoning
    critical_tests_removed = Column(Integer, nullable=False, default=0)
    # flaky_tests_manually_restored: tests added that have an active FlakyTestProfile
    flaky_tests_manually_restored = Column(Integer, nullable=False, default=0)

    # Identity preservation (append-only lineage, not mutable)
    manually_added_test_ids = Column(JSONB, nullable=False, default=list)    # [UUID str, ...]
    manually_removed_test_ids = Column(JSONB, nullable=False, default=list)  # [UUID str, ...]
    critical_removed_test_ids = Column(JSONB, nullable=False, default=list)  # [UUID str, ...]
    flaky_restored_test_ids = Column(JSONB, nullable=False, default=list)    # [UUID str, ...]

    # Boolean summary flags for fast filtering
    widening_detected = Column(Boolean, nullable=False, default=False)
    narrowing_detected = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    outcome = relationship("RecommendationOutcome", back_populates="override_record")
    recommendation_run = relationship("RecommendationRun")


class RecommendationEngineerFeedback(Base):
    """Stores granular human engineer feedback on recommendation relevance."""
    __tablename__ = "recommendation_engineer_feedbacks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_outcome_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_outcomes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    feedback_type = Column(String, nullable=False) # USEFUL, NOT_USEFUL, MISSING_TESTS, TOO_MANY_TESTS, UNCLEAR_REASONING
    feedback_text = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    outcome = relationship("RecommendationOutcome", back_populates="feedbacks")


class RecommendationReasoningEntry(Base):
    """Persistent explainability evidence chain for audits and debugging."""
    __tablename__ = "recommendation_reasoning_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True)
    reason_type = Column(String, nullable=False) # e.g. historical_fragility, dependency_expansion, direct_file_mapping
    source_entity = Column(String, nullable=True) # e.g., "auth/middleware.py"
    source_reference = Column(String, nullable=True) # e.g., commit_sha or incident_id
    human_readable_reason = Column(String, nullable=False)
    confidence_level = Column(String, nullable=False) # HIGH, MEDIUM, LOW
    
    # Explainability Hierarchy
    evidence_priority = Column(String, nullable=False) # CRITICAL, IMPORTANT, SUPPORTING
    
    reasoning_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    recommendation_run = relationship("RecommendationRun", back_populates="reasoning_entries")
    test_case = relationship("TestCase")

class RecommendationInputSnapshot(Base):
    """Immutable audit snapshot of the exact inputs fed to the recommendation run."""
    __tablename__ = "recommendation_input_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Serialized snapshots
    changed_files = Column(JSONB, nullable=False)
    direct_mappings_used = Column(JSONB, nullable=False, default=list)
    heuristic_mappings_used = Column(JSONB, nullable=False, default=list)
    dependency_files_expanded = Column(JSONB, nullable=False)
    coverage_links_used = Column(JSONB, nullable=False)
    flaky_profiles_used = Column(JSONB, nullable=False)
    historical_failures_used = Column(JSONB, nullable=False)
    degradation_rules_triggered = Column(JSONB, nullable=False)
    ranking_inputs = Column(JSONB, nullable=False, default=dict)
    
    # External context snapshots
    linked_work_items = Column(JSONB, nullable=False, default=list)
    acceptance_criteria = Column(JSONB, nullable=False, default=list)
    external_test_cases = Column(JSONB, nullable=False, default=list)
    external_requirement_coverage = Column(JSONB, nullable=False, default=list)
    integration_sync_status = Column(JSONB, nullable=False, default=list)
    external_context_gaps = Column(JSONB, nullable=False, default=list)
    
    snapshot_truncated = Column(Boolean, nullable=False, default=False)
    snapshot_size_bytes = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    recommendation_run = relationship("RecommendationRun", back_populates="input_snapshot")


@event.listens_for(RecommendationOutcome, "before_insert")
def receive_before_insert(mapper, connection, target):
    # Backfill workspace_id, repository_id, pull_request_id, recommendation_snapshot_hash from RecommendationRun
    session = object_session(target)
    if session:
        run = session.query(RecommendationRun).filter(RecommendationRun.id == target.recommendation_run_id).first()
        if run:
            if not target.workspace_id:
                target.workspace_id = run.workspace_id
            if not target.repository_id:
                target.repository_id = run.repository_id
            if not target.pull_request_id:
                target.pull_request_id = run.pull_request_id
            if not target.recommendation_snapshot_hash or target.recommendation_snapshot_hash == "legacy_hash":
                target.recommendation_snapshot_hash = run.evidence_fingerprint or str(run.id)


class ScenarioIntent(Base):
    """Canonical identity for test/scenario meaning to prevent duplicate or conflicting recommendations."""
    __tablename__ = "scenario_intents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Canonical identity fields
    domain = Column(String, nullable=False, index=True)  # e.g., "authentication", "billing"
    feature = Column(String, nullable=False, index=True)  # e.g., "reset-password", "signup"
    behavior = Column(String, nullable=False, index=True)  # e.g., "expired-token-rejected", "weak-password-rejected"
    layer = Column(String, nullable=False, index=True)  # e.g., "api", "ui", "integration"
    case_type = Column(String, nullable=False, index=True)  # e.g., "positive", "negative", "edge"
    
    # Deterministic canonical key: domain.feature.behavior.layer.case_type
    canonical_key = Column(String, nullable=False, unique=True, index=True)
    
    # Human-readable fields
    title = Column(String, nullable=False)
    priority = Column(String, nullable=False)  # "MUST", "SHOULD", "OPTIONAL"
    risk_category = Column(String, nullable=False)  # "Security", "Functional", "Regression"
    
    # Related files
    related_changed_files = Column(JSONB, nullable=False, default=list)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    recommendation_run = relationship("RecommendationRun")


class RecommendationOutcomeEvidence(Base):
    """
    Append-only evidence audit record for recommendation outcomes.
    Stores and preserves snapshots of sources (TestRuns, TestResults, Incidents, Rollbacks)
    along with hashes and metadata to ensure deterministic replayability.
    """
    __tablename__ = "recommendation_outcome_evidences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_outcome_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_outcomes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # "TEST_RUN", "INCIDENT", "ROLLBACK", "FEEDBACK", "OVERRIDE"
    evidence_type = Column(String, nullable=False)
    
    # Unique reference ID/hash of the source entity
    source_reference_id = Column(String, nullable=False)
    
    # JSON snapshot payload of the source evidence at the time it was captured
    evidence_payload = Column(JSONB, nullable=False)
    
    # Fingerprint to detect and prevent historical drift
    evidence_fingerprint = Column(String, nullable=False)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    outcome = relationship("RecommendationOutcome", back_populates="evidences")


@event.listens_for(RecommendationReasoningEntry, "before_update")
def prevent_reasoning_entry_mutation(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError("Forensic Immutability Violation: RecommendationReasoningEntry is append-only and cannot be mutated.")


@event.listens_for(RecommendationReasoningEntry, "before_delete")
def prevent_reasoning_entry_deletion(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError("Forensic Immutability Violation: RecommendationReasoningEntry is append-only and cannot be deleted.")


@event.listens_for(RecommendationOutcomeEvidence, "before_insert")
def receive_evidence_before_insert(mapper, connection, target):
    # Auto-compute fingerprint if not set
    if not target.evidence_fingerprint:
        import hashlib
        import json
        # Stable JSON serialization of evidence_payload
        payload_str = json.dumps(target.evidence_payload, sort_keys=True)
        raw_fingerprint = f"{target.evidence_type}:{target.source_reference_id}:{payload_str}"
        target.evidence_fingerprint = hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()


@event.listens_for(RecommendationOutcomeEvidence, "before_update")
def prevent_evidence_mutation(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError("Forensic Immutability Violation: RecommendationOutcomeEvidence is append-only and cannot be mutated.")


@event.listens_for(RecommendationOutcomeEvidence, "before_delete")
def prevent_evidence_deletion(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError("Forensic Immutability Violation: RecommendationOutcomeEvidence is append-only and cannot be deleted.")


class RecommendationOutcomeSnapshot(Base):
    """
    Immutable, replayable snapshot of a recommendation outcome's state.
    Generated after final outcome classification to freeze and verify the lineage.
    """
    __tablename__ = "recommendation_outcome_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_outcome_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_outcomes.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    outcome_snapshot_hash = Column(String, nullable=False, unique=True, index=True)
    recommendation_snapshot_hash = Column(String, nullable=False)
    fragility_snapshot_hash = Column(String, nullable=True)
    executed_test_snapshot_hash = Column(String, nullable=False)
    incident_snapshot_hash = Column(String, nullable=True)
    rollback_snapshot_hash = Column(String, nullable=True)
    classification_snapshot_hash = Column(String, nullable=False)
    
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    snapshot_version = Column(Integer, nullable=False, default=1)

    # Relationships
    outcome = relationship("RecommendationOutcome", back_populates="snapshot")


@event.listens_for(RecommendationOutcomeSnapshot, "before_update")
def prevent_snapshot_mutation(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError("Forensic Immutability Violation: RecommendationOutcomeSnapshot is immutable and cannot be mutated.")


@event.listens_for(RecommendationOutcomeSnapshot, "before_delete")
def prevent_snapshot_deletion(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError("Forensic Immutability Violation: RecommendationOutcomeSnapshot is immutable and cannot be deleted.")


class RecommendationExplanation(Base):
    """Stores granular plain-English explainability tracing data for recommended tests."""
    __tablename__ = "recommendation_explanations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_id = Column(String, nullable=False, index=True) # stable_identity
    triggered_files = Column(JSONB, nullable=False, default=list) # triggered_files[]
    domains = Column(JSONB, nullable=False, default=list) # domains[]
    testing_types = Column(JSONB, nullable=False, default=list) # testing_types[]
    signals = Column(JSONB, nullable=False, default=list) # signals[]
    score_breakdown = Column(JSONB, nullable=False, default=dict) # score_breakdown[]
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    recommendation_run = relationship("RecommendationRun", back_populates="explanations")


class SuggestedTestScenario(Base):
    """Represents a concrete functional test scenario recommended when automated coverage is weak or missing."""
    __tablename__ = "suggested_test_scenarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_intent_id = Column(UUID(as_uuid=True), ForeignKey("scenario_intents.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String, nullable=False)
    testing_type = Column(String, nullable=False)
    impacted_area = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    preconditions = Column(JSONB, nullable=False) # List of preconditions (strings)
    test_data = Column(JSONB, nullable=False) # JSON dictionary of test data
    steps = Column(JSONB, nullable=False) # List of steps (strings)
    expected_result = Column(String, nullable=False)
    automation_candidate = Column(Boolean, nullable=False, default=True)
    related_changed_files = Column(JSONB, nullable=False) # List of files (strings)
    reason = Column(String, nullable=False)
    confidence = Column(String, nullable=False)
    source_signal = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    recommendation_run = relationship("RecommendationRun", back_populates="suggested_scenarios")
    scenario_intent = relationship("ScenarioIntent")


class SuggestedScenarioOutcome(Base):
    """Tracks what happened to suggested missing/manual scenarios."""
    __tablename__ = "suggested_scenario_outcomes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_outcome_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_outcomes.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    suggested_scenario_id = Column(UUID(as_uuid=True), ForeignKey("suggested_test_scenarios.id", ondelete="SET NULL"), nullable=True, index=True)
    scenario_intent_key = Column(String, nullable=False, index=True)
    
    # engineer_decision: ACCEPTED, DISMISSED, MARKED_IMPORTANT, NOT_DECIDED
    engineer_decision = Column(String, nullable=False, default="NOT_DECIDED")
    
    # execution_status: NOT_EXECUTED, PASSED, FAILED, BLOCKED, UNKNOWN
    execution_status = Column(String, nullable=False, default="NOT_EXECUTED")
    
    converted_to_test = Column(Boolean, nullable=False, default=False)
    linked_test_identifier = Column(String, nullable=True)
    comment = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    recommendation_outcome = relationship("RecommendationOutcome")
    recommendation_run = relationship("RecommendationRun")
    suggested_scenario = relationship("SuggestedTestScenario")

    def __init__(self, **kwargs):
        # Set default values for new mandatory fields if not provided
        if "engineer_decision" not in kwargs:
            kwargs["engineer_decision"] = "NOT_DECIDED"
        if "execution_status" not in kwargs:
            kwargs["execution_status"] = "NOT_EXECUTED"
        if "converted_to_test" not in kwargs:
            kwargs["converted_to_test"] = False
        super().__init__(**kwargs)


class RecommendationOverride(Base):
    """Captures individual test/scenario override events for learning."""
    __tablename__ = "recommendation_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_outcome_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_outcomes.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # override_type: TEST_ADDED, TEST_REMOVED, SCENARIO_ADDED, SCENARIO_REMOVED, PRIORITY_CHANGED
    override_type = Column(String, nullable=False)
    
    test_identifier = Column(String, nullable=True, index=True)
    scenario_intent_key = Column(String, nullable=True, index=True)
    reason = Column(String, nullable=True)
    
    # source: MANUAL_UI, CI_DIFF, API, IMPORTED
    source = Column(String, nullable=False, default="MANUAL_UI")
    
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    recommendation_outcome = relationship("RecommendationOutcome")
    recommendation_run = relationship("RecommendationRun")

    def __init__(self, **kwargs):
        # Set default values for new mandatory fields if not provided
        if "source" not in kwargs:
            kwargs["source"] = "MANUAL_UI"
        super().__init__(**kwargs)


