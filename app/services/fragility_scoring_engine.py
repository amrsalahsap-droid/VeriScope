import math
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from app.models.fragility_pattern import FragilityPattern

logger = logging.getLogger(__name__)

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: RepositoryCalibrationProfile
# ====================================================================
# Future versions should accept per-repository weight overrides so that
# high-velocity monorepos can tune the churn/frequency balance, and
# incident-sensitive domains can raise W_INCIDENT beyond the default.
#
# The weight dataclass is already structured to accept override injection
# with no schema changes required.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: Non-linear incident multipliers
# ====================================================================
# A future tier could apply non-linear escalation when a pattern is
# linked to multiple P0 incidents within a short window:
#   incident_boost = log(1 + linked_p0_count) * INCIDENT_BOOST_FACTOR
# This would sit on top of the base incident_score component without
# altering the additive weighted formula.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================


# ---------------------------------------------------------------------------
# Scoring formula version — bump whenever weights or saturation constants
# change so that persisted score_components remain replayable.
# ---------------------------------------------------------------------------
SCORING_FORMULA_VERSION = "weighted.v2"

# ---------------------------------------------------------------------------
# Risk band boundaries  (Rule 5)
# 0–24   LOW
# 25–49  MODERATE
# 50–74  HIGH
# 75–100 CRITICAL
# ---------------------------------------------------------------------------
RISK_BANDS = [
    (75.0, "CRITICAL"),
    (50.0, "HIGH"),
    (25.0, "MODERATE"),
    (0.0,  "LOW"),
]


@dataclass(frozen=True)
class FragilityScoringWeights:
    """
    Immutable weight vector for the FragilityScoringEngine.

    All weights must sum to 1.0.  The default vector satisfies this
    constraint and matches the spec's priority ordering:
      - incident_linkage and rollback_linkage receive the highest
        individual weights (high impact).
      - failure_frequency and recency receive moderate weight.
      - module_churn, test_instability, and dependency_proximity
        receive supporting weights.

    The stale_evidence_decay multiplier is applied as a post-hoc
    reduction rather than a weighted component — it scales the
    composite score down rather than participating in the additive sum.
    """
    # ---- Additive components (must sum to 1.0) ----
    w_incident_linkage:     float = 0.25   # HIGH IMPACT — confirmed prod regression
    w_rollback_linkage:     float = 0.20   # HIGH IMPACT — deployed rollback
    w_failure_frequency:    float = 0.15   # MODERATE — repeated co-failure signal
    w_recency:              float = 0.15   # MODERATE — time-decay freshness
    w_module_churn:         float = 0.10   # SUPPORTING — line-change volume
    w_test_instability:     float = 0.08   # SUPPORTING — flaky test density
    w_dependency_proximity: float = 0.07   # SUPPORTING — dependency hop distance

    # ---- Stale evidence decay multiplier (Rule 4) ----
    # Applied after the additive sum:  score *= (1 - decay_factor)
    # The engine reads `score_components["stale_decay_factor"]` if present;
    # otherwise it computes it from `days_since_last_seen`.
    stale_decay_rate_per_30_days: float = 0.10   # 10 % score reduction per 30 days

    # ---- Saturation constants ----
    # Each component saturates at this number of events / units
    incident_saturation:       float = 3.0   # 3 incidents → 100 % incident score
    rollback_saturation:       float = 3.0   # 3 rollbacks → 100 % rollback score
    frequency_saturation:      float = 10.0  # 10 failures → 100 % frequency score
    churn_log_reference:       float = 1000.0 # log-normalised churn reference
    instability_saturation:    float = 1.0   # instability_score is already 0–1

    def __post_init__(self) -> None:
        total = (
            self.w_incident_linkage
            + self.w_rollback_linkage
            + self.w_failure_frequency
            + self.w_recency
            + self.w_module_churn
            + self.w_test_instability
            + self.w_dependency_proximity
        )
        if not math.isclose(total, 1.0, rel_tol=1e-6):
            raise ValueError(
                f"FragilityScoringWeights: additive weights must sum to 1.0, "
                f"got {total:.6f}."
            )


