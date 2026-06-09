from typing import Dict, Any, List, Optional, Set
import re
from app.models.project_context_index import ProjectContextIndex

class ProductSMEAnalyzer:
    """
    ProductSMEAnalyzer infers product capabilities and user journeys affected by changes.
    Combines static context (ProjectContextIndex) and real-time pull request evidence.
    """

    @classmethod
    def analyze(
        cls,
        context_index: Optional[ProjectContextIndex],
        changed_files: List[str],
        pr_title: str,
        pr_description: str
    ) -> Dict[str, Any]:
        """
        Runs deterministic analysis on changed files, context index, and PR metadata.
        Returns a structured ProductImpact dictionary.
        """
        pr_title = pr_title or ""
        pr_description = pr_description or ""
        combined_text = f"{pr_title}\n{pr_description}".lower()

        affected_user_journeys: List[Dict[str, Any]] = []
        affected_capabilities: Set[str] = set()
        evidence: List[str] = []

        # Define 8 standard capabilities and their user journeys and keyword mappings
        rules = {
            "signup": {
                "journey": "User Registration Flow",
                "keywords": ("signup", "sign-up", "register", "registration", "onboarding")
            },
            "login": {
                "journey": "User Authentication Flow",
                "keywords": ("login", "signin", "sign-in", "auth", "session", "jwt", "token")
            },
            "password reset": {
                "journey": "Password Recovery Flow",
                "keywords": ("reset-password", "reset_password", "forgot-password", "forgot_password", "password/reset", "password-reset")
            },
            "checkout": {
                "journey": "Payment Checkout Flow",
                "keywords": ("checkout", "payment", "stripe", "checkout-form", "pay")
            },
            "subscription": {
                "journey": "Subscription Billing Flow",
                "keywords": ("subscription", "subscribe", "plan", "invoice", "billing")
            },
            "notifications": {
                "journey": "Notification Dispatch Flow",
                "keywords": ("notification", "notify", "email", "mail", "sms", "alert")
            },
            "profile/account": {
                "journey": "User Profile Modification Flow",
                "keywords": ("profile", "account", "user-profile", "avatar", "settings/profile")
            },
            "admin/settings": {
                "journey": "Administrative Control Flow",
                "keywords": ("admin", "settings", "control-panel", "configuration", "system-settings")
            }
        }

        # 1. Inspect ProjectContextIndex for high-fidelity matches if available
        if context_index:
            # Check user_journeys in index
            index_journeys = context_index.user_journeys or []
            for j_item in index_journeys:
                j_name = j_item.get("name")
                j_files = j_item.get("source_files", [])
                
                # If any of the changed files are associated with this user journey in the index
                intersect = set(changed_files).intersection(set(j_files))
                if intersect:
                    # Find corresponding capability
                    cap_found = "unknown"
                    for cap, rule_info in rules.items():
                        if rule_info["journey"].lower() == j_name.lower():
                            cap_found = cap
                            break
                    
                    for f in sorted(list(intersect)):
                        affected_user_journeys.append({
                            "journey": j_name,
                            "source_file": f,
                            "confidence": "HIGH"
                        })
                        evidence.append(f"Context index mapped {f} to {j_name}")
                        if cap_found != "unknown":
                            affected_capabilities.add(cap_found)

            # Check domains in index
            index_domains = context_index.domains or []
            for d_item in index_domains:
                d_name = d_item.get("name")
                d_files = d_item.get("source_files", [])
                
                intersect = set(changed_files).intersection(set(d_files))
                if intersect:
                    # Map domain to standard capability
                    cap_map = {
                        "Authentication & Identity": "login",
                        "Billing & Subscription": "subscription",
                        "GitHub Integration": "admin/settings",
                        "Observability & Monitoring": "admin/settings"
                    }
                    cap = cap_map.get(d_name)
                    if cap:
                        affected_capabilities.add(cap)
                        for f in sorted(list(intersect)):
                            journey_name = rules[cap]["journey"]
                            # Avoid duplicates
                            if not any(x["journey"] == journey_name and x["source_file"] == f for x in affected_user_journeys):
                                affected_user_journeys.append({
                                    "journey": journey_name,
                                    "source_file": f,
                                    "confidence": "HIGH"
                                })
                                evidence.append(f"Context index mapped domain {d_name} to file {f}")

        # 2. File path-based matching (for all changed files)
        for f in changed_files:
            f_lower = f.lower()
            for cap, rule in rules.items():
                if any(kw in f_lower for kw in rule["keywords"]):
                    affected_capabilities.add(cap)
                    journey_name = rule["journey"]
                    # Add if not already present from context index
                    if not any(x["journey"] == journey_name and x["source_file"] == f for x in affected_user_journeys):
                        affected_user_journeys.append({
                            "journey": journey_name,
                            "source_file": f,
                            "confidence": "HIGH"
                        })
                        evidence.append(f"File path match: '{f}' contains keyword associated with {journey_name}")

        # 3. PR Title and Description text-based matching
        for cap, rule in rules.items():
            journey_name = rule["journey"]
            # Look for word-boundary matches in combined_text
            for kw in rule["keywords"]:
                clean_kw = kw.replace("-", " ").replace("_", " ")
                if re.search(rf"\b{re.escape(clean_kw)}\b", combined_text) or re.search(rf"\b{re.escape(kw)}\b", combined_text):
                    affected_capabilities.add(cap)
                    # Citing the PR title/description as evidence
                    # Add a general journey item if none exist for this journey
                    if not any(x["journey"] == journey_name for x in affected_user_journeys):
                        # Find a representative file in changed files or default to None
                        source_f = "None"
                        for f in changed_files:
                            if any(k in f.lower() for k in rule["keywords"]):
                                source_f = f
                                break
                        
                        affected_user_journeys.append({
                            "journey": journey_name,
                            "source_file": source_f,
                            "confidence": "MODERATE"
                        })
                        evidence.append(f"PR metadata match: '{kw}' keyword detected in title/description")

        # Sort lists for determinism
        sorted_journeys = sorted(
            affected_user_journeys, 
            key=lambda x: (x["journey"], x["source_file"])
        )
        sorted_caps = sorted(list(affected_capabilities))
        sorted_evidence = sorted(list(set(evidence)))

        # Fallback to unknown if nothing is detected
        if not sorted_journeys:
            sorted_journeys = [{
                "journey": "unknown",
                "source_file": "None",
                "confidence": "LOW"
            }]
            sorted_caps = ["unknown"]
            business_impact_summary = "No specific product user journeys or capabilities were identified as affected by this change."
            confidence = "LOW"
        else:
            # Build business impact summary
            journey_names = sorted(list(set(x["journey"] for x in sorted_journeys)))
            business_impact_summary = (
                f"This pull request directly impacts key product capabilities: {', '.join(sorted_caps)}. "
                f"Changes affect the following critical user journeys: {', '.join(journey_names)}."
            )
            # Confidence calculation
            if any(x["confidence"] == "HIGH" for x in sorted_journeys):
                confidence = "HIGH"
            elif any(x["confidence"] == "MODERATE" for x in sorted_journeys):
                confidence = "MODERATE"
            else:
                confidence = "LOW"

        return {
            "affected_user_journeys": sorted_journeys,
            "affected_capabilities": sorted_caps,
            "business_impact_summary": business_impact_summary,
            "confidence": confidence,
            "evidence": sorted_evidence
        }
