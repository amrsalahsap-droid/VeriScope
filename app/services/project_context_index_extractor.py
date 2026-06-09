import os
import re
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Set
from sqlalchemy.orm import Session

from app.models.project_context_index import ProjectContextIndex
from app.models.repository import Repository
from app.models.dependency import FileDependency
from app.models.test_result import TestCase
from app.models.coverage import CoverageFileEntry
from app.models.pull_request import PullRequest, PullRequestChangedFile

class ProjectContextIndexExtractor:
    """
    Extracts and builds a deterministic, evidence-based project understanding layer
    per repository without AI guessing, ensuring full source file traceability.
    """

    def __init__(self, db: Session):
        self.db = db

    def extract_and_persist(self, repository_id: uuid.UUID, checkout_dir: str) -> ProjectContextIndex:
        """
        Scans a repository workspace checkout and database logs,
        builds a deterministic project context index, and persists it.
        """
        # Determine paths relative to checkout_dir or check filesystem existence
        checkout_exists = os.path.isdir(checkout_dir)
        all_files: Set[str] = set()

        if checkout_exists:
            for root, dirs, files in os.walk(checkout_dir):
                # Ignore control / build dirs
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist", "build", "coverage", ".venv", "venv", ".next")]
                for file in files:
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, checkout_dir).replace("\\", "/")
                    all_files.add(rel_path)

        # Always merge database-seeded files to guarantee maximum evidence alignment
        db_deps = self.db.query(FileDependency).filter(FileDependency.repository_id == repository_id).all()
        for dep in db_deps:
            all_files.add(dep.file_path)
            all_files.add(dep.depends_on_file_path)
        
        db_cov = self.db.query(CoverageFileEntry).filter(CoverageFileEntry.repository_id == repository_id).all()
        for cov in db_cov:
            all_files.add(cov.file_path)

        db_pr_files = self.db.query(PullRequestChangedFile).join(
            PullRequest, PullRequest.id == PullRequestChangedFile.pull_request_id
        ).filter(PullRequest.repository_id == repository_id).all()
        for pr_f in db_pr_files:
            all_files.add(pr_f.file_path)

        # Ensure all_files list is sorted for determinism
        sorted_files = sorted(list(all_files))

        # 1. Detected Frameworks
        detected_frameworks = self._detect_frameworks(checkout_dir, sorted_files)

        # 2. Routes, Pages, API Endpoints
        routes, pages, api_endpoints = self._extract_routes_and_pages(checkout_dir, sorted_files)

        # 3. Modules
        modules = self._extract_modules(sorted_files)

        # 4. Domains
        domains = self._extract_domains(sorted_files)

        # 5. User Journeys
        user_journeys = self._extract_user_journeys(repository_id, checkout_dir, sorted_files)

        # 6. Test Assets
        test_assets = self._extract_test_assets(sorted_files)

        # 7. Security Sensitive Areas
        security_sensitive_areas = self._extract_security_sensitive_areas(sorted_files)

        # Calculate Confidence
        confidence = "HIGH" if checkout_exists and len(sorted_files) > 0 else "MODERATE"
        if not sorted_files:
            confidence = "LOW"

        # Persistence: Idempotently upsert/replace index for this repository
        existing_index = self.db.query(ProjectContextIndex).filter(
            ProjectContextIndex.repository_id == repository_id
        ).first()

        if existing_index:
            existing_index.detected_frameworks = detected_frameworks
            existing_index.routes = routes
            existing_index.pages = pages
            existing_index.api_endpoints = api_endpoints
            existing_index.modules = modules
            existing_index.domains = domains
            existing_index.user_journeys = user_journeys
            existing_index.test_assets = test_assets
            existing_index.security_sensitive_areas = security_sensitive_areas
            existing_index.generated_at = datetime.utcnow()
            existing_index.confidence = confidence
            index_record = existing_index
        else:
            index_record = ProjectContextIndex(
                id=uuid.uuid4(),
                repository_id=repository_id,
                detected_frameworks=detected_frameworks,
                routes=routes,
                pages=pages,
                api_endpoints=api_endpoints,
                modules=modules,
                domains=domains,
                user_journeys=user_journeys,
                test_assets=test_assets,
                security_sensitive_areas=security_sensitive_areas,
                generated_at=datetime.utcnow(),
                confidence=confidence
            )
            self.db.add(index_record)

        self.db.commit()
        return index_record

    def _detect_frameworks(self, checkout_dir: str, sorted_files: List[str]) -> List[Dict[str, Any]]:
        frameworks: Dict[str, Set[str]] = {}

        # Scan files for physical evidence
        for rel_path in sorted_files:
            abs_path = os.path.join(checkout_dir, rel_path)
            # package.json
            if rel_path.endswith("package.json") and os.path.isfile(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        pkg = json.load(f)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    if "next" in deps:
                        frameworks.setdefault("Next.js", set()).add(rel_path)
                        frameworks.setdefault("React", set()).add(rel_path)
                    if "express" in deps:
                        frameworks.setdefault("Express", set()).add(rel_path)
                    if "tailwindcss" in deps:
                        frameworks.setdefault("TailwindCSS", set()).add(rel_path)
                    if "typescript" in deps:
                        frameworks.setdefault("TypeScript", set()).add(rel_path)
                except Exception:
                    pass

            # Python config / requirement files
            if rel_path.endswith(("requirements.txt", "Pipfile", "pyproject.toml")) and os.path.isfile(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().lower()
                    if "fastapi" in content:
                        frameworks.setdefault("FastAPI", set()).add(rel_path)
                    if "django" in content:
                        frameworks.setdefault("Django", set()).add(rel_path)
                    if "flask" in content:
                        frameworks.setdefault("Flask", set()).add(rel_path)
                    if "sqlalchemy" in content:
                        frameworks.setdefault("SQLAlchemy", set()).add(rel_path)
                    if "pytest" in content:
                        frameworks.setdefault("Pytest", set()).add(rel_path)
                except Exception:
                    pass

        # Heuristics based on file extensions and content imports
        for rel_path in sorted_files:
            if rel_path.endswith((".tsx", ".jsx")):
                frameworks.setdefault("React", set()).add(rel_path)
            if rel_path.endswith((".ts", ".tsx")):
                frameworks.setdefault("TypeScript", set()).add(rel_path)
            if "landing-page/" in rel_path:
                frameworks.setdefault("Next.js", set()).add(rel_path)
            if rel_path.endswith(".py"):
                frameworks.setdefault("Python", set()).add(rel_path)
                abs_path = os.path.join(checkout_dir, rel_path)
                if os.path.isfile(abs_path):
                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        if "from fastapi" in content or "import fastapi" in content:
                            frameworks.setdefault("FastAPI", set()).add(rel_path)
                        if "sqlalchemy" in content:
                            frameworks.setdefault("SQLAlchemy", set()).add(rel_path)
                        if "import pytest" in content or "from pytest" in content:
                            frameworks.setdefault("Pytest", set()).add(rel_path)
                    except Exception:
                        pass

        return [{"name": name, "source_files": sorted(list(files))} for name, files in sorted(frameworks.items())]

    def _extract_routes_and_pages(self, checkout_dir: str, sorted_files: List[str]) -> tuple:
        routes: List[Dict[str, Any]] = []
        pages: List[Dict[str, Any]] = []
        api_endpoints: List[Dict[str, Any]] = []

        route_pattern = re.compile(r'@(?:router|app)\.(get|post|put|delete|patch|options|head)\(\s*["\']([^"\']+)["\']')

        for rel_path in sorted_files:
            abs_path = os.path.join(checkout_dir, rel_path)
            
            # Next.js App Router Page check (landing-page/app/.../page.tsx)
            if ("landing-page/app/" in rel_path or "app/" in rel_path) and rel_path.endswith(("page.tsx", "page.jsx", "page.js")):
                parts = rel_path.split("/")
                app_idx = -1
                for i, p in enumerate(parts):
                    if p == "app":
                        app_idx = i
                        break
                if app_idx != -1:
                    route_parts = parts[app_idx + 1:-1]
                    route_parts = [p for p in route_parts if not (p.startswith("(") and p.endswith(")"))]
                    route_path = "/" + "/".join(route_parts)
                    pages.append({"url_path": route_path, "source_files": [rel_path]})
                    routes.append({"path": route_path, "method": "GET", "source_files": [rel_path]})

            # Next.js App Router Route handler check (landing-page/app/api/.../route.ts)
            elif ("landing-page/app/api/" in rel_path or "app/api/" in rel_path) and rel_path.endswith(("route.ts", "route.js")):
                parts = rel_path.split("/")
                app_idx = -1
                for i, p in enumerate(parts):
                    if p == "app":
                        app_idx = i
                        break
                if app_idx != -1:
                    route_parts = parts[app_idx + 1:-1]
                    api_path = "/" + "/".join(route_parts)
                    api_endpoints.append({"path": api_path, "source_files": [rel_path]})

            # FastAPI/Python route decorator scan
            elif rel_path.endswith(".py"):
                if os.path.isfile(abs_path):
                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        matches = route_pattern.findall(content)
                        for method, path in matches:
                            method_upper = method.upper()
                            api_endpoints.append({"path": path, "source_files": [rel_path]})
                            routes.append({"path": path, "method": method_upper, "source_files": [rel_path]})
                    except Exception:
                        pass

        # Deduplicate and sort routes, pages, and api_endpoints deterministically
        routes_dedup: Dict[tuple, Set[str]] = {}
        for r in routes:
            key = (r["path"], r["method"])
            routes_dedup.setdefault(key, set()).update(r["source_files"])
        
        pages_dedup: Dict[str, Set[str]] = {}
        for p in pages:
            pages_dedup.setdefault(p["url_path"], set()).update(p["source_files"])

        api_dedup: Dict[str, Set[str]] = {}
        for a in api_endpoints:
            api_dedup.setdefault(a["path"], set()).update(a["source_files"])

        final_routes = [{"path": k[0], "method": k[1], "source_files": sorted(list(files))} for k, files in sorted(routes_dedup.items())]
        final_pages = [{"url_path": k, "source_files": sorted(list(files))} for k, files in sorted(pages_dedup.items())]
        final_api_endpoints = [{"path": k, "source_files": sorted(list(files))} for k, files in sorted(api_dedup.items())]

        return final_routes, final_pages, final_api_endpoints

    def _extract_modules(self, sorted_files: List[str]) -> List[Dict[str, Any]]:
        modules: Dict[str, Set[str]] = {}
        for rel_path in sorted_files:
            parts = rel_path.split("/")
            if len(parts) >= 2:
                if parts[0] in ("app", "landing-page", "src"):
                    mod_name = "/".join(parts[:2])
                    modules.setdefault(mod_name, set()).add(rel_path)

        return [{"name": name, "source_files": sorted(list(files))} for name, files in sorted(modules.items())]

    def _extract_domains(self, sorted_files: List[str]) -> List[Dict[str, Any]]:
        domains: Dict[str, Set[str]] = {}
        keyword_map = {
            "Authentication & Identity": ("auth", "login", "signup", "user", "password", "session"),
            "Billing & Subscription": ("billing", "payment", "stripe", "checkout", "subscription"),
            "Coverage Analysis": ("coverage", "cobertura", "lcov", "report"),
            "Test Recommendations": ("recommendation", "scoring", "ranking", "recommender"),
            "GitHub Integration": ("github", "webhook", "installation"),
            "Flakiness Intelligence": ("flaky", "flake", "stabilize"),
            "Observability & Monitoring": ("observability", "ingestion", "telemetry")
        }

        for rel_path in sorted_files:
            path_lower = rel_path.lower()
            for domain_name, keywords in keyword_map.items():
                if any(kw in path_lower for kw in keywords):
                    domains.setdefault(domain_name, set()).add(rel_path)

        return [{"name": name, "source_files": sorted(list(files))} for name, files in sorted(domains.items())]

    def _extract_user_journeys(self, repository_id: uuid.UUID, checkout_dir: str, sorted_files: List[str]) -> List[Dict[str, Any]]:
        journeys: Dict[str, Set[str]] = {}
        journey_tests = {
            "User Login Flow": ("login", "signin", "sign_in"),
            "User Registration Flow": ("signup", "register", "sign_up"),
            "Password Reset Flow": ("reset_password", "reset-password", "forgot_password"),
            "Payment checkout Flow": ("checkout", "payment", "subscribe"),
            "Test Recommendation Flow": ("recommend", "recommendation", "scoring"),
            "Coverage Ingestion Flow": ("upload_coverage", "ingest_coverage", "cobertura", "lcov")
        }

        # 1. Inspect TestCase inventory from DB
        db_tests = self.db.query(TestCase).filter(TestCase.repository_id == repository_id).all()
        for test in db_tests:
            name_lower = test.test_name.lower()
            suite_lower = test.suite_name.lower()
            test_file = ""
            for rel_path in sorted_files:
                if rel_path.endswith((".py", ".ts", ".tsx", ".js", ".jsx")) and (test.test_name in rel_path or test.suite_name.replace(".", "/") in rel_path):
                    test_file = rel_path
                    break

            for journey_name, keywords in journey_tests.items():
                if any(kw in name_lower or kw in suite_lower for kw in keywords):
                    if test_file:
                        journeys.setdefault(journey_name, set()).add(test_file)

        # 2. Heuristically match filename keywords for code file lineage
        for rel_path in sorted_files:
            path_lower = rel_path.lower()
            for journey_name, keywords in journey_tests.items():
                if any(kw in path_lower for kw in keywords):
                    journeys.setdefault(journey_name, set()).add(rel_path)

        return [{"name": name, "source_files": sorted(list(files))} for name, files in sorted(journeys.items())]

    def _extract_test_assets(self, sorted_files: List[str]) -> List[Dict[str, Any]]:
        test_assets: List[Dict[str, Any]] = []
        for rel_path in sorted_files:
            if "tests/" in rel_path or rel_path.endswith(("_test.py", "test_*.py", ".test.ts", ".test.js", ".spec.ts", ".spec.js")):
                basename = os.path.basename(rel_path)
                test_assets.append({"name": basename, "source_files": [rel_path]})
        
        assets_dedup: Dict[str, Set[str]] = {}
        for asset in test_assets:
            assets_dedup.setdefault(asset["name"], set()).update(asset["source_files"])

        return [{"name": name, "source_files": sorted(list(files))} for name, files in sorted(assets_dedup.items())]

    def _extract_security_sensitive_areas(self, sorted_files: List[str]) -> List[Dict[str, Any]]:
        security_areas: Dict[str, Set[str]] = {}
        sensitive_keywords = ("auth", "security", "password", "token", "session", "jwt", "encrypt", "decrypt", "hash", "secrets")

        for rel_path in sorted_files:
            path_lower = rel_path.lower()
            if any(kw in path_lower for kw in sensitive_keywords):
                security_areas.setdefault("Authentication & Cryptographic Secrets", set()).add(rel_path)

        return [{"name": name, "source_files": sorted(list(files))} for name, files in sorted(security_areas.items())]