@dataclass
class FragilityScoringInputs:
    """
    Structured input bundle for a single ``calculate_fragility_score`` call.

    All fields are optional so callers can pass only the signals they have
    evidence for; absent signals default to zero (no contribution).

    Fields
    ------
    failure_frequency : int
        Number of qualifying failure events (test runs, co-failures, …)
        involving this pattern's files/modules.
    days_since_last_seen : int
        Calendar days since the most recent supporting evidence event.
        Used to compute the recency score and the stale-evidence decay.
    module_churn : int
        Total line additions + deletions across all changed files that
        are part of this pattern over the evidence window.
    test_instability_score : float  [0.0 – 1.0]
        Aggregate instability score for tests linked to this pattern.
        Derived from FlakyTestProfile.instability_score values.
    incident_count : int
        Number of distinct confirmed production incidents linked to this
        pattern (escaped_defect=True outcomes).
    dependency_proximity_weight : float  [0.0 – 1.0]
        Proximity weight of the most relevant dependency hop.
        1.0 = direct dependency (distance 0), 0.7 = 1 hop, 0.4 = 2 hops.
        0.0 = no dependency evidence.
    rollback_count : int
        Number of distinct rollback events linked to this pattern
        (rollback_occurred=True outcomes).
    evidence_count : int
        Total raw evidence links attached to this pattern (used for
        confidence-level derivation and as a cross-check on frequency).
    evidence_window_days : int
        Width of the evidence window in calendar days (e.g. 60).
        Used in the final explanation string only.
    """
    failure_frequency:           int   = 0
    days_since_last_seen:        int   = 0
    module_churn:                int   = 0
    test_instability_score:      float = 0.0
    incident_count:              int   = 0
    dependency_proximity_weight: float = 0.0
    rollback_count:              int   = 0
    evidence_count:              int   = 0
    evidence_window_days:        int   = 60


@dataclass
class FragilityScoringResult:
    """
    Immutable output of a single ``calculate_fragility_score`` call.

    Carries every intermediate value needed to reconstruct the final
    score from first principles — satisfying the explainability
    acceptance criterion.
    """
    # ---- Final outputs ----
    fragility_score:     float   # Normalised 0–100
    risk_level:          str     # LOW | MODERATE | HIGH | CRITICAL
    confidence_level:    str     # LOW | MODERATE | HIGH

    # ---- Per-component sub-scores (each 0–100 before weighting) ----
    incident_score:              float
    rollback_score:              float
    frequency_score:             float
    recency_score:               float
    churn_score:                 float
    instability_score:           float
    dependency_proximity_score:  float

    # ---- Decay & meta ----
    stale_decay_factor:      float   # 0.0 = no decay; 1.0 = fully decayed
    raw_composite_score:     float   # Score before decay reduction
    scoring_formula_version: str     = field(default=SCORING_FORMULA_VERSION)

    def to_score_components(self) -> Dict[str, Any]:
        """
        Serialises the result to the JSONB ``score_components`` dictionary
        stored on FragilityPattern for full explainability (Rule 6).
        """
        return {
            # Per-component sub-scores
            "incident":              round(self.incident_score,             2),
            "rollback":              round(self.rollback_score,             2),
            "frequency":             round(self.frequency_score,            2),
            "recency":               round(self.recency_score,              2),
            "churn":                 round(self.churn_score,                2),
            "instability":           round(self.instability_score,          2),
            "dependency_proximity":  round(self.dependency_proximity_score, 2),
            # Decay meta
            "stale_decay_factor":    round(self.stale_decay_factor,         4),
            "raw_composite_score":   round(self.raw_composite_score,        2),
            # Audit trail
            "scoring_formula_version": self.scoring_formula_version,
        }


# ---------------------------------------------------------------------------
# Default shared weight vector
# ---------------------------------------------------------------------------
_DEFAULT_WEIGHTS = FragilityScoringWeights()


