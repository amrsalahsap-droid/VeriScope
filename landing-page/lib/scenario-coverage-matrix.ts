// ── Test Data Library ─────────────────────────────────────────────────────────────

/**
 * Safe placeholder test data for scenario generation
 * 
 * IMPORTANT: All values below are PLACEHOLDERS for testing purposes only.
 * They must NEVER be used in production environments.
 * - Emails are example.com domain placeholders
 * - Passwords are weak/strong examples for validation testing
 * - Tokens are placeholder strings, not real cryptographic tokens
 * - JWTs are malformed placeholders for testing rejection logic
 */
const TEST_DATA = {
  // Password Reset Domain - specific test data for password reset workflows
  passwordReset: {
    registeredEmail: "registered.user@example.com [PLACEHOLDER]",
    unregisteredEmail: "nonexistent.user@example.com [PLACEHOLDER]",
    validResetToken: "abc123-reset-token-placeholder [PLACEHOLDER]",
    expiredResetToken: "expired-reset-token-placeholder [PLACEHOLDER]",
    consumedResetToken: "already-used-reset-token-placeholder [PLACEHOLDER]",
    invalidResetToken: "malformed-token-placeholder [PLACEHOLDER]",
    weakNewPassword: "123456 [PLACEHOLDER - WEAK]",
    validNewPassword: "NewSecurePass456! [PLACEHOLDER]",
    oldPassword: "OldPassword123! [PLACEHOLDER]"
  },
  
  // Signup/Registration Domain - specific test data for user registration
  signup: {
    validEmail: "new.user@example.com [PLACEHOLDER]",
    existingEmail: "existing.user@example.com [PLACEHOLDER]",
    invalidEmailFormat: "invalid-email-format [PLACEHOLDER]",
    duplicateEmail: "duplicate.user@example.com [PLACEHOLDER]",
    validPassword: "SecurePass123! [PLACEHOLDER]",
    weakPassword: "password [PLACEHOLDER - WEAK]",
    passwordMissingUppercase: "password123! [PLACEHOLDER - MISSING UPPERCASE]",
    passwordMissingNumber: "Password! [PLACEHOLDER - MISSING NUMBER]",
    shortPassword: "Pass1! [PLACEHOLDER - TOO SHORT]",
    validName: "QA Test User [PLACEHOLDER]",
    nameWithSpecialChars: "User@#$% [PLACEHOLDER]"
  },
  
  // Auth/Security Domain - specific test data for authentication middleware
  auth: {
    validJWT: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLXV1aWQtcGxhY2Vob2xkZXIiLCJpYXQiOjE2MjAwMDAwMDB9.signature-placeholder [PLACEHOLDER - FOR AUTH ENDPOINTS ONLY]",
    expiredJWT: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLXV1aWQiLCJleHAiOjE1MDAwMDAwMDB9.expired-signature [PLACEHOLDER - EXPIRED]",
    invalidJWT: "invalid.jwt.token [PLACEHOLDER - MALFORMED]",
    tamperedJWT: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered-payload [PLACEHOLDER - TAMPERED]",
    missingAuthHeader: "[PLACEHOLDER - NO AUTH HEADER]",
    validUserUUID: "550e8400-e29b-41d4-a716-446655440000 [PLACEHOLDER]",
    staleSessionToken: "stale-session-token-abc123 [PLACEHOLDER]"
  },
  
  // API Payload Domain - generic API request/response test data
  api: {
    validAuthPayload: JSON.stringify({ email: "user@example.com [PLACEHOLDER]", password: "SecurePass123! [PLACEHOLDER]" }),
    missingFieldPayload: JSON.stringify({ email: "user@example.com [PLACEHOLDER]" }),
    invalidEmailPayload: JSON.stringify({ email: "invalid-email [PLACEHOLDER]", password: "123 [PLACEHOLDER]" }),
    invalidTypePayload: JSON.stringify({ email: 123, password: null }),
    emptyPayload: JSON.stringify({})
  },
  
  // UI Form Domain - frontend form interaction test data
  ui: {
    validSignupForm: {
      email: "ui.test@example.com [PLACEHOLDER]",
      password: "UIPass123! [PLACEHOLDER]",
      name: "UI Test User [PLACEHOLDER]"
    },
    incompleteForm: {
      email: "ui.test@example.com [PLACEHOLDER]"
    },
    invalidEmailForm: {
      email: "invalid [PLACEHOLDER]",
      password: "UIPass123! [PLACEHOLDER]"
    },
    weakPasswordForm: {
      email: "ui.test@example.com [PLACEHOLDER]",
      password: "123 [PLACEHOLDER - WEAK]"
    }
  }
};

// ── Scenario Coverage Matrix Types ────────────────────────────────────────────────

export interface ScenarioCoverageMatrix {
  impactedArea: string;
  testingType: string;
  requiredScenario: string;
  existingTest?: string; // test stable_identity if exists
  suggestedScenario?: string; // description if missing
  status: "covered" | "missing" | "suggested";
  riskLevel?: "HIGH" | "MODERATE" | "LOW";
  scenarioType?: "positive" | "negative" | "edge" | "regression";
  priority: "MUST" | "SHOULD" | "OPTIONAL";
  testData?: string; // test data/inputs
  steps?: string[]; // test steps
  expectedResult?: string; // expected result
  automationCandidate?: boolean; // whether this scenario is suitable for automation
  relatedChangedFiles?: string[]; // files that triggered this scenario
}

export interface TestingScopeItem {
  category: string;
  item: string;
}

export interface RecommendedTest {
  stable_identity: string;
  display_name: string;
  testing_type?: string;
  impacted_area?: string;
  tier?: "must_run" | "should_run" | "fallback";
  confidence?: string;
  reason?: string;
  priority_score?: number;
  reason_type?: string;
  signals?: { name: string; value: string }[];
}

export interface MatrixGenerationInput {
  testingScope: {
    must_test: TestingScopeItem[];
    should_test: TestingScopeItem[];
    optional: TestingScopeItem[];
  };
  recommendedTests: RecommendedTest[];
  riskLevel: "HIGH" | "MODERATE" | "LOW";
  impactedAreas: string[];
}

// ── Scenario Coverage Matrix Types ────────────────────────────────────────────────

export interface ScenarioCoverageMatrix {
  impactedArea: string;
  testingType: string;
  requiredScenario: string;
  existingTest?: string; // test stable_identity if exists
  suggestedScenario?: string; // description if missing
  status: "covered" | "missing" | "suggested";
  riskLevel?: "HIGH" | "MODERATE" | "LOW";
  scenarioType?: "positive" | "negative" | "edge" | "regression";
  priority: "MUST" | "SHOULD" | "OPTIONAL";
  actionabilityScore?: "LOW" | "MEDIUM" | "HIGH"; // execution readiness score
  
