"""
ArchitectureGraphBuilder for building and maintaining the repository architecture graph.
Orchestrates node indexing, dependency extraction, and metadata calculation.
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.architecture_node import ArchitectureNode, ArchitectureNodeType
from app.models.architecture_edge import ArchitectureEdge
from app.services.repository_architecture_indexer import RepositoryArchitectureIndexer
from app.services.architecture_dependency_indexer import ArchitectureDependencyIndexer

logger = logging.getLogger(__name__)

class ArchitectureGraphBuilder:
    """
    Orchestrates the building of architecture nodes and edges for a repository.
    Calculates structural metadata for the resulting graph.
    """

    @classmethod
    def build_repository_graph(
        cls,
        db: Session,
        repository_id: UUID,
        file_paths: Optional[List[str]] = None,
        checkout_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Performs a full rebuild or update of the repository architecture graph.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            file_paths: Optional list of file paths (e.g. from GitHub sync)
            checkout_dir: Optional local checkout directory
            
        Returns:
            Dictionary with sync statistics
        """
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository {repository_id} not found.")

        # If not provided, try to use repository's workspace_path
        if not checkout_dir:
            checkout_dir = repo.workspace_path

        # 1. & 2. Create/Update Architecture Nodes
        # If file_paths is not provided, we could scan the checkout_dir
        # For now, we assume file_paths is passed from the sync process or we fail
        if not file_paths and checkout_dir:
            import os
            file_paths = []
            for root, _, files in os.walk(checkout_dir):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), checkout_dir)
                    file_paths.append(rel_path.replace("\\", "/"))

        if not file_paths:
            logger.warning(f"No file paths provided for graph building in {repository_id}")
            return {"nodes_indexed": 0, "edges_indexed": 0, "status": "skipped_no_files"}

        nodes = RepositoryArchitectureIndexer.index_repository(
            db=db,
            repository_id=repository_id,
            file_paths=file_paths,
            framework_hints=repo.framework_hints
        )
        
        # 3. & 4. & 5. Parse imports and create Architecture Edges
        edges_count = 0
        if checkout_dir:
            edges_count = ArchitectureDependencyIndexer.index_dependencies(
                db=db,
                repository_id=repository_id,
                checkout_dir=checkout_dir
            )
        else:
            logger.warning(f"No checkout directory provided for dependency indexing in {repository_id}")

        # 6. Calculate Node Metadata
        cls.calculate_node_metadata(db, repository_id)

        return {
            "nodes_indexed": len(nodes),
            "edges_indexed": edges_count,
            "status": "success"
        }

    @classmethod
    def calculate_node_metadata(cls, db: Session, repository_id: UUID):
        """
        Calculates and updates metadata for all architecture nodes in a repository.
        """
        # Fetch all nodes for this repository
        nodes = db.query(ArchitectureNode).filter(
            ArchitectureNode.repository_id == repository_id
        ).all()

        # Get inbound and outbound counts in bulk
        inbound_counts = dict(
            db.query(ArchitectureEdge.target_node_id, func.count(ArchitectureEdge.id))
            .filter(ArchitectureEdge.repository_id == repository_id)
            .group_by(ArchitectureEdge.target_node_id)
            .all()
        )

        outbound_counts = dict(
            db.query(ArchitectureEdge.source_node_id, func.count(ArchitectureEdge.id))
            .filter(ArchitectureEdge.repository_id == repository_id)
            .group_by(ArchitectureEdge.source_node_id)
            .all()
        )

        for node in nodes:
            inbound = inbound_counts.get(node.id, 0)
            outbound = outbound_counts.get(node.id, 0)
            
            # Metadata structure
            metadata = node.node_metadata or {}
            metadata.update({
                "inbound_dependency_count": inbound,
                "outbound_dependency_count": outbound,
                "is_entrypoint": inbound == 0 and outbound > 0, # Heuristic
                "is_test_file": node.node_type == ArchitectureNodeType.TEST,
                "is_api_route": node.node_type in [ArchitectureNodeType.ROUTE, ArchitectureNodeType.API_ENDPOINT],
                "is_ui_page": node.node_type == ArchitectureNodeType.PAGE,
            })
            
            node.node_metadata = metadata
            
        db.commit()
        logger.info(f"Updated metadata for {len(nodes)} nodes in repository {repository_id}")
