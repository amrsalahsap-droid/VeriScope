import uuid
from typing import Dict, Any, List, Optional, Set

class SecuritySMEAnalyzer:
    """
    SecuritySMEAnalyzer detects security-sensitive changes and recommends security tests.
    
    Rules:
    - No speculative vulnerability claims without evidence.
    - Phrase all risk points and abuse cases as "should verify".
    - Cite changed files in each risk and abuse case.
    - Gracefully falls back when no security-sensitive capabilities or keywords are found.
    """

    CAPABILITY_KEYWORDS = {
        "password": ("password", "passphrase", "passwd"),
        "token": ("token", "jwt", "key", "secret", "session_token", "api_key"),
        "session": ("session", "cookie", "cookies", "sid"),
        "auth": ("auth", "authenticate", "credential", "credentials", "signin", "sign_in"),
        "permission": ("permission", "permissions", "role", "roles", "privilege", "privileges", "acl", "rbac", "authorize"),
        "reset": ("reset", "recovery", "forgot"),
        "signup": ("signup", "sign-up", "register", "registration", "onboarding"),
        "login": ("login", "signin", "sign-in"),
        "admin": ("admin", "administrator", "superadmin", "settings", "configuration"),
        "api auth boundary": ("api/", "route.ts", "route.js", "endpoints/", "controllers/", "router")
    }

    @classmethod
    def analyze(
        cls,
        changed_files: List[str],
        product_impact: Dict[str, Any],
        context_index: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Runs deterministic analysis on changed files, product impact capabilities,
        and context index to produce a SecurityAssessment.
        """
        detected_categories: Set[str] = set()
        evidence: List[str] = []

        # 1. Match from product impact capabilities
        capabilities = product_impact.get("affected_capabilities", [])
        for cap in capabilities:
            if cap == "unknown":
                continue
            if cap == "signup":
                detected_categories.update(["signup", "auth"])
                evidence.append("Capability 'signup' affected in ProductImpact")
            elif cap == "login":
                detected_categories.update(["login", "auth", "session", "token"])
                evidence.append("Capability 'login' affected in ProductImpact")
            elif cap == "password reset":
                detected_categories.update(["reset", "password", "token"])
                evidence.append("Capability 'password reset' affected in ProductImpact")
            elif cap == "admin/settings":
                detected_categories.update(["admin", "permission"])
                evidence.append("Capability 'admin/settings' affected in ProductImpact")
            elif cap in ("checkout", "subscription", "notifications", "profile/account"):
                detected_categories.add("api auth boundary")
                evidence.append(f"Capability '{cap}' indicates potential API Auth Boundary interaction in ProductImpact")

        # 2. Match from changed file paths
        for f in changed_files:
            f_lower = f.lower()
            for cat, keywords in cls.CAPABILITY_KEYWORDS.items():
                if any(kw in f_lower for kw in keywords):
                    detected_categories.add(cat)
                    evidence.append(f"Keyword match for security category '{cat}' in file: {f}")

        # 3. Match from context index security_sensitive_areas
        if context_index is not None and hasattr(context_index, "security_sensitive_areas") and context_index.security_sensitive_areas:
            for area in context_index.security_sensitive_areas:
                area_files = area.get("source_files", [])
                intersect = set(changed_files).intersection(set(area_files))
                if intersect:
                    detected_categories.update(["auth", "token"])
                    for f in sorted(list(intersect)):
                        evidence.append(f"Context index mapped file {f} to Security Sensitive Area '{area.get('name')}'")

        # Sort evidence for determinism
        sorted_evidence = sorted(list(set(evidence)))

        security_risks: List[str] = []
        abuse_cases: List[str] = []
        required_security_tests: List[str] = []
        suggested_test_data: Dict[str, Any] = {}

        # If no categories are detected, fallback gracefully
        if not detected_categories:
            return {
                "security_risks": ["should verify that modified files adhere to general secure coding standards"],
                "abuse_cases": ["An attacker exploits unspecified parameter validation gaps in modified modules to execute arbitrary logic"],
                "required_security_tests": ["Static Application Security Testing (SAST) linter checks"],
                "suggested_test_data": {},
                "evidence": ["Fallback: No explicit security-sensitive keywords or API boundaries detected in changed files or ProductImpact"]
            }

        # Select a representative changed file to cite in risks and abuse cases
        rep_file = changed_files[0] if changed_files else "None"

        # Populate risks, abuse cases, tests, and data based on detected categories
        # A. Password reset / reset / password changes
        if "reset" in detected_categories or "password" in detected_categories:
            security_risks.extend([
                f"should verify that weak passwords are rejected during reset in file: {rep_file}",
                f"should verify that expired reset tokens are rejected in file: {rep_file}",
                f"should verify that reused reset tokens are rejected in file: {rep_file}",
                f"should verify that invalid reset tokens are rejected in file: {rep_file}",
                f"should verify that account enumeration is prevented on reset endpoints in file: {rep_file}",
                f"should verify that old password is invalid after reset in file: {rep_file}"
            ])
            abuse_cases.extend([
                f"An attacker attempts to brute force or guess reset tokens to hijack user accounts (should verify invalid reset tokens are rejected in: {rep_file})",
                f"An attacker attempts to capture and replay a previously used reset token to change password (should verify reused token is rejected in: {rep_file})",
                f"An attacker attempts to harvest active accounts by submitting non-existent emails to the password reset endpoint (should verify enumeration protection in: {rep_file})"
            ])
            required_security_tests.extend([
                "Validation of weak, short, or common passwords during password reset flow",
                "Token lifecycle validation (verifying expired, invalid, and single-use/reused reset token rejection)",
                "Verification of old password invalidation post-reset"
            ])
            suggested_test_data.update({
                "weak_password": "123",
                "expired_token": "expired-reset-token-999",
                "invalid_token": "invalid-token-111",
                "reused_token": "reused-token-222"
            })

        # B. Signup changes
        if "signup" in detected_categories:
            security_risks.extend([
                f"should verify that registration with a pre-existing email is rejected in file: {rep_file}",
                f"should verify that signup inputs are sanitized and validated against injections in file: {rep_file}"
            ])
            abuse_cases.append(
                f"An attacker attempts automated script registration of bulk fake accounts to exhaust DB storage (should verify registration rate limits in: {rep_file})"
            )
            required_security_tests.extend([
                "Input sanitation testing for SQL Injection and Cross-Site Scripting (XSS) in registration forms",
                "Duplicate email constraint testing in signup flow"
            ])
            suggested_test_data.update({
                "existing_email": "existing@example.com",
                "malformed_email": "invalid-email@"
            })

        # C. Login changes
        if "login" in detected_categories:
            security_risks.extend([
                f"should verify that brute force login attempts trigger lockout/CAPTCHA in file: {rep_file}",
                f"should verify that login rejects disabled or inactive user accounts in file: {rep_file}"
            ])
            abuse_cases.append(
                f"An attacker attempts brute-force credential stuffing attacks against the authentication endpoint (should verify lockout mechanism in: {rep_file})"
            )
            required_security_tests.extend([
                "Rate limiting and automated attack resilience testing on authentication endpoints",
                "Harvesting threat assessment (verifying generic authentication errors prevent user enumeration)"
            ])
            suggested_test_data.update({
                "valid_signup": {"email": "newuser@example.com", "password": "StrongPass123!"}
            })

        # D. Session changes
        if "session" in detected_categories:
            security_risks.extend([
                f"should verify that session cookies have Secure, HttpOnly, and SameSite attributes enabled in file: {rep_file}",
                f"should verify that session is completely invalidated upon logout in file: {rep_file}"
            ])
            abuse_cases.append(
                f"An attacker attempts session hijacking via cross-site scripting (XSS) (should verify HttpOnly flags in: {rep_file})"
            )
            required_security_tests.append(
                "Cookie attributes inspection (Secure, HttpOnly, SameSite checks) in HTTP responses"
            )
            suggested_test_data.update({
                "expired_session_cookie": "session=expired_val"
            })

        # E. Token changes
        if "token" in detected_categories:
            security_risks.extend([
                f"should verify that session/JWT tokens are securely signed with strong keys in file: {rep_file}",
                f"should verify that authentication tokens are stored securely on the client side in file: {rep_file}"
            ])
            abuse_cases.append(
                f"An attacker attempts to forge credentials using altered signatures on JWTs (should verify token signature validation in: {rep_file})"
            )
            required_security_tests.append(
                "JWT integrity and signature validation testing"
            )
            suggested_test_data.update({
                "invalid_jwt": "header.payload.signature_invalid"
            })

        # F. Permission changes
        if "permission" in detected_categories:
            security_risks.extend([
                f"should verify that role-based access control (RBAC) permissions are strictly enforced on endpoints in file: {rep_file}",
                f"should verify that unauthorized privilege escalation attempts are blocked in file: {rep_file}"
            ])
            abuse_cases.append(
                f"A standard user attempts parameter tampering (Insecure Direct Object Reference) to access other users' accounts (should verify authorization in: {rep_file})"
            )
            required_security_tests.extend([
                "Role-Based Access Control (RBAC) matrix validation tests",
                "Privilege escalation boundary testing"
            ])
            suggested_test_data.update({
                "test_roles": ["member", "guest"]
            })

        # G. Admin changes
        if "admin" in detected_categories:
            security_risks.extend([
                f"should verify that only super-admin or authorized roles can modify system configurations in file: {rep_file}",
                f"should verify that admin settings actions are recorded in system audit logs in file: {rep_file}"
            ])
            abuse_cases.append(
                f"An unauthenticated user attempts to access administrative configurations by direct URL navigation (should verify RBAC controls in: {rep_file})"
            )
            suggested_test_data.update({
                "admin_payload": {"maintenance_mode": True}
            })

        # H. Auth changes
        if "auth" in detected_categories:
            security_risks.extend([
                f"should verify that credentials are sent over encrypted TLS connections in file: {rep_file}",
                f"should verify that authentication endpoints return generic error messages to prevent credential harvesting in file: {rep_file}"
            ])
            suggested_test_data.update({
                "injection_payload": "admin' OR 1=1--"
            })

        # I. API Auth Boundary changes
        if "api auth boundary" in detected_categories:
            security_risks.extend([
                f"should verify that public API routes are strictly rate-limited to prevent DOS in file: {rep_file}",
                f"should verify that unauthorized access to protected API paths returns 401/403 status in file: {rep_file}"
            ])
            abuse_cases.append(
                f"An unauthenticated client attempts to query sensitive database records via direct API endpoints (should verify endpoint authentication in: {rep_file})"
            )
            required_security_tests.extend([
                "Authorization header presence and token validity testing on private routes",
                "API Rate limit threshold tests"
            ])

        # Deduplicate and sort lists for clean output
        def dedup(lst: List[str]) -> List[str]:
            seen = set()
            res = []
            for x in lst:
                if x not in seen:
                    seen.add(x)
                    res.append(x)
            return res

        return {
            "security_risks": dedup(security_risks),
            "abuse_cases": dedup(abuse_cases),
            "required_security_tests": dedup(required_security_tests),
            "suggested_test_data": suggested_test_data,
            "evidence": sorted_evidence
        }