  // Advanced detailed scenario fields for QA Leads/SDETs:
  purpose?: string;
  executionLayer?: string;
  preconditions?: string[];
  testData?: string; // test data/inputs
  steps?: string[]; // test steps
  expectedResult?: string; // expected result
  expectedResultAssertions?: string[]; // detailed assertions list
  negativeEdgeVariants?: string[]; // related negative/edge cases
  primaryTriggerFile?: string; // primary trigger file
  relatedChangedFiles?: string[]; // files that triggered this scenario
  supportingContextFiles?: string[]; // supporting context files for the scenario
  automationRecommendation?: string; // recommendation text
  automationCandidate?: boolean; // whether this scenario is suitable for automation
}

export interface TestingScopeItem {
  category: string;
  item: string;
}

export interface RecommendedTest {
  stable_identity: string;
  display_name: string;
  testing_type?: string;
  impacted_area?: string;
  tier?: "must_run" | "should_run" | "fallback";
  confidence?: string;
  reason?: string;
  priority_score?: number;
  reason_type?: string;
  signals?: { name: string; value: string }[];
}

export interface MatrixGenerationInput {
  testingScope: {
    must_test: TestingScopeItem[];
    should_test: TestingScopeItem[];
    optional: TestingScopeItem[];
  };
  recommendedTests: RecommendedTest[];
  riskLevel: "HIGH" | "MODERATE" | "LOW";
  impactedAreas: string[];
}

// ── Comprehensive Scenario Templates ─────────────────────────────────────────────

interface ScenarioTemplate {
  requiredScenario: string;
  scenarioType: "positive" | "negative" | "edge" | "regression";
  priority: "MUST" | "SHOULD" | "OPTIONAL";
  purpose: string;
  executionLayer: string;
  preconditions: string[];
  testData: string;
  steps: string[];
  expectedResult: string;
  expectedResultAssertions: string[];
  negativeEdgeVariants?: string[];
  primaryTriggerFile: string;
  automationRecommendation: string;
  automationCandidate: boolean;
  supportingContextFiles?: string[];
}

const AUTH_SECURITY_SCENARIOS: ScenarioTemplate[] = [
  {
    requiredScenario: "valid token accepted",
    scenarioType: "positive",
    priority: "MUST",
    purpose: "Ensure valid active sessions can query protected resources without interruption.",
    executionLayer: "API Integration Gateway",
    preconditions: ["User account exists in DB", "Database connection is active", "JWT signing keys match STATE_SECRET_KEY"],
    testData: `JWT: ${TEST_DATA.auth.validJWT} (generated using secret key, sub: active-user-uuid)`,
    steps: [
      "Configure STATE_SECRET_KEY in verification context",
      "Generate a valid HS256 JWT with registered user claims",
      "Send request to protected endpoint /auth/me with Authorization: Bearer <token>",
      "Verify response status and payload profile"
    ],
    expectedResult: "Request is allowed through API Gateway and successfully fetches active user session profile details matching database record.",
    expectedResultAssertions: [
      "HTTP response status MUST be 200 OK",
      "Response JSON MUST contain user.id matching the token claim sub",
      "Response JSON MUST NOT expose sensitive credentials or password hashes",
      "JWT signature is verified against STATE_SECRET_KEY",
      "Token expiration time (exp) is validated and not exceeded"
    ],
    negativeEdgeVariants: ["Invalid token signature rejected", "Tampered payload claims rejected"],
    primaryTriggerFile: "app/dependencies/auth.py",
    supportingContextFiles: ["app/routers/auth.py", "app/models/user.py"],
    automationRecommendation: "Highly recommended: Integrate into standard pytest API request verification suites.",
    automationCandidate: true
  },
  {
    requiredScenario: "expired token rejected",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Prevent expired sessions from accessing secure user accounts.",
    executionLayer: "API Integration Gateway",
    preconditions: ["Valid STATE_SECRET_KEY is configured", "Previous session expired >= 3600s ago"],
    testData: `JWT: ${TEST_DATA.auth.expiredJWT} (generated with exp: current_time - 3600)`,
    steps: [
      "Create expired HS256 JWT token with registered user claims",
      "Send GET /auth/me with the expired token in Authorization: Bearer <token> header",
      "Verify response code and error message"
    ],
    expectedResult: "Request is blocked at the gateway, returning 401 Unauthorized with token expired error message.",
    expectedResultAssertions: [
      "HTTP response status MUST be 401 Unauthorized",
      "Response JSON error detail MUST contain 'Token has expired.'",
      "No protected user data is returned in response",
      "Token expiration timestamp is verified against current time"
    ],
    negativeEdgeVariants: ["Unexpired token succeeds", "Token with missing exp claim rejected"],
    primaryTriggerFile: "app/dependencies/auth.py",
    supportingContextFiles: ["app/routers/auth.py", "app/models/user.py"],
    automationRecommendation: "Highly recommended: Standard automated security boundary regression test.",
    automationCandidate: true
  },
  {
    requiredScenario: "invalid token rejected",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Prevent requests with malformed, tampered, or invalid tokens from retrieving protected resources.",
    executionLayer: "API Integration Gateway",
    preconditions: ["Protected endpoint expects Bearer authorization header"],
    testData: `JWT: ${TEST_DATA.auth.invalidJWT} (malformed or signed with incorrect key)`,
    steps: [
      "Send request to /auth/me with an invalid JWT string in Authorization: Bearer <token> header",
      "Verify response code and error message details"
    ],
    expectedResult: "Request is blocked, returning 401 Unauthorized with invalid token error message.",
    expectedResultAssertions: [
      "HTTP response status MUST be 401 Unauthorized",
      "Response JSON error detail MUST contain 'Invalid authentication token.'",
      "No protected user data is returned in response",
      "Error message does not reveal internal token validation details"
    ],
    negativeEdgeVariants: ["Empty token header returns 401", "Blank Authorization header returns 401"],
    primaryTriggerFile: "app/dependencies/auth.py",
    supportingContextFiles: ["app/routers/auth.py"],
    automationRecommendation: "Highly recommended: API gateway automated filter regression test.",
    automationCandidate: true
  },
  {
    requiredScenario: "reused token rejected",
    scenarioType: "negative",
    priority: "SHOULD",
    purpose: "Prevent token replay attacks or session hijacking via reused single-use tokens.",
    executionLayer: "Database & Authentication Service Layer",
    preconditions: ["One-time use token was generated and already used once", "Token-use registry or DB flag is active"],
    testData: `Token: ${TEST_DATA.passwordReset.consumedResetToken}`,
    steps: [
      "Generate reset token for user account",
      "Consume token to perform password reset successfully",
      "Attempt to use same token a second time to perform reset password",
      "Verify 401/400 response and rejection details"
    ],
    expectedResult: "The second attempt to reset password using the same token is rejected as unauthorized.",
    expectedResultAssertions: [
      "HTTP response status MUST be 401 Unauthorized or 400 Bad Request",
      "Response body details must indicate token has already been consumed",
      "User password remains unchanged in database",
      "Token consumption state is verified in database"
    ],
    negativeEdgeVariants: ["Valid unused token succeeds", "Fuzzed token format rejected"],
    primaryTriggerFile: "app/routers/auth.py",
    supportingContextFiles: ["app/dependencies/auth.py", "app/models/user.py"],
    automationRecommendation: "Highly recommended: Automate as an integration/API level replay test.",
    automationCandidate: true
  },
  {
    requiredScenario: "unauthorized request blocked",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Ensure endpoints without any authorization header are blocked by default.",
    executionLayer: "API Integration Gateway",
    preconditions: ["Endpoint is configured to require authentication (get_current_user dependency)"],
    testData: TEST_DATA.auth.missingAuthHeader,
    steps: [
      "Send GET /auth/me with no Authorization header",
      "Assert 401 response and schema details"
    ],
    expectedResult: "Request is blocked at the gateway, returning 401 Unauthorized with missing credentials message.",
    expectedResultAssertions: [
      "HTTP response status MUST be 401 Unauthorized",
      "Response JSON must detail that HTTP Bearer auth is required",
      "No protected user data is returned in response",
      "Request does not proceed to business logic layer"
    ],
    negativeEdgeVariants: ["Passing invalid schema header e.g. Basic instead of Bearer"],
    primaryTriggerFile: "app/dependencies/auth.py",
    supportingContextFiles: ["app/routers/auth.py"],
    automationRecommendation: "Highly recommended: Basic positive security policy enforcement test.",
    automationCandidate: true
  },
  {
    requiredScenario: "old session behavior verified",
    scenarioType: "edge",
    priority: "SHOULD",
    purpose: "Ensure previous sessions are invalidated upon logout or password change.",
    executionLayer: "Database & Cache Layer",
    preconditions: ["User was logged in with active session token", "Password was reset or logout was performed"],
    testData: `Session Token: ${TEST_DATA.auth.staleSessionToken}`,
    steps: [
      "Log in to retrieve valid session token",
      "Perform password reset",
      "Attempt to use the pre-reset session token to fetch /auth/me",
      "Verify session is invalidated"
    ],
    expectedResult: "Session token is successfully invalidated and rejected after credential rotation.",
    expectedResultAssertions: [
      "Stale token request returns 401 Unauthorized",
      "Session cache/DB record is flagged as deleted or inactive",
      "No protected user data is returned with stale token",
      "New session token is required after credential change"
    ],
    negativeEdgeVariants: ["Token remains valid if no password change occurs"],
    primaryTriggerFile: "app/routers/auth.py",
    supportingContextFiles: ["app/dependencies/auth.py", "app/models/user.py"],
    automationRecommendation: "Recommended: Run as integration backend API test.",
    automationCandidate: false
  }
];

