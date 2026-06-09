import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.pull_request_comment_formatter import PullRequestCommentFormatter

def run_comment_formatter_verification():
    print("======================================================================")
    print("STARTING PR COMMENT FORMATTER PLATFORM VERIFICATIONS")
    print("======================================================================\n")

    # ====================================================================
    # Test 1. Determinism and Structure Verification
    # ====================================================================
    print("--- 1. Testing Format Layout and Example Match ---")

    summary = {
        "recommended_tests_count": 42,
        "total_tests_count": 847,
        "estimated_runtime_minutes": 18,
        "full_suite_runtime_minutes": 134, # 2h 14m
        "coverage_confidence": "MODERATE",
        "recommendation_mode": "NORMAL"
    }

    reasoning = {
        "bullets": [
            "auth/middleware.ts has high fragility history",
            "billing/subscriptions.ts changed 4 times this sprint",
            "auth + billing co-failed in 3 previous regressions",
            "coverage confidence is Moderate"
        ],
        "formatted_text": (
            "Why:\n"
            "1. auth/middleware.ts has high fragility history\n"
            "2. billing/subscriptions.ts changed 4 times this sprint\n"
            "3. auth + billing co-failed in 3 previous regressions\n"
            "4. coverage confidence is Moderate"
        )
    }

    action = "Run auth-billing integration tests before merge."

    metadata = {
        "generated_at": "2026-05-23 21:43:36",
        "recommendation_version": "v1.2.0",
        "replay_id": "f1e2d3c4"
    }

    rendered = PullRequestCommentFormatter.render_comment(summary, reasoning, action, metadata)
    print(f"DEBUG: Rendered Comment:\n{rendered}\n")

    # Verify exact layout matches example
    expected = (
        "# Veriscope Regression Intelligence\n\n"
        "## Recommended Regression Suite\n"
        "Run 42 tests out of 847\n\n"
        "Estimated runtime:\n"
        "18 min vs 2h 14m full suite\n\n"
        "Coverage confidence:\n"
        "Moderate\n\n"
        "## Risk Reasoning\n"
        "Moderate risk\n\n"
        "Why:\n"
        "1. auth/middleware.ts has high fragility history\n"
        "2. billing/subscriptions.ts changed 4 times this sprint\n"
        "3. auth + billing co-failed in 3 previous regressions\n"
        "4. coverage confidence is Moderate\n\n"
        "## Recommended Action\n"
        "Run auth-billing integration tests before merge.\n\n"
        "---\n"
        "*Recommendation Replay ID: f1e2d3c4 - Version: v1.2.0 - Generated: 2026-05-23 21:43:36*\n"
        "<!-- veriscope-pr-comment -->"
    )
    assert rendered == expected
    print("[OK] Rendered layout matches the specifications exactly!")

    # ====================================================================
    # Test 2. Bullet limit and line counting ceiling (< 40 lines)
    # ====================================================================
    print("\n--- 2. Checking Line Count Ceiling ---")
    line_count = len(rendered.split("\n"))
    print(f"DEBUG: Rendered Line Count: {line_count}")
    assert line_count <= 40
    print("[OK] Generated comment is highly concise and strictly under 40 lines limit.")

    # ====================================================================
    # Test 3. Verification of Formatting Rules
    # ====================================================================
    print("\n--- 3. Verifying Layout Formatting Rules ---")
    assert "|" not in rendered, "Markdown tables are strictly prohibited!"
    assert "🔍" not in rendered, "Emojis are strictly prohibited!"
    
    # Prohibited words and phrases checks
    assert "safe to ship" not in rendered.lower(), "Catastrophic AI statements are prohibited!"
    assert "unsafe to merge" not in rendered.lower(), "Catastrophic AI statements are prohibited!"
    assert "production risk guaranteed" not in rendered.lower(), "Catastrophic AI statements are prohibited!"
    
    print("[OK] Checked and certified: no tables, no emojis, no speculative AI copilot claims.")

    # ====================================================================
    # Test 4. Pure Determinism
    # ====================================================================
    print("\n--- 4. Testing Pure Determinism ---")
    rendered1 = PullRequestCommentFormatter.render_comment(summary, reasoning, action, metadata)
    rendered2 = PullRequestCommentFormatter.render_comment(summary, reasoning, action, metadata)
    assert rendered1 == rendered2
    print("[OK] Determinism verified: identical inputs always produce identical output.")

    print("\n=======================================================")
    print("ALL PR COMMENT FORMATTER PLATFORM VERIFICATIONS PASSED!")
    print("=======================================================\n")

if __name__ == "__main__":
    run_comment_formatter_verification()
