"""Business Behavior Mapper service.

Maps extracted business intent and acceptance criteria to Behavior Catalog
and BehaviorScenario using synonym/domain vocabulary matching.
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import uuid

from app.models.business_behavior_mapping import BusinessBehaviorMapping
from app.models.behavior import Behavior
from app.models.behavior_scenario import BehaviorScenario
from app.models.journey import Journey
from app.models.acceptance_criterion import AcceptanceCriterion


class BusinessBehaviorMapper:
    """Maps acceptance criteria to behaviors and scenarios."""
    
    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    MEDIUM_CONFIDENCE_THRESHOLD = 0.5
    LOW_CONFIDENCE_THRESHOLD = 0.2
    
    # Synonym mappings for behavior matching
    BEHAVIOR_SYNONYMS = {
        "password": ["credential", "auth", "authentication", "login", "security"],
        "reset": ["recover", "restore", "change", "update"],
        "registration": ["signup", "sign-up", "register", "create account", "onboarding"],
        "validation": ["verify", "check", "validate", "confirm", "ensure"],
        "billing": ["payment", "invoice", "subscription", "pricing"],
        "notification": ["email", "alert", "message", "push", "sms"],
        "user": ["customer", "account", "profile", "member"],
        "admin": ["administrator", "management", "settings", "configuration"],
    }
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the mapper with optional database session."""
        self.db = db
    
    def map_acceptance_criteria_to_behaviors(
        self,
        acceptance_criteria: List[AcceptanceCriterion],
        behaviors: List[Behavior],
        scenarios: List[BehaviorScenario],
        journeys: List[Journey],
        domain_vocabulary: Optional[Dict[str, List[str]]] = None
    ) -> List[BusinessBehaviorMapping]:
        """Map acceptance criteria to behaviors and scenarios.
        
        Returns:
            List of BusinessBehaviorMapping objects
        """
        mappings = []
        
        # Build behavior and scenario lookup maps
        behavior_map = {str(b.id): b for b in behaviors}
        scenario_map = {str(s.id): s for s in scenarios}
        journey_map = {str(j.id): j for j in journeys}
        
        # Build behavior scenarios by behavior
        scenarios_by_behavior = {}
        for scenario in scenarios:
            b_id = str(scenario.behavior_id)
            if b_id not in scenarios_by_behavior:
                scenarios_by_behavior[b_id] = []
            scenarios_by_behavior[b_id].append(scenario)
        
        for ac in acceptance_criteria:
            # Map to behavior
            behavior_match = self._match_to_behavior(ac.text, behaviors, domain_vocabulary)
            
            if not behavior_match:
                # No behavior match, skip
                continue
            
            behavior_id, behavior_confidence, matched_terms, reason = behavior_match
            
            # Get behavior object
            behavior = behavior_map.get(behavior_id)
            if not behavior:
                continue
            
            # Map to scenario
            scenario_match = self._match_to_scenario(
                ac.text, 
                scenarios_by_behavior.get(behavior_id, []),
                domain_vocabulary
            )
            
            if scenario_match:
                scenario_id, scenario_confidence, scenario_matched_terms, scenario_reason = scenario_match
            else:
                # No scenario match - create candidate missing scenario
                scenario_id = None
                scenario_confidence = 0.0
                scenario_matched_terms = []
                scenario_reason = "No matching scenario found - candidate missing scenario"
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(
                behavior_confidence, 
                scenario_confidence
            )
            
            # Create mapping
            mapping = BusinessBehaviorMapping(
                id=uuid.uuid4(),
                acceptance_criterion_id=ac.id,
                behavior_id=behavior_id,
                behavior_scenario_id=scenario_id,
                journey_id=behavior.journey_id,
                match_confidence=overall_confidence,
                matched_terms=matched_terms + scenario_matched_terms,
                reason=f"{reason}. {scenario_reason}",
                is_candidate_missing_scenario="true" if scenario_id is None else "false",
            )
            
            mappings.append(mapping)
        
        return mappings
    
    def _match_to_behavior(
        self,
        text: str,
        behaviors: List[Behavior],
        domain_vocabulary: Optional[Dict[str, List[str]]] = None
    ) -> Optional[Tuple[str, float, List[str], str]]:
        """Match text to a behavior."""
        text_lower = text.lower()
        
        best_match = None
        best_confidence = 0.0
        best_matched_terms = []
        best_reason = ""
        
        for behavior in behaviors:
            confidence, matched_terms, reason = self._calculate_behavior_match(
                text_lower, behavior, domain_vocabulary
            )
            
            if confidence > best_confidence:
                best_match = str(behavior.id)
                best_confidence = confidence
                best_matched_terms = matched_terms
                best_reason = reason
        
        if best_confidence < self.LOW_CONFIDENCE_THRESHOLD:
            return None
        
        return best_match, best_confidence, best_matched_terms, best_reason
    
    def _calculate_behavior_match(
        self,
        text: str,
        behavior: Behavior,
        domain_vocabulary: Optional[Dict[str, List[str]]] = None
    ) -> Tuple[float, List[str], str]:
        """Calculate match confidence between text and behavior."""
        behavior_name_lower = behavior.name.lower()
        behavior_desc_lower = (behavior.description or "").lower()
        
        matched_terms = []
        confidence = 0.0
        reason = ""
        
        # Check for direct behavior name match
        if behavior_name_lower in text:
            confidence += 0.6
            matched_terms.append(behavior.name)
            reason = f"Direct behavior name match: {behavior.name}"
        
        # Check for partial name match
        for word in behavior_name_lower.split():
            if word in text and len(word) > 3:
                confidence += 0.2
                matched_terms.append(word)
                if not reason:
                    reason = f"Partial behavior name match: {word}"
        
        # Check description keywords
        for word in behavior_desc_lower.split():
            if word in text and len(word) > 3:
                confidence += 0.1
                matched_terms.append(word)
        
        # Check synonym matches
        for term, synonyms in self.BEHAVIOR_SYNONYMS.items():
            all_synonyms = [term] + synonyms
            # Find which synonyms are in the behavior name
            matching_in_behavior = [s for s in all_synonyms if s in behavior_name_lower]
            if matching_in_behavior:
                # Find which synonyms are in the text
                for s in all_synonyms:
                    if s in text and s not in matching_in_behavior:
                        confidence += 0.15
                        matched_terms.append(s)
                        if not reason:
                            reason = f"Synonym match: {s} -> {term}"
        
        # Check domain vocabulary
        if domain_vocabulary:
            for term, related_terms in domain_vocabulary.items():
                if term in behavior_name_lower:
                    for related in related_terms:
                        if related in text:
                            confidence += 0.15
                            matched_terms.append(related)
                            if not reason:
                                reason = f"Domain vocabulary match: {related} -> {term}"
        
        # Cap confidence at 1.0
        confidence = min(1.0, confidence)
        
        return confidence, matched_terms, reason
    
    def _match_to_scenario(
        self,
        text: str,
        scenarios: List[BehaviorScenario],
        domain_vocabulary: Optional[Dict[str, List[str]]] = None
    ) -> Optional[Tuple[str, float, List[str], str]]:
        """Match text to a scenario."""
        text_lower = text.lower()
        
        best_match = None
        best_confidence = 0.0
        best_matched_terms = []
        best_reason = ""
        
        for scenario in scenarios:
            confidence, matched_terms, reason = self._calculate_scenario_match(
                text_lower, scenario, domain_vocabulary
            )
            
            if confidence > best_confidence:
                best_match = str(scenario.id)
                best_confidence = confidence
                best_matched_terms = matched_terms
                best_reason = reason
        
        if best_confidence < self.MEDIUM_CONFIDENCE_THRESHOLD:
            return None
        
        return best_match, best_confidence, best_matched_terms, best_reason
    
    def _calculate_scenario_match(
        self,
        text: str,
        scenario: BehaviorScenario,
        domain_vocabulary: Optional[Dict[str, List[str]]] = None
    ) -> Tuple[float, List[str], str]:
        """Calculate match confidence between text and scenario."""
        scenario_title_lower = scenario.title.lower()
        scenario_desc_lower = (scenario.description or "").lower()
        
        matched_terms = []
        confidence = 0.0
        reason = ""
        
        # Check for direct scenario title match
        if scenario_title_lower in text:
            confidence += 0.5
            matched_terms.append(scenario.title)
            reason = f"Direct scenario title match: {scenario.title}"
        
        # Check for partial title match
        for word in scenario_title_lower.split():
            if word in text and len(word) > 3:
                confidence += 0.2
                matched_terms.append(word)
                if not reason:
                    reason = f"Partial scenario title match: {word}"
        
        # Check description keywords
        for word in scenario_desc_lower.split():
            if word in text and len(word) > 3:
                confidence += 0.1
                matched_terms.append(word)
        
        # Check for negative/positive case type match
        if "reject" in text or "fail" in text or "invalid" in text:
            if scenario.case_type == "negative":
                confidence += 0.2
                matched_terms.append("negative_case")
                if not reason:
                    reason = "Negative case type match"
        
        if "accept" in text or "pass" in text or "valid" in text or "success" in text:
            if scenario.case_type == "positive":
                confidence += 0.2
                matched_terms.append("positive_case")
                if not reason:
                    reason = "Positive case type match"
        
        # Cap confidence at 1.0
        confidence = min(1.0, confidence)
        
        return confidence, matched_terms, reason
    
    def _calculate_overall_confidence(
        self,
        behavior_confidence: float,
        scenario_confidence: float
    ) -> float:
        """Calculate overall match confidence."""
        if scenario_confidence == 0.0:
            # No scenario match, rely on behavior confidence
            return behavior_confidence * 0.7  # Discount for missing scenario
        
        # Weight behavior match higher than scenario match
        return (behavior_confidence * 0.6) + (scenario_confidence * 0.4)
    
    def persist_mappings(
        self,
        mappings: List[BusinessBehaviorMapping],
        db: Session
    ) -> List[BusinessBehaviorMapping]:
        """Persist mappings to the database."""
        if not self.db:
            self.db = db
        
        persisted = []
        
        for mapping in mappings:
            db.add(mapping)
            db.commit()
            persisted.append(mapping)
        
        return mappings
    
    def map_business_intent_override_to_behaviors(
        self,
        business_intent_override_id: str,
        business_change_summary: str,
        acceptance_criteria_text: str,
        affected_users_journeys: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Map business intent override to business behaviors.
        
        Args:
            business_intent_override_id: ID of the business intent override
            business_change_summary: Business change summary text
            acceptance_criteria_text: Acceptance criteria text
            affected_users_journeys: Optional affected users/journeys
            db: Database session
            
        Returns:
            List of business behavior mapping dictionaries
        """
        if not self.db:
            self.db = db
        
        # Guard against None inputs
        business_change_summary = business_change_summary or ""
        acceptance_criteria_text = acceptance_criteria_text or ""
        affected_users_journeys = affected_users_journeys or ""

        # Combine all text for analysis
        combined_text = f"{business_change_summary} {acceptance_criteria_text}"
        if affected_users_journeys:
            combined_text += f" {affected_users_journeys}"
        
        # Extract behavior keywords and concepts
        behavior_mappings = []
        
        # Analyze business change summary for behaviors
        summary_behaviors = self._extract_behavior_keywords(business_change_summary)
        
        # Analyze acceptance criteria for behaviors
        ac_behaviors = self._extract_behavior_keywords(acceptance_criteria_text)
        
        # Analyze affected users/journeys for behaviors
        journey_behaviors = []
        if affected_users_journeys:
            journey_behaviors = self._extract_behavior_keywords(affected_users_journeys)
        
        # Combine and deduplicate behaviors
        all_behaviors = list(set(summary_behaviors + ac_behaviors + journey_behaviors))
        
        # Create behavior mappings
        for behavior in all_behaviors:
            mapping = {
                "behavior_name": behavior,
                "behavior_description": self._generate_behavior_description(behavior, combined_text),
                "behavior_category": self._categorize_behavior(behavior),
                "source_text": self._find_source_text(behavior, combined_text),
                "confidence_score": self._calculate_behavior_confidence(behavior, combined_text),
                "impact_level": self._assess_impact_level(behavior, business_change_summary),
                "affected_components": self._identify_affected_components(behavior, combined_text)
            }
            behavior_mappings.append(mapping)
        
        return behavior_mappings
    
    def _extract_behavior_keywords(self, text: str) -> List[str]:
        """Extract behavior keywords from text."""
        behaviors = []
        text_lower = text.lower()
        
        # Check for behavior patterns
        behavior_patterns = {
            "user_authentication": ["login", "authentication", "signin", "sign in", "log in", "auth"],
            "user_registration": ["register", "signup", "sign up", "create account", "registration"],
            "password_management": ["password", "reset password", "change password", "forgot password"],
            "user_profile": ["profile", "account", "user settings", "personal information"],
            "data_management": ["create", "update", "delete", "edit", "modify", "manage data"],
            "search_functionality": ["search", "find", "lookup", "filter", "query"],
            "navigation": ["navigate", "menu", "navigation", "browse", "go to"],
            "checkout_process": ["checkout", "purchase", "buy", "payment", "order"],
            "content_management": ["content", "article", "post", "publish", "manage content"],
            "notification_system": ["notification", "alert", "message", "email", "push"],
            "reporting": ["report", "analytics", "dashboard", "statistics", "metrics"],
            "file_management": ["file", "upload", "download", "document", "attachment"],
            "permission_management": ["permission", "access", "role", "authorization", "grant"],
            "workflow": ["workflow", "process", "approval", "review", "task"],
            "integration": ["integration", "api", "connect", "sync", "import", "export"]
        }
        
        for behavior_name, keywords in behavior_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                behaviors.append(behavior_name)
        
        return behaviors
    
    def _generate_behavior_description(self, behavior: str, text: str) -> str:
        """Generate behavior description from context."""
        # Find sentences containing behavior keywords
        sentences = text.split('.')
        relevant_sentences = []
        
        behavior_keywords = self.BEHAVIOR_SYNONYMS.get(behavior, [behavior])
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in behavior_keywords):
                relevant_sentences.append(sentence.strip())
        
        if relevant_sentences:
            return relevant_sentences[0][:200] + "..." if len(relevant_sentences[0]) > 200 else relevant_sentences[0]
        else:
            return f"Business behavior related to {behavior.replace('_', ' ')}"
    
    def _categorize_behavior(self, behavior: str) -> str:
        """Categorize behavior into business process types."""
        categories = {
            "user_authentication": "user_journey",
            "user_registration": "user_journey", 
            "password_management": "user_journey",
            "user_profile": "user_journey",
            "data_management": "business_process",
            "search_functionality": "business_process",
            "navigation": "user_journey",
            "checkout_process": "business_process",
            "content_management": "business_process",
            "notification_system": "business_process",
            "reporting": "business_process",
            "file_management": "business_process",
            "permission_management": "business_process",
            "workflow": "business_process",
            "integration": "technical_process"
        }
        
        return categories.get(behavior, "business_process")
    
    def _find_source_text(self, behavior: str, text: str) -> str:
        """Find the source text that led to this behavior mapping."""
        behavior_keywords = self.BEHAVIOR_SYNONYMS.get(behavior, [behavior])
        text_lower = text.lower()
        
        for keyword in behavior_keywords:
            index = text_lower.find(keyword)
            if index != -1:
                # Extract context around the keyword
                start = max(0, index - 50)
                end = min(len(text), index + len(keyword) + 50)
                return text[start:end].strip()
        
        return ""
    
    def _calculate_behavior_confidence(self, behavior: str, text: str) -> str:
        """Calculate confidence score for behavior mapping."""
        text_lower = text.lower()
        behavior_keywords = self.BEHAVIOR_SYNONYMS.get(behavior, [behavior])
        
        # Count keyword matches
        matches = sum(1 for keyword in behavior_keywords if keyword in text_lower)
        
        # Calculate confidence based on matches and text length
        if matches >= 3:
            return "HIGH"
        elif matches >= 2:
            return "MEDIUM"
        elif matches >= 1:
            return "LOW"
        else:
            return "LOW"
    
    def _assess_impact_level(self, behavior: str, business_change_summary: str) -> str:
        """Assess impact level of behavior."""
        summary_lower = business_change_summary.lower()
        
        # High impact indicators
        high_impact_words = ["critical", "essential", "required", "must", "security", "payment", "authentication"]
        
        # Medium impact indicators  
        medium_impact_words = ["important", "improve", "enhance", "optimize", "feature"]
        
        if any(word in summary_lower for word in high_impact_words):
            return "HIGH"
        elif any(word in summary_lower for word in medium_impact_words):
            return "MEDIUM"
        else:
            return "LOW"
    
    def _identify_affected_components(self, behavior: str, text: str) -> List[str]:
        """Identify components affected by this behavior."""
        components = []
        text_lower = text.lower()
        
        # Component patterns
        component_patterns = {
            "frontend": ["ui", "frontend", "interface", "page", "screen", "view"],
            "backend": ["api", "backend", "service", "server", "database"],
            "database": ["database", "db", "data", "storage", "persistence"],
            "authentication": ["auth", "authentication", "login", "security"],
            "payment": ["payment", "billing", "checkout", "transaction"],
            "notification": ["notification", "email", "message", "alert"]
        }
        
        for component, keywords in component_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                components.append(component)
        
        return components[:3]  # Limit to top 3
