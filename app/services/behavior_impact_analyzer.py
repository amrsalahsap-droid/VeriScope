from typing import List, Dict, Any, Optional, Set
import re
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.behavior import Behavior
from app.models.behavior_evidence import BehaviorEvidence
from app.models.behavior_scenario import BehaviorScenario
from app.models.journey_behavior import JourneyBehavior
from app.models.journey import Journey
from app.models.journey_relationship import JourneyRelationship
from app.config import settings


class BehaviorImpactAnalyzer:
    """Deterministic, evidence-backed analyzer to identify impacted business behaviors for a PR."""

    # File path to behavior keyword mapping
    FILE_BEHAVIOR_KEYWORDS = {
        "auth": ["Authentication", "Login", "Logout", "Session"],
        "login": ["Authentication", "Login"],
        "logout": ["Authentication", "Logout"],
        "password": ["Authentication", "Password Reset", "Password Recovery"],
        "reset": ["Authentication", "Password Reset", "Password Recovery"],
        "signup": ["Registration", "Signup", "User Registration"],
        "register": ["Registration", "Signup", "User Registration"],
        "subscription": ["Billing", "Subscription", "Subscription Lifecycle"],
        "billing": ["Billing", "Invoice", "Payment"],
        "invoice": ["Billing", "Invoice"],
        "payment": ["Billing", "Payment", "Payment Processing"],
        "notification": ["Notifications", "Email", "Push", "SMS"],
        "email": ["Notifications", "Email"],
        "push": ["Notifications", "Push"],
        "admin": ["Administration", "User Management", "Role Management"],
        "report": ["Reporting", "Analytics", "Dashboard"],
        "analytics": ["Reporting", "Analytics"],
    }

    def __init__(self, db: Optional[Session] = None):
        """Initialize the behavior impact analyzer with optional database session."""
        self.db = db

    def analyze_behavior_impact(
        self,
        repository_id: Any,
        pull_request_id: Optional[Any],
        changed_files: List[str],
        behaviors: List[Behavior],
        behavior_evidences: List[BehaviorEvidence],
        behavior_scenarios: List[BehaviorScenario],
        journey_behaviors: List[JourneyBehavior],
        journeys: List[Journey],
        journey_relationships: List[JourneyRelationship] = [],
        pr_title: Optional[str] = None,
        pr_description: Optional[str] = None,
        architecture_impact: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Identify which business behaviors are impacted by a PR."""
        impacted_behaviors = []
        impacted_journey_set = set()

        # Gather behavior mapping components
        behavior_evidence_map = self._build_behavior_evidence_map(behavior_evidences)
        behavior_scenarios_map = self._build_behavior_scenarios_map(behavior_scenarios)
        behavior_to_journeys = self._build_behavior_to_journeys_map(journey_behaviors, journeys)

        # Use ChangedFileBehaviorMatcher to perform multi-stage matching
        from app.services.changed_file_behavior_matcher import ChangedFileBehaviorMatcher
        matcher = ChangedFileBehaviorMatcher(db=self.db)
        
        # Enrich changed files with architecture impact if available
        enriched_changed_files = changed_files
        if architecture_impact and settings.USE_ARCHITECTURE_V2:
            enriched_changed_files = architecture_impact.get("impacted_files", changed_files)
        
        file_matches = matcher.match_changed_files(
            changed_files=enriched_changed_files,
            behaviors=behaviors,
            evidences=behavior_evidences,
            journey_behaviors=journey_behaviors,
            journeys=journeys,
        )

        # Process matching results into the final structure
        for match in file_matches:
            behavior = next((b for b in behaviors if str(b.id) == match["behavior_id"]), None)
            if not behavior:
                continue
                
            b_id_str = str(behavior.id)
            evidences = behavior_evidence_map.get(b_id_str, [])
            scenarios = behavior_scenarios_map.get(b_id_str, [])
            mapped_journeys = behavior_to_journeys.get(b_id_str, [])
            
            # Map affected scenarios
            affected_scenarios_list = [
                {
                    "id": str(s.id),
                    "title": s.title,
                    "priority": s.priority,
                    "scenario_type": s.scenario_type,
                }
                for s in scenarios
            ]
            
            # Check if this behavior is already added to impacted_behaviors
            existing = next((ib for ib in impacted_behaviors if ib["behavior_id"] == b_id_str), None)
            if existing:
                if match["file_path"] not in existing["impacted_files"]:
                    existing["impacted_files"].append(match["file_path"])
                if match["signal_type"] not in existing["source_signals"]:
                    existing["source_signals"].append(match["signal_type"])
                # Elevate impact level / confidence if needed
                level_weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
                if level_weights[match["confidence"].replace("MODERATE", "MEDIUM")] > level_weights[existing["confidence"].replace("MODERATE", "MEDIUM")]:
                    existing["confidence"] = match["confidence"]
                continue

            # Identify journey_id if mapped
            journey_id = None
            if mapped_journeys:
                journey_id = str(mapped_journeys[0].id)

            # Match matched evidences for this behavior
            matched_evidence_list = []
            for ev in evidences:
                if ev.source_path and ev.source_path.lower() in match["file_path"].lower():
                    matched_evidence_list.append({
                        "evidence_type": ev.evidence_type,
                        "source_path": ev.source_path,
                        "confidence": ev.confidence,
                        "excerpt": ev.excerpt,
                    })

            # Require at least one evidence reason
            impact_reason = match["reason"]
            if not matched_evidence_list and evidences:
                matched_evidence_list.append({
                    "evidence_type": evidences[0].evidence_type,
                    "source_path": evidences[0].source_path,
                    "confidence": evidences[0].confidence,
                    "excerpt": evidences[0].excerpt,
                })

            # Derive impact level and reason from BehaviorImpactLevelCalculator
            from app.services.behavior_impact_level_calculator import BehaviorImpactLevelCalculator
            
            # Determine related journey risk
            journey_risk = "MEDIUM"
            if mapped_journeys:
                journey_risk = mapped_journeys[0].risk_level if hasattr(mapped_journeys[0], "risk_level") else "MEDIUM"
                
            impact_envelope = BehaviorImpactLevelCalculator.calculate_impact_level(
                behavior_name=behavior.name,
                behavior_risk_level=behavior.risk_level,
                impacted_files=[match["file_path"]],
                related_journey_risk=journey_risk,
                security_sensitivity=behavior.risk_level == "CRITICAL" or any(k in behavior.name.lower() for k in ["auth", "security", "permission"]),
                historical_fragility="reset" in behavior.slug or "billing" in behavior.slug,
                match_signal_type=match["signal_type"],
            )
            
            impact_level = impact_envelope["impact_level"]
            impact_reason = impact_envelope["impact_reason"] or impact_reason

            # Classify impact_type: DIRECT if evidence path or test reference, INDIRECT otherwise
            direct_signal_types = {"EVIDENCE_PATH_MATCH", "TEST_REFERENCE_MATCH", "DIRECT_FILE_MATCH"}
            impact_type = "DIRECT" if match["signal_type"] in direct_signal_types else "INDIRECT"

            impacted_behaviors.append({
                "behavior_id": b_id_str,
                "behavior_name": behavior.name,
                "journey_id": journey_id,
                "impact_type": impact_type,
                "impact_level": impact_level,
                "impact_reason": impact_reason,
                "impacted_files": [match["file_path"]],
                "matched_evidence": matched_evidence_list,
                "affected_scenarios": affected_scenarios_list,
                "confidence": match["confidence"],
                "behavior_confidence": behavior.confidence or "MEDIUM",
                "behavior_risk_level": behavior.risk_level or "MEDIUM",
                "source_signals": [match["signal_type"]],
            })

            # Register affected journeys
            for journey in mapped_journeys:
                impacted_journey_set.add((str(journey.id), journey.name))

        # Use JourneyRelationshipEngine to expand impact across journeys
        if journey_relationships:
            expanded_journeys = self._expand_journey_impact(
                affected_journeys=list(impacted_journey_set),
                relationships=journey_relationships,
            )
            for j_id, j_name in expanded_journeys:
                impacted_journey_set.add((j_id, j_name))

        # Construct impacted journeys output
        impacted_journeys_list = [
            {"journey_id": j_id, "journey_name": j_name}
            for j_id, j_name in impacted_journey_set
        ]

        # Calculate aggregate confidence
        overall_confidence = "LOW"
        if impacted_behaviors:
            high_conf_count = sum(1 for b in impacted_behaviors if b["confidence"] == "HIGH")
            if high_conf_count / len(impacted_behaviors) >= 0.7:
                overall_confidence = "HIGH"
            elif high_conf_count / len(impacted_behaviors) >= 0.4:
                overall_confidence = "MODERATE"

        # Generate impact summary
        impact_summary = self._generate_impact_summary(impacted_behaviors)

        return {
            "repository_id": str(repository_id),
            "pull_request_id": str(pull_request_id) if pull_request_id else None,
            "impacted_behaviors": impacted_behaviors,
            "impacted_journeys": impacted_journeys_list,
            "impact_summary": impact_summary,
            "confidence": overall_confidence,
        }

    def _evaluate_behavior_impact(
        self,
        behavior: Behavior,
        changed_files: List[str],
        evidences: List[BehaviorEvidence],
        pr_title: Optional[str] = None,
        pr_description: Optional[str] = None,
    ) -> tuple:
        """Evaluate if behavior is impacted using deterministic rules."""
        matched_evidence = []
        source_signals = []
        impact_reasons = []

        # Rule 1: Changed file directly matches behavior evidence
        for file_path in changed_files:
            file_lower = file_path.lower()
            for ev in evidences:
                if ev.source_path and ev.source_path.lower() in file_lower:
                    matched_evidence.append(ev)
                    source_signals.append("EVIDENCE_PATH_MATCH")
                    impact_reasons.append(f"Changed file {file_path} matches discovered evidence source {ev.source_path}")

        # Rule 2: Changed file path tokens match behavior slug/name
        for file_path in changed_files:
            file_lower = file_path.lower()
            slug_clean = behavior.slug.lower().replace("-", " ")
            name_clean = behavior.name.lower()
            
            if slug_clean in file_lower or name_clean in file_lower:
                source_signals.append("PATH_TOKEN_MATCH")
                impact_reasons.append(f"File path {file_path} matches behavior name/slug token '{behavior.name}'")

            # Keyword matching from FILE_BEHAVIOR_KEYWORDS
            for kw, behavior_keywords in self.FILE_BEHAVIOR_KEYWORDS.items():
                if kw in file_lower and any(bk.lower() in name_clean for bk in behavior_keywords):
                    source_signals.append("HEURISTIC_KEYWORD_MATCH")
                    impact_reasons.append(f"File path {file_path} contains heuristic keyword '{kw}' associated with {behavior.name}")

        # Rule 3: PR title/description matches behavior terms
        pr_text = f"{pr_title or ''} {pr_description or ''}".lower()
        if pr_text.strip():
            slug_clean = behavior.slug.lower().replace("-", " ")
            name_clean = behavior.name.lower()
            if slug_clean in pr_text or name_clean in pr_text:
                source_signals.append("PR_METADATA_MATCH")
                impact_reasons.append(f"PR metadata matches behavior descriptor '{behavior.name}'")

        # Rule 4: Test file change references behavior
        for file_path in changed_files:
            file_lower = file_path.lower()
            if "test" in file_lower:
                name_clean = behavior.name.lower().replace(" ", "")
                slug_clean = behavior.slug.lower().replace("-", "")
                if name_clean in file_lower or slug_clean in file_lower:
                    source_signals.append("TEST_REFERENCE_MATCH")
                    impact_reasons.append(f"Test file change {file_path} references behavior '{behavior.name}'")

        # Determine output
        if not source_signals:
            return None, None, [], "LOW", []

        # Deduplicate signals and reasons
        source_signals = list(set(source_signals))
        impact_reasons = list(set(impact_reasons))

        # Confidence assessment
        confidence = "LOW"
        if len(source_signals) >= 3 or ("EVIDENCE_PATH_MATCH" in source_signals and len(source_signals) >= 2):
            confidence = "HIGH"
        elif len(source_signals) >= 2:
            confidence = "MODERATE"

        # Determine impact level based on behavior risk level and signal strength
        risk_level = behavior.risk_level or "MEDIUM"
        if risk_level == "CRITICAL" and confidence in ["HIGH", "MODERATE"]:
            impact_level = "CRITICAL"
        elif risk_level in ["HIGH", "CRITICAL"] or confidence == "HIGH":
            impact_level = "HIGH"
        elif risk_level == "MEDIUM" or confidence == "MODERATE":
            impact_level = "MEDIUM"
        else:
            impact_level = "LOW"

        reason = " / ".join(impact_reasons)
        return impact_level, reason, matched_evidence, confidence, source_signals

    def _file_matches_behavior(self, file_path: str, behavior: Behavior, evidences: List[BehaviorEvidence]) -> bool:
        """Check if file matches behavior patterns or evidence."""
        file_lower = file_path.lower()
        slug_clean = behavior.slug.lower().replace("-", " ")
        name_clean = behavior.name.lower()
        
        if slug_clean in file_lower or name_clean in file_lower:
            return True
            
        for ev in evidences:
            if ev.source_path and ev.source_path.lower() in file_lower:
                return True

        for kw, behavior_keywords in self.FILE_BEHAVIOR_KEYWORDS.items():
            if kw in file_lower and any(bk.lower() in name_clean for bk in behavior_keywords):
                return True
                
        return False

    def _expand_journey_impact(
        self,
        affected_journeys: List[tuple],
        relationships: List[JourneyRelationship],
    ) -> List[tuple]:
        """Expand journey impact across defined journey relationships (e.g. DEPENDS_ON)."""
        expanded = []
        affected_ids = [j_id for j_id, _ in affected_journeys]

        for rel in relationships:
            source_id = str(rel.source_journey_id)
            target_id = str(rel.target_journey_id)

            if source_id in affected_ids and target_id not in affected_ids:
                if rel.target_journey:
                    expanded.append((target_id, rel.target_journey.name))
            if target_id in affected_ids and source_id not in affected_ids and rel.relationship_type == "DEPENDS_ON":
                if rel.source_journey:
                    expanded.append((source_id, rel.source_journey.name))

        return expanded

    def _build_behavior_evidence_map(self, evidences: List[BehaviorEvidence]) -> Dict[str, List[BehaviorEvidence]]:
        """Group evidence list by behavior ID."""
        evidence_map = {}
        for ev in evidences:
            b_id = str(ev.behavior_id)
            if b_id not in evidence_map:
                evidence_map[b_id] = []
            evidence_map[b_id].append(ev)
        return evidence_map

    def _build_behavior_scenarios_map(self, scenarios: List[BehaviorScenario]) -> Dict[str, List[BehaviorScenario]]:
        """Group scenarios list by behavior ID."""
        scenarios_map = {}
        for s in scenarios:
            b_id = str(s.behavior_id)
            if b_id not in scenarios_map:
                scenarios_map[b_id] = []
            scenarios_map[b_id].append(s)
        return scenarios_map

    def _build_behavior_to_journeys_map(
        self,
        journey_behaviors: List[JourneyBehavior],
        journeys: List[Journey],
    ) -> Dict[str, List[Journey]]:
        """Map behavior IDs to list of associated Journeys."""
        b_map = {}
        journey_dict = {str(j.id): j for j in journeys}

        for jb in journey_behaviors:
            b_id = str(jb.behavior_id)
            j_id = str(jb.journey_id)
            if b_id not in b_map:
                b_map[b_id] = []
            if j_id in journey_dict:
                b_map[b_id].append(journey_dict[j_id])

        return b_map

    def _generate_impact_summary(self, impacted_behaviors: List[Dict]) -> str:
        """Create a high-level summarized string of behavior impact."""
        if not impacted_behaviors:
            return "No behavior impact detected."

        critical_count = sum(1 for b in impacted_behaviors if b["impact_level"] == "CRITICAL")
        high_count = sum(1 for b in impacted_behaviors if b["impact_level"] == "HIGH")
        medium_count = sum(1 for b in impacted_behaviors if b["impact_level"] == "MEDIUM")
        low_count = sum(1 for b in impacted_behaviors if b["impact_level"] == "LOW")

        levels = []
        if critical_count > 0:
            levels.append(f"{critical_count} CRITICAL")
        if high_count > 0:
            levels.append(f"{high_count} HIGH")
        if medium_count > 0:
            levels.append(f"{medium_count} MEDIUM")
        if low_count > 0:
            levels.append(f"{low_count} LOW")

        summary = f"Pull Request impacts {len(impacted_behaviors)} business behaviors ({', '.join(levels)}). "
        
        # Add primary impacted behavior example
        sorted_behaviors = sorted(impacted_behaviors, key=lambda x: {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}[x["impact_level"]], reverse=True)
        prime = sorted_behaviors[0]
        summary += f"Primary impact detected on behavior '{prime['behavior_name']}' with {prime['impact_level']} risk."
        
        return summary
