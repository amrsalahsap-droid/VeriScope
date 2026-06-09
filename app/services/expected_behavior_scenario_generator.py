"""Expected Behavior Scenario Generator service.

Converts business intent and acceptance criteria into concrete expected behavior scenarios.
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import uuid

from app.models.expected_behavior_scenario import ExpectedBehaviorScenario
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.acceptance_criterion import AcceptanceCriterion


class ExpectedBehaviorScenarioGenerator:
    """Generates expected behavior scenarios from business intent and AC."""
    
    # Priority keywords
    MUST_KEYWORDS = ["must", "required", "mandatory", "shall", "critical", "essential"]
    SHOULD_KEYWORDS = ["should", "recommended", "preferable", "important"]
    OPTIONAL_KEYWORDS = ["optional", "nice to have", "could", "might", "consider"]
    
    # Scenario type keywords
    TYPE_KEYWORDS = {
        "SECURITY": ["security", "auth", "authentication", "authorization", "permission", "encrypt", "protect"],
        "VALIDATION": ["validate", "verify", "check", "ensure", "confirm", "reject", "accept"],
        "UI": ["display", "show", "hide", "render", "view", "page", "screen", "button", "form"],
        "API": ["api", "endpoint", "request", "response", "json", "http", "rest"],
        "INTEGRATION": ["integration", "external", "third-party", "service", "sync", "webhook"],
        "PERFORMANCE": ["fast", "slow", "latency", "response time", "load", "scale", "optimize"],
    }
    
    # Testing type keywords
    AUTOMATED_KEYWORDS = ["automated", "api", "endpoint", "json", "http"]
    MANUAL_KEYWORDS = ["ui", "visual", "manual", "user experience", "ux"]
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the generator with optional database session."""
        self.db = db
    
    def generate_from_acceptance_criteria(
        self,
        acceptance_criteria: List[AcceptanceCriterion],
        affected_behaviors: List[Behavior],
        affected_journeys: List[Journey],
        recommendation_run_id: Optional[str] = None
    ) -> List[ExpectedBehaviorScenario]:
        """Generate expected scenarios from acceptance criteria.
        
        AC-derived scenarios are stronger than inferred scenarios.
        """
        scenarios = []
        
        # Build behavior and journey maps
        behavior_map = {str(b.id): b for b in affected_behaviors}
        journey_map = {str(j.id): j for j in affected_journeys}
        
        for ac in acceptance_criteria:
            # Handle both dict and object types
            ac_text = ac.get("text") if isinstance(ac, dict) else ac.text
            ac_confidence = ac.get("confidence", 0.5) if isinstance(ac, dict) else ac.confidence
            ac_id = ac.get("id") if isinstance(ac, dict) else ac.id
            
            # Determine priority
            priority = self._determine_priority(ac_text)
            
            # Determine scenario type
            scenario_type = self._determine_scenario_type(ac_text)
            
            # Determine testing type
            testing_type = self._determine_testing_type(ac_text)
            
            # Generate title from AC text
            title = self._generate_title(ac_text)
            
            # Generate preconditions
            preconditions = self._generate_preconditions(ac_text)
            
            # Generate test data
            test_data = self._generate_test_data(ac_text)
            
            # Generate steps
            steps = self._generate_steps(ac_text)
            
            # Generate expected result
            expected_result = self._generate_expected_result(ac_text)
            
            # Calculate confidence (AC-derived is higher)
            confidence = min(1.0, ac_confidence + 0.1)  # Boost AC-derived confidence
            
            # Create scenario
            scenario = ExpectedBehaviorScenario(
                id=uuid.uuid4(),
                title=title,
                behavior_id=None,  # Will be set by BusinessBehaviorMapper
                journey_id=None,  # Will be set by BusinessBehaviorMapper
                acceptance_criterion_id=ac_id,
                priority=priority,
                testing_type=testing_type,
                scenario_type=scenario_type,
                preconditions=preconditions,
                test_data=test_data,
                steps=steps,
                expected_result=expected_result,
                source="ACCEPTANCE_CRITERIA",
                confidence=confidence,
                matches_existing_test="false",
                recommendation_run_id=recommendation_run_id,
            )
            
            scenarios.append(scenario)
        
        return scenarios
    
    def generate_from_business_intent(
        self,
        business_intent: Dict[str, Any],
        affected_behaviors: List[Behavior],
        affected_journeys: List[Journey],
        recommendation_run_id: Optional[str] = None
    ) -> List[ExpectedBehaviorScenario]:
        """Generate expected scenarios from business intent snapshot.
        
        Inferred scenarios have lower confidence than AC-derived scenarios.
        """
        scenarios = []
        
        # Extract intent information
        intent_text = business_intent.get("description", "")
        changed_files = business_intent.get("changed_files", [])
        
        if not intent_text and not changed_files:
            return scenarios
        
        # Generate scenarios based on changed files and intent
        for file_path in changed_files:
            # Infer scenario from file path
            title = self._infer_title_from_file(file_path)
            
            if not title:
                continue
            
            # Determine priority (inferred scenarios default to SHOULD)
            priority = "SHOULD"
            
            # Determine scenario type from file path
            scenario_type = self._infer_scenario_type_from_file(file_path)
            
            # Determine testing type
            testing_type = "AUTOMATED" if "api" in file_path.lower() else "MANUAL"
            
            # Generate basic steps
            steps = self._generate_basic_steps_from_file(file_path)
            
            # Inferred scenarios have lower confidence
            confidence = 0.4
            
            # Create scenario
            scenario = ExpectedBehaviorScenario(
                id=uuid.uuid4(),
                title=title,
                behavior_id=None,
                journey_id=None,
                acceptance_criterion_id=None,
                priority=priority,
                testing_type=testing_type,
                scenario_type=scenario_type,
                preconditions=[],
                test_data=None,
                steps=steps,
                expected_result="Expected behavior should be verified",
                source="BUSINESS_INTENT",
                confidence=confidence,
                matches_existing_test="false",
                recommendation_run_id=recommendation_run_id,
            )
            
            scenarios.append(scenario)
        
        return scenarios
    
    def _determine_priority(self, text: str) -> str:
        """Determine priority from text."""
        text_lower = text.lower()
        
        for keyword in self.MUST_KEYWORDS:
            if keyword in text_lower:
                return "MUST"
        
        for keyword in self.SHOULD_KEYWORDS:
            if keyword in text_lower:
                return "SHOULD"
        
        for keyword in self.OPTIONAL_KEYWORDS:
            if keyword in text_lower:
                return "OPTIONAL"
        
        # Default to MUST for AC-derived scenarios
        return "MUST"
    
    def _determine_scenario_type(self, text: str) -> str:
        """Determine scenario type from text."""
        text_lower = text.lower()
        
        scores = {scenario_type: 0 for scenario_type in self.TYPE_KEYWORDS}
        
        for scenario_type, keywords in self.TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[scenario_type] += 1
        
        max_score = max(scores.values())
        if max_score == 0:
            return "FUNCTIONAL"
        
        return max(scores, key=scores.get)
    
    def _determine_testing_type(self, text: str) -> str:
        """Determine testing type from text."""
        text_lower = text.lower()
        
        for keyword in self.AUTOMATED_KEYWORDS:
            if keyword in text_lower:
                return "AUTOMATED"
        
        for keyword in self.MANUAL_KEYWORDS:
            if keyword in text_lower:
                return "MANUAL"
        
        # Default to AUTOMATED
        return "AUTOMATED"
    
    def _generate_title(self, text: str) -> str:
        """Generate scenario title from AC text."""
        # Remove common prefixes
        text = re.sub(r"^(the|a|an)\s+", "", text, flags=re.IGNORECASE)
        
        # Capitalize first letter
        text = text[0].upper() + text[1:] if text else text
        
        # Remove trailing punctuation
        text = text.rstrip(".!?")
        
        # Limit length
        if len(text) > 100:
            text = text[:97] + "..."
        
        return text
    
    def _generate_preconditions(self, text: str) -> List[str]:
        """Generate preconditions from text."""
        preconditions = []
        text_lower = text.lower()
        
        # Common preconditions based on keywords
        if "user" in text_lower:
            preconditions.append("User is logged in")
        
        if "password" in text_lower:
            preconditions.append("User has an account")
        
        if "email" in text_lower:
            preconditions.append("User has a valid email address")
        
        if "token" in text_lower:
            preconditions.append("User has a valid token")
        
        return preconditions
    
    def _generate_test_data(self, text: str) -> Optional[Dict[str, Any]]:
        """Generate test data from text."""
        text_lower = text.lower()
        test_data = {}
        
        # Extract test data based on keywords
        if "email" in text_lower:
            test_data["email"] = "test@example.com"
        
        if "password" in text_lower:
            test_data["password"] = "TestPassword123!"
            test_data["weak_password"] = "123"
        
        if "token" in text_lower:
            test_data["valid_token"] = "abc123xyz"
            test_data["expired_token"] = "expired123"
        
        if "username" in text_lower:
            test_data["username"] = "testuser"
        
        return test_data if test_data else None
    
    def _generate_steps(self, text: str) -> List[str]:
        """Generate test steps from text."""
        steps = []
        text_lower = text.lower()
        
        # Extract action from text
        if "can" in text_lower or "should" in text_lower or "must" in text_lower:
            # Find the action verb
            action_match = re.search(r"(can|should|must)\s+(\w+)", text_lower)
            if action_match:
                action = action_match.group(2)
                steps.append(f"Perform {action}")
            else:
                steps.append("Perform the described action")
        
        # Add verification step
        if "reject" in text_lower or "fail" in text_lower:
            steps.append("Verify that the action is rejected")
        elif "accept" in text_lower or "succeed" in text_lower or "pass" in text_lower:
            steps.append("Verify that the action succeeds")
        else:
            steps.append("Verify the expected behavior")
        
        return steps
    
    def _generate_expected_result(self, text: str) -> str:
        """Generate expected result from text."""
        text_lower = text.lower()
        
        if "reject" in text_lower or "fail" in text_lower:
            return "Action should be rejected with appropriate error message"
        elif "accept" in text_lower or "succeed" in text_lower or "pass" in text_lower:
            return "Action should succeed"
        elif "validate" in text_lower or "verify" in text_lower:
            return "Validation should pass"
        else:
            return "Expected behavior should be observed"
    
    def _infer_title_from_file(self, file_path: str) -> Optional[str]:
        """Infer scenario title from file path."""
        # Extract meaningful part from file path
        parts = file_path.split("/")
        filename = parts[-1] if parts else file_path
        
        # Remove extension
        filename = filename.rsplit(".", 1)[0] if "." in filename else filename
        
        # Convert to title case
        title = filename.replace("-", " ").replace("_", " ").title()
        
        # Add action prefix
        if "route" in filename.lower() or "api" in filename.lower():
            title = f"Test {title} endpoint"
        elif "page" in filename.lower():
            title = f"Test {title} page"
        else:
            title = f"Test {title}"
        
        return title
    
    def _infer_scenario_type_from_file(self, file_path: str) -> str:
        """Infer scenario type from file path."""
        file_lower = file_path.lower()
        
        if "auth" in file_lower or "password" in file_lower:
            return "SECURITY"
        elif "api" in file_lower or "route" in file_lower:
            return "API"
        elif "page" in file_lower or "component" in file_lower:
            return "UI"
        elif "validation" in file_lower or "verify" in file_lower:
            return "VALIDATION"
        
        return "FUNCTIONAL"
    
    def _generate_basic_steps_from_file(self, file_path: str) -> List[str]:
        """Generate basic test steps from file path."""
        steps = []
        
        steps.append(f"Navigate to {file_path}")
        steps.append("Verify the expected behavior")
        steps.append("Check for errors or exceptions")
        
        return steps
    
    def persist_scenarios(
        self,
        scenarios: List[ExpectedBehaviorScenario],
        db: Session
    ) -> List[ExpectedBehaviorScenario]:
        """Persist scenarios to the database."""
        if not self.db:
            self.db = db
        
        persisted = []
        
        for scenario in scenarios:
            db.add(scenario)
            db.commit()
            persisted.append(scenario)
        
        return scenarios