const PASSWORD_RESET_SCENARIOS: ScenarioTemplate[] = [
  {
    requiredScenario: "registered user can request reset",
    scenarioType: "positive",
    priority: "MUST",
    purpose: "Verify that users with valid registered accounts can trigger the password recovery workflow.",
    executionLayer: "API Service Layer",
    preconditions: ["User account exists in the database", "Mailing service is configured/mocked"],
    testData: `Email: ${TEST_DATA.passwordReset.registeredEmail}`,
    steps: [
      "Send POST to /api/auth/reset-password/request with registered email",
      "Verify successful 200/202 response",
      "Query DB or mock mailer to assert reset token is generated"
    ],
    expectedResult: "Reset request is processed successfully, generating a unique token and dispatching reset email.",
    expectedResultAssertions: [
      "HTTP response status is 200 OK or 202 Accepted",
      "A secure reset token is saved in the database associated with the user",
      "Mailer service is invoked with the correct template and user email address",
      "Reset token is not exposed in API response",
      "User account state remains unchanged (password not modified)"
    ],
    negativeEdgeVariants: ["Spamming reset requests throttled by rate-limiter"],
    primaryTriggerFile: "app/api/auth/reset-password/route.ts",
    supportingContextFiles: ["app/routers/auth.py", "app/models/user.py"],
    automationRecommendation: "Highly recommended: Automated integration test with mocked mailer interface.",
    automationCandidate: true
  },
  {
    requiredScenario: "unregistered email handled safely",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Prevent account enumeration attacks by ensuring unregistered emails receive identical success/generic feedback without disclosing user existence.",
    executionLayer: "API Gateway & Security Layer",
    preconditions: ["Email does not exist in users database"],
    testData: `Email: ${TEST_DATA.passwordReset.unregisteredEmail}`,
    steps: [
      "Send POST to /api/auth/reset-password/request with unregistered email",
      "Verify successful generic response",
      "Assert no emails are sent and no records generated"
    ],
    expectedResult: "API returns a generic success/acknowledgment message, without indicating whether the email exists.",
    expectedResultAssertions: [
      "HTTP response status MUST match registered path (e.g. 200 OK or 202 Accepted)",
      "Response payload is indistinguishable from registered email request",
      "No email is actually dispatched to the unknown address",
      "No database records are created for non-existent user",
      "Response timing is consistent to prevent timing-based enumeration"
    ],
    negativeEdgeVariants: ["Response time timing analysis is uniform"],
    primaryTriggerFile: "app/api/auth/reset-password/route.ts",
    supportingContextFiles: ["app/routers/auth.py"],
    automationRecommendation: "Highly recommended: Automated vulnerability scan/regression test for API enumeration.",
    automationCandidate: true
  },
  {
    requiredScenario: "valid reset token changes password",
    scenarioType: "positive",
    priority: "MUST",
    purpose: "Verify that a user who has received a valid reset token can successfully change their password.",
    executionLayer: "Database & Authentication Service",
    preconditions: ["Active unused reset token exists in database linked to active user"],
    testData: `Token: ${TEST_DATA.passwordReset.validResetToken}, New Password: ${TEST_DATA.passwordReset.validNewPassword}`,
    steps: [
      "Send POST request to /api/auth/reset-password/confirm with valid token and strong new password",
      "Verify password is encrypted and updated in database",
      "Assert old password is no longer functional"
    ],
    expectedResult: "Password is secure-hashed and updated in the database, token is invalidated, and user can now log in.",
    expectedResultAssertions: [
      "HTTP response status is 200 OK",
      "User password_hash in DB is updated with secure bcrypt/argon2 hash",
      "Reset token is deleted or marked used in the database",
      "Old password authentication fails after reset",
      "New password authentication succeeds after reset",
      "Token cannot be reused for subsequent password changes"
    ],
    negativeEdgeVariants: ["Submitting invalid password format rejected"],
    primaryTriggerFile: "app/api/auth/reset-password/route.ts",
    supportingContextFiles: ["app/routers/auth.py", "app/models/user.py"],
    automationRecommendation: "Highly recommended: Integrate into Jest/Playwright API testing suites.",
    automationCandidate: true
  },
  {
    requiredScenario: "expired token rejected",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Ensure password reset tokens have strict lifespans and are rejected once expired.",
    executionLayer: "API Service Layer",
    preconditions: ["Reset token exists in database but generated_at timestamp is older than expiration limit"],
    testData: `Token: ${TEST_DATA.passwordReset.expiredResetToken}`,
    steps: [
      "Send confirmation request with expired token and new password",
      "Assert request is rejected and password remains unchanged"
    ],
    expectedResult: "Request is rejected with a validation error indicating token has expired.",
    expectedResultAssertions: [
      "HTTP response status MUST be 400 Bad Request",
      "Response error message MUST detail expired token condition",
      "User password remains unchanged in database",
      "Reset token details are not exposed in error response",
      "No authentication session is created"
    ],
    negativeEdgeVariants: ["Token generated exactly at expiration threshold"],
    primaryTriggerFile: "app/api/auth/reset-password/route.ts",
    supportingContextFiles: ["app/routers/auth.py"],
    automationRecommendation: "Highly recommended: Standard unit/integration regression test.",
    automationCandidate: true
  },
  {
    requiredScenario: "reused token rejected",
    scenarioType: "negative",
    priority: "SHOULD",
    purpose: "Ensure a password reset token can only be consumed exactly once.",
    executionLayer: "API Service Layer",
    preconditions: ["Reset token is flagged as used or already deleted"],
    testData: `Token: ${TEST_DATA.passwordReset.consumedResetToken}`,
    steps: [
      "Submit reset password request with a previously consumed token",
      "Assert request rejection and error feedback"
    ],
    expectedResult: "Request is rejected with a validation error indicating token is invalid or already used.",
    expectedResultAssertions: [
      "HTTP response status is 400 Bad Request or 401 Unauthorized",
      "DB user password remains unchanged",
      "Response does not expose token details or user information",
      "Token consumption state is verified in database"
    ],
    negativeEdgeVariants: ["Reused token from another user account"],
    primaryTriggerFile: "app/api/auth/reset-password/route.ts",
    supportingContextFiles: ["app/routers/auth.py", "app/models/user.py"],
    automationRecommendation: "Highly recommended: Security token lifecycle integration test.",
    automationCandidate: true
  },
  {
    requiredScenario: "old password rejected after reset",
    scenarioType: "negative",
    priority: "SHOULD",
    purpose: "Verify the user's previous password is deprecated and cannot be used to authenticate.",
    executionLayer: "Authentication Service",
    preconditions: ["Password reset was completed successfully"],
    testData: `Email: ${TEST_DATA.passwordReset.registeredEmail}, Old Password: ${TEST_DATA.passwordReset.oldPassword}`,
    steps: [
      "Attempt to authenticate using email and the stale password",
      "Assert login rejection and error status"
    ],
    expectedResult: "Authentication fails, returning 401 Unauthorized indicating bad credentials.",
    expectedResultAssertions: [
      "HTTP response status is 401 Unauthorized",
      "No valid session JWT or cookie is returned in headers",
      "Error message does not reveal whether user exists or password is incorrect",
      "Database password hash remains unchanged"
    ],
    negativeEdgeVariants: ["Multiple attempts with old password trigger account lockout"],
    primaryTriggerFile: "app/routers/auth.py",
    supportingContextFiles: ["app/dependencies/auth.py", "app/api/auth/reset-password/route.ts"],
    automationRecommendation: "Highly recommended: Automate as an E2E login lifecycle test.",
    automationCandidate: true
  },
  {
    requiredScenario: "new password accepted after reset",
    scenarioType: "positive",
    priority: "MUST",
    purpose: "Ensure user can successfully log in using their newly updated credentials.",
    executionLayer: "Authentication Service",
    preconditions: ["Password reset was completed successfully"],
    testData: `Email: ${TEST_DATA.passwordReset.registeredEmail}, Password: ${TEST_DATA.passwordReset.validNewPassword}`,
    steps: [
      "Authenticate using email and the newly reset password",
      "Assert successful login and token generation"
    ],
    expectedResult: "Authentication succeeds, returning valid session details and JWT tokens.",
    expectedResultAssertions: [
      "HTTP response status is 200 OK",
      "Response payload contains valid active user profile",
      "Set-Cookie or Auth response contains well-formed active session JWT",
      "JWT does not expose sensitive password or internal user data",
      "Session is properly linked to user account in database"
    ],
    negativeEdgeVariants: ["Case-sensitive password matching holds true"],
    primaryTriggerFile: "app/routers/auth.py",
    supportingContextFiles: ["app/dependencies/auth.py", "app/api/auth/reset-password/route.ts"],
    automationRecommendation: "Highly recommended: E2E login automated integration test.",
    automationCandidate: true
  }
];

