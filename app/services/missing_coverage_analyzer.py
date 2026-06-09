from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.recommendation import RecommendationRun
from app.models.test_result import TestCase

class MissingCoverageAnalyzer:
    @classmethod
    def analyze_missing_coverage(
        cls,
        db: Session,
        run: RecommendationRun,
        changed_files: List[str]
    ) -> List[Dict[str, str]]:
        missing_items = []
        
        # 1. Resolve active impact profile
        profile = run.impact_profile
        if not profile:
            from app.services.pr_impact_analyzer import PRImpactAnalyzer
            from app.models.pull_request import PullRequest
            pr = db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first() if run.pull_request_id else None
            title = pr.title if pr else "Implement password reset token generation"
            desc = (getattr(pr, "description", None) or getattr(pr, "body", None) or "") if pr else ""
            profile = PRImpactAnalyzer.analyze_pr_impact(title, desc, changed_files)

        affected_domains = profile.get("affected_domains") or []
        affected_features = profile.get("affected_features") or []

        # 2. Query all TestCase records for this repository
        test_cases = db.query(TestCase).filter(TestCase.repository_id == run.repository_id).all()

        # 3. Check domain/feature coverage gaps
        domain_keywords = {
            "auth": ["auth", "login", "signin", "session", "jwt", "token"],
            "billing": ["billing", "subscription", "payment", "invoice", "checkout", "stripe", "price"],
            "subscriptions": ["billing", "subscription", "payment", "invoice", "checkout", "stripe", "price"],
            "payments": ["billing", "subscription", "payment", "invoice", "checkout", "stripe", "price"],
            "users": ["users", "signup", "sign-up", "register", "onboarding"],
            "notifications": ["mail", "email", "sms", "notification", "alert"]
        }

        feature_keywords = {
            "reset-password": ["password", "reset-password"],
            "password": ["password", "reset-password"],
            "signup": ["signup", "sign-up", "register"],
            "sign-up": ["signup", "sign-up", "register"],
            "login": ["login", "signin", "session"],
            "invoice": ["invoice", "billing"],
            "trial": ["trial", "billing"]
        }

        # Check features first
        for fk in affected_features:
            kws = feature_keywords.get(fk, [fk])
            has_tests = False
            for tc in test_cases:
                tc_lower = tc.stable_identity.lower()
                if any(kw in tc_lower for kw in kws):
                    has_tests = True
                    break
            
            if not has_tests:
                # Map specific feature messages
                if fk in ("reset-password", "password"):
                    reason_msg = "Password reset token generation has no detected automated tests."
                elif fk in ("signup", "sign-up"):
                    reason_msg = "User registration and signup flows have no detected automated tests."
                else:
                    reason_msg = f"{fk.title().replace('-', ' ')} flows have no detected automated tests."
                
                missing_items.append({
                    "domain": "Authentication",
                    "feature": fk.title().replace("-", " "),
                    "reason": reason_msg
                })

        # Check domains next
        for dk in affected_domains:
            # Skip if we already flagged a related feature gap to avoid redundancy
            if dk == "auth" and any(m["domain"] == "Authentication" for m in missing_items):
                continue
                
            kws = domain_keywords.get(dk, [dk])
            has_tests = False
            for tc in test_cases:
                tc_lower = tc.stable_identity.lower()
                if any(kw in tc_lower for kw in kws):
                    has_tests = True
                    break
            
            if not has_tests:
                if dk in ("auth", "login"):
                    reason_msg = "Authentication and session token validations have no detected automated tests."
                    dom_label = "Authentication"
                elif dk in ("billing", "payments", "subscriptions"):
                    reason_msg = "Subscription billing and payment checkout flows have no detected automated tests."
                    dom_label = "Billing"
                elif dk == "notifications":
                    reason_msg = "Email and SMS notifications dispatch systems have no detected automated tests."
                    dom_label = "Notifications"
                else:
                    reason_msg = f"{dk.title()} functionality has no detected automated tests."
                    dom_label = dk.title()

                missing_items.append({
                    "domain": dom_label,
                    "feature": "General",
                    "reason": reason_msg
                })

        return missing_items
