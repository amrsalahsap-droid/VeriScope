import re
from typing import Dict, Any, List, Optional

class PRImpactAnalyzer:
    """
    PRImpactAnalyzer deterministically assesses pull request metadata
    and changed file trees to construct an evidence-backed ImpactProfile.
    
    It operates with:
    - Zero speculative / AI logic.
    - Strict deterministic keyword and path rules.
    - Evidence-based classification of change types, risks, and test types.
    """

    @classmethod
    def analyze_pr_impact(
        cls,
        title: str,
        description: Optional[str],
        changed_files: List[Any]
    ) -> Dict[str, Any]:
        """
        Main entry point to run deterministic analysis.
        Returns a dictionary representing the persisted ImpactProfile.
        """
        title = title or ""
        description = description or ""
        combined_text = f"{title}\n{description}".lower()

        # 1. Standardize changed files to path strings
        paths = []
        for f in changed_files:
            if isinstance(f, str):
                paths.append(f)
            elif hasattr(f, "file_path"):
                paths.append(f.file_path)
            elif isinstance(f, dict) and "file_path" in f:
                paths.append(f["file_path"])

        # 2. Extract affected domains and features deterministically from paths
        affected_domains = set()
        affected_features = set()

        domain_keywords = ["auth", "billing", "users", "subscriptions", "payments", "organizations", "repos", "repositories", "coverage"]
        feature_keywords = ["reset-password", "signup", "sign-up", "login", "password", "invoice", "trial", "quarantine", "flaky", "sync"]

        for path in paths:
            path_lower = path.lower()
            
            # Extract standard domains and features
            for dk in domain_keywords:
                if dk in path_lower:
                    affected_domains.add(dk)
            for fk in feature_keywords:
                if fk in path_lower:
                    affected_features.add(fk)

            # Suffix/folder based checks
            parts = [p.lower() for p in re.split(r"[/\\]", path) if p]
            if "modules" in parts:
                idx = parts.index("modules")
                if idx + 1 < len(parts):
                    affected_domains.add(parts[idx + 1])
            elif "app" in parts:
                idx = parts.index("app")
                if idx + 1 < len(parts) and parts[idx + 1] not in ("api", "components", "ui"):
                    affected_domains.add(parts[idx + 1])

        # Also extract from PR Title if direct matches exist
        for dk in domain_keywords:
            if re.search(rf"\b{dk}\b", combined_text):
                affected_domains.add(dk)
        for fk in feature_keywords:
            if re.search(rf"\b{fk}\b", combined_text):
                affected_features.add(fk)

        # 3. Determine Change Types
        change_types = set()
        
        # AUTH_CHANGE
        auth_kws = ["auth", "login", "signup", "signin", "password", "token", "session", "jwt", "credential"]
        if any(kw in combined_text for kw in auth_kws) or any(any(kw in p.lower() for kw in auth_kws) for p in paths):
            change_types.add("AUTH_CHANGE")

        # API_CHANGE
        api_kws = ["api/", "route.ts", "route.js", "endpoints/", "controllers/"]
        if any(any(kw in p.lower() for kw in api_kws) for p in paths) or any(kw in combined_text for kw in ["api change", "api endpoint", "rest api", "endpoint"]):
            change_types.add("API_CHANGE")

        # UI_CHANGE
        ui_kws = ["components/", "pages/", "page.tsx", "page.jsx", "view", "css", "html", "tailwind", ".scss"]
        if any(any(kw in p.lower() for kw in ui_kws) for p in paths) or any(kw in combined_text for kw in ["ui change", "frontend", "styling", "layout", "button", "component", "page"]):
            change_types.add("UI_CHANGE")

        # VALIDATION_CHANGE
        val_kws = ["validation", "validators", "schemas", "rules"]
        if any(any(kw in p.lower() for kw in val_kws) for p in paths) or "validation" in combined_text or "validator" in combined_text:
            change_types.add("VALIDATION_CHANGE")

        # DATABASE_CHANGE
        db_kws = ["db/", "models/", "migration", "alembic", "schema", "sql"]
        if any(any(kw in p.lower() for kw in db_kws) for p in paths) or any(kw in combined_text for kw in ["database", "migration", "sql", "schema change", "db table"]):
            change_types.add("DATABASE_CHANGE")

        # CONFIG_CHANGE
        cfg_kws = ["config", "settings", ".env", "tsconfig.json"]
        if any(any(kw in p.lower() for kw in cfg_kws) for p in paths) or any(kw in combined_text for kw in ["config change", "settings", "configuration"]):
            change_types.add("CONFIG_CHANGE")

        # TEST_CHANGE
        test_kws = ["test", "spec", "mock"]
        if any(any(kw in p.lower() for kw in test_kws) for p in paths) or any(kw in combined_text for kw in ["test change", "test suite", "fix test", "unit test"]):
            change_types.add("TEST_CHANGE")

        # DEPENDENCY_CHANGE
        dep_kws = ["package.json", "package-lock.json", "requirements.txt", "poetry.lock", "go.mod", "go.sum"]
        if any(any(kw in p.lower() for kw in dep_kws) for p in paths) or any(kw in combined_text for kw in ["dependency", "dependencies", "npm install", "pip install", "upgrade package"]):
            change_types.add("DEPENDENCY_CHANGE")

        # WORKFLOW_CHANGE
        wf_kws = ["workflows/", "actions/", ".github/", "ci/"]
        if any(any(kw in p.lower() for kw in wf_kws) for p in paths) or any(kw in combined_text for kw in ["workflow change", "ci pipeline", "github actions"]):
            change_types.add("WORKFLOW_CHANGE")

        # 4. Determine Risk Categories
        risk_categories = set()
        
        # AUTH
        if any(kw in combined_text for kw in ["auth", "login", "signin", "session", "jwt", "token"]) or any(any(kw in p.lower() for kw in ["auth", "login", "signin", "session", "jwt", "token"]) for p in paths):
            risk_categories.add("AUTH")

        # SECURITY
        sec_kws = ["password", "reset-password", "credential", "encryption", "secret", "hash", "crypto", "security", "acl", "permission"]
        if any(kw in combined_text for kw in sec_kws) or any(any(kw in p.lower() for kw in sec_kws) for p in paths) or "AUTH" in risk_categories:
            risk_categories.add("SECURITY")

        # DATA_INTEGRITY
        if "DATABASE_CHANGE" in change_types or any(kw in combined_text for kw in ["write", "save", "delete", "update"]):
            risk_categories.add("DATA_INTEGRITY")

        # USER_REGISTRATION
        if any(kw in combined_text for kw in ["signup", "sign-up", "register", "user-registration", "onboarding"]) or any(any(kw in p.lower() for kw in ["signup", "sign-up", "register", "user-registration", "onboarding"]) for p in paths):
            risk_categories.add("USER_REGISTRATION")

        # PAYMENTS
        pay_kws = ["billing", "subscription", "payment", "invoice", "checkout", "stripe", "price"]
        if any(kw in combined_text for kw in pay_kws) or any(any(kw in p.lower() for kw in pay_kws) for p in paths):
            risk_categories.add("PAYMENTS")

        # NOTIFICATIONS
        not_kws = ["mail", "email", "sms", "notification", "alert", "send-email"]
        if any(kw in combined_text for kw in not_kws) or any(any(kw in p.lower() for kw in not_kws) for p in paths):
            risk_categories.add("NOTIFICATIONS")

        # PERMISSIONS
        perm_kws = ["role", "permission", "acl", "member", "access", "authorize"]
        if any(kw in combined_text for kw in perm_kws) or any(any(kw in p.lower() for kw in perm_kws) for p in paths):
            risk_categories.add("PERMISSIONS")

        # WORKFLOW
        if "WORKFLOW_CHANGE" in change_types or any(kw in combined_text for kw in ["pipeline", "process", "step"]):
            risk_categories.add("WORKFLOW")

        # 5. Determine Testing Types
        recommended_testing_types = set()
        
        # REGRESSION is always recommended
        recommended_testing_types.add("REGRESSION")

        if paths:
            # UNIT is recommended if actual code changed
            recommended_testing_types.add("UNIT")

        if "API_CHANGE" in change_types:
            recommended_testing_types.add("API")
            recommended_testing_types.add("INTEGRATION")

        if "UI_CHANGE" in change_types:
            recommended_testing_types.add("UI")
            recommended_testing_types.add("E2E")

        if "DATABASE_CHANGE" in change_types or "DATA_INTEGRITY" in risk_categories:
            recommended_testing_types.add("DATABASE")
            recommended_testing_types.add("INTEGRATION")

        if "SECURITY" in risk_categories or "AUTH" in risk_categories or "PERMISSIONS" in risk_categories:
            recommended_testing_types.add("SECURITY")
            recommended_testing_types.add("SMOKE")

        if "PAYMENTS" in risk_categories:
            recommended_testing_types.add("E2E")
            recommended_testing_types.add("SMOKE")

        if any(kw in combined_text for kw in ["performance", "optimize", "cache", "slow", "speed"]):
            recommended_testing_types.add("PERFORMANCE")

        # 6. Construct Impact Summary
        change_desc = ", ".join(sorted(change_types)) if change_types else "STANDARD_CODE_CHANGE"
        risk_desc = "elevated risk categories: " + ", ".join(sorted(risk_categories)) if risk_categories else "no high-risk categories"
        impact_summary = (
            f"PR triggers {change_desc} classification with {risk_desc}. "
            f"Optimized verification requires {', '.join(sorted(recommended_testing_types))} testing suites."
        )

        return {
            "affected_domains": sorted(list(affected_domains)),
            "affected_features": sorted(list(affected_features)),
            "change_types": sorted(list(change_types)),
            "risk_categories": sorted(list(risk_categories)),
            "recommended_testing_types": sorted(list(recommended_testing_types)),
            "impact_summary": impact_summary
        }