const SIGNUP_REGISTRATION_SCENARIOS: ScenarioTemplate[] = [
  {
    requiredScenario: "valid signup creates account",
    scenarioType: "positive",
    priority: "MUST",
    purpose: "Verify fresh, valid registration requests successfully provision user profiles and workspace configurations.",
    executionLayer: "API Service Layer",
    preconditions: ["Email does not exist in database"],
    testData: `Email: ${TEST_DATA.signup.validEmail}, Name: ${TEST_DATA.signup.validName}, Password: ${TEST_DATA.signup.validPassword}`,
    steps: [
      "POST valid registration request to /api/auth/signup",
      "Verify DB user creation and automatic OWNER workspace assignment",
      "Verify confirmation trigger"
    ],
    expectedResult: "User record is created with secure-hashed password, workspace is provisioned, and success payload is returned.",
    expectedResultAssertions: [
      "HTTP response status MUST be 201 Created or 200 OK",
      "User row in DB exists with matching email, hashed password, and default metadata",
      "Workspace created automatically with user linked as OWNER role",
      "Password is stored as secure hash (bcrypt/argon2), not plaintext",
      "Response does not expose password or sensitive internal data"
    ],
    negativeEdgeVariants: ["Special characters in user display name are handled safely"],
    primaryTriggerFile: "app/routers/auth.py",
    supportingContextFiles: ["app/models/user.py", "app/models/workspace.py"],
    automationRecommendation: "Highly recommended: Automate as backend integration test.",
    automationCandidate: true
  },
  {
    requiredScenario: "duplicate email rejected",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Verify registration with a previously registered email address is cleanly rejected to avoid account duplicates.",
    executionLayer: "API Service Layer",
    preconditions: ["User account with matching email already exists in DB"],
    testData: `Email: ${TEST_DATA.signup.existingEmail}, Password: ${TEST_DATA.signup.validPassword}`,
    steps: [
      "POST registration details with an existing email",
      "Verify 400 rejection and user-friendly validation message"
    ],
    expectedResult: "Request is rejected with a validation error indicating email is already registered.",
    expectedResultAssertions: [
      "HTTP response status is 400 Bad Request or 422 Unprocessable Entity",
      "Response JSON contains clean error detail stating email already registered",
      "No duplicate database row or workspace is generated",
      "Error message does not reveal existing user details or account status",
      "Database state remains unchanged"
    ],
    negativeEdgeVariants: ["Case insensitive matching (e.g. USER@example.com vs user@example.com) rejected"],
    primaryTriggerFile: "app/routers/auth.py",
    supportingContextFiles: ["app/models/user.py"],
    automationRecommendation: "Highly recommended: Basic API validation test.",
    automationCandidate: true
  },
  {
    requiredScenario: "invalid email rejected",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Ensure email formats must conform to valid patterns before processing registration.",
    executionLayer: "API Validation Layer",
    preconditions: ["None"],
    testData: `Email: ${TEST_DATA.signup.invalidEmailFormat}`,
    steps: [
      "POST registration details with invalid email format",
      "Verify validation error and request block"
    ],
    expectedResult: "Request is blocked at validation layer before querying database.",
    expectedResultAssertions: [
      "HTTP response status is 400 Bad Request or 422 Unprocessable Entity",
      "Response details reference invalid email syntax",
      "No database query is executed for invalid email format",
      "No user account is created in database"
    ],
    negativeEdgeVariants: ["Extremely long emails", "Missing domain", "Multiple @ symbols"],
    primaryTriggerFile: "app/routers/auth.py",
    supportingContextFiles: ["app/dependencies/auth.py"],
    automationRecommendation: "Highly recommended: Fast API validation unit test.",
    automationCandidate: true
  },
  {
    requiredScenario: "weak password rejected",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Enforce security standards by rejecting passwords that do not meet complexity requirements.",
    executionLayer: "API Validation / Auth Service",
    preconditions: ["Complexity guidelines: min 8 chars, 1 uppercase, 1 number"],
    testData: `Password: ${TEST_DATA.signup.weakPassword}`,
    steps: [
      "POST registration with a weak password",
      "Verify complexity enforcement error response"
    ],
    expectedResult: "Request is rejected with error specifying password requirements.",
    expectedResultAssertions: [
      "HTTP response status is 400 Bad Request or 422 Unprocessable Entity",
      "Response message clearly lists complexity requirements that were violated",
      "No user account is created in database",
      "Password is not stored or processed by the system"
    ],
    negativeEdgeVariants: ["Password with 7 characters", "Password with no uppercase", "Password with no digits"],
    primaryTriggerFile: "app/routers/auth.py",
    supportingContextFiles: ["app/dependencies/auth.py"],
    automationRecommendation: "Highly recommended: Unit test coverage in Python auth validators.",
    automationCandidate: true
  },
  {
    requiredScenario: "required fields enforced",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Verify registration is blocked if essential field inputs (email, password) are absent.",
    executionLayer: "API Validation Layer",
    preconditions: ["None"],
    testData: `Form Payload: ${JSON.stringify({ email: TEST_DATA.signup.validEmail })}`,
    steps: [
      "POST payload with missing required email/password field",
      "Assert validation payload details"
    ],
    expectedResult: "Request is blocked with explicit field validation feedback.",
    expectedResultAssertions: [
      "HTTP response status is 422 Unprocessable Entity",
      "Response payload specifies missing fields precisely",
      "No database records are created",
      "No partial data is persisted"
    ],
    negativeEdgeVariants: ["Null values passed", "Empty spaces passed as names"],
    primaryTriggerFile: "app/routers/auth.py",
    supportingContextFiles: ["app/dependencies/auth.py"],
    automationRecommendation: "Highly recommended: Automated validation schema test.",
    automationCandidate: true
  },
  {
    requiredScenario: "successful signup can login",
    scenarioType: "positive",
    priority: "MUST",
    purpose: "Verify end-to-end user path: successful sign-up immediately followed by successful authentication.",
    executionLayer: "E2E Integration Layer",
    preconditions: ["Clean DB environment for test user"],
    testData: `Email: ${TEST_DATA.signup.validEmail}, Password: ${TEST_DATA.signup.validPassword}`,
    steps: [
      "Register new user account",
      "Query authenticate POST with matching credentials",
      "Assert token generation and session credentials"
    ],
    expectedResult: "User can successfully login and retrieve valid active JWT credentials immediately post-signup.",
    expectedResultAssertions: [
      "Signup returns 201/200 OK",
      "Login returns 200 OK with valid bearer token",
      "Token yields authorized state on protected endpoints",
      "JWT does not expose password or sensitive user data",
      "User account state is consistent between signup and login"
    ],
    negativeEdgeVariants: ["Login works on subsequent attempts after registration"],
    primaryTriggerFile: "app/routers/auth.py",
    supportingContextFiles: ["app/dependencies/auth.py", "app/models/user.py"],
    automationRecommendation: "Highly recommended: Playwright/Cypress E2E scenario.",
    automationCandidate: true
  }
];

