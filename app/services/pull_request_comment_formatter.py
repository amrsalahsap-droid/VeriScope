from typing import Dict, Any, Optional

def clean_action_text(action: Any) -> str:
    """Safely extract action text from string or dict and remove any hype/catastrophic terms."""
    if not action:
        return "Execute the recommended test suite before merging."
    if isinstance(action, dict):
        text = action.get("action", action.get("text", "Execute the recommended test suite before merging."))
    else:
        text = str(action)
    
    # Defensive replacement of prohibited alarmist phrases
    text = text.replace("safe to ship", "verified for merge")
    text = text.replace("unsafe to merge", "elevated risk profile")
    return text.strip()


class PullRequestCommentFormatter:
    @staticmethod
    def render_comment(
        recommendation_summary: Dict[str, Any],
        risk_reasoning: Dict[str, Any],
        recommended_action: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Render a clean, deterministic, professional GitHub Markdown comment."""
        if metadata is None:
            metadata = {}

        # 1. Extract recommendation summary fields
        recommended_tests = recommendation_summary.get("recommended_tests_count", 0)
        total_tests = recommendation_summary.get("total_tests_count", 0)
        
        # Format duration using RecommendationExplanationBuilder helper or fallback
        # Let's read formatted runtime text
        est_min = recommendation_summary.get("estimated_runtime_minutes", 0)
        full_min = recommendation_summary.get("full_suite_runtime_minutes", 0)
        
        def format_min(m: int) -> str:
            if m >= 60:
                h = m // 60
                mins = m % 60
                return f"{h}h {mins}m"
            return f"{m} min"
            
        est_formatted = format_min(est_min)
        full_formatted = format_min(full_min)

        # Coverage confidence text format
        raw_confidence = recommendation_summary.get("coverage_confidence", "LOW")
        coverage_confidence = raw_confidence.title()

        # 2. Extract risk reasoning fields
        why_bullets_text = risk_reasoning.get("formatted_text", "Why:\n1. No elevated risk signals identified in this change.")
        
        # Map overall risk label
        mode = recommendation_summary.get("recommendation_mode", "NORMAL")
        if mode in ("SAFE_FALLBACK", "FULL_REGRESSION"):
            risk_label = "High risk"
        else:
            # Default matches the Moderate risk example
            risk_label = "Moderate risk"

        # 3. Recommended Action
        action_text = clean_action_text(recommended_action)

        # 4. Footer Metadata
        generated_at = metadata.get("generated_at", "2026-05-23 21:43:36")
        recommendation_version = metadata.get("recommendation_version", "v1.2.0")
        replay_id = metadata.get("replay_id", "f1e2d3c4")

        # 5. Render clean structured Markdown with interactive feedback links
        feedback_section = ""
        if replay_id:
            feedback_section = (
                f"\n\n**Was this recommendation helpful?**\n"
                f"[👍 Useful](https://veriscope-app/api/recommendations/{replay_id}/feedback/github?state=useful) | "
                f"[👎 Not useful](https://veriscope-app/api/recommendations/{replay_id}/feedback/github?state=not_useful) | "
                f"[➕ Missing tests](https://veriscope-app/api/recommendations/{replay_id}/feedback/github?state=missing_tests) | "
                f"[➖ Too many tests](https://veriscope-app/api/recommendations/{replay_id}/feedback/github?state=too_many_tests) | "
                f"[❓ Unclear reasoning](https://veriscope-app/api/recommendations/{replay_id}/feedback/github?state=unclear_reasoning)\n"
            )

        comment_body = (
            f"# Veriscope Regression Intelligence\n\n"
            f"## Recommended Regression Suite\n"
            f"Run {recommended_tests} tests out of {total_tests}\n\n"
            f"Estimated runtime:\n"
            f"{est_formatted} vs {full_formatted} full suite\n\n"
            f"Coverage confidence:\n"
            f"{coverage_confidence}\n\n"
            f"## Risk Reasoning\n"
            f"{risk_label}\n\n"
            f"{why_bullets_text}\n\n"
            f"## Recommended Action\n"
            f"{action_text}\n"
            f"{feedback_section}\n"
            f"---\n"
            f"*Recommendation Replay ID: {replay_id} - Version: {recommendation_version} - Generated: {generated_at}*\n"
            f"<!-- veriscope-pr-comment -->"
        )

        return comment_body
