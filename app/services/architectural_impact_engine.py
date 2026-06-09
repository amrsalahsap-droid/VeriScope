"""
app/services/architectural_impact_engine.py
=============================================

ArchitecturalImpactEngine
=========================
Analyzes system impact beyond individual changed files by traversing the static
import dependency graph. Discovers service relationships, maps impacted domains,
and suggests appropriate testing types (Integration, Workflow, Regression).
"""

import logging
from typing import Dict, List, Any, Set, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.dependency import FileDependency

logger = logging.getLogger("veriscope.architectural_impact_engine")


class ArchitecturalImpactEngine:
    """Read-only static dependency analysis engine.

    Computes transitive impact, maps services/domains, and suggests testing types.
    """

    @classmethod
    def analyze_impact(
        cls,
        db: Session,
        *,
        repository_id: UUID,
        commit_sha: str,
        changed_files: List[str]
    ) -> Dict[str, Any]:
        """Performs transitive reachability analysis to discover architectural impact.

        Parameters
        ----------
        db:
            SQLAlchemy database session.
        repository_id:
            UUID of the repository.
        commit_sha:
            Active commit identifier.
        changed_files:
            List of repository-relative changed file paths in the PR.

        Returns
        -------
        Dict[str, Any]
            Structured dictionary of discovered architectural impact elements.
        """
        if not changed_files:
            return {
                "impacted_files": [],
                "discovered_services": [],
                "impacted_domains": [],
                "recommended_testing_types": [],
                "explanation": "No changed files provided."
            }

        # 1. Fetch file dependency graph edges for this commit
        deps = (
            db.query(FileDependency)
            .filter(
                FileDependency.repository_id == repository_id,
                FileDependency.commit_sha == commit_sha
            )
            .all()
        )

        # 2. Build incoming and outgoing adjacency lists
        incoming: Dict[str, Set[str]] = {}
        outgoing: Dict[str, Set[str]] = {}

        for dep in deps:
            src = dep.file_path.replace("\\", "/")
            tgt = dep.depends_on_file_path.replace("\\", "/")

            incoming.setdefault(tgt, set()).add(src)
            outgoing.setdefault(src, set()).add(tgt)

        # 3. Compute Transitive Closure (Reachability Analysis)
        impacted_files: Set[str] = set()
        visited: Set[str] = set()
        queue: List[str] = [f.replace("\\", "/") for f in changed_files]

        for f in queue:
            visited.add(f)
            impacted_files.add(f)

        # BFS to find everything that imports our changed files (incoming dependents)
        # and everything our changed files import (outgoing dependencies)
        while queue:
            current = queue.pop(0)

            # Traverse dependents (who imports current?)
            for dependent in incoming.get(current, set()):
                if dependent not in visited:
                    visited.add(dependent)
                    impacted_files.add(dependent)
                    queue.append(dependent)

            # Traverse neighbors (what does current import?)
            for dependency in outgoing.get(current, set()):
                if dependency not in visited:
                    visited.add(dependency)
                    impacted_files.add(dependency)
                    queue.append(dependency)

        # 4. Discover Services
        discovered_services = cls._discover_services(impacted_files)

        # 5. Discover Impacted Domains
        impacted_domains = cls._map_domains(discovered_services)

        # 6. Suggest Testing Types
        recommended_testing_types = cls._suggest_testing_types(
            impacted_files=impacted_files,
            discovered_services=discovered_services
        )

        # 7. Compose Human Explanation
        explanation = cls._compose_explanation(
            discovered_services=discovered_services,
            impacted_domains=impacted_domains,
            recommended_testing_types=recommended_testing_types
        )

        return {
            "impacted_files": sorted(list(impacted_files)),
            "discovered_services": sorted(list(discovered_services)),
            "impacted_domains": sorted(list(impacted_domains)),
            "recommended_testing_types": sorted(list(recommended_testing_types)),
            "explanation": explanation
        }

    @classmethod
    def _discover_services(cls, file_paths: Set[str]) -> Set[str]:
        """Discovers distinct system components/services from file paths."""
        services: Set[str] = set()

        for path in file_paths:
            p_lower = path.lower()

            # Service mappings based on keyword matching
            if "auth" in p_lower or "login" in p_lower:
                services.add("auth service")
            elif "user" in p_lower or "member" in p_lower or "profile" in p_lower:
                services.add("user service")
            elif any(k in p_lower for k in ("notification", "email", "sms", "alert")):
                services.add("notification service")
            elif any(k in p_lower for k in ("billing", "payment", "invoice", "stripe", "charge")):
                services.add("billing service")
            elif any(k in p_lower for k in ("api", "router", "controller", "route")):
                services.add("api service")
            elif any(k in p_lower for k in ("db", "model", "schema", "entity", "orm", "repository")):
                services.add("database service")
            else:
                # Fallback to direct directory category if applicable
                parts = [x for x in path.split("/") if x]
                if len(parts) >= 2 and parts[0] in ("services", "src", "app"):
                    services.add(f"{parts[1].replace('_', ' ').replace('-', ' ')} service")

        return services

    @classmethod
    def _map_domains(cls, services: Set[str]) -> Set[str]:
        """Maps discovered service names to user-friendly architectural domain labels."""
        domains: Set[str] = set()

        for svc in services:
            if svc == "auth service":
                domains.add("Authentication")
            elif svc == "user service":
                domains.add("User Management")
            elif svc == "notification service":
                domains.add("Email Notifications")
            elif svc == "billing service":
                domains.add("Billing")
            elif svc == "api service":
                domains.add("API Endpoints")
            elif svc == "database service":
                domains.add("Data Platform")
            else:
                # Fallback capitalization
                domains.add(svc.title())

        return domains

    @classmethod
    def _suggest_testing_types(
        cls,
        *,
        impacted_files: Set[str],
        discovered_services: Set[str]
    ) -> Set[str]:
        """Statically suggests appropriate testing types based on graph topology."""
        types: Set[str] = set()

        # Rule A: Suggest Integration tests if changes span multiple services
        if len(discovered_services) >= 2:
            types.add("Integration")

        # Rule B: Suggest Workflow tests if API/routing code is impacted
        for path in impacted_files:
            p_lower = path.lower()
            if any(k in p_lower for k in ("api", "router", "controller", "route", "endpoint")):
                types.add("Workflow")
                break

        # Rule C: Suggest Regression tests if core shared libraries or high ripple-impact occurs
        has_shared_impact = False
        for path in impacted_files:
            p_lower = path.lower()
            if any(k in p_lower for k in ("shared", "common", "util")):
                has_shared_impact = True
                break

        if has_shared_impact or len(impacted_files) >= 5:
            types.add("Regression")

        return types

    @classmethod
    def _compose_explanation(
        cls,
        *,
        discovered_services: Set[str],
        impacted_domains: Set[str],
        recommended_testing_types: Set[str]
    ) -> str:
        """Constructs a concise, structured human-readable explanation."""
        if not discovered_services:
            return "Minimal architectural impact detected."

        services_str = ", ".join(sorted(list(discovered_services)))
        domains_str = ", ".join(sorted(list(impacted_domains)))
        testing_str = ", ".join(sorted(list(recommended_testing_types)))

        explanation = (
            f"Discovered architectural impact spanning {services_str}. "
            f"Affects domains: {domains_str}. "
            f"Recommended testing categories: {testing_str}."
        )
        return explanation