const UI_SCENARIOS: ScenarioTemplate[] = [
  {
    requiredScenario: "validation message shown",
    scenarioType: "positive",
    priority: "MUST",
    purpose: "Verify that validation messages are displayed immediately on the UI when input validation fails.",
    executionLayer: "Frontend Client UI",
    preconditions: ["User is on the sign-up or reset-password form page"],
    testData: `Form fields: email: ${TEST_DATA.ui.invalidEmailForm.email}, password: ${TEST_DATA.ui.invalidEmailForm.password}`,
    steps: [
      "Navigate to form page",
      "Type invalid email into email input",
      "Click Submit button",
      "Verify error message appears near email input field"
    ],
    expectedResult: "UI displays clear, accessible validation message explaining that the input email is invalid.",
    expectedResultAssertions: [
      "Error message element is visible in the DOM",
      "Error message specifies invalid email criteria",
      "Form submission is prevented",
      "No API request is sent to backend",
      "User input remains in form field for correction"
    ],
    negativeEdgeVariants: ["Keyboard navigation focuses on field with error"],
    primaryTriggerFile: "landing-page/app/page.tsx",
    supportingContextFiles: ["landing-page/components/signup-form.tsx"],
    automationRecommendation: "Highly recommended: Playwright component/unit test.",
    automationCandidate: false
  },
  {
    requiredScenario: "submit disabled for invalid form",
    scenarioType: "negative",
    priority: "SHOULD",
    purpose: "Ensure the form submit button is disabled when inputs are invalid, preventing unnecessary backend load.",
    executionLayer: "Frontend Client UI",
    preconditions: ["User is on form page"],
    testData: `Form fields: email: empty, password: ${TEST_DATA.ui.weakPasswordForm.password}`,
    steps: [
      "Type weak password and leave email empty",
      "Verify submit button has disabled attribute or class"
    ],
    expectedResult: "Submit button is visually styled as disabled and click actions are entirely blocked.",
    expectedResultAssertions: [
      "Button element contains 'disabled' attribute or isDisabled property",
      "Pointer events on button are disabled via CSS",
      "No API request is sent when button is clicked",
      "Button visual state clearly indicates disabled state to user"
    ],
    negativeEdgeVariants: ["Attempting submit via Enter keypress is blocked"],
    primaryTriggerFile: "landing-page/app/page.tsx",
    supportingContextFiles: ["landing-page/components/signup-form.tsx"],
    automationRecommendation: "Recommended: Playwright frontend regression test.",
    automationCandidate: false
  },
  {
    requiredScenario: "loading state shown",
    scenarioType: "positive",
    priority: "SHOULD",
    purpose: "Provide visual feedback to users during network requests to prevent duplicate submissions.",
    executionLayer: "Frontend Client UI",
    preconditions: ["Form inputs are valid", "Network speed is simulated as slow"],
    testData: `Form: ${JSON.stringify(TEST_DATA.ui.validSignupForm)}`,
    steps: [
      "Enter valid registration inputs",
      "Click Submit button",
      "Verify loading spinner or button loading indicator appears instantly",
      "Verify button is disabled during request flight"
    ],
    expectedResult: "UI renders a beautiful loading state and blocks multi-click actions while network request is pending.",
    expectedResultAssertions: [
      "Spinner or loading text is visible in DOM",
      "Submit button is disabled while state is pending",
      "Original submit button text is replaced by loader",
      "Multiple button clicks do not trigger duplicate API requests",
      "Loading state is cleared when request completes or fails"
    ],
    negativeEdgeVariants: ["Fast connection handles loader gracefully without flicker"],
    primaryTriggerFile: "landing-page/app/page.tsx",
    supportingContextFiles: ["landing-page/components/signup-form.tsx"],
    automationRecommendation: "Recommended: Playwright frontend interaction test.",
    automationCandidate: false
  },
  {
    requiredScenario: "server error displayed",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Gracefully handle backend failure by presenting user-friendly error messages instead of raw crash details.",
    executionLayer: "Frontend Client UI",
    preconditions: ["Backend API returns 500 Internal Server Error"],
    testData: "Mocked API endpoint returns 500 error",
    steps: [
      "Submit valid form on UI",
      "Intercept request and return 500 error response",
      "Verify Toast or Alert error banner appears with clean message"
    ],
    expectedResult: "UI intercepts error response and displays a helpful, non-technical error notification.",
    expectedResultAssertions: [
      "Toast or alert banner is visible in viewport",
      "No raw webpack stack trace or DB errors are printed on screen",
      "User is given option to retry or dismiss",
      "Error message does not expose sensitive system details",
      "Form state is preserved for retry"
    ],
    negativeEdgeVariants: ["Network disconnect is handled with offline message"],
    primaryTriggerFile: "landing-page/app/page.tsx",
    supportingContextFiles: ["landing-page/lib/api-client.ts"],
    automationRecommendation: "Highly recommended: Playwright error intercept test.",
    automationCandidate: false
  },
  {
    requiredScenario: "success redirect/message shown",
    scenarioType: "positive",
    priority: "MUST",
    purpose: "Ensure the UI navigates or presents successful confirmation once backend operations complete.",
    executionLayer: "Frontend Client UI",
    preconditions: ["Backend API returns success"],
    testData: "Mocked API returns success response",
    steps: [
      "Submit valid form",
      "Intercept API with 200/201 success",
      "Verify routing change or success dialog display"
    ],
    expectedResult: "Successful flow completes, prompting redirect or friendly onboarding instructions.",
    expectedResultAssertions: [
      "Success toast/message is displayed",
      "Browser redirects to landing page or workspace dashboard as configured",
      "Form is cleared after successful submission",
      "User session is established with valid authentication"
    ],
    negativeEdgeVariants: ["Back button navigation is handled safely"],
    primaryTriggerFile: "landing-page/app/page.tsx",
    supportingContextFiles: ["landing-page/lib/router.ts"],
    automationRecommendation: "Highly recommended: Playwright workflow verification test.",
    automationCandidate: false
  }
];

