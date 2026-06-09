"""
ModuleRiskScoringEngine
=======================

Deterministic, evidence-based risk scorer for ModuleRiskProfile.

Design rules
------------
- No ML.  No fake percentages.  No normalisation against a moving baseline.
- risk_score is a plain weighted sum of raw evidence counts.
- It is *only* used as a relative ranking key — larger value → higher
  historical fragility → the recommendation engine should prioritise it.
- score_components is persisted verbatim so any score can be reconstructed
  from first principles (full explainability / auditability).
- Formula version is bumped any time weights change so stored components
  remain replayable.

Scoring formula (v1)
--------------------
    risk_score =
          W_ESCAPED_DEFECT   × escaped_defects
        + W_ROLLBACK         × rollback_count
        + W_FAILURE_FREQ     × failure_frequency
        + W_CHANGE_FREQ      × change_frequency
        + W_LOW_ACCURACY     × low_accuracy_penalty

    Where:
        low_accuracy_penalty = max(0, recommendations_presented − recommendations_accepted)
            (represents the count of times a recommendation was presented but
             NOT followed — a direct signal of module unreliability)

Weight rationale
----------------
Escaped defects and rollbacks have the highest weight because they represent
confirmed production impact.  Failure frequency and change frequency are
supporting signals — high churn alone does not imply risk without failures.
Low recommendation accuracy is a soft penalty: it rewards modules where
engineers consistently ignored recommendations (historically dangerous).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from app.models.module_risk_profile import ModuleRiskProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Formula version — bump whenever weights change
# ---------------------------------------------------------------------------
SCORING_FORMULA_VERSION = "module_risk.v1"

# ---------------------------------------------------------------------------
# Weights — plain multipliers applied to raw integer counts.
# They are intentionally kept as simple integers so the formula output is
# human-readable and not confusable with a probability or percentage.
# ---------------------------------------------------------------------------
W_ESCAPED_DEFECT = 10   # Highest: confirmed production regression
W_ROLLBACK       = 8    # High: deployed code had to be reversed
W_FAILURE_FREQ   = 3    # Moderate: repeated test failure signal
W_CHANGE_FREQ    = 1    # Supporting: churn volume proxy
W_LOW_ACCURACY   = 2    # Soft penalty: recommendation ignored


@dataclass
class ModuleRiskInputs:
    """
    Structured input bundle for a single score calculation.

    All fields default to zero so callers may pass only the signals they have
    evidence for.
    """
    change_frequency:          int = 0
    failure_frequency:         int = 0
    escaped_defects:           int = 0
    rollback_count:            int = 0
    recommendations_presented: int = 0
    recommendations_accepted:  int = 0


@dataclass
class ModuleRiskResult:
    """
    Immutable output of a single score calculation.

    Carries every intermediate value needed to reconstruct the final score from
    first principles.
    """
    risk_score:               float
    # Per-component contributions (raw weight × count)
    escaped_defect_contrib:   float
    rollback_contrib:         float
    failure_freq_contrib:     float
    change_freq_contrib:      float
    low_accuracy_penalty:     int    # raw count of non-accepted recommendations
    low_accuracy_contrib:     float
    # Formula metadata
    scoring_formula_version:  str = field(default=SCORING_FORMULA_VERSION)

    def to_score_components(self) -> Dict[str, Any]:
        """
        Serialises result to the JSONB ``score_components`` dictionary stored on
        ModuleRiskProfile for full explainability.
        """
        return {
            "escaped_defect_contrib":  round(self.escaped_defect_contrib, 4),
            "rollback_contrib":        round(self.rollback_contrib,       4),
            "failure_freq_contrib":    round(self.failure_freq_contrib,   4),
            "change_freq_contrib":     round(self.change_freq_contrib,    4),
            "low_accuracy_penalty":    self.low_accuracy_penalty,
            "low_accuracy_contrib":    round(self.low_accuracy_contrib,   4),
            "risk_score":              round(self.risk_score,             4),
            "scoring_formula_version": self.scoring_formula_version,
        }


class ModuleRiskScoringEngine:
    """
    Calculates a deterministic risk_score for a ModuleRiskProfile.

    Usage — score from structured inputs::

        engine = ModuleRiskScoringEngine()
        inputs = ModuleRiskInputs(
            change_frequency=12,
            failure_frequency=5,
            escaped_defects=1,
            rollback_count=0,
            recommendations_presented=8,
            recommendations_accepted=3,
        )
        result = engine.calculate_from_inputs(inputs)
        profile.risk_score       = result.risk_score
        profile.score_components = result.to_score_components()

    Usage — rescore an existing ORM object in-place::

        result = engine.rescore_and_update(profile)
        db.add(profile)
        db.commit()
    """

    @staticmethod
    def calculate_from_inputs(inputs: ModuleRiskInputs) -> ModuleRiskResult:
        """
        Pure, deterministic scoring.  No DB access, no side effects.
        """
        escaped_defect_contrib = W_ESCAPED_DEFECT * inputs.escaped_defects
        rollback_contrib       = W_ROLLBACK       * inputs.rollback_count
        failure_freq_contrib   = W_FAILURE_FREQ   * inputs.failure_frequency
        change_freq_contrib    = W_CHANGE_FREQ    * inputs.change_frequency

        low_accuracy_penalty = max(
            0,
            inputs.recommendations_presented - inputs.recommendations_accepted,
        )
        low_accuracy_contrib = W_LOW_ACCURACY * low_accuracy_penalty

        risk_score = (
            escaped_defect_contrib
            + rollback_contrib
            + failure_freq_contrib
            + change_freq_contrib
            + low_accuracy_contrib
        )

        return ModuleRiskResult(
            risk_score              = round(risk_score, 4),
            escaped_defect_contrib  = escaped_defect_contrib,
            rollback_contrib        = rollback_contrib,
            failure_freq_contrib    = failure_freq_contrib,
            change_freq_contrib     = change_freq_contrib,
            low_accuracy_penalty    = low_accuracy_penalty,
            low_accuracy_contrib    = low_accuracy_contrib,
            scoring_formula_version = SCORING_FORMULA_VERSION,
        )

    @staticmethod
    def calculate_from_profile(profile: ModuleRiskProfile) -> ModuleRiskResult:
        """
        Derives inputs from an existing ORM object and delegates to
        ``calculate_from_inputs``.  Used for audit replay and recalculation jobs.
        """
        inputs = ModuleRiskInputs(
            change_frequency          = profile.change_frequency          or 0,
            failure_frequency         = profile.failure_frequency         or 0,
            escaped_defects           = profile.escaped_defects           or 0,
            rollback_count            = profile.rollback_count            or 0,
            recommendations_presented = profile.recommendations_presented or 0,
            recommendations_accepted  = profile.recommendations_accepted  or 0,
        )
        return ModuleRiskScoringEngine.calculate_from_inputs(inputs)

    @staticmethod
    def rescore_and_update(profile: ModuleRiskProfile) -> ModuleRiskResult:
        """
        Rescores an existing ``ModuleRiskProfile`` and mutates it in-place.

        Does **not** call ``db.commit()``; the caller is responsible for
        committing the session.

        Fields updated:
          - ``risk_score``
          - ``score_components``
          - ``scoring_formula_version``
          - ``last_scored_at``
          - ``updated_at``
        """
        result = ModuleRiskScoringEngine.calculate_from_profile(profile)

        profile.risk_score              = result.risk_score
        profile.score_components        = result.to_score_components()
        profile.scoring_formula_version = SCORING_FORMULA_VERSION
        profile.last_scored_at          = datetime.utcnow()
        profile.updated_at              = datetime.utcnow()

        logger.debug(
            "ModuleRiskScoringEngine: rescored module_path=%r risk_score=%.2f",
            profile.module_path,
            profile.risk_score,
        )

        return result
