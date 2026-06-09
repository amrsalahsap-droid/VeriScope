# Behavior Catalog Architecture Proposal

This proposal outlines the design and integration strategy for a repository-scoped **Behavior Catalog** in Veriscope. The catalog serves as the single source of truth for business-level capabilities, user journeys, and expected system behaviors. By moving this intelligence from hardcoded static analyzer scripts into a structured database layer, Veriscope becomes fully customizable, queryable, and extensible per repository.

---

## 1. Architectural Overview & Answers to Key Questions

### Question 1: What repository-scoped entities already exist?
Veriscope currently has several repository-scoped modeling layers:
*   **Repository** (`repositories` table): The root scope owning all PRs, sync jobs, and recommendation artifacts.
*   **TestCase** (`test_cases` table): The stable, historically tracked identity of existing code-level JUnit tests.
*   **TestCoverageLink** (`test_coverage_links` table): The directed knowledge-graph edge mapping `test_identifier` to `file_path` with telemetry counters (runs, successes, failures, overrides, defects).
*   **DomainMap** (`domain_maps` table): High-level mappings from folders/modules to domains automatically learned from code organization.
*   **ProjectContextIndex** (`project_context_indices` table): Flat JSONB collections describing detected frameworks, routes, pages, domains, user journeys, test assets, and security-sensitive files.

### Question 2: Where should Behavior Catalog be attached?
The Behavior Catalog should be attached at the **Repository** level, with optional **Workspace** level inheritance.
*   **Scoped directly to `repositories`**: Each repository owns its specific business capabilities and journeys.
*   **Fallback to global defaults**: Veriscope will seed the system with a set of default catalog items (e.g., standard authentication and billing flows) which apply when no custom repository-scoped behavior is defined.

### Question 3: How should behaviors relate to:
*   **Repositories**: A `Repository` has a 1-to-many relationship with `BehaviorCatalogItem`.
*   **Journeys**: Each catalog item specifies a string identifier for the high-level `user_journey` (e.g., "Password Recovery Flow") it belongs to, acting as a grouping/organizing dimension.
*   **Risks**: Each catalog item has defined `risk_level` ("HIGH", "MEDIUM", "LOW") and `risk_category` ("Security", "Functional", "Regression") attributes which are referenced by the recommendation engine.
*   **Scenarios**: A single `BehaviorCatalogItem` defines the schema/contract from which executable `SuggestedTestScenario` records are generated for a run.
*   **Recommendation Runs**: Many-to-many. During a `RecommendationRun`, `ScenarioIntent` records (which are run-scoped) will map back to a canonical `BehaviorCatalogItem` via its unique `canonical_key`.

### Question 4: Are there existing tables that overlap with behaviors?
*   **`ScenarioIntent`**: Currently duplicates many fields that a behavior catalog requires (domain, feature, behavior, layer, case_type, title, priority, risk_category), but is structurally restricted per recommendation run.
*   **`ProjectContextIndex`**: Houses unstructured `user_journeys` and `domains` within JSONB columns. The relational Behavior Catalog table will extract these into strongly-typed queryable columns and relationships.

### Question 5: What naming conventions should be reused?
*   **Canonical Key Format**: Reuses the deterministic `domain.feature.behavior.layer.case_type` format (e.g., `authentication.reset-password.expired-token-rejected.api.negative`) managed by the `ScenarioIntentNormalizer`.
*   **SME Terminology**: Maintains standard capabilities (`login`, `signup`, `checkout`, etc.) and user journeys ("User Authentication Flow", "User Registration Flow") to prevent schema mismatch.
*   **Priority values**: Standardizes on `"MUST"`, `"SHOULD"`, and `"OPTIONAL"`.

---

## 2. Entity Relationship Diagram (ERD)

```mermaid
er_diagram
    repositories ||--o{ behavior_catalog_items : "owns"
    repositories ||--o{ recommendation_runs : "generates"
    repositories ||--o{ test_cases : "tracks"
    
    behavior_catalog_items ||--o{ scenario_intents : "instantiated_as"
    behavior_catalog_items ||--o{ test_coverage_links : "defines_behavior_for_file_edges"

    recommendation_runs ||--o{ scenario_intents : "contains"
    recommendation_runs ||--o{ suggested_test_scenarios : "recommends"

    scenario_intents ||--o| suggested_test_scenarios : "describes"
    test_cases ||--o{ test_coverage_links : "has_edges"
```

### Table Definitions

#### `behavior_catalog_items`
Holds the canonical specifications of all known system behaviors.

| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PRIMARY KEY | Unique ID of the behavior. |
| `repository_id` | UUID | FOREIGN KEY (`repositories.id`), Nullable | Scoped to a specific repo. NULL implies global default behavior. |
| `workspace_id` | UUID | FOREIGN KEY (`workspaces.id`), Nullable | Scoped to a specific workspace. |
| `canonical_key` | VARCHAR | UNIQUE, NOT NULL | Deterministic key: `domain.feature.behavior.layer.case_type`. |
| `domain` | VARCHAR | NOT NULL | Canonical capability (e.g., `authentication`). |
| `feature` | VARCHAR | NOT NULL | Canonical feature (e.g., `reset-password`). |
| `behavior` | VARCHAR | NOT NULL | Expected behavior (e.g., `expired-token-rejected`). |
| `layer` | VARCHAR | NOT NULL | System layer (`api`, `ui`, `integration`). |
| `case_type` | VARCHAR | NOT NULL | Positivity/Negative type (`positive`, `negative`, `edge`). |
| `title` | VARCHAR | NOT NULL | Short human-readable summary. |
| `description` | TEXT | Nullable | In-depth description of the behavior. |
| `user_journey` | VARCHAR | NOT NULL | Associated high-level flow (e.g., `Password Recovery Flow`). |
| `base_priority` | VARCHAR | NOT NULL | Default priority (`MUST`, `SHOULD`, `OPTIONAL`). |
| `risk_level` | VARCHAR | NOT NULL | Default risk category (`HIGH`, `MEDIUM`, `LOW`). |
| `preconditions` | JSONB | NOT NULL, Default `[]` | List of setup requirements (strings). |
| `steps` | JSONB | NOT NULL, Default `[]` | List of user/system actions (strings). |
| `expected_result` | VARCHAR | NOT NULL | Final assertion target. |
| `test_data` | JSONB | NOT NULL, Default `{}` | Sample input parameters. |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Ingestion timestamp. |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last-update timestamp. |

---

## 3. Entity Relationships

```
                  +--------------------------+
                  |        Repository        |
                  +--------------------------+
                               |
                               | 1
                               |
                               | *
                  +--------------------------+
                  |   BehaviorCatalogItem    | <----------------------+
                  +--------------------------+                        |
                               |                                      |
                               | 1                                    | 1
                               |                                      | (via canonical_key)
                               | *                                    |
+--------------------+   *   1 +--------------------------+           |
|  RecommendationRun |-------- |      ScenarioIntent      |           |
+--------------------+         +--------------------------+           |
         |                                  |                         |
         | 1                                | 1                       |
         |                                  |                         |
         | *                                | *                       |
+--------------------+   *   1 +--------------------------+           |
| SuggestedScenario  |-------- |  test_coverage_links     |-----------+
+--------------------+         +--------------------------+
```

*   **Repository & BehaviorCatalogItem (1:N)**: A repository can define its own unique, custom behavior catalog or inherit the global defaults.
*   **BehaviorCatalogItem & ScenarioIntent (1:N)**: When a recommendation run compiles, it instantiates active behaviors as run-specific `ScenarioIntent` records.
*   **BehaviorCatalogItem & TestCoverageLink (1:N)**: Knowledge-graph edges mapping test cases to file paths are associated with canonical behaviors to calculate coverage accuracy.

---

## 4. Migration Plan

### Step 1: Create Database Migration (Alembic)
Generate a new migration script to add the `behavior_catalog_items` table. Ensure indexes on `canonical_key`, `domain`, `feature`, and `repository_id` are included to optimize high-volume queries.

### Step 2: Seed Global Defaults
Create a database seed script that populates `behavior_catalog_items` with standard system templates. This includes:
1.  **Authentication (Login)**: Successful authentication, failed credentials handling, brute-force locking.
2.  **Registration (Signup)**: Unique email signup, password validation complexity.
3.  **Password Recovery**: Reset token request, reset token validation, reuse token rejection, old password invalidation.
4.  **Checkout & Billing**: Successful payment checkout, card rejection, subscription creation.

### Step 3: Populate Run-independent Relationships
Add a script to link existing `TestCoverageLink` entities to their matching `BehaviorCatalogItem` records based on parsed test name signatures (using the normalizer).

---

## 5. Integration Points

### I. ProductSMEAnalyzer & QALeadSMEAnalyzer Refactor
*   **Current State**: Inquiries are resolved by checking static lists inside `ProductSMEAnalyzer` rules and generating hardcoded scenarios in `QALeadSMEAnalyzer`.
*   **Future State**:
    1.  `ProductSMEAnalyzer` identifies the capability (e.g., `login`) and queries the `BehaviorCatalogItem` table for all canonical behaviors matching that domain.
    2.  `QALeadSMEAnalyzer` receives these database-backed behaviors, dynamically resolving their executable checklists (preconditions, steps, expectation) instead of fabricating hardcoded strings.

### II. ScenarioIntent Normalizer Alignment
*   The normalizer will serve as the validation gateway when saving new behaviors into the database, guaranteeing all behaviors conform to strict, standard canonical paths (e.g., forcing standard domain values).

### III. Recommendation Action Generation (Matrix Builder)
*   The recommendation action builder and matrix builder will retrieve coverage of these canonical behaviors, checking if there is a passing test mapped to the matching `canonical_key` on the current PR.
*   If a behavior exists in the catalog but has no execution evidence, it immediately surfaces as an executable `SuggestedTestScenario`.

---

## 6. Business Value & Benefits

1.  **Durable Knowledge Layer**: Business behavior requirements are fully persisted and do not disappear when recommendation runs are cleaned or updated.
2.  **No AI Hallucinations**: Standard business scenarios are completely deterministic; Veriscope will only recommend scenarios that are officially declared inside the catalog.
3.  **Extensible Domain Knowledge**: Engineers can easily register new business requirements or modify existing ones directly from the UI or via code annotations.