const API_SCENARIOS: ScenarioTemplate[] = [
  {
    requiredScenario: "valid request returns success",
    scenarioType: "positive",
    priority: "MUST",
    purpose: "Verify the core API contract behaves correctly under optimal inputs.",
    executionLayer: "API Controller / Router Layer",
    preconditions: ["Backend database is online", "Input arguments conform to schema"],
    testData: `Payload: ${TEST_DATA.api.validAuthPayload}`,
    steps: [
      "Send POST request with valid email and password payload",
      "Verify 200 OK status",
      "Assert response payload matches OpenAPI contract schema"
    ],
    expectedResult: "Endpoint processes request and returns success state with expected metadata.",
    expectedResultAssertions: [
      "HTTP response status MUST be 200 OK",
      "Response payload must contain expected keys",
      "Database state changes reflect request execution",
      "Response does not expose sensitive internal data or passwords",
      "Response conforms to OpenAPI schema contract"
    ],
    negativeEdgeVariants: ["Submitting valid fields with unexpected query params works safely"],
    primaryTriggerFile: "app/main.py",
    supportingContextFiles: ["app/routers/auth.py", "app/models/user.py"],
    automationRecommendation: "Highly recommended: Pytest/httpx integration test.",
    automationCandidate: true
  },
  {
    requiredScenario: "missing required fields returns 400",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Ensure controller/router validation intercepts invalid empty request payloads prior to business processing.",
    executionLayer: "API Controller / Validator",
    preconditions: ["None"],
    testData: `Payload: ${TEST_DATA.api.missingFieldPayload}`,
    steps: [
      "Send request with missing password field",
      "Verify rejection details"
    ],
    expectedResult: "Request is rejected immediately, returning 422/400 validation error.",
    expectedResultAssertions: [
      "HTTP response status is 422 Unprocessable Entity or 400 Bad Request",
      "Error JSON identifies missing 'password' field precisely",
      "No database query is executed for missing required fields",
      "No partial data is persisted in database"
    ],
    negativeEdgeVariants: ["Null values in optional fields allowed"],
    primaryTriggerFile: "app/main.py",
    supportingContextFiles: ["app/routers/auth.py"],
    automationRecommendation: "Highly recommended: Automated endpoint schema test.",
    automationCandidate: true
  },
  {
    requiredScenario: "invalid payload returns validation error",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Prevent malformed payload types (e.g. integer emails) from causing runtime server exceptions.",
    executionLayer: "API Controller / Validator",
    preconditions: ["None"],
    testData: `Payload: ${TEST_DATA.api.invalidEmailPayload}`,
    steps: [
      "Send request with malformed payloads",
      "Assert validation response details"
    ],
    expectedResult: "Request is cleanly intercepted and blocked with user validation feedback.",
    expectedResultAssertions: [
      "HTTP response status is 422 Unprocessable Entity or 400 Bad Request",
      "No internal database queries are made",
      "Error message does not expose internal system details",
      "Request does not reach business logic layer"
    ],
    negativeEdgeVariants: ["Passing extremely nested payloads"],
    primaryTriggerFile: "app/main.py",
    supportingContextFiles: ["app/routers/auth.py"],
    automationRecommendation: "Highly recommended: Schema validator unit test.",
    automationCandidate: true
  },
  {
    requiredScenario: "unauthenticated request blocked if relevant",
    scenarioType: "negative",
    priority: "MUST",
    purpose: "Ensure protected API routes block anonymous requests uniformly.",
    executionLayer: "Security Interceptor Gateway",
    preconditions: ["Route requires active authentication"],
    testData: "No Bearer token present",
    steps: [
      "Send GET/DELETE request to protected endpoint without Authorization header",
      "Assert rejection details"
    ],
    expectedResult: "Request is blocked with 401 Unauthorized status.",
    expectedResultAssertions: [
      "HTTP response status MUST be 401 Unauthorized",
      "Response payload defines auth error clearly",
      "No protected data is returned in response",
      "Request does not proceed to business logic layer"
    ],
    negativeEdgeVariants: ["Passing empty string as Bearer token"],
    primaryTriggerFile: "app/dependencies/auth.py",
    supportingContextFiles: ["app/routers/auth.py"],
    automationRecommendation: "Highly recommended: Fast security policy test.",
    automationCandidate: true
  },
  {
    requiredScenario: "response schema matches expected contract",
    scenarioType: "positive",
    priority: "SHOULD",
    purpose: "Enforce contract stability across API responses to avoid regression breakage on downstream microservices.",
    executionLayer: "API Integration / Validation Layer",
    preconditions: ["Database has active test records"],
    testData: `Payload: ${TEST_DATA.api.validAuthPayload}`,
    steps: [
      "Query endpoint successfully",
      "Validate JSON response structure against pydantic schema contract"
    ],
    expectedResult: "Response structure matches exactly without missing/extra keys.",
    expectedResultAssertions: [
      "HTTP response status is 200 OK",
      "Pydantic model validation of response succeeds without ValidationError",
      "Response does not contain unexpected fields",
      "Response does not expose sensitive internal data"
    ],
    negativeEdgeVariants: ["Contract validation holds on different DB engine versions"],
    primaryTriggerFile: "app/main.py",
    supportingContextFiles: ["app/routers/auth.py", "app/models/user.py"],
    automationRecommendation: "Highly recommended: Pytest automated schema validator.",
    automationCandidate: true
  }
];

