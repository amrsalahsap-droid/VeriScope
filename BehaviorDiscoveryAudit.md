# Behavior Discovery Audit Report

This report presents a deep inspection of Veriscope's current **Behavior Discovery Engine**, analyzing its accuracy, structural limitations, confidence scoring, evidence generation quality, and scalability before proposing enhancements.

---

## 1. Behaviors Currently Discovered

The current implementation in `@c:\Users\amrsa\Downloads\veriscope\app\services\behavior_discovery_engine.py:53-120` relies on a deterministic keyword pattern matching dictionary containing **12 default canonical behavior categories**:

- **Password Reset**: Discovered via keyword regex patterns like `reset-password`, `forgot-password`, `recover-password`.
- **User Registration**: Discovered via patterns like `signup`, `register`, `create-account`.
- **Authentication**: Discovered via patterns like `login`, `auth`, `signin`, `log-in`.
- **Subscription Management**: Discovered via patterns like `billing`, `subscription`, `plan`, `pricing`.
- **Checkout**: Discovered via patterns like `checkout`, `cart`, `payment`, `purchase`.
- **User Management**: Discovered via patterns like `profile`, `settings`, `account`, `user`.
- **Notifications**: Discovered via patterns like `notification`, `alert`, `message`, `email`.
- **Reporting**: Discovered via patterns like `report`, `analytics`, `dashboard`, `statistics`.
- **Administration**: Discovered via patterns like `admin`, `manage`, `control`.
- **File Upload**: Discovered via patterns like `upload`, `file`, `attachment`.
- **Search**: Discovered via patterns like `search`, `query`, `find`.
- **API Integration**: Discovered via patterns like `api`, `webhook`, `integration`.

These patterns are evaluated across five distinct input channels (routes, pages, folders, modules, and test names), mapping any match directly to a canonical name, journey, and risk level.

---

## 2. Behaviors Likely Missed (False Negatives)

Because the current engine relies on hardcoded string matching on paths, many critical business behaviors are entirely missed:

- **Niche/Custom Domain Flows**: Custom business flows (e.g. `onboarding`, `kyc`, `refund`, `payout`, `transfer`, `audit-trail`, `checkout-v2`) are completely ignored because they don't map to the 12 generic default buckets.
- **Abstract Architectural Naming**: In well-structured repositories, controllers or handlers might be named abstractly (e.g., `ActionController`, `BaseService`, `RequestInterceptor`). Since their paths do not contain keywords like `login` or `billing`, they are entirely missed.
- **Specific Security/Compliance Workflows**: Behaviors like Multi-Factor Authentication (MFA), Single Sign-On (SSO), OAuth providers, or session timeouts are missed or incorrectly lumped into generic "Authentication" because terms like `mfa`, `2fa`, `totp`, `saml`, or `oidc` are not recognized.
- **Framework-Specific Dispatchers**: Some frameworks route requests dynamically (e.g. Django's `views.py` or Node's `index.js`). The path names are completely generic, hiding all the behaviors defined *inside* the file.

---

## 3. False Positive Behaviors

The extremely generic nature of several keywords leads to severe evidence bloat and false behavior classification:

- **The `user` Multi-Match**: The keyword `user` is mapped to "User Management". However, `user` is present in almost every file, database schema, and route (e.g., `/api/v1/auth/user-reset-password` or `user_id` context). This marks unrelated security files as "User Management" behaviors.
- **The `api` Overlap**: The pattern `api` maps to "API Integration". Since standard backend routing prefixes *every* route with `/api/...` (e.g., `/api/auth/login`), **every single route** in the repository is flagged as an "API Integration" behavior, drowning out actual external third-party API configurations.
- **The `file` Misclassification**: The keyword `file` maps to "File Upload". Consequently, generic files like `config_file.py`, `log_file_handler.py`, or `temp_file.tmp` generate false-positive behaviors for "File Upload" where no upload functionality exists.
- **The `query` / `find` Over-match**: The search patterns map `query` or `find` to "Search". Any generic database utility file (e.g., `db_query_builder.py` or `find_by_id()`) is flagged as user-facing search capability.

---

## 4. Confidence Quality

