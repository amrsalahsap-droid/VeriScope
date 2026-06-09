import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.dependency import FileDependency
from app.schemas.recommendation import DependencyExpansionBundle


class DependencyExpansionResolver:
    @staticmethod
    def expand_dependencies(
        db: Session,
        repository_id: uuid.UUID,
        changed_files: List[str],
        max_depth: Optional[int] = None,
        max_nodes: Optional[int] = None
    ) -> DependencyExpansionBundle:
        """
        Expand changed files into directly/transitively impacted files using existing FileDependency records.
        """
        # Fetch all dependency records for this repository
        deps = db.query(FileDependency).filter(FileDependency.repository_id == repository_id).all()

        reasons = []
        limit_exceeded = False
        expanded_files = []
        expansion_edges = {}
        expansion_depth_reached = 0

        # Hard Limits (Rule 5)
        MAX_DEPENDENCY_EXPANSION_DEPTH = 3
        MAX_DEPENDENCY_NODES_VISITED = 500
        MAX_DEPENDENCY_TEST_EXPANSION = 200

        # Rule 6: If graph is missing
        if not deps:
            reasons.append("No dependency graph available.")
            return DependencyExpansionBundle(
                expanded_files=[],
                expansion_edges={},
                expansion_depth_reached=0,
                limit_exceeded=False,
                dependency_state_hash=None,
                reasons=reasons
            )

        # Generate a deterministic dependency_state_hash by sorting and hashing all dependency paths (Rule 3 & 7)
        sorted_paths = sorted([f"{d.file_path.replace('\\', '/')}->{d.depends_on_file_path.replace('\\', '/')}" for d in deps])
        dependency_state_hash = hashlib.sha256(",".join(sorted_paths).encode("utf-8")).hexdigest()

        # Rule 7: If graph is stale
        newest_dep = max(deps, key=lambda x: x.created_at)
        is_stale = (datetime.utcnow() - newest_dep.created_at).days > 14
        if is_stale:
            reasons.append("Dependency confidence is LOW.")

        # Map out adjacency list of both incoming dependents and outgoing dependencies
        # B imports A -> A is depends_on_file_path (target), B is file_path (source)
        # We expand bi-directionally for maximum coverage safety.
        adj = {}
        for d in deps:
            u = d.depends_on_file_path.replace("\\", "/")
            v = d.file_path.replace("\\", "/")
            if u not in adj:
                adj[u] = set()
            adj[u].add(v)
            if v not in adj:
                adj[v] = set()
            adj[v].add(u)

        # Normalize and sort starting nodes
        sorted_starts = sorted(list(set([f.replace("\\", "/") for f in changed_files])))

        # BFS Traversal
        queue = []
        visited = set(sorted_starts)

        for node in sorted_starts:
            queue.append((node, 0))

        # Respect user constraints capped at hard thresholds
        depth_limit = min(max_depth if max_depth is not None else 1, MAX_DEPENDENCY_EXPANSION_DEPTH)
        nodes_limit = min(max_nodes if max_nodes is not None else MAX_DEPENDENCY_NODES_VISITED, MAX_DEPENDENCY_NODES_VISITED)

        nodes_visited_count = 0

        while queue:
            curr_node, curr_depth = queue.pop(0)

            if curr_depth > expansion_depth_reached:
                expansion_depth_reached = curr_depth

            if curr_depth >= depth_limit:
                continue

            nodes_visited_count += 1
            if nodes_visited_count > nodes_limit:
                limit_exceeded = True
                reasons.append("Dependency expansion limit exceeded; recommendation widened conservatively.")
                break

            neighbors = sorted(list(adj.get(curr_node, set())))
            if neighbors:
                expansion_edges[curr_node] = neighbors

            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)

                    # Check max expanded test limit
                    expanded_count = len(visited) - len(sorted_starts)
                    if expanded_count > MAX_DEPENDENCY_TEST_EXPANSION:
                        limit_exceeded = True
                        reasons.append("Dependency expansion limit exceeded; recommendation widened conservatively.")
                        break

                    queue.append((neighbor, curr_depth + 1))

            if limit_exceeded:
                break

        expanded_files = sorted(list(visited - set(sorted_starts)))

        return DependencyExpansionBundle(
            expanded_files=expanded_files,
            expansion_edges=expansion_edges,
            expansion_depth_reached=expansion_depth_reached,
            limit_exceeded=limit_exceeded,
            dependency_state_hash=dependency_state_hash,
            reasons=reasons
        )