// ── Scenario Generation Logic ─────────────────────────────────────────────────────

/**
 * Calculate actionability score for a scenario based on execution readiness
 * 
 * Scoring criteria:
 * - has specific title (requiredScenario)
 * - has preconditions
 * - has test data
 * - has detailed steps (at least 2 steps)
 * - has multi-assertion expected result (at least 3 assertions)
 * - has primary trigger file
 * - has execution layer
 * 
 * Score:
 * - HIGH: 6-7 criteria met
 * - MEDIUM: 4-5 criteria met
 * - LOW: 0-3 criteria met
 */
function calculateActionabilityScore(scenario: ScenarioCoverageMatrix): "LOW" | "MEDIUM" | "HIGH" {
  let score = 0;
  
  // Has specific title
  if (scenario.requiredScenario && scenario.requiredScenario.length > 5) {
    score += 1;
  }
  
  // Has preconditions
  if (scenario.preconditions && scenario.preconditions.length > 0) {
    score += 1;
  }
  
  // Has test data
  if (scenario.testData && scenario.testData.length > 0) {
    score += 1;
  }
  
  // Has detailed steps (at least 2 steps)
  if (scenario.steps && scenario.steps.length >= 2) {
    score += 1;
  }
  
  // Has multi-assertion expected result (at least 3 assertions)
  if (scenario.expectedResultAssertions && scenario.expectedResultAssertions.length >= 3) {
    score += 1;
  }
  
  // Has primary trigger file
  if (scenario.primaryTriggerFile && scenario.primaryTriggerFile.length > 0) {
    score += 1;
  }
  
  // Has execution layer
  if (scenario.executionLayer && scenario.executionLayer.length > 0) {
    score += 1;
  }
  
  if (score >= 6) return "HIGH";
  if (score >= 4) return "MEDIUM";
  return "LOW";
}

/**
 * Get scenario templates based on impacted area and testing type
 */
function getScenarioTemplates(
  impactedArea: string,
  testingType: string,
  riskLevel: "HIGH" | "MODERATE" | "LOW"
): ScenarioTemplate[] {
  const areaLower = impactedArea.toLowerCase();
  const typeLower = testingType.toLowerCase();
  
  // AUTH/SECURITY scenarios
  if (areaLower.includes("auth") || areaLower.includes("security") || typeLower.includes("security")) {
    return AUTH_SECURITY_SCENARIOS;
  }
  
  // PASSWORD RESET scenarios
  if (areaLower.includes("password") || areaLower.includes("reset")) {
    return PASSWORD_RESET_SCENARIOS;
  }
  
  // SIGNUP/REGISTRATION scenarios
  if (areaLower.includes("signup") || areaLower.includes("registration") || areaLower.includes("sign-up")) {
    return SIGNUP_REGISTRATION_SCENARIOS;
  }
  
  // UI scenarios
  if (typeLower.includes("ui") || typeLower.includes("frontend")) {
    return UI_SCENARIOS;
  }
  
  // API scenarios
  if (typeLower.includes("api") || typeLower.includes("endpoint")) {
    return API_SCENARIOS;
  }
  
  // Default fallback scenarios
  return [
    {
      requiredScenario: "valid input accepted",
      scenarioType: "positive",
      priority: "MUST",
      purpose: "Ensure standard valid inputs are processed correctly without errors.",
      executionLayer: "Service Component Layer",
      preconditions: ["System context is initialized"],
      testData: "valid input parameters",
      steps: ["Provide valid input parameter", "Verify processing succeeds without exception"],
      expectedResult: "Input processed successfully",
      expectedResultAssertions: ["Execution completes without errors", "State mutations match expectation"],
      primaryTriggerFile: "app/main.py",
      automationRecommendation: "Highly recommended: Automate as a backend component unit test.",
      automationCandidate: true
    },
    {
      requiredScenario: "invalid input rejected",
      scenarioType: "negative",
      priority: "MUST",
      purpose: "Ensure malformed or invalid inputs are caught and rejected cleanly.",
      executionLayer: "Service Component Layer",
      preconditions: ["System context is initialized"],
      testData: "invalid fuzzed input parameters",
      steps: ["Provide invalid/empty input parameter", "Verify system rejects request with validation error"],
      expectedResult: "Input rejected with appropriate validation error",
      expectedResultAssertions: ["HTTP status or method returns error code", "Error response identifies invalid parameter"],
      primaryTriggerFile: "app/main.py",
      automationRecommendation: "Highly recommended: Automate as a backend validation test.",
      automationCandidate: true
    }
  ];
}

/**
 * Check if a scenario has an existing test in the recommended tests
 */
function findExistingTest(
  scenario: string,
  testingType: string,
  impactedArea: string,
  recommendedTests: RecommendedTest[]
): string | undefined {
  const matchingTest = recommendedTests.find(test => {
    const testType = test.testing_type || "Regression";
    const testArea = test.impacted_area || "";
    
    if (testType.toLowerCase() !== testingType.toLowerCase()) {
      return false;
    }
    
    if (impactedArea && testArea && testArea.toLowerCase() !== impactedArea.toLowerCase()) {
      return false;
    }
    
    const scenarioKeywords = scenario.toLowerCase().split(" ").filter(w => w.length > 3);
    const testName = test.display_name.toLowerCase();
    const hasKeywordMatch = scenarioKeywords.some(keyword => testName.includes(keyword));
    
    return hasKeywordMatch;
  });
  
  return matchingTest?.stable_identity;
}

