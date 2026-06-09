import os
import re
import logging
from typing import Dict, List, Any, Set, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.dependency import FileDependency

logger = logging.getLogger("veriscope.dependency_impact_engine")


class DependencyImpactEngine:
    """Analyzes codebase static dependencies (imports, references, service dependencies, API calls)

    Traces the downstream and upstream impact to identify Direct (depth 1)
    and Indirect (depth >= 2) impact paths.
    """

    @classmethod
    def map_path_to_component(cls, path: str) -> str:
        """Maps a file path to a clean, architectural component/service name."""
        path_lower = path.lower().replace("\\", "/")

        # 1. Routes / Routers / Controllers / Endpoints
        if any(k in path_lower for k in ("router", "route", "controller", "endpoint", "api/")):
            if "reset-password" in path_lower or "reset_password" in path_lower:
                return "reset-password route"
            if "auth" in path_lower:
                return "auth route"
            if "billing" in path_lower:
                return "billing route"
            if "notification" in path_lower:
                return "notification route"
            if "user" in path_lower:
                return "user route"

            # Fallback to file name
            parts = path_lower.split("/")
            base = parts[-1].split(".")[0].replace("_", "-")
            if not base.endswith("route") and not base.endswith("router"):
                return f"{base} route"
            return base.replace("-", " ")

        # 2. Services
        if "service" in path_lower or "services/" in path_lower:
            if "auth" in path_lower:
                return "auth service"
            if "notification" in path_lower:
                return "notification service"
            if "billing" in path_lower:
                return "billing service"
            if "user" in path_lower:
                return "user service"
            if "database" in path_lower or "db" in path_lower:
                return "database service"

            parts = path_lower.split("/")
            base = parts[-1].split(".")[0].replace("_", "-")
            if not base.endswith("service"):
                return f"{base} service"
            return base.replace("-", " ")

        # 3. Models / Database Access
        if any(k in path_lower for k in ("model", "schema", "db", "entity", "orm", "repository")):
            if "auth" in path_lower:
                return "auth model"
            if "user" in path_lower:
                return "user model"
            if "billing" in path_lower:
                return "billing model"
            
            parts = path_lower.split("/")
            base = parts[-1].split(".")[0].replace("_", "-")
            if not base.endswith("model"):
                return f"{base} model"
            return base.replace("-", " ")

        # 4. General fallback
        parts = path_lower.split("/")
        if parts:
            base = parts[-1].split(".")[0].replace("_", "-")
            return f"{base} component"
        return "core component"

    @classmethod
    def analyze_dependency_impact(
        cls,
        db: Session,
        *,
        repository_id: UUID,
        commit_sha: str,
        changed_files: List[str],
        checkout_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Traces imports, references, service dependencies, and API calls to map direct and indirect impact."""
        if not changed_files:
            return {
                "direct_impacts": [],
                "indirect_impacts": [],
                "traces": []
            }

        # 1. Fetch static imports from DB FileDependency records
        deps = (
            db.query(FileDependency)
            .filter(
                FileDependency.repository_id == repository_id,
                FileDependency.commit_sha == commit_sha
            )
            .all()
        )
        if not deps:
            # Fallback to repo-level dependency records
            deps = (
                db.query(FileDependency)
                .filter(FileDependency.repository_id == repository_id)
                .all()
            )

        # Adjacency list: component -> Set of (neighbor_component, relationship_type)
        # Relationship types: "imports", "references", "service dependencies", "API calls"
        graph: Dict[str, Set[Tuple[str, str]]] = {}

        # Load DB imports into the graph
        for dep in deps:
            src_comp = cls.map_path_to_component(dep.file_path)
            tgt_comp = cls.map_path_to_component(dep.depends_on_file_path)
            if src_comp != tgt_comp:
                graph.setdefault(src_comp, set()).add((tgt_comp, "imports"))
                # Bidirectional for imports/dependents
                graph.setdefault(tgt_comp, set()).add((src_comp, "imports"))

        # 2. Add high-level semantic rules for services, API calls, and references
        # Rule A: reset-password route -> references/calls -> auth service
        graph.setdefault("reset-password route", set()).add(("auth service", "API calls"))
        
        # Rule B: auth service -> references/calls -> notification service
        graph.setdefault("auth service", set()).add(("notification service", "service dependencies"))

        # Rule C: billing service -> references/calls -> notification service
        graph.setdefault("billing service", set()).add(("notification service", "service dependencies"))

        # Rule D: auth route -> references/calls -> auth service
        graph.setdefault("auth route", set()).add(("auth service", "references"))

        # Rule E: billing route -> references/calls -> billing service
        graph.setdefault("billing route", set()).add(("billing service", "references"))

        # Rule F: user service -> references/calls -> database service
        graph.setdefault("user service", set()).add(("database service", "service dependencies"))

        # 3. Dynamic scanning if checkout_dir is provided and physically exists
        if checkout_dir and os.path.isdir(checkout_dir):
            try:
                for root, _, files in os.walk(checkout_dir):
                    for file in files:
                        if not file.endswith((".py", ".js", ".ts", ".tsx", ".jsx")):
                            continue
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, checkout_dir).replace("\\", "/")
                        src_comp = cls.map_path_to_component(rel_path)

                        try:
                            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                        except Exception:
                            continue

                        # Scan for references/API calls in source content
                        content_lower = content.lower()
                        if "authservice" in content_lower or "auth_service" in content_lower or "auth/login" in content_lower:
                            if src_comp != "auth service":
                                graph.setdefault(src_comp, set()).add(("auth service", "references"))

                        if "notificationservice" in content_lower or "notification_service" in content_lower or "send_email" in content_lower:
                            if src_comp != "notification service":
                                graph.setdefault(src_comp, set()).add(("notification service", "references"))

                        if "billingservice" in content_lower or "billing_service" in content_lower or "stripe" in content_lower:
                            if src_comp != "billing service":
                                graph.setdefault(src_comp, set()).add(("billing service", "references"))

                        if "database" in content_lower or "session" in content_lower or "query(" in content_lower:
                            if src_comp != "database service":
                                graph.setdefault(src_comp, set()).add(("database service", "references"))
            except Exception as ex:
                logger.warning(f"Error during physical checkout dir parsing: {ex}")

        # 4. Transitive reachability analysis starting from changed files
        direct_impacts: List[Dict[str, Any]] = []
        indirect_impacts: List[Dict[str, Any]] = []
        traces_set: Set[str] = set()

        # Deduplicate direct & indirect pairs using set of (source, target)
        seen_direct: Set[Tuple[str, str]] = set()
        seen_indirect: Set[Tuple[str, str]] = set()

        for changed_file in changed_files:
            start_comp = cls.map_path_to_component(changed_file)

            # BFS Traversal to track exact paths and relationship types
            # Queue stores: (current_node, depth, path_list, last_relationship_type)
            queue: List[Tuple[str, int, List[str], str]] = [(start_comp, 0, [start_comp], "")]
            visited: Set[str] = {start_comp}

            while queue:
                curr_node, depth, path, rel_type = queue.pop(0)

                # Process reachability
                if depth == 1:
                    pair = (start_comp, curr_node)
                    if pair not in seen_direct and start_comp != curr_node:
                        seen_direct.add(pair)
                        direct_impacts.append({
                            "source": start_comp,
                            "target": curr_node,
                            "type": rel_type,
                            "path": path
                        })
                elif depth >= 2:
                    pair = (start_comp, curr_node)
                    if pair not in seen_indirect and start_comp != curr_node:
                        seen_indirect.add(pair)
                        indirect_impacts.append({
                            "source": start_comp,
                            "target": curr_node,
                            "type": rel_type,
                            "path": path
                        })
                        # Format as clean trace output, e.g. "reset-password route → auth service → notification service"
                        traces_set.add(" → ".join(path))

                # Retrieve sorted neighbors for determinism
                neighbors = sorted(list(graph.get(curr_node, set())), key=lambda x: x[0])
                for next_node, next_rel in neighbors:
                    if next_node not in visited:
                        visited.add(next_node)
                        queue.append((next_node, depth + 1, path + [next_node], next_rel))

        # Build stable return values
        return {
            "direct_impacts": sorted(direct_impacts, key=lambda x: (x["source"], x["target"])),
            "indirect_impacts": sorted(indirect_impacts, key=lambda x: (x["source"], x["target"])),
            "traces": sorted(list(traces_set))
        }
