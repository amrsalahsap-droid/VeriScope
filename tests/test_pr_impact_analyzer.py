import pytest
from app.services.pr_impact_analyzer import PRImpactAnalyzer

def test_analyze_pr_impact_auth_and_api():
    """Verify that a PR with auth and API changes is analyzed correctly."""
    title = "Implement modern password validation rules and fix test suites"
    description = "Updates the backend routes to enforce password rules and adds unit tests."
    changed_files = [
        "src/app/api/auth/reset-password/route.ts",
        "src/modules/users/__tests__/sign-up.test.ts",
        "src/modules/users/sign-up.ts",
        "src/tests/integration/auth-workflow.test.ts"
    ]

    profile = PRImpactAnalyzer.analyze_pr_impact(
        title=title,
        description=description,
        changed_files=changed_files
    )

    # Change Types
    assert "AUTH_CHANGE" in profile["change_types"]
    assert "API_CHANGE" in profile["change_types"]
    assert "TEST_CHANGE" in profile["change_types"]
    assert "VALIDATION_CHANGE" in profile["change_types"]

    # Risk Categories
    assert "AUTH" in profile["risk_categories"]
    assert "SECURITY" in profile["risk_categories"]
    assert "USER_REGISTRATION" in profile["risk_categories"]

    # Recommended Testing Types
    assert "UNIT" in profile["recommended_testing_types"]
    assert "API" in profile["recommended_testing_types"]
    assert "INTEGRATION" in profile["recommended_testing_types"]
    assert "SECURITY" in profile["recommended_testing_types"]
    assert "SMOKE" in profile["recommended_testing_types"]
    assert "REGRESSION" in profile["recommended_testing_types"]

    # Domains and Features
    assert "auth" in profile["affected_domains"]
    assert "users" in profile["affected_domains"]
    assert "password" in profile["affected_features"]
    assert "signup" in profile["affected_features"] or "sign-up" in profile["affected_features"]

    # Summary
    assert "PR triggers" in profile["impact_summary"]

def test_analyze_pr_impact_billing_and_ui():
    """Verify that billing and UI changes are classified correctly with respective E2E/smoke testing recommendations."""
    title = "Add custom checkout pricing slider components"
    description = "Implements interactive billing page layout and Stripe integration updates."
    changed_files = [
        "landing-page/components/ui/pricing-slider.tsx",
        "src/modules/billing/subscription.ts",
        "package.json"
    ]

    profile = PRImpactAnalyzer.analyze_pr_impact(
        title=title,
        description=description,
        changed_files=changed_files
    )

    assert "UI_CHANGE" in profile["change_types"]
    assert "DEPENDENCY_CHANGE" in profile["change_types"]
    assert "PAYMENTS" in profile["risk_categories"]
    assert "billing" in profile["affected_domains"]

    assert "UI" in profile["recommended_testing_types"]
    assert "E2E" in profile["recommended_testing_types"]
    assert "SMOKE" in profile["recommended_testing_types"]

def test_analyze_pr_impact_database_and_config():
    """Verify database and config modifications are classified properly."""
    title = "Add module risk profile columns"
    description = "Includes database migration to add risk level fields."
    changed_files = [
        "alembic/versions/fedd9b1c0ace_add_module_risk_profiles.py",
        "app/models/module_risk_profile.py",
        "app/config.py"
    ]

    profile = PRImpactAnalyzer.analyze_pr_impact(
        title=title,
        description=description,
        changed_files=changed_files
    )

    assert "DATABASE_CHANGE" in profile["change_types"]
    assert "CONFIG_CHANGE" in profile["change_types"]
    assert "DATA_INTEGRITY" in profile["risk_categories"]
    assert "DATABASE" in profile["recommended_testing_types"]

def test_analyze_pr_impact_empty_fallbacks():
    """Verify safe fallback logic on empty files or None descriptions."""
    profile = PRImpactAnalyzer.analyze_pr_impact(
        title="",
        description=None,
        changed_files=[]
    )

    assert profile["change_types"] == []
    assert profile["risk_categories"] == []
    assert profile["recommended_testing_types"] == ["REGRESSION"]
    assert profile["affected_domains"] == []
    assert profile["affected_features"] == []
    assert "PR triggers STANDARD_CODE_CHANGE" in profile["impact_summary"]
