"""
QC Lead Scenario Language Service

Transforms machine-generated scenario data into professional QC lead language.
Generates professional titles, objectives, preconditions, test data, steps, and expected results.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import re
from enum import Enum

class ScenarioType(Enum):
    AUTHENTICATION = "authentication"
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"
    USER_PROFILE = "user_profile"
    DATA_VALIDATION = "data_validation"
    API_ENDPOINT = "api_endpoint"
    UI_COMPONENT = "ui_component"
    BUSINESS_LOGIC = "business_logic"
    SECURITY = "security"
    PERFORMANCE = "performance"
    INTEGRATION = "integration"
    GENERAL = "general"

class Priority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ExecutionLayer(Enum):
    API = "api"
    UI = "ui"
    INTEGRATION = "integration"
    E2E = "e2e"
    UNIT = "unit"

@dataclass
class ProfessionalScenario:
    """Professional QC lead scenario structure"""
    title: str
    objective: str
    preconditions: List[str]
    test_data: Dict[str, Any]
    steps: List[str]
    expected_results: List[str]
    priority: Priority
    execution_layer: ExecutionLayer
    automation_candidate: bool
    impacted_behavior: str
    impacted_journey: str
    related_changed_files: List[str]
    original_identifier: Optional[str] = None

class QCLeadScenarioLanguageService:
    """Service for generating professional QC lead scenario language"""
    
    def __init__(self):
        self.action_verbs = [
            "Verify", "Validate", "Test", "Confirm", "Check", "Ensure", "Assess", "Evaluate",
            "Examine", "Review", "Analyze", "Demonstrate", "Prove", "Authenticate", "Authorize"
        ]
        
        self.success_outcomes = [
            "succeeds", "completes successfully", "functions correctly", "operates as expected",
            "returns expected results", "processes without errors", "handles properly", "responds correctly"
        ]
        
        self.failure_outcomes = [
            "fails appropriately", "handles errors gracefully", "rejects invalid input",
            "prevents unauthorized access", "displays appropriate error messages", "maintains security"
        ]
        
        self.security_contexts = [
            "authentication", "authorization", "access control", "data protection", "security",
            "privacy", "compliance", "audit", "logging", "validation"
        ]

    def generate_professional_scenario(self, scenario_data: Dict[str, Any]) -> ProfessionalScenario:
        """Transform raw scenario data into professional QC lead scenario"""
        
        # Extract basic information
        original_id = scenario_data.get('stable_identity') or scenario_data.get('scenario_id')
        behavior_name = scenario_data.get('affected_behavior_name', '')
        journey_name = scenario_data.get('affected_journey_name', '')
        changed_files = scenario_data.get('changed_files', [])
        
        # Determine scenario type
        scenario_type = self._determine_scenario_type(behavior_name, journey_name, changed_files)
        
        # Generate professional title
        title = self._generate_professional_title(scenario_data, scenario_type)
        
        # Generate objective
        objective = self._generate_objective(scenario_data, scenario_type)
        
        # Generate preconditions
        preconditions = self._generate_preconditions(scenario_data, scenario_type)
        
        # Generate test data
        test_data = self._generate_test_data(scenario_data, scenario_type)
        
        # Generate test steps
        steps = self._generate_test_steps(scenario_data, scenario_type)
        
        # Generate expected results
        expected_results = self._generate_expected_results(scenario_data, scenario_type)
        
        # Determine priority
        priority = self._determine_priority(scenario_data)
        
        # Determine execution layer
        execution_layer = self._determine_execution_layer(scenario_data)
        
        # Determine automation candidate
        automation_candidate = self._is_automation_candidate(scenario_data)
        
        return ProfessionalScenario(
            title=title,
            objective=objective,
            preconditions=preconditions,
            test_data=test_data,
            steps=steps,
            expected_results=expected_results,
            priority=priority,
            execution_layer=execution_layer,
            automation_candidate=automation_candidate,
            impacted_behavior=behavior_name,
            impacted_journey=journey_name,
            related_changed_files=changed_files,
            original_identifier=original_id
        )

    def _determine_scenario_type(self, behavior: str, journey: str, files: List[str]) -> ScenarioType:
        """Determine scenario type based on behavior, journey, and changed files"""
        
        # Combine all text for analysis
        combined_text = f"{behavior} {journey} {' '.join(files)}".lower()
        
        # Check for specific patterns
        if any(keyword in combined_text for keyword in ['auth', 'login', 'signin', 'token', 'credential']):
            return ScenarioType.AUTHENTICATION
        elif any(keyword in combined_text for keyword in ['register', 'signup', 'create account', 'new user']):
            return ScenarioType.REGISTRATION
        elif any(keyword in combined_text for keyword in ['password', 'reset', 'forgot', 'recover']):
            return ScenarioType.PASSWORD_RESET
        elif any(keyword in combined_text for keyword in ['profile', 'account', 'user', 'settings']):
            return ScenarioType.USER_PROFILE
        elif any(keyword in combined_text for keyword in ['validate', 'validation', 'input', 'form']):
            return ScenarioType.DATA_VALIDATION
        elif any(keyword in combined_text for keyword in ['api', 'endpoint', 'service', 'controller']):
            return ScenarioType.API_ENDPOINT
        elif any(keyword in combined_text for keyword in ['ui', 'component', 'view', 'page', 'interface']):
            return ScenarioType.UI_COMPONENT
        elif any(keyword in combined_text for keyword in ['security', 'permission', 'access', 'authorize']):
            return ScenarioType.SECURITY
        elif any(keyword in combined_text for keyword in ['performance', 'load', 'speed', 'response']):
            return ScenarioType.PERFORMANCE
        elif any(keyword in combined_text for keyword in ['integration', 'connect', 'sync', 'bridge']):
            return ScenarioType.INTEGRATION
        elif any(keyword in combined_text for keyword in ['logic', 'business', 'rule', 'process']):
            return ScenarioType.BUSINESS_LOGIC
        else:
            return ScenarioType.GENERAL

    def _generate_professional_title(self, scenario_data: Dict[str, Any], scenario_type: ScenarioType) -> str:
        """Generate professional scenario title"""
        
        behavior = scenario_data.get('affected_behavior_name', '')
        journey = scenario_data.get('affected_journey_name', '')
        original_id = scenario_data.get('stable_identity', '')
        
        # Extract key information
        main_action = self._extract_main_action(behavior, journey, original_id)
        context = self._extract_context(behavior, journey, scenario_type)
        condition = self._extract_condition(behavior, journey, original_id)
        
        # Generate title based on scenario type
        if scenario_type == ScenarioType.AUTHENTICATION:
            if 'valid' in original_id.lower() or 'success' in original_id.lower():
                return f"Verify user authentication succeeds with valid {context}"
            elif 'invalid' in original_id.lower() or 'fail' in original_id.lower():
                return f"Verify user authentication fails appropriately with invalid {context}"
            else:
                return f"Verify user authentication process handles {context} correctly"
        
        elif scenario_type == ScenarioType.REGISTRATION:
            return f"Verify user registration completes successfully with valid required data"
        
        elif scenario_type == ScenarioType.PASSWORD_RESET:
            if 'token' in original_id.lower():
                return f"Verify password reset succeeds with a valid, unexpired token"
            else:
                return f"Verify password reset process handles {context} correctly"
        
        elif scenario_type == ScenarioType.DATA_VALIDATION:
            return f"Verify {context} validation processes {condition} correctly"
        
        elif scenario_type == ScenarioType.API_ENDPOINT:
            return f"Verify {context} API endpoint handles {condition} appropriately"
        
        elif scenario_type == ScenarioType.SECURITY:
            return f"Verify security controls prevent {context} when {condition}"
        
        elif scenario_type == ScenarioType.UI_COMPONENT:
            return f"Verify {context} component functions correctly with {condition}"
        
        else:
            # Generic title generation
            if original_id:
                # Convert snake_case to readable format
                readable_id = original_id.replace('_', ' ').replace('should', 'Verify').title()
                # Add more professional language
                if 'validate' in readable_id.lower():
                    return f"Verify {readable_id.replace('Validate', '').strip()} functions correctly"
                elif 'test' in readable_id.lower():
                    return f"Verify {readable_id.replace('Test', '').strip()} operates as expected"
                else:
                    return f"Verify {readable_id} completes successfully"
            else:
                return f"Verify {behavior or 'system functionality'} operates correctly"

    def _generate_objective(self, scenario_data: Dict[str, Any], scenario_type: ScenarioType) -> str:
        """Generate professional scenario objective"""
        
        behavior = scenario_data.get('affected_behavior_name', '')
        journey = scenario_data.get('affected_journey_name', '')
        
        if scenario_type == ScenarioType.AUTHENTICATION:
            return "To ensure the authentication system properly validates user credentials and provides appropriate access based on authentication status."
        
        elif scenario_type == ScenarioType.REGISTRATION:
            return "To verify that new user registration process correctly validates required information and creates user accounts successfully."
        
        elif scenario_type == ScenarioType.PASSWORD_RESET:
            return "To ensure password reset functionality securely authenticates users and allows password changes with valid tokens."
        
        elif scenario_type == ScenarioType.DATA_VALIDATION:
            return f"To validate that {behavior} properly processes input data and enforces business rules and constraints."
        
        elif scenario_type == ScenarioType.SECURITY:
            return "To verify that security controls properly protect against unauthorized access and maintain data integrity."
        
        else:
            return f"To ensure {behavior or 'the system'} functions correctly and handles various input scenarios appropriately."

    def _generate_preconditions(self, scenario_data: Dict[str, Any], scenario_type: ScenarioType) -> List[str]:
        """Generate scenario preconditions"""
        
        preconditions = []
        
        # Common preconditions
        preconditions.append("System is running and accessible")
        preconditions.append("Database connections are established")
        
        if scenario_type == ScenarioType.AUTHENTICATION:
            preconditions.append("User accounts exist in the system")
            preconditions.append("Authentication service is configured")
        elif scenario_type == ScenarioType.REGISTRATION:
            preconditions.append("Registration service is enabled")
            preconditions.append("Required user data fields are defined")
        elif scenario_type == ScenarioType.PASSWORD_RESET:
            preconditions.append("Password reset service is configured")
            preconditions.append("Email delivery service is operational")
        elif scenario_type == ScenarioType.API_ENDPOINT:
            preconditions.append("API service is deployed and running")
            preconditions.append("Required API endpoints are accessible")
        elif scenario_type == ScenarioType.UI_COMPONENT:
            preconditions.append("Frontend application is loaded")
            preconditions.append("Required UI components are rendered")
        
        return preconditions

    def _generate_test_data(self, scenario_data: Dict[str, Any], scenario_type: ScenarioType) -> Dict[str, Any]:
        """Generate suggested test data"""
        
        test_data = {}
        
        if scenario_type == ScenarioType.AUTHENTICATION:
            test_data.update({
                "valid_credentials": {
                    "username": "testuser@example.com",
                    "password": "ValidPassword123!"
                },
                "invalid_credentials": {
                    "username": "invalid@example.com",
                    "password": "WrongPassword123!"
                },
                "expired_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.expired.token"
            })
        elif scenario_type == ScenarioType.REGISTRATION:
            test_data.update({
                "valid_user_data": {
                    "email": "newuser@example.com",
                    "password": "SecurePassword123!",
                    "confirmPassword": "SecurePassword123!",
                    "firstName": "John",
                    "lastName": "Doe"
                },
                "invalid_user_data": {
                    "email": "invalid-email",
                    "password": "123",
                    "confirmPassword": "different"
                }
            })
        elif scenario_type == ScenarioType.PASSWORD_RESET:
            test_data.update({
                "valid_reset_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid.reset.token",
                "new_password": "NewSecurePassword456!",
                "confirm_password": "NewSecurePassword456!"
            })
        else:
            test_data.update({
                "sample_input": "Sample test data for scenario execution",
                "boundary_values": ["minimum", "maximum", "edge_case"]
            })
        
        return test_data

    def _generate_test_steps(self, scenario_data: Dict[str, Any], scenario_type: ScenarioType) -> List[str]:
        """Generate professional test steps"""
        
        steps = []
        
        if scenario_type == ScenarioType.AUTHENTICATION:
            steps.extend([
                "Navigate to the login page",
                "Enter valid username and password",
                "Click the login button",
                "Verify successful authentication and redirection",
                "Confirm user session is established"
            ])
        elif scenario_type == ScenarioType.REGISTRATION:
            steps.extend([
                "Navigate to the registration page",
                "Enter all required user information",
                "Submit the registration form",
                "Verify account creation confirmation",
                "Validate user can login with new credentials"
            ])
        elif scenario_type == ScenarioType.PASSWORD_RESET:
            steps.extend([
                "Navigate to password reset page",
                "Enter valid email address",
                "Submit reset request",
                "Access reset link from email",
                "Enter new password and confirmation",
                "Submit password change",
                "Verify login with new password"
            ])
        else:
            steps.extend([
                "Navigate to the relevant system component",
                "Provide appropriate input data",
                "Execute the primary action",
                "Verify system response",
                "Validate expected behavior"
            ])
        
        return steps

    def _generate_expected_results(self, scenario_data: Dict[str, Any], scenario_type: ScenarioType) -> List[str]:
        """Generate professional expected results"""
        
        results = []
        
        if scenario_type == ScenarioType.AUTHENTICATION:
            if 'valid' in str(scenario_data.get('stable_identity', '')).lower():
                results.extend([
                    "User is successfully authenticated",
                    "System redirects to appropriate dashboard/home page",
                    "User session is established with correct permissions",
                    "Authentication token is generated and stored securely"
                ])
            else:
                results.extend([
                    "Authentication fails with appropriate error message",
                    "User remains on login page",
                    "No session or token is created",
                    "System logs authentication attempt for security audit"
                ])
        elif scenario_type == ScenarioType.REGISTRATION:
            results.extend([
                "User account is created successfully",
                "Confirmation message is displayed",
                "Welcome email is sent to user",
                "User can login with new credentials"
            ])
        elif scenario_type == ScenarioType.PASSWORD_RESET:
            results.extend([
                "Password is updated successfully",
                "User receives confirmation notification",
                "Previous password is invalidated",
                "User can login with new password"
            ])
        elif scenario_type == ScenarioType.SECURITY:
            results.extend([
                "Security controls prevent unauthorized access",
                "Appropriate error messages are displayed",
                "Security events are logged for audit",
                "System integrity is maintained"
            ])
        else:
            results.extend([
                "System processes input correctly",
                "Expected output is generated",
                "No errors or exceptions occur",
                "System state remains consistent"
            ])
        
        return results

    def _determine_priority(self, scenario_data: Dict[str, Any]) -> Priority:
        """Determine scenario priority"""
        
        # Check for explicit priority
        explicit_priority = scenario_data.get('priority')
        if explicit_priority:
            return Priority(explicit_priority.lower())
        
        # Determine based on impact and tier
        tier = scenario_data.get('tier', '').lower()
        behavior = scenario_data.get('affected_behavior_name', '').lower()
        
        if tier == 'must_run' or 'critical' in behavior or 'security' in behavior:
            return Priority.CRITICAL
        elif tier == 'should_run' or 'important' in behavior:
            return Priority.HIGH
        elif tier == 'fallback':
            return Priority.LOW
        else:
            return Priority.MEDIUM

    def _determine_execution_layer(self, scenario_data: Dict[str, Any]) -> ExecutionLayer:
        """Determine execution layer"""
        
        # Check for explicit layer
        explicit_layer = scenario_data.get('layer') or scenario_data.get('execution_layer')
        if explicit_layer:
            return ExecutionLayer(explicit_layer.lower())
        
        # Determine based on context
        behavior = scenario_data.get('affected_behavior_name', '').lower()
        files = scenario_data.get('changed_files', [])
        
        if any('api' in str(f).lower() or 'service' in str(f).lower() for f in files):
            return ExecutionLayer.API
        elif any('ui' in str(f).lower() or 'component' in str(f).lower() or 'view' in str(f).lower() for f in files):
            return ExecutionLayer.UI
        elif any('integration' in str(f).lower() or 'connect' in str(f).lower() for f in files):
            return ExecutionLayer.INTEGRATION
        elif 'unit' in behavior or 'component' in behavior:
            return ExecutionLayer.UNIT
        else:
            return ExecutionLayer.E2E

    def _is_automation_candidate(self, scenario_data: Dict[str, Any]) -> bool:
        """Determine if scenario is suitable for automation"""
        
        # Check explicit automation flag
        if 'automation_candidate' in scenario_data:
            return bool(scenario_data['automation_candidate'])
        
        # Determine based on characteristics
        tier = scenario_data.get('tier', '').lower()
        behavior = scenario_data.get('affected_behavior_name', '').lower()
        
        # High-priority, stable scenarios are good automation candidates
        if tier in ['must_run', 'should_run'] and not 'manual' in behavior:
            return True
        
        # Security and authentication scenarios are good automation candidates
        if any(keyword in behavior for keyword in ['auth', 'login', 'security', 'api']):
            return True
        
        return False

    def _extract_main_action(self, behavior: str, journey: str, original_id: str) -> str:
        """Extract main action from scenario data"""
        
        combined_text = f"{behavior} {journey} {original_id}".lower()
        
        if any(keyword in combined_text for keyword in ['auth', 'login', 'signin']):
            return "authentication"
        elif any(keyword in combined_text for keyword in ['register', 'signup']):
            return "registration"
        elif any(keyword in combined_text for keyword in ['reset', 'recover', 'forgot']):
            return "password reset"
        elif any(keyword in combined_text for keyword in ['validate', 'validation']):
            return "validation"
        elif any(keyword in combined_text for keyword in ['create', 'add', 'insert']):
            return "creation"
        elif any(keyword in combined_text for keyword in ['update', 'modify', 'edit']):
            return "update"
        elif any(keyword in combined_text for keyword in ['delete', 'remove']):
            return "deletion"
        else:
            return "processing"

    def _extract_context(self, behavior: str, journey: str, scenario_type: ScenarioType) -> str:
        """Extract context from scenario data"""
        
        if scenario_type == ScenarioType.AUTHENTICATION:
            return "user credentials"
        elif scenario_type == ScenarioType.REGISTRATION:
            return "user account"
        elif scenario_type == ScenarioType.PASSWORD_RESET:
            return "password reset token"
        elif scenario_type == ScenarioType.DATA_VALIDATION:
            return "input data"
        elif scenario_type == ScenarioType.API_ENDPOINT:
            return "API request"
        elif scenario_type == ScenarioType.UI_COMPONENT:
            return "user interface"
        else:
            return "system functionality"

    def _extract_condition(self, behavior: str, journey: str, original_id: str) -> str:
        """Extract condition from scenario data"""
        
        combined_text = f"{behavior} {journey} {original_id}".lower()
        
        if any(keyword in combined_text for keyword in ['valid', 'success', 'correct']):
            return "valid input"
        elif any(keyword in combined_text for keyword in ['invalid', 'wrong', 'incorrect', 'fail']):
            return "invalid input"
        elif any(keyword in combined_text for keyword in ['empty', 'null', 'missing']):
            return "empty input"
        elif any(keyword in combined_text for keyword in ['expired', 'old', 'outdated']):
            return "expired data"
        else:
            return "various conditions"
