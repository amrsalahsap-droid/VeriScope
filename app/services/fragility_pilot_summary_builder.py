import uuid
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.fragility_pattern import FragilityPattern

logger = logging.getLogger("veriscope.fragility_pilot_summary_builder")

class FragilityPilotSummaryBuilder:
    """
    FragilityPilotSummaryBuilder
    ===========================
    Generates deterministic operational summaries of historical fragility patterns
    for pilot evaluation and reporting, strictly respecting top-5 limits and
    avoiding synthetic architectural claims.
    """

    @classmethod
    def generate_fragility_summary(cls, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """
        Query active fragility patterns for a repository and group them into top-5 summaries.
        """
        # Query active persisted fragility patterns for the repository
        patterns = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repository_id,
            FragilityPattern.status == "ACTIVE"
        ).all()

        # Classify patterns into their respective reporting categories
        groups = {
            "most_fragile_modules": [],
            "most_repeated_co_failure_patterns": [],
            "rollback_linked_fragility_patterns": [],
            "unstable_dependency_neighborhoods": [],
            "high_churn_modules": []
        }

        for pat in patterns:
            pt = pat.pattern_type
            cat_key = None
            
            if pt == "UNSTABLE_MODULE":
                cat_key = "most_fragile_modules"
            elif pt == "CO_FAILURE_PATTERN":
                cat_key = "most_repeated_co_failure_patterns"
            elif pt == "ROLLBACK_INVOLVEMENT":
                cat_key = "rollback_linked_fragility_patterns"
            elif pt == "DEPENDENCY_PROXIMITY":
                cat_key = "unstable_dependency_neighborhoods"
            elif pt == "FILE_FAILURE_FREQUENCY":
                cat_key = "high_churn_modules"

            if cat_key:
                groups[cat_key].append(pat)

        # Process each category: sort by score DESC and truncate to top 5
        summary_payload = {
            "repository_id": str(repository_id),
            "most_fragile_modules": [],
            "most_repeated_co_failure_patterns": [],
            "rollback_linked_fragility_patterns": [],
            "unstable_dependency_neighborhoods": [],
            "high_churn_modules": []
        }

        for cat_key, pat_list in groups.items():
            # Sort in descending order of fragility score
            sorted_pats = sorted(pat_list, key=lambda x: x.fragility_score or 0.0, reverse=True)
            # Limit to top 5
            top_5 = sorted_pats[:5]

            for pat in top_5:
                summary_payload[cat_key].append({
                    "pattern_id": str(pat.id),
                    "normalized_pattern_key": pat.normalized_pattern_key,
                    "title": pat.title or "",
                    "explanation": pat.explanation or "",
                    "fragility_score": round(pat.fragility_score or 0.0, 2),
                    "risk_level": pat.risk_level or "LOW"
                })

        return summary_payload