/**
 * Generate the complete Scenario Coverage Matrix with comprehensive scenarios
 */
export function generateScenarioCoverageMatrix(input: MatrixGenerationInput): ScenarioCoverageMatrix[] {
  const { testingScope, recommendedTests, riskLevel, impactedAreas } = input;
  
  const matrix: ScenarioCoverageMatrix[] = [];
  const defaultImpactedArea = impactedAreas[0] || "General";
  
  // Process MUST TEST items with comprehensive scenarios
  for (const item of testingScope.must_test) {
    const templates = getScenarioTemplates(defaultImpactedArea, item.category, riskLevel);
    
    for (const template of templates) {
      const existingTest = findExistingTest(
        template.requiredScenario,
        item.category,
        defaultImpactedArea,
        recommendedTests
      );
      
      const scenario: ScenarioCoverageMatrix = {
        impactedArea: defaultImpactedArea,
        testingType: item.category,
        requiredScenario: template.requiredScenario,
        existingTest: existingTest,
        suggestedScenario: existingTest ? undefined : template.requiredScenario,
        status: (existingTest ? "covered" : "suggested") as "covered" | "missing" | "suggested",
        riskLevel,
        scenarioType: template.scenarioType,
        priority: template.priority,
        purpose: template.purpose,
        executionLayer: template.executionLayer,
        preconditions: template.preconditions,
        testData: template.testData,
        steps: template.steps,
        expectedResult: template.expectedResult,
        expectedResultAssertions: template.expectedResultAssertions,
        negativeEdgeVariants: template.negativeEdgeVariants,
        primaryTriggerFile: template.primaryTriggerFile,
        automationRecommendation: template.automationRecommendation,
        automationCandidate: template.automationCandidate,
        relatedChangedFiles: impactedAreas,
        supportingContextFiles: template.supportingContextFiles
      };
      
      // Calculate actionability score
      scenario.actionabilityScore = calculateActionabilityScore(scenario);
      
      matrix.push(scenario);
    }
  }
  
  // Process SHOULD TEST items with comprehensive scenarios
  for (const item of testingScope.should_test) {
    const templates = getScenarioTemplates(defaultImpactedArea, item.category, riskLevel);
    
    // For SHOULD test, use fewer scenarios (prioritize MUST scenarios)
    const prioritizedTemplates = templates.filter(t => t.priority === "MUST").slice(0, 3);
    
    for (const template of prioritizedTemplates) {
      const existingTest = findExistingTest(
        template.requiredScenario,
        item.category,
        defaultImpactedArea,
        recommendedTests
      );
      
      const scenario: ScenarioCoverageMatrix = {
        impactedArea: defaultImpactedArea,
        testingType: item.category,
        requiredScenario: template.requiredScenario,
        existingTest: existingTest,
        suggestedScenario: existingTest ? undefined : template.requiredScenario,
        status: (existingTest ? "covered" : "suggested") as "covered" | "missing" | "suggested",
        riskLevel,
        scenarioType: template.scenarioType,
        priority: "SHOULD",
        purpose: template.purpose,
        executionLayer: template.executionLayer,
        preconditions: template.preconditions,
        testData: template.testData,
        steps: template.steps,
        expectedResult: template.expectedResult,
        expectedResultAssertions: template.expectedResultAssertions,
        negativeEdgeVariants: template.negativeEdgeVariants,
        primaryTriggerFile: template.primaryTriggerFile,
        automationRecommendation: template.automationRecommendation,
        automationCandidate: template.automationCandidate,
        relatedChangedFiles: impactedAreas,
        supportingContextFiles: template.supportingContextFiles
      };
      
      // Calculate actionability score
      scenario.actionabilityScore = calculateActionabilityScore(scenario);
      
      matrix.push(scenario);
    }
  }
  
  // Process OPTIONAL items (minimal scenarios)
  for (const item of testingScope.optional) {
    const existingTest = findExistingTest(
      item.item,
      item.category,
      defaultImpactedArea,
      recommendedTests
    );
    
    matrix.push({
      impactedArea: defaultImpactedArea,
      testingType: item.category,
      requiredScenario: item.item,
      existingTest: existingTest,
      suggestedScenario: existingTest ? undefined : item.item,
      status: existingTest ? "covered" : "suggested",
      riskLevel,
      scenarioType: "regression",
      priority: "OPTIONAL",
      testData: "regression test data",
      steps: ["Execute regression test", "Verify expected behavior"],
      expectedResult: "Regression test passes",
      automationCandidate: true,
      relatedChangedFiles: impactedAreas
    });
  }
  
  // Deduplicate exact duplicates only (keep distinct scenarios separate)
  // Deduplication criteria: normalized title, testing_type, impacted_area, and expected_result must all match
  const deduplicatedMatrix: ScenarioCoverageMatrix[] = [];
  const seen = new Set<string>();
  
  for (const row of matrix) {
    // Normalize title for comparison (lowercase, trim)
    const normalizedTitle = row.requiredScenario.toLowerCase().trim();
    const normalizedTestingType = row.testingType.toLowerCase().trim();
    const normalizedImpactedArea = row.impactedArea.toLowerCase().trim();
    const normalizedExpectedResult = row.expectedResult?.toLowerCase().trim() || "";
    
    // Create comprehensive deduplication key
    const key = `${normalizedImpactedArea}|${normalizedTestingType}|${normalizedTitle}|${normalizedExpectedResult}`;
    
    if (!seen.has(key)) {
      seen.add(key);
      deduplicatedMatrix.push(row);
    }
  }
  
  // Filter by actionability score: only show HIGH/MEDIUM scenarios
  // If no HIGH/MEDIUM scenarios exist for a category, include LOW scenarios as fallback
  const filteredMatrix: ScenarioCoverageMatrix[] = [];
  
  // Group by testing type to check if we have any HIGH/MEDIUM scenarios
  const scenariosByType = new Map<string, ScenarioCoverageMatrix[]>();
  for (const scenario of deduplicatedMatrix) {
    const type = scenario.testingType;
    if (!scenariosByType.has(type)) {
      scenariosByType.set(type, []);
    }
    scenariosByType.get(type)!.push(scenario);
  }
  
  // For each testing type, include HIGH/MEDIUM scenarios, or LOW if no better options
  for (const [type, scenarios] of scenariosByType) {
    const highMediumScenarios = scenarios.filter(s => 
      s.actionabilityScore === "HIGH" || s.actionabilityScore === "MEDIUM"
    );
    
    if (highMediumScenarios.length > 0) {
      filteredMatrix.push(...highMediumScenarios);
    } else {
      // Fallback to LOW scenarios if no HIGH/MEDIUM exist
      filteredMatrix.push(...scenarios);
    }
  }
  
  return filteredMatrix;
}
