"""
ArchitectureDependencyIndexer for creating dependency edges between architecture nodes.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.architecture_node import ArchitectureNode
from app.services.import_parser import ImportParserV1
from app.services.path_alias_resolver import PathAliasResolver

logger = logging.getLogger(__name__)

class ArchitectureDependencyIndexer:
    """
    Indexes dependencies between architecture nodes in a repository.
    """
    
    @classmethod
    def index_dependencies(
        cls,
        db: Session,
        repository_id: UUID,
        checkout_dir: str
    ) -> int:
        """
        Scans all architecture nodes in a repository and extracts dependencies.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            checkout_dir: Path to the local checkout of the repository
            
        Returns:
            Number of dependency edges created or updated.
        """
        # Fetch all nodes for this repository
        nodes = db.query(ArchitectureNode).filter(
            ArchitectureNode.repository_id == repository_id
        ).all()
        
        if not nodes:
            logger.info(f"No architecture nodes found for repository {repository_id}")
            return 0
            
        # Initialize PathAliasResolver to handle aliases (tsconfig, package.json, etc.)
        alias_resolver = PathAliasResolver(checkout_dir)
        
        total_edges = 0
        processed_count = 0
        
        logger.info(f"Starting dependency indexing for {len(nodes)} nodes in {repository_id}")
        
        for node in nodes:
            # We only parse files that exist on disk
            abs_path = os.path.join(checkout_dir, node.path)
            if not os.path.isfile(abs_path):
                continue
                
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                edges_count = ImportParserV1.extract_and_persist(
                    db=db,
                    repository_id=repository_id,
                    source_file_path=node.path,
                    content=content,
                    checkout_dir=checkout_dir,
                    alias_resolver=alias_resolver
                )
                total_edges += edges_count
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process node {node.path} at {abs_path}: {e}")
                
        logger.info(f"Dependency indexing complete for {repository_id}: processed {processed_count} files, created {total_edges} edges.")
        return total_edges
