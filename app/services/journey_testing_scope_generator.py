from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from app.models.journey import Journey
from app.models.behavior import Behavior
from app.models.journey_step import JourneyStep
from app.services.journey_testing_scope import JourneyTestingScope


class JourneyTestingScopeGenerator:
    """Generator to create business-oriented testing scope from journeys."""
    
    # Journey-specific test mappings
    JOURNEY_TEST_MAPPING = {
        "Authentication": {
            "must_test": [
                "Login",
                "Password Reset",
                "Token Validation",
                "Session Management",
            ],
            "should_test": [
                "Session Refresh",
                "Logout",
                "Multi-factor Authentication",
            ],
            "optional": [
                "Authentication Smoke",
                "Login Performance",
                "Session Timeout",
            ],
        },
        "Registration": {
            "must_test": [
                "Signup",
                "Email Verification",
                "Account Creation",
            ],
            "should_test": [
                "Profile Creation",
                "Welcome Flow",
                "Duplicate Email Prevention",
            ],
            "optional": [
                "Registration Smoke",
                "Signup Performance",
                "Social Registration",
            ],
        },
        "Billing": {
            "must_test": [
                "Subscription",
                "Payment Processing",
                "Invoice Generation",
                "Refund Processing",
            ],
            "should_test": [
                "Payment Retry",
                "Payment Method Management",
                "Billing History",
            ],
            "optional": [
                "Billing Smoke",
                "Payment Performance",
                "Discount Application",
            ],
        },
        "Subscription Lifecycle": {
            "must_test": [
                "Subscription Creation",
                "Subscription Modification",
                "Subscription Cancellation",
                "Renewal Processing",
            ],
            "should_test": [
                "Plan Upgrade/Downgrade",
                "Proration Calculation",
                "Subscription Status",
            ],
            "optional": [
                "Subscription Smoke",
                "Billing Cycle Test",
                "Trial Conversion",
            ],
        },
        "Notifications": {
            "must_test": [
                "Email Delivery",
                "Push Notification",
                "Notification Preferences",
            ],
            "should_test": [
                "SMS Notification",
                "Notification Queue",
                "Failed Notification Retry",
            ],
            "optional": [
                "Notification Smoke",
                "Email Performance",
                "Notification Analytics",
            ],
        },
        "Administration": {
            "must_test": [
                "User Management",
                "Role Management",
                "Permission Management",
            ],
            "should_test": [
                "Audit Logging",
                "Admin Dashboard",
                "System Configuration",
            ],
            "optional": [
                "Admin Smoke",
                "Bulk Operations",
                "Admin Performance",
            ],
        },
        "Reporting": {
            "must_test": [
                "Analytics Dashboard",
                "Report Generation",
                "Data Export",
            ],
            "should_test": [
                "Custom Reports",
                "Report Scheduling",
                "Data Accuracy",
            ],
            "optional": [
                "Reporting Smoke",
                "Report Performance",
                "Historical Data",
            ],
        },
    }
    
    # Behavior risk to test priority mapping
    RISK_TO_PRIORITY = {
        "CRITICAL": "must_test",
        "HIGH": "must_test",
        "MEDIUM": "should_test",
        "LOW": "optional",
    }
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the journey testing scope generator with optional database session."""
        self.db = db
    
    def generate_testing_scope(
        self,
        journey: Journey,
        behaviors: List[Behavior],
        journey_steps: Optional[List[JourneyStep]] = None,
    ) -> JourneyTestingScope:
        """Generate testing scope for a journey."""
        # Get base test mapping for journey
        base_mapping = self.JOURNEY_TEST_MAPPING.get(journey.name, {
            "must_test": [],
            "should_test": [],
            "optional": [],
        })
        
        # Adjust based on affected behaviors
        must_test = set(base_mapping["must_test"])
        should_test = set(base_mapping["should_test"])
        optional = set(base_mapping["optional"])
        
        # Add behavior-specific tests
        for behavior in behaviors:
            priority = self.RISK_TO_PRIORITY.get(behavior.risk_level, "should_test")
            test_name = behavior.name
            
            if priority == "must_test":
                must_test.add(test_name)
            elif priority == "should_test":
                should_test.add(test_name)
            else:
                optional.add(test_name)
        
        # Add journey step tests
        if journey_steps:
            for step in journey_steps:
                if not step.is_optional:
                    must_test.add(step.step_name)
                else:
                    should_test.add(step.step_name)
        
        # Convert to sorted lists
        return JourneyTestingScope(
            journey=journey.name,
            journey_id=str(journey.id),
            must_test=sorted(list(must_test)),
            should_test=sorted(list(should_test)),
            optional=sorted(list(optional)),
        )
    
    def batch_generate_scopes(
        self,
        journeys: List[Journey],
        behaviors_map: Dict[str, List[Behavior]],
        journey_steps_map: Optional[Dict[str, List[JourneyStep]]] = None,
    ) -> List[JourneyTestingScope]:
        """Generate testing scopes for multiple journeys."""
        scopes = []
        
        for journey in journeys:
            behaviors = behaviors_map.get(str(journey.id), [])
            journey_steps = journey_steps_map.get(str(journey.id), []) if journey_steps_map else None
            scope = self.generate_testing_scope(journey, behaviors, journey_steps)
            scopes.append(scope)
        
        return scopes
    
    def generate_scope_from_impact(
        self,
        journey: Journey,
        affected_behaviors: List[Behavior],
        journey_steps: Optional[List[JourneyStep]] = None,
    ) -> JourneyTestingScope:
        """Generate testing scope from journey impact (affected behaviors only)."""
        # Get base test mapping for journey
        base_mapping = self.JOURNEY_TEST_MAPPING.get(journey.name, {
            "must_test": [],
            "should_test": [],
            "optional": [],
        })
        
        # Only include tests for affected behaviors
        must_test = set()
        should_test = set()
        optional = set()
        
        # Add behavior-specific tests based on risk
        for behavior in affected_behaviors:
            priority = self.RISK_TO_PRIORITY.get(behavior.risk_level, "should_test")
            test_name = behavior.name
            
            if priority == "must_test":
                must_test.add(test_name)
            elif priority == "should_test":
                should_test.add(test_name)
            else:
                optional.add(test_name)
        
        # Add related tests from base mapping
        for test in base_mapping["must_test"]:
            if any(test.lower() in b.name.lower() for b in affected_behaviors):
                must_test.add(test)
        
        for test in base_mapping["should_test"]:
            if any(test.lower() in b.name.lower() for b in affected_behaviors):
                should_test.add(test)
        
        # Add journey step tests if affected
        if journey_steps:
            for step in journey_steps:
                if any(step.behavior_id == b.id for b in affected_behaviors):
                    if not step.is_optional:
                        must_test.add(step.step_name)
                    else:
                        should_test.add(step.step_name)
        
        # Convert to sorted lists
        return JourneyTestingScope(
            journey=journey.name,
            journey_id=str(journey.id),
            must_test=sorted(list(must_test)),
            should_test=sorted(list(should_test)),
            optional=sorted(list(optional)),
        )
    
    def get_scope_summary(self, scopes: List[JourneyTestingScope]) -> Dict:
        """Get summary of testing scopes."""
        if not scopes:
            return {
                "total_journeys": 0,
                "total_must_test": 0,
                "total_should_test": 0,
                "total_optional": 0,
            }
        
        total_must_test = sum(len(scope.must_test) for scope in scopes)
        total_should_test = sum(len(scope.should_test) for scope in scopes)
        total_optional = sum(len(scope.optional) for scope in scopes)
        
        return {
            "total_journeys": len(scopes),
            "total_must_test": total_must_test,
            "total_should_test": total_should_test,
            "total_optional": total_optional,
        }
