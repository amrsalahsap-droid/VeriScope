from typing import List, Dict, Any, Optional


class BehaviorImpactLevelCalculator:
    """Calculates impact level, explainable reason and confidence for behavior-level changes."""

    @classmethod
    def calculate_impact_level(
        cls,
        behavior_name: str,
        behavior_risk_level: str,  # LOW, MEDIUM, HIGH, CRITICAL
        impacted_files: List[str],
        file_statuses: Optional[Dict[str, str]] = None,  # file_path -> "modified"|"added"|"deleted"
        additions: int = 0,
        deletions: int = 0,
        touched_layers: Optional[List[str]] = None,      # e.g., ["API", "UI", "Database", "Service"]
        related_journey_risk: str = "MEDIUM",            # LOW, MEDIUM, HIGH, CRITICAL
        security_sensitivity: bool = False,
        historical_fragility: bool = False,
        match_signal_type: str = "TOKEN_MATCH",
    ) -> Dict[str, Any]:
        """Convert behavior matches and code metadata into a business-oriented impact level."""
        # Initialize defaults
        impact_level = "LOW"
        reasons = []
        confidence = "LOW"

        # Normalize inputs
        b_name_lower = behavior_name.lower()
        risk_level = (behavior_risk_level or "MEDIUM").upper()
        j_risk = (related_journey_risk or "MEDIUM").upper()
        layers = [layer.upper() for layer in (touched_layers or [])]

        # 1. Analyze file types
        is_tests_only = len(impacted_files) > 0 and all(
            "test" in f.lower() or "spec" in f.lower() for f in impacted_files
        )
        is_docs_only = len(impacted_files) > 0 and all(
            "doc" in f.lower() or "readme" in f.lower() or f.endswith(".md") for f in impacted_files
        )
        is_config_only = len(impacted_files) > 0 and all(
            f.endswith(".json") or f.endswith(".yaml") or f.endswith(".yml") or "config" in f.lower()
            for f in impacted_files
        )

        # Detect specific layers in file paths if touched_layers is empty
        if not layers:
            for f in impacted_files:
                f_lower = f.lower()
                if "api/" in f_lower or "route" in f_lower or "endpoint" in f_lower:
                    layers.append("API")
                if "db/" in f_lower or "schema" in f_lower or "models/" in f_lower or "migration" in f_lower:
                    layers.append("DATABASE")
                if "service" in f_lower or "logic" in f_lower or "utils" in f_lower:
                    layers.append("SERVICE")
                if "pages/" in f_lower or "ui" in f_lower or "component" in f_lower or "form" in f_lower or "view" in f_lower:
                    layers.append("UI")
            layers = list(set(layers))

        # Check for core functional code changes
        has_logic_change = not (is_tests_only or is_docs_only or is_config_only)

        # Calculate base confidence based on signals and direct mapping
        if match_signal_type in ["DIRECT_EVIDENCE", "PATH_SUFFIX"]:
            confidence = "HIGH"
        elif match_signal_type in ["ROUTE_PAGE_MODULE", "TOKEN_MATCH"]:
            confidence = "MODERATE"
        else:
            confidence = "LOW"

        # Apply rules in cascading order of severity:

        # STAGE 1: CRITICAL RULE CHECK
        is_billing_checkout = any(k in b_name_lower for k in ["billing", "payment", "checkout", "subscription"])
        is_security_permission = any(k in b_name_lower for k in ["security", "admin", "permission", "authorization"])
        has_api_service_db_change = any(l in layers for l in ["API", "SERVICE", "DATABASE"])

        if has_logic_change and (
            (risk_level == "CRITICAL" and has_api_service_db_change) or
            (is_billing_checkout and has_api_service_db_change) or
            (is_security_permission and risk_level == "CRITICAL")
        ):
            impact_level = "CRITICAL"
            reasons.append(f"Critical behavior '{behavior_name}' modified at core backend layer (API/Service/Database)")
            if security_sensitivity:
                reasons.append("Change alters high-risk security permission flows")
            if historical_fragility:
                reasons.append("Behavior is historically fragile / prone to regression")

        # STAGE 2: HIGH RULE CHECK
        elif has_logic_change and (
            any(k in b_name_lower for k in ["auth", "password", "token", "session"]) or
            (any(k in b_name_lower for k in ["signup", "registration", "reset-password"]) and "API" in layers) or
            (risk_level == "HIGH" and match_signal_type in ["DIRECT_EVIDENCE", "PATH_SUFFIX"]) or
            (risk_level in ["CRITICAL", "HIGH"] and security_sensitivity)
        ):
            impact_level = "HIGH"
            if any(k in b_name_lower for k in ["auth", "password", "token", "session"]):
                reasons.append("Modifies sensitive user session, token, or auth controls")
            elif any(k in b_name_lower for k in ["signup", "registration", "reset-password"]) and "API" in layers:
                reasons.append("Modifies public user registration or reset password API contracts")
            else:
                reasons.append(f"High risk behavior '{behavior_name}' directly impacted by PR changes")

        # STAGE 3: MEDIUM RULE CHECK
        elif has_logic_change and (
            "UI" in layers or
            risk_level == "MEDIUM" or
            j_risk in ["HIGH", "CRITICAL"]
        ):
            impact_level = "MEDIUM"
            if "UI" in layers:
                reasons.append(f"User journey page or frontend form component changed for behavior '{behavior_name}'")
            else:
                reasons.append(f"Behavior change for '{behavior_name}' with medium baseline business risk")

        # STAGE 4: LOW RULE CHECK
        else:
            impact_level = "LOW"
            if is_docs_only:
                reasons.append("Documentation-only changes (no logical impact)")
            elif is_tests_only:
                reasons.append("Tests-only modifications (does not affect runtime coverage)")
            elif is_config_only:
                reasons.append("Minor non-operational configuration changes")
            else:
                reasons.append("Minor logical change with low risk context")

        # Return impact envelope
        return {
            "impact_level": impact_level,
            "impact_reason": " / ".join(reasons),
            "confidence": confidence,
        }