class FragilityScoringEngine:
    """
    Calculates a **deterministic**, evidence-backed fragility score for a
    FragilityPattern using a fixed weighted formula.

    Design principles
    -----------------
    * **No ML** — every score is a pure mathematical function of the
      input signals.  The same inputs always produce the same output
      (acceptance criterion: determinism).
    * **Fully explainable** — ``score_components`` captures every
      intermediate sub-score so the final number can be reconstructed
      from first principles (acceptance criterion: explainability).
    * **Normalised 0–100** — the weighted composite is already in
      [0, 100]; the stale-evidence decay multiplier can reduce it but
      never below 0 (acceptance criterion: normalisation).
    * **High-impact signals first** — incident_linkage (0.25) and
      rollback_linkage (0.20) dominate the formula as specified.

    Scoring formula
    ---------------
    Each component ``c_i`` is independently normalised to [0, 100]:

        raw_composite = Σ  w_i × c_i          (weighted additive sum)
        stale_factor  = 0.10^(days/30)         (10 % decay per 30 days)
        final_score   = raw_composite × (1 − stale_factor)
                        clipped to [0, 100]

    Risk band mapping (Rule 5)
    --------------------------
        75–100  CRITICAL
        50–74   HIGH
        25–49   MODERATE
        0–24    LOW

    Usage
    -----
    Direct scoring from structured inputs::

        engine = FragilityScoringEngine()
        inputs = FragilityScoringInputs(
            failure_frequency=5,
            days_since_last_seen=10,
            module_churn=300,
            test_instability_score=0.15,
            incident_count=2,
            dependency_proximity_weight=0.7,
            rollback_count=1,
            evidence_count=8,
        )
        result = engine.calculate_fragility_score_from_inputs(inputs)
        pattern.fragility_score   = result.fragility_score
        pattern.risk_level        = result.risk_level
        pattern.score_components  = result.to_score_components()

    Rescoring an existing pattern from its stored components::

        result = engine.calculate_fragility_score(pattern)
        pattern.fragility_score   = result.fragility_score
        pattern.risk_level        = result.risk_level
        pattern.score_components  = result.to_score_components()
    """

    def __init__(
        self,
        weights: Optional[FragilityScoringWeights] = None,
    ) -> None:
        self.weights: FragilityScoringWeights = weights or _DEFAULT_WEIGHTS

    # ================================================================== #
    # Primary public API — takes a FragilityPattern ORM object            #
    # ================================================================== #

    def calculate_fragility_score(
        self,
        pattern: FragilityPattern,
    ) -> FragilityScoringResult:
        """
        Derives scoring inputs from the stored ``score_components`` and
        ``replayable_evidence_snapshot`` JSONB fields of the given
        ``FragilityPattern`` and returns a fully deterministic
        ``FragilityScoringResult``.

        This is the canonical entry point when re-scoring existing patterns
        from stored evidence (e.g. during recalculation jobs, stale-decay
        passes, or audit replays).

        The method reads:
          - ``score_components["incident"]``          → incident_count proxy
          - ``score_components["rollback"]``          → rollback_count proxy
          - ``score_components["frequency"]``         → failure_frequency proxy
          - ``score_components["recency"]``           → days_since derived
          - ``score_components["churn"]``             → module_churn proxy
          - ``score_components["instability"]``       → test_instability_score proxy
          - ``score_components["dependency_proximity"]`` → proximity weight proxy
          - ``replayable_evidence_snapshot["summary_statistics"]`` → raw counts
          - ``pattern.incident_count``                → overrides component if set
          - ``pattern.evidence_count``                → evidence_count
          - ``pattern.last_seen_at``                  → days_since_last_seen

        The extracted values are then passed to
        ``calculate_fragility_score_from_inputs`` for the actual
        deterministic computation.
        """
        sc      = pattern.score_components or {}
        snap    = pattern.replayable_evidence_snapshot or {}
        stats   = snap.get("summary_statistics", {})

        # ---- Extract raw counts from evidence snapshot (preferred)
        incident_count = (
            pattern.incident_count
            or stats.get("incident_count", 0)
            or stats.get("incident_runs_count", 0)
        )
        rollback_count = (
            stats.get("rollback_count", 0)
            or stats.get("rollback_recs_count", 0)
        )
        failure_frequency = (
            stats.get("total_evidence", 0)
            or pattern.evidence_count
        )
        evidence_count = pattern.evidence_count or failure_frequency

        # ---- Days since last seen
        now = datetime.utcnow()
        if pattern.last_seen_at:
            days_since = max((now - pattern.last_seen_at).days, 0)
        else:
            days_since = int(stats.get("days_since_last_seen", 0))

        # ---- Churn: recover raw churn from log-normalised component
        # score_components["churn"] stores a 0–100 log-normalised value.
        # We invert it: raw_churn = (churn_score/100) * log(1+1000)
        # so that the scoring function can re-derive the same value.
        churn_score_stored = float(sc.get("churn", 0.0))
        churn_log_ref      = math.log(1.0 + self.weights.churn_log_reference)
        # Invert: (churn_score/100) = log(1+churn)/log(1+ref)
        # → log(1+churn) = churn_score/100 * log(1+ref)
        # → churn = exp(churn_score/100 * log(1+ref)) - 1
        recovered_churn = max(
            math.exp((churn_score_stored / 100.0) * churn_log_ref) - 1.0, 0.0
        )

        # ---- Test instability: stored as 0–100, recover as 0–1
        instability_score_stored = float(sc.get("instability", 0.0))
        recovered_instability    = instability_score_stored / 100.0

        # ---- Dependency proximity: stored as 0–100; recover weight in [0,1]
        prox_score_stored = float(
            sc.get("dependency_proximity", 0.0)
            or sc.get("proximity_weight",  0.0)
        )
        recovered_proximity = prox_score_stored / 100.0

        inputs = FragilityScoringInputs(
            failure_frequency           = int(failure_frequency),
            days_since_last_seen        = days_since,
            module_churn                = int(round(recovered_churn)),
            test_instability_score      = min(recovered_instability, 1.0),
            incident_count              = int(incident_count),
            dependency_proximity_weight = min(recovered_proximity, 1.0),
            rollback_count              = int(rollback_count),
            evidence_count              = int(evidence_count),
        )

        return self.calculate_fragility_score_from_inputs(inputs)

    # ================================================================== #
    # Secondary API — takes structured inputs directly                    #
    # ================================================================== #

    def calculate_fragility_score_from_inputs(
        self,
        inputs: FragilityScoringInputs,
    ) -> FragilityScoringResult:
        """
        Pure, deterministic scoring function.

        Accepts a ``FragilityScoringInputs`` bundle and returns a
        ``FragilityScoringResult`` with full component breakdown.

        This method is the single source of truth for the scoring formula.
        No database access, no side effects.
        """
        w = self.weights

        # ---------------------------------------------------------------- #
        # 1. Incident linkage score  (HIGH IMPACT — 0.25 weight)           #
        #    Saturates at INCIDENT_SATURATION distinct incidents.           #
        # ---------------------------------------------------------------- #
        incident_score = (
            min(inputs.incident_count / w.incident_saturation, 1.0) * 100.0
        )

        # ---------------------------------------------------------------- #
        # 2. Rollback linkage score  (HIGH IMPACT — 0.20 weight)           #
        #    Progressive: each additional rollback increases score.         #
        # ---------------------------------------------------------------- #
        rollback_score = (
            min(inputs.rollback_count / w.rollback_saturation, 1.0) * 100.0
        )

        # ---------------------------------------------------------------- #
        # 3. Failure frequency score  (MODERATE — 0.15 weight)             #
        #    Repeated co-failure signal.                                    #
        # ---------------------------------------------------------------- #
        frequency_score = (
            min(inputs.failure_frequency / w.frequency_saturation, 1.0) * 100.0
        )

        # ---------------------------------------------------------------- #
        # 4. Recency score  (MODERATE — 0.15 weight)                       #
        #    Exponential decay with half-life 14 days.                      #
        # ---------------------------------------------------------------- #
        recency_score = math.exp(-inputs.days_since_last_seen / 14.0) * 100.0

        # ---------------------------------------------------------------- #
        # 5. Module churn score  (SUPPORTING — 0.10 weight)                #
        #    Log-normalised against a 1000-line reference.                  #
        # ---------------------------------------------------------------- #
        churn_log_ref = math.log(1.0 + w.churn_log_reference)
        churn_score   = (
            min(
                math.log(1.0 + inputs.module_churn) / churn_log_ref,
                1.0,
            )
            * 100.0
        )

        # ---------------------------------------------------------------- #
        # 6. Test instability score  (SUPPORTING — 0.08 weight)            #
        #    Raw instability [0–1] scaled to [0–100].                      #
        # ---------------------------------------------------------------- #
        instability_score = (
            min(inputs.test_instability_score / w.instability_saturation, 1.0)
            * 100.0
        )

        # ---------------------------------------------------------------- #
        # 7. Dependency proximity score  (SUPPORTING — 0.07 weight)        #
        #    Proximity weight [0–1] scaled to [0–100].                     #
        #    1.0 → direct dependency (distance 0).                         #
        # ---------------------------------------------------------------- #
        dependency_proximity_score = (
            min(inputs.dependency_proximity_weight, 1.0) * 100.0
        )

        # ---------------------------------------------------------------- #
        # 8. Weighted additive composite                                    #
        # ---------------------------------------------------------------- #
        raw_composite = (
            w.w_incident_linkage     * incident_score
            + w.w_rollback_linkage   * rollback_score
            + w.w_failure_frequency  * frequency_score
            + w.w_recency            * recency_score
            + w.w_module_churn       * churn_score
            + w.w_test_instability   * instability_score
            + w.w_dependency_proximity * dependency_proximity_score
        )

        # ---------------------------------------------------------------- #
        # 9. Stale evidence decay  (Rule 4 — reduces score)                #
        #    decay_factor = 1 - (1 - rate)^(days/30) [continuous compound] #
        #    Positive factor means *reduction* applied to raw_composite.   #
        # ---------------------------------------------------------------- #
        stale_decay_factor = 1.0 - (
            (1.0 - w.stale_decay_rate_per_30_days) ** (inputs.days_since_last_seen / 30.0)
        )
        # Scale: factor in [0,1] represents the fraction lost to decay.
        # When days=0 → factor≈0 (no decay).
        # When days=30 → factor=0.10 (10 % decay).
        # When days=90 → factor≈0.27 (27 % decay).
        final_score = raw_composite * (1.0 - stale_decay_factor)
        final_score = max(0.0, min(round(final_score, 2), 100.0))

        # ---------------------------------------------------------------- #
        # 10. Risk level mapping  (Rule 5)                                 #
        # ---------------------------------------------------------------- #
        risk_level = _map_risk_level(final_score)

        # ---------------------------------------------------------------- #
        # 11. Confidence level                                              #
        # ---------------------------------------------------------------- #
        confidence_level = _derive_confidence_level(
            evidence_count        = inputs.evidence_count,
            days_since_last_seen  = inputs.days_since_last_seen,
            incident_count        = inputs.incident_count,
            rollback_count        = inputs.rollback_count,
        )

        return FragilityScoringResult(
            fragility_score              = final_score,
            risk_level                   = risk_level,
            confidence_level             = confidence_level,
            incident_score               = incident_score,
            rollback_score               = rollback_score,
            frequency_score              = frequency_score,
            recency_score                = recency_score,
            churn_score                  = churn_score,
            instability_score            = instability_score,
            dependency_proximity_score   = dependency_proximity_score,
            stale_decay_factor           = stale_decay_factor,
            raw_composite_score          = raw_composite,
            scoring_formula_version      = SCORING_FORMULA_VERSION,
        )

    # ================================================================== #
    # Convenience: rescore + persist in-place                             #
    # ================================================================== #

    def rescore_and_update(
        self,
        pattern: FragilityPattern,
    ) -> FragilityScoringResult:
        """
        Rescores an existing ``FragilityPattern``, updates its mutable
        fields in-place, and returns the result for the caller to commit.

        Does **not** call ``db.commit()``; the caller is responsible for
        committing the session.

        Fields updated on the pattern object:
          - ``fragility_score``
          - ``risk_level``
          - ``confidence_level``
          - ``score_components``   (merged — existing keys preserved,
                                    new/changed keys overwritten)
          - ``scoring_formula_version``
          - ``updated_at``
        """
        result = self.calculate_fragility_score(pattern)

        pattern.fragility_score        = result.fragility_score
        pattern.risk_level             = result.risk_level
        pattern.confidence_level       = result.confidence_level
        pattern.scoring_formula_version = SCORING_FORMULA_VERSION
        pattern.updated_at             = datetime.utcnow()

        # Merge new components into existing dict (preserves decay metadata
        # written by lifecycle engines such as "decayed", "decay_days")
        existing = dict(pattern.score_components or {})
        existing.update(result.to_score_components())
        pattern.score_components = existing

        return result


