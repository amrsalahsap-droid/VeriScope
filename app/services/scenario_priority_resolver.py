"""
ScenarioPriorityResolver
=========================
Determines the final priority for scenario intents based on multiple factors.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ScenarioPriority(Enum):
    """Priority levels for scenario intents."""
    BLOCKER = "BLOCKER"
    MUST = "MUST"
    SHOULD = "SHOULD"
    OPTIONAL = "OPTIONAL"
    VERIFIED = "VERIFIED"  # Special status for already verified scenarios


@dataclass
class PriorityContext:
    """Context information for priority determination."""
    risk_level: str  # CRITICAL, HIGH, MODERATE, LOW
    testing_type: str  # api, ui, integration, unit
    impacted_area: str  # domain/feature
    changed_file_relevance: float  # 0.0 to 1.0
    security_sensitive: bool
    coverage_status: str  # from ScenarioCoverageStatus
    current_pr_execution_status: str  # from ScenarioCoverageStatus
    historical_failure: bool
    business_journey_criticality: str  # CRITICAL, HIGH, MEDIUM, LOW
    is_negative_case: bool  # Whether this is a negative test case
    domain: str  # authentication, payment, etc.
    feature: str  # password, token, etc.


class ScenarioPriorityResolver:
    """
    Resolves the final priority for scenario intents based on multiple factors.
    
    Rules:
    - Security/auth/password/token negative cases default to MUST
    - If already verified on current PR, reduce to VERIFIED
    - If existing automated test exists but not run on PR, keep as MUST/SHOULD
    - If missing automated coverage in high-risk area, mark as MUST
    - Do not duplicate same scenario with multiple priorities
    """
    
    # Security-sensitive domains and features
    SECURITY_DOMAINS = {"authentication", "auth", "security", "authorization"}
    SECURITY_FEATURES = {"password", "token", "session", "login", "signup", "reset", "2fa", "mfa"}
    
    # High-risk domains
    HIGH_RISK_DOMAINS = {"payment", "billing", "subscription", "authentication", "security"}
    
    # Business-critical journeys
    CRITICAL_JOURNEYS = {"checkout", "payment", "signup", "login", "subscription"}
    
    @classmethod
    def is_security_sensitive(cls, context: PriorityContext) -> bool:
        """
        Determine if the scenario is security-sensitive.
        
        Args:
            context: PriorityContext with scenario information
        
        Returns:
            True if security-sensitive
        """
        domain_lower = context.domain.lower()
        feature_lower = context.feature.lower()
        impacted_lower = context.impacted_area.lower()
        
        # Check domain
        if any(sec in domain_lower for sec in cls.SECURITY_DOMAINS):
            return True
        
        # Check feature
        if any(sec in feature_lower for sec in cls.SECURITY_FEATURES):
            return True
        
        # Check impacted area
        if any(sec in impacted_lower for sec in cls.SECURITY_DOMAINS):
            return True
        
        return context.security_sensitive
    
    @classmethod
    def is_high_risk_area(cls, context: PriorityContext) -> bool:
        """
        Determine if the scenario is in a high-risk area.
        
        Args:
            context: PriorityContext with scenario information
        
        Returns:
            True if high-risk area
        """
        domain_lower = context.domain.lower()
        impacted_lower = context.impacted_area.lower()
        
        # Check high-risk domains
        if any(risk in domain_lower for risk in cls.HIGH_RISK_DOMAINS):
            return True
        
        if any(risk in impacted_lower for risk in cls.HIGH_RISK_DOMAINS):
            return True
        
        # Check risk level
        if context.risk_level in ("CRITICAL", "HIGH"):
            return True
        
        return False
    
    @classmethod
    def is_business_critical(cls, context: PriorityContext) -> bool:
        """
        Determine if the scenario is business-critical.
        
        Args:
            context: PriorityContext with scenario information
        
        Returns:
            True if business-critical
        """
        journey_lower = context.business_journey_criticality.lower()
        impacted_lower = context.impacted_area.lower()
        
        # Check critical journeys
        if any(critical in journey_lower for critical in cls.CRITICAL_JOURNEYS):
            return True
        
        if any(critical in impacted_lower for critical in cls.CRITICAL_JOURNEYS):
            return True
        
        return context.business_journey_criticality == "CRITICAL"
    
    @classmethod
    def determine_base_priority(cls, context: PriorityContext) -> ScenarioPriority:
        """
        Determine base priority from context factors.
        
        Args:
            context: PriorityContext with scenario information
        
        Returns:
            Base ScenarioPriority
        """
        # Rule: Security/auth/password/token negative cases default to MUST
        if context.is_negative_case and cls.is_security_sensitive(context):
            return ScenarioPriority.MUST
        
        # Rule: Missing automated coverage in high-risk area = MUST
        if context.coverage_status == "MISSING_AUTOMATED_COVERAGE" and cls.is_high_risk_area(context):
            return ScenarioPriority.MUST
        
        # High risk level
        if context.risk_level == "CRITICAL":
            return ScenarioPriority.BLOCKER
        
        if context.risk_level == "HIGH":
            return ScenarioPriority.MUST
        
        # Business critical
        if cls.is_business_critical(context):
            return ScenarioPriority.MUST
        
        # High file relevance
        if context.changed_file_relevance >= 0.8:
            return ScenarioPriority.MUST
        
        if context.changed_file_relevance >= 0.5:
            return ScenarioPriority.SHOULD
        
        # Default to SHOULD for most scenarios
        return ScenarioPriority.SHOULD
    
    @classmethod
    def adjust_for_coverage_status(
        cls,
        base_priority: ScenarioPriority,
        context: PriorityContext
    ) -> ScenarioPriority:
        """
        Adjust priority based on coverage status.
        
        Args:
            base_priority: Base priority from determine_base_priority
            context: PriorityContext with scenario information
        
        Returns:
            Adjusted ScenarioPriority
        """
        # Rule: If already verified on current PR, reduce to VERIFIED
        if context.current_pr_execution_status == "PASSED":
            return ScenarioPriority.VERIFIED
        
        # Rule: If existing automated test exists but not run on PR, keep as MUST/SHOULD
        if context.coverage_status == "COVERED_NOT_RUN":
            # Keep MUST as MUST, downgrade others to SHOULD
            if base_priority == ScenarioPriority.BLOCKER:
                return ScenarioPriority.MUST
            elif base_priority in (ScenarioPriority.MUST, ScenarioPriority.SHOULD):
                return base_priority
            else:
                return ScenarioPriority.SHOULD
        
        # PARTIALLY_COVERED: reduce priority
        if context.coverage_status == "PARTIALLY_COVERED":
            if base_priority == ScenarioPriority.BLOCKER:
                return ScenarioPriority.MUST
            elif base_priority == ScenarioPriority.MUST:
                return ScenarioPriority.SHOULD
            elif base_priority == ScenarioPriority.SHOULD:
                return ScenarioPriority.OPTIONAL
        
        # SUGGEST_MANUAL_VALIDATION: reduce priority
        if context.coverage_status == "SUGGEST_MANUAL_VALIDATION":
            if base_priority in (ScenarioPriority.BLOCKER, ScenarioPriority.MUST):
                return ScenarioPriority.SHOULD
            else:
                return ScenarioPriority.OPTIONAL
        
        return base_priority
    
    @classmethod
    def adjust_for_historical_failure(
        cls,
        priority: ScenarioPriority,
        context: PriorityContext
    ) -> ScenarioPriority:
        """
        Adjust priority based on historical failure.
        
        Args:
            priority: Current priority
            context: PriorityContext with scenario information
        
        Returns:
            Adjusted ScenarioPriority
        """
        # Historical failure increases priority
        if context.historical_failure:
            if priority == ScenarioPriority.OPTIONAL:
                return ScenarioPriority.SHOULD
            elif priority == ScenarioPriority.SHOULD:
                return ScenarioPriority.MUST
            elif priority == ScenarioPriority.MUST:
                return ScenarioPriority.BLOCKER
        
        return priority
    
    @classmethod
    def resolve_priority(cls, context: PriorityContext) -> ScenarioPriority:
        """
        Resolve final priority for a scenario intent.
        
        Args:
            context: PriorityContext with all relevant information
        
        Returns:
            Final ScenarioPriority
        """
        # Determine base priority
        base_priority = cls.determine_base_priority(context)
        
        # Adjust for coverage status
        adjusted_priority = cls.adjust_for_coverage_status(base_priority, context)
        
        # Adjust for historical failure
        final_priority = cls.adjust_for_historical_failure(adjusted_priority, context)
        
        return final_priority
    
    @classmethod
    def resolve_priority_from_scenario(
        cls,
        scenario_data: Dict[str, Any],
        coverage_status: Optional[Any] = None,
        risk_level: str = "MODERATE",
        business_journey_criticality: str = "MEDIUM",
        historical_failure: bool = False
    ) -> ScenarioPriority:
        """
        Resolve priority from scenario data dictionary.
        
        Args:
            scenario_data: Dictionary with scenario information
            coverage_status: ScenarioCoverageStatus object (optional)
            risk_level: Risk level (CRITICAL, HIGH, MODERATE, LOW)
            business_journey_criticality: Business journey criticality
            historical_failure: Whether this scenario has historical failures
        
        Returns:
            Final ScenarioPriority
        """
        # Extract coverage status information
        coverage_status_str = "MISSING_AUTOMATED_COVERAGE"
        current_pr_execution_status = "NOT_RUN"
        
        if coverage_status:
            coverage_status_str = coverage_status.final_status.value
            current_pr_execution_status = coverage_status.current_pr_execution_status.value
        
        # Determine if negative case
        title = scenario_data.get("title", "").lower()
        priority = scenario_data.get("priority", "").lower()
        risk_category = scenario_data.get("risk_category", "").lower()
        
        is_negative_case = (
            "negative" in risk_category or
            "reject" in title or
            "deny" in title or
            "fail" in title or
            "invalid" in title or
            "unauthorized" in title or
            "error" in title
        )
        
        # Extract domain and feature
        domain = scenario_data.get("domain", scenario_data.get("impacted_area", "general"))
        feature = scenario_data.get("feature", scenario_data.get("impacted_area", "general"))
        
        # Determine security sensitivity
        security_sensitive = cls.is_security_sensitive_from_data(domain, feature, title)
        
        # Calculate file relevance (simplified)
        changed_files = scenario_data.get("related_changed_files", [])
        changed_file_relevance = 0.5 if changed_files else 0.0
        
        # Create context
        context = PriorityContext(
            risk_level=risk_level,
            testing_type=scenario_data.get("testing_type", "api"),
            impacted_area=scenario_data.get("impacted_area", "general"),
            changed_file_relevance=changed_file_relevance,
            security_sensitive=security_sensitive,
            coverage_status=coverage_status_str,
            current_pr_execution_status=current_pr_execution_status,
            historical_failure=historical_failure,
            business_journey_criticality=business_journey_criticality,
            is_negative_case=is_negative_case,
            domain=domain,
            feature=feature
        )
        
        return cls.resolve_priority(context)
    
    @classmethod
    def is_security_sensitive_from_data(
        cls,
        domain: str,
        feature: str,
        title: str
    ) -> bool:
        """
        Determine security sensitivity from scenario data.
        
        Args:
            domain: Domain string
            feature: Feature string
            title: Scenario title
        
        Returns:
            True if security-sensitive
        """
        domain_lower = domain.lower()
        feature_lower = feature.lower()
        title_lower = title.lower()
        
        # Check domain
        if any(sec in domain_lower for sec in cls.SECURITY_DOMAINS):
            return True
        
        # Check feature
        if any(sec in feature_lower for sec in cls.SECURITY_FEATURES):
            return True
        
        # Check title
        if any(sec in title_lower for sec in cls.SECURITY_FEATURES):
            return True
        
        return False
    
    @classmethod
    def resolve_batch_priorities(
        cls,
        scenarios: List[Dict[str, Any]],
        coverage_statuses: Optional[Dict[str, Any]] = None,
        risk_level: str = "MODERATE",
        business_journey_criticality: str = "MEDIUM",
        historical_failures: Optional[Dict[str, bool]] = None
    ) -> Dict[str, ScenarioPriority]:
        """
        Resolve priorities for multiple scenarios.
        
        Args:
            scenarios: List of scenario data dictionaries
            coverage_statuses: Dictionary mapping canonical keys to coverage statuses
            risk_level: Risk level
            business_journey_criticality: Business journey criticality
            historical_failures: Dictionary mapping canonical keys to historical failure status
        
        Returns:
            Dictionary mapping canonical keys to priorities
        """
        priorities = {}
        
        for scenario in scenarios:
            # Generate canonical key for lookup
            from app.services.scenario_intent_normalizer import ScenarioIntentNormalizer
            intent_data = ScenarioIntentNormalizer.create_intent_from_scenario(
                title=scenario.get("title", ""),
                priority=scenario.get("priority", "SHOULD"),
                risk_category=scenario.get("risk_category", "Functional"),
                related_changed_files=scenario.get("related_changed_files", []),
                recommendation_run_id="",  # Not needed for key generation
                domain=scenario.get("domain", scenario.get("impacted_area", "general")),
                feature=scenario.get("feature", scenario.get("impacted_area", "general")),
                behavior=scenario.get("title", ""),
                layer=scenario.get("layer", scenario.get("impacted_layer", "api")),
                case_type=scenario.get("case_type", "positive")
            )
            
            canonical_key = intent_data["canonical_key"]
            
            # Get coverage status
            coverage_status = None
            if coverage_statuses:
                coverage_status = coverage_statuses.get(canonical_key)
            
            # Get historical failure
            historical_failure = False
            if historical_failures:
                historical_failure = historical_failures.get(canonical_key, False)
            
            # Resolve priority
            priority = cls.resolve_priority_from_scenario(
                scenario_data=scenario,
                coverage_status=coverage_status,
                risk_level=risk_level,
                business_journey_criticality=business_journey_criticality,
                historical_failure=historical_failure
            )
            
            priorities[canonical_key] = priority
        
        return priorities
