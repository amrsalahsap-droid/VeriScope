"""
Architecture V2 Impact Engine
=============================
Analyzes system impact using the ArchitectureNode/ArchitectureEdge graph.

This engine replaces the legacy FileDependency-based analysis with the new
architecture graph, providing richer structural analysis and better integration
with behavior/journey intelligence.
"""

import logging
from typing import Dict, List, Any, Set, Tuple, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.architecture_node import ArchitectureNode, ArchitectureNodeType, ArchitectureLayer
from app.models.architecture_edge import ArchitectureEdge, ArchitectureEdgeType

logger = logging.getLogger("veriscope.architecture_v2_impact_engine")


class ArchitectureV2ImpactEngine:
    """Analyzes architectural impact using ArchitectureNode/ArchitectureEdge graph.
    
    This engine provides the same interface as the legacy ArchitecturalImpactEngine
    but reads from the new architecture graph for richer analysis.
    """

    @classmethod
    def analyze_impact(
        cls,
        db: Session,
        *,
        repository_id: UUID,
        changed_files: List[str],
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """Performs transitive reachability analysis using ArchitectureNode/ArchitectureEdge graph.

        Parameters
        ----------
        db:
            SQLAlchemy database session.
        repository_id:
            UUID of the repository.
        changed_files:
            List of repository-relative changed file paths in the PR.
        max_depth:
            Maximum depth for transitive impact analysis (default: 3).

        Returns
        -------
        Dict[str, Any]
            Structured dictionary of discovered architectural impact elements.
        """
        if not changed_files:
            return {
                "impacted_files": [],
                "changed_nodes": [],
                "direct_impacts": [],
                "indirect_impacts": [],
                "impacted_layers": [],
                "impacted_services": [],
                "impacted_domains": [],
                "recommended_testing_types": [],
                "explanation": "No changed files provided.",
                "confidence": "NONE"
            }

        # 1. Map changed files to ArchitectureNodes
        changed_nodes = cls._map_files_to_nodes(db, repository_id, changed_files)
        
        if not changed_nodes:
            logger.warning(f"No ArchitectureNodes found for changed files in repository {repository_id}")
            return {
                "impacted_files": changed_files,
                "changed_nodes": [],
                "direct_impacts": [],
                "indirect_impacts": [],
                "impacted_layers": [],
                "impacted_services": [],
                "impacted_domains": [],
                "recommended_testing_types": [],
                "explanation": "No architecture nodes found for changed files. Graph may not be indexed.",
                "confidence": "LOW"
            }

        # 2. Build adjacency lists from ArchitectureEdges
        incoming, outgoing = cls._build_adjacency_lists(db, repository_id, changed_nodes)

        # 3. Compute transitive closure (BFS)
        impacted_nodes: Set[UUID] = set(node.id for node in changed_nodes)
        visited: Set[UUID] = set(node.id for node in changed_nodes)
        queue: List[Tuple[UUID, int]] = [(node.id, 0) for node in changed_nodes]

        direct_impacts: List[Dict[str, Any]] = []
        indirect_impacts: List[Dict[str, Any]] = []

        while queue:
            current_id, depth = queue.pop(0)

            # Traverse incoming edges (dependents)
            for neighbor_id, edge_type in incoming.get(current_id, set()):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    impacted_nodes.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))

                    if depth == 0:
                        direct_impacts.append({
                            "source_node_id": str(current_id),
                            "target_node_id": str(neighbor_id),
                            "edge_type": edge_type,
                            "depth": depth + 1
                        })
                    else:
                        indirect_impacts.append({
                            "source_node_id": str(current_id),
                            "target_node_id": str(neighbor_id),
                            "edge_type": edge_type,
                            "depth": depth + 1
                        })

            # Traverse outgoing edges (dependencies)
            for neighbor_id, edge_type in outgoing.get(current_id, set()):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    impacted_nodes.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))

                    if depth == 0:
                        direct_impacts.append({
                            "source_node_id": str(current_id),
                            "target_node_id": str(neighbor_id),
                            "edge_type": edge_type,
                            "depth": depth + 1
                        })
                    else:
                        indirect_impacts.append({
                            "source_node_id": str(current_id),
                            "target_node_id": str(neighbor_id),
                            "edge_type": edge_type,
                            "depth": depth + 1
                        })

        # 4. Fetch all impacted nodes for analysis
        all_impacted_nodes = db.query(ArchitectureNode).filter(
            ArchitectureNode.id.in_(impacted_nodes)
        ).all()

        # 5. Discover impacted layers
        impacted_layers = set(node.layer.value for node in all_impacted_nodes)

        # 6. Discover impacted services (from module_name or path)
        impacted_services = cls._discover_services(all_impacted_nodes)

        # 7. Map to domains
        impacted_domains = cls._map_domains(impacted_services)

        # 8. Suggest testing types
        recommended_testing_types = cls._suggest_testing_types(
            impacted_nodes=all_impacted_nodes,
            impacted_layers=impacted_layers,
            impacted_services=impacted_services
        )

        # 9. Compose explanation
        explanation = cls._compose_explanation(
            changed_nodes=changed_nodes,
            impacted_services=impacted_services,
            impacted_domains=impacted_domains,
            recommended_testing_types=recommended_testing_types
        )

        # 10. Determine confidence
        confidence = "HIGH" if len(changed_nodes) == len(changed_files) else "MEDIUM"

        return {
            "impacted_files": [node.path for node in all_impacted_nodes],
            "changed_nodes": [
                {
                    "id": str(node.id),
                    "path": node.path,
                    "node_type": node.node_type.value,
                    "layer": node.layer.value,
                    "module_name": node.module_name
                }
                for node in changed_nodes
            ],
            "direct_impacts": direct_impacts,
            "indirect_impacts": indirect_impacts,
            "impacted_layers": sorted(list(impacted_layers)),
            "impacted_services": sorted(list(impacted_services)),
            "impacted_domains": sorted(list(impacted_domains)),
            "recommended_testing_types": sorted(list(recommended_testing_types)),
            "explanation": explanation,
            "confidence": confidence
        }

    @classmethod
    def _map_files_to_nodes(
        cls,
        db: Session,
        repository_id: UUID,
        file_paths: List[str]
    ) -> List[ArchitectureNode]:
        """Maps file paths to ArchitectureNodes using normalized paths."""
        normalized_paths = [cls._normalize_path(f) for f in file_paths]
        
        nodes = db.query(ArchitectureNode).filter(
            ArchitectureNode.repository_id == repository_id,
            ArchitectureNode.normalized_path.in_(normalized_paths)
        ).all()
        
        return nodes

    @classmethod
    def _normalize_path(cls, path: str) -> str:
        """Normalizes a file path for consistent lookups."""
        return path.replace("\\", "/").lstrip("/")

    @classmethod
    def _build_adjacency_lists(
        cls,
        db: Session,
        repository_id: UUID,
        nodes: List[ArchitectureNode]
    ) -> Tuple[Dict[UUID, Set[Tuple[UUID, str]]], Dict[UUID, Set[Tuple[UUID, str]]]]:
        """Builds incoming and outgoing adjacency lists from ArchitectureEdges."""
        node_ids = [node.id for node in nodes]
        
        edges = db.query(ArchitectureEdge).filter(
            ArchitectureEdge.repository_id == repository_id,
            (ArchitectureEdge.source_node_id.in_(node_ids)) |
            (ArchitectureEdge.target_node_id.in_(node_ids))
        ).all()
        
        incoming: Dict[UUID, Set[Tuple[UUID, str]]] = {}
        outgoing: Dict[UUID, Set[Tuple[UUID, str]]] = {}
        
        for edge in edges:
            # Outgoing from source
            outgoing.setdefault(edge.source_node_id, set()).add(
                (edge.target_node_id, edge.edge_type.value)
            )
            # Incoming to target
            incoming.setdefault(edge.target_node_id, set()).add(
                (edge.source_node_id, edge.edge_type.value)
            )
        
        return incoming, outgoing

    @classmethod
    def _discover_services(cls, nodes: List[ArchitectureNode]) -> Set[str]:
        """Discovers distinct services from architecture nodes."""
        services: Set[str] = set()
        
        for node in nodes:
            # Use module_name if available
            if node.module_name:
                services.add(f"{node.module_name} service")
                continue
            
            # Fallback to path-based detection
            path_lower = node.path.lower()
            
            if "auth" in path_lower or "login" in path_lower:
                services.add("auth service")
            elif "user" in path_lower or "member" in path_lower or "profile" in path_lower:
                services.add("user service")
            elif any(k in path_lower for k in ("notification", "email", "sms", "alert")):
                services.add("notification service")
            elif any(k in path_lower for k in ("billing", "payment", "invoice", "stripe", "charge")):
                services.add("billing service")
            elif any(k in path_lower for k in ("api", "router", "controller", "route")):
                services.add("api service")
            elif any(k in path_lower for k in ("db", "model", "schema", "entity", "orm", "repository")):
                services.add("database service")
            else:
                # Use node type as service
                services.add(f"{node.node_type.value.lower()} service")
        
        return services

    @classmethod
    def _map_domains(cls, services: Set[str]) -> Set[str]:
        """Maps service names to architectural domains."""
        domains: Set[str] = set()
        
        for svc in services:
            if "auth" in svc.lower():
                domains.add("Authentication")
            elif "user" in svc.lower():
                domains.add("User Management")
            elif "notification" in svc.lower() or "email" in svc.lower():
                domains.add("Email Notifications")
            elif "billing" in svc.lower() or "payment" in svc.lower():
                domains.add("Billing")
            elif "api" in svc.lower():
                domains.add("API Endpoints")
            elif "database" in svc.lower() or "db" in svc.lower():
                domains.add("Data Platform")
            else:
                domains.add(svc.title())
        
        return domains

    @classmethod
    def _suggest_testing_types(
        cls,
        impacted_nodes: List[ArchitectureNode],
        impacted_layers: Set[str],
        impacted_services: Set[str]
    ) -> Set[str]:
        """Suggests appropriate testing types based on graph topology."""
        types: Set[str] = set()
        
        # Rule A: Integration tests if multiple services impacted
        if len(impacted_services) >= 2:
            types.add("Integration")
        
        # Rule B: Workflow tests if API/routing code impacted
        if any(node.node_type in [ArchitectureNodeType.ROUTE, ArchitectureNodeType.API_ENDPOINT] 
               for node in impacted_nodes):
            types.add("Workflow")
        
        # Rule C: UI tests if UI layer impacted
        if ArchitectureLayer.UI.value in impacted_layers:
            types.add("UI")
        
        # Rule D: Regression tests if high ripple impact
        if len(impacted_nodes) >= 5:
            types.add("Regression")
        
        # Rule E: Unit tests if domain layer impacted
        if ArchitectureLayer.DOMAIN.value in impacted_layers:
            types.add("Unit")
        
        return types

    @classmethod
    def _compose_explanation(
        cls,
        changed_nodes: List[ArchitectureNode],
        impacted_services: Set[str],
        impacted_domains: Set[str],
        recommended_testing_types: Set[str]
    ) -> str:
        """Composes human-readable explanation."""
        if not impacted_services:
            return "Minimal architectural impact detected."
        
        services_str = ", ".join(sorted(list(impacted_services)))
        domains_str = ", ".join(sorted(list(impacted_domains)))
        testing_str = ", ".join(sorted(list(recommended_testing_types)))
        
        return (
            f"Discovered architectural impact spanning {services_str}. "
            f"Affects domains: {domains_str}. "
            f"Recommended testing categories: {testing_str}."
        )

    @classmethod
    def get_impacted_behaviors(
        cls,
        db: Session,
        *,
        repository_id: UUID,
        changed_files: List[str]
    ) -> List[Dict[str, Any]]:
        """Identifies behaviors impacted by architectural changes.
        
        This method maps impacted architecture nodes to behaviors based on
        file path associations and module membership.
        """
        from app.models.behavior import Behavior
        
        # Get architecture impact
        impact = cls.analyze_impact(db, repository_id=repository_id, changed_files=changed_files)
        impacted_files = impact.get("impacted_files", [])
        
        if not impacted_files:
            return []
        
        # Find behaviors that reference impacted files
        # This is a heuristic - in production, you'd have explicit behavior->file mappings
        behaviors = db.query(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False
        ).all()
        
        impacted_behaviors = []
        for behavior in behaviors:
            # Check if behavior description or name references impacted areas
            behavior_text = f"{behavior.name} {behavior.description}".lower()
            
            for file_path in impacted_files:
                file_lower = file_path.lower()
                
                # Simple heuristic: if file path keywords match behavior
                if any(keyword in behavior_text for keyword in file_lower.split("/")):
                    impacted_behaviors.append({
                        "id": str(behavior.id),
                        "name": behavior.name,
                        "risk_level": behavior.risk_level,
                        "matched_file": file_path
                    })
                    break
        
        return impacted_behaviors

    @classmethod
    def get_impacted_journeys(
        cls,
        db: Session,
        *,
        repository_id: UUID,
        changed_files: List[str]
    ) -> List[Dict[str, Any]]:
        """Identifies journeys impacted by architectural changes.
        
        This method maps impacted architecture nodes to journeys based on
        behavior associations.
        """
        from app.models.journey import Journey
        from app.models.journey_behavior import JourneyBehavior
        
        # Get impacted behaviors
        impacted_behaviors = cls.get_impacted_behaviors(
            db, repository_id=repository_id, changed_files=changed_files
        )
        
        if not impacted_behaviors:
            return []
        
        behavior_ids = [UUID(b["id"]) for b in impacted_behaviors]
        
        # Find journeys containing impacted behaviors
        journey_behaviors = db.query(JourneyBehavior).filter(
            JourneyBehavior.behavior_id.in_(behavior_ids)
        ).all()
        
        journey_ids = set(jb.journey_id for jb in journey_behaviors)
        
        journeys = db.query(Journey).filter(
            Journey.id.in_(journey_ids),
            Journey.is_deleted == False
        ).all()
        
        return [
            {
                "id": str(journey.id),
                "name": journey.name,
                "risk_level": journey.risk_level,
                "impacted_behavior_count": len(
                    [jb for jb in journey_behaviors if jb.journey_id == journey.id]
                )
            }
            for journey in journeys
        ]