# ---------------------------------------------------------------------------
# Pure helper functions (module-level so they can be unit-tested directly)
# ---------------------------------------------------------------------------

def _map_risk_level(score: float) -> str:
    """
    Maps a normalised fragility score (0–100) to a risk level string.

    Boundaries (inclusive lower bound):
        75–100  → CRITICAL
        50–74   → HIGH
        25–49   → MODERATE
        0–24    → LOW
    """
    for threshold, label in RISK_BANDS:
        if score >= threshold:
            return label
    return "LOW"   # unreachable but safe


def _derive_confidence_level(
    evidence_count:       int,
    days_since_last_seen: int,
    incident_count:       int,
    rollback_count:       int,
) -> str:
    """
    Derives a confidence level (HIGH / MODERATE / LOW) from evidence
    quantity, freshness, and production-outcome linkage.

    HIGH:
      - ≥ 5 evidence links AND seen within 30 days
      - OR: any confirmed incident linkage
    MODERATE:
      - ≥ 3 evidence links AND seen within 90 days
      - OR: any rollback linkage
    LOW:
      - everything else
    """
    if incident_count > 0 or (evidence_count >= 5 and days_since_last_seen < 30):
        return "HIGH"
    if rollback_count > 0 or (evidence_count >= 3 and days_since_last_seen < 90):
        return "MODERATE"
    return "LOW"
