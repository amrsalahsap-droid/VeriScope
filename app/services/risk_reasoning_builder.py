import re
from typing import Dict, Any, List
from app.models.recommendation import RecommendationRun

def shorten_path(path: str) -> str:
    """Shorten path to at most 2 components for conciseness."""
    if not path:
        return ""
    parts = path.split('/')
    if len(parts) > 2:
        return "/".join(parts[-2:])
    return path

def extract_component(path: str) -> str:
    """Extract component or folder name from path."""
    if not path:
        return "unknown"
    parts = path.split('/')
    if len(parts) > 1:
        return parts[-2]
    return path.split('.')[0]

def map_risk_level(level: str) -> str:
    """Enforce strictly allowed risk levels (LOW, MODERATE, HIGH) and demote CRITICAL to HIGH."""
    l = (level or "LOW").upper()
    if l == "CRITICAL":
        return "HIGH"
    if l not in ("LOW", "MODERATE", "HIGH"):
        return "LOW"
    return l


class RiskReasoningBuilder:
    @classmethod
    def build_risk_reasoning(
        cls,
        run: RecommendationRun,
        fragility_patterns: List[Any],
        recommendation_snapshot: Any
    ) -> Dict[str, Any]:
        """Generate concise evidence-backed risk reasoning for PR comments."""
        bullets = []

        # 1. Extraction helpers for recommendation snapshot
        changed_files = []
        file_churn = {}
        if recommendation_snapshot:
            # Handle both SQLAlchemy objects and raw dictionaries
            if hasattr(recommendation_snapshot, "changed_files"):
                changed_files = recommendation_snapshot.changed_files or []
            elif isinstance(recommendation_snapshot, dict):
                changed_files = recommendation_snapshot.get("changed_files", [])

            # Pull file churn if present in context or dict
            if hasattr(recommendation_snapshot, "context") and recommendation_snapshot.context:
                file_churn = recommendation_snapshot.context.get("file_churn", {})
            elif isinstance(recommendation_snapshot, dict):
                file_churn = recommendation_snapshot.get("context", {}).get("file_churn", {})

        # Priority 1: Fragility History (FILE_FAILURE_FREQUENCY patterns on changed files)
        fragility_bullets = []
        for pat in fragility_patterns:
            if pat.pattern_type == "FILE_FAILURE_FREQUENCY" and pat.status == "ACTIVE":
                trigger_file = pat.context.get("trigger_file")
                if trigger_file and trigger_file in changed_files:
                    risk = map_risk_level(pat.risk_level)
                    fragility_bullets.append(
                        (pat.evidence_count, f"{shorten_path(trigger_file)} has {risk.lower()} fragility history")
                    )
        # Sort fragility bullets descending by evidence count
        fragility_bullets.sort(key=lambda x: x[0], reverse=True)
        for _, b in fragility_bullets:
            bullets.append(b)

        # Churn Signal (Part of Fragility/Activity - e.g. billing/subscriptions.ts changed 4 times this sprint)
        churn_bullets = []
        for file in changed_files:
            churn_count = file_churn.get(file, 0)
            if churn_count >= 3:
                churn_bullets.append(
                    (churn_count, f"{shorten_path(file)} changed {churn_count} times this sprint")
                )
        churn_bullets.sort(key=lambda x: x[0], reverse=True)
        for _, b in churn_bullets:
            bullets.append(b)

        # Priority 2: Repeated Co-failures (CO_FAILURE_PATTERN patterns)
        cofail_bullets = []
        for pat in fragility_patterns:
            if pat.pattern_type == "CO_FAILURE_PATTERN" and pat.status == "ACTIVE":
                trigger_file = pat.context.get("trigger_file")
                failure_test = pat.context.get("failure_test") or pat.context.get("related_tests", [""])[0]
                if trigger_file and failure_test:
                    comp1 = extract_component(trigger_file)
                    comp2 = extract_component(failure_test)
                    cofail_bullets.append(
                        (pat.evidence_count, f"{comp1} + {comp2} co-failed in {pat.evidence_count} previous regressions")
                    )
        cofail_bullets.sort(key=lambda x: x[0], reverse=True)
        for _, b in cofail_bullets:
            bullets.append(b)

        # Priority 3: Unstable Modules (UNSTABLE_MODULE / TEST_CLUSTER_FAILURE)
        unstable_bullets = []
        for pat in fragility_patterns:
            if pat.pattern_type in ("UNSTABLE_MODULE", "TEST_CLUSTER_FAILURE") and pat.status == "ACTIVE":
                dir_prefix = pat.context.get("trigger_dir") or pat.context.get("trigger_neighborhood") or pat.normalized_pattern_key.split(":")[-1]
                if dir_prefix:
                    unstable_bullets.append(
                        (pat.evidence_count, f"{shorten_path(dir_prefix)} has active instability history ({pat.evidence_count} failures)")
                    )
        unstable_bullets.sort(key=lambda x: x[0], reverse=True)
        for _, b in unstable_bullets:
            bullets.append(b)

        # Priority 4: Low Coverage Confidence (LOW or MODERATE run coverage evidence)
        cov_confidence = map_risk_level(run.evidence_quality)  # Reuses LOW/MODERATE/HIGH mapper
        if cov_confidence in ("LOW", "MODERATE"):
            bullets.append(f"coverage confidence is {cov_confidence.title()}")

        # Priority 5: Rollback-linked patterns (ESCAPED_DEFECT_PATTERN / ROLLBACK_INVOLVEMENT)
        rollback_bullets = []
        for pat in fragility_patterns:
            if pat.pattern_type in ("ESCAPED_DEFECT_PATTERN", "ROLLBACK_INVOLVEMENT") and pat.status == "ACTIVE":
                trigger_file = pat.context.get("trigger_file")
                if trigger_file and trigger_file in changed_files:
                    rollback_bullets.append(
                        (pat.evidence_count, f"{shorten_path(trigger_file)} was involved in {pat.evidence_count} rollback-linked regressions")
                    )
        rollback_bullets.sort(key=lambda x: x[0], reverse=True)
        for _, b in rollback_bullets:
            bullets.append(b)

        # Deduplicate while preserving order
        unique_bullets = []
        seen = set()
        for b in bullets:
            # Enforce forbidden phrase replacement to be defensive
            b_clean = b.replace("critical", "high").replace("unsafe", "elevated risk").replace("production risk guaranteed", "elevated risk profile")
            if b_clean not in seen:
                unique_bullets.append(b_clean)
                seen.add(b_clean)

        # Cap strictly at 4 bullets
        final_bullets = unique_bullets[:4]

        # Generate formatted plain text output block
        formatted_bullets = "\n".join([f"{i+1}. {bullet}" for i, bullet in enumerate(final_bullets)])
        formatted_text = f"Why:\n{formatted_bullets}" if final_bullets else "Why:\n1. No elevated risk signals identified in this change."

        return {
            "bullets": final_bullets,
            "formatted_text": formatted_text
        }