Aggregate confidence in `@c:\Users\amrsa\Downloads\veriscope\app\services\behavior_discovery_engine.py:33-46` is calculated using simple file counts rather than structural validation:

- **Static Attribution**: Confidence is assigned statically by source type (`ROUTE`/`PAGE` -> `HIGH`, `MODULE`/`TEST` -> `MODERATE`).
- **Inflation Vulnerability**: If three empty dummy files named `temp_user_test1.py`, `temp_user_test2.py`, and `temp_user_test3.py` exist, the system calculates an aggregate confidence of `MODERATE` or `HIGH` for "User Management" without any actual logic or tests being present.
- **Zero Content Inspection**: The engine does not verify if the file contains code, exports functions, or compiles. File paths are treated as absolute truth.
- **Keyword Clashing**: A single path like `/api/v1/user/checkout` triggers multiple high-confidence matches ("API Integration", "User Management", "Checkout"), resulting in overlapping evidence chains.

---

## 5. Missing Evidence Sources

The current engine looks strictly at filenames and paths. It misses highly reliable signals that would definitively confirm behavior presence:

- **Third-Party Imports & SDKs**: Imports of packages like `stripe` (Checkout/Billing), `@sendgrid/mail` (Notifications), `bcrypt` / `passport` (Authentication), or `@aws-sdk/s3` (File Upload) are the ultimate proof of a behavior's existence.
- **Code AST & Annotations**: Decorators or decorators like `@router.post("/login")`, `@login_required`, `@roles_accepted('admin')`, or class declarations like `class AuthMiddleware` provide context that paths alone cannot.
- **Database Models & Entities**: Defining models like `User`, `Subscription`, `Invoice`, `Transaction`, `Role`, or `AuditLog` in ORM schemas is extremely solid behavior evidence.
- **Git Commit History & PR Context**: Pull Request titles, descriptions, and commit logs (e.g., "Implement Stripe webhook for subscription renew") offer direct human explanations of business intent.

---

## 6. Current Discovery Limitations

- **String-Only Dependency**: Relying on simple path substrings rather than AST parse trees, import maps, or execution graphs.
- **No Extensibility**: The pattern mappings and rules are hardcoded as static dictionaries. Users cannot customize patterns or add domain-specific behaviors.
- **Next.js & Python Framework Bias**: The repository file scanner in `@c:\Users\amrsa\Downloads\veriscope\app\services\behavior_catalog_builder.py:216-242` specifically looks for Next.js app router structures (`*route*` and `*page*`) and Python modules (`*.py`). It lacks out-of-the-box support for other major frameworks (Ruby on Rails, Go, Express, Spring Boot).

---

## 7. Scalability Concerns

- **No Folder Exclusions**: The repository scan in `@c:\Users\amrsa\Downloads\veriscope\app\services\behavior_catalog_builder.py:206-249` runs `Path.rglob("*")` and `Path.rglob("*.py")` recursively over the entire folder. On large repositories, this will scan massive dependencies and build artifacts (e.g., `node_modules`, `.next`, `dist`, `.venv`, `.git`), causing severe performance bottlenecks, long lock times, or system crashes.
- **Database N+1 Querying**: When saving behaviors, the builder queries the database for existing behaviors and journeys one-by-one. In a scan with hundreds of candidate elements, this will cause significant DB latency and connection pooling exhaustion.
- **Evidence Explosion**: Generic matching rules (like `user` or `api`) attach hundreds of files as evidence to single behavior nodes, severely bloating database tables and rendering the frontend table sluggish.

---

## Improvement Opportunities

1. **Implement Directory Exclusions**: Restrict `rglob` to ignore known dependency, build, and configuration directories (`node_modules`, `venv`, `.git`, `dist`, `.next`).
2. **Abstract Framework Signature Matchers**: Move from generic filename matches to framework-specific detectors (e.g., parsing `package.json` for Next.js, `requirements.txt` for FastAPI).
3. **AST Content Scanner**: Create a lightweight parser that opens candidate files and looks for specific imports, function declarations, or decorators to assign much higher confidence scores.
4. **Metadata Filtering**: Introduce custom exclusions for matches like `/api` or `user_id` to eliminate the most flagrant false positive noise.
