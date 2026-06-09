"""Service for managing repository architecture edges.

Provides functionality to create, update, and query architecture edges
representing dependencies between architecture nodes.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.architecture_edge import ArchitectureEdge, ArchitectureEdgeType


class ArchitectureEdgeService:
    """Service for managing repository architecture edges."""

    @classmethod
    def create_or_update_edge(
        cls,
        db: Session,
        repository_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: ArchitectureEdgeType,
        evidence: Dict[str, Any],
        confidence: str = "HIGH",
    ) -> ArchitectureEdge:
        """Create or update an architecture edge.
        
        This method uses upsert logic to ensure idempotent operations:
        - If an edge with the same repository_id, source_node_id, target_node_id, 
          and edge_type exists, update it.
        - Otherwise, create a new edge.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            source_node_id: Source node UUID
            target_node_id: Target node UUID
            edge_type: Classification of the edge
            evidence: Required proof of the dependency
            confidence: Confidence level (default "HIGH")
            
        Returns:
            Created or updated ArchitectureEdge
        """
        # Ensure evidence is provided
        if not evidence:
            raise ValueError("Evidence is required for architecture edges.")
            
        # Prepare the insert statement with upsert logic
        stmt = insert(ArchitectureEdge).values(
            repository_id=repository_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            evidence=evidence,
            confidence=confidence,
        )
        
        # Define the on_conflict_do_update (upsert) behavior
        update_stmt = stmt.on_conflict_do_update(
            index_elements=["repository_id", "source_node_id", "target_node_id", "edge_type"],
            set_={
                "evidence": stmt.excluded.evidence,
                "confidence": stmt.excluded.confidence,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        
        # Execute the upsert
        db.execute(update_stmt)
        db.commit()
        
        # Fetch and return the created/updated edge
        edge = (
            db.query(ArchitectureEdge)
            .filter(
                ArchitectureEdge.repository_id == repository_id,
                ArchitectureEdge.source_node_id == source_node_id,
                ArchitectureEdge.target_node_id == target_node_id,
                ArchitectureEdge.edge_type == edge_type,
            )
            .first()
        )
        
        return edge

    @classmethod
    def get_edge(
        cls,
        db: Session,
        repository_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: ArchitectureEdgeType,
    ) -> Optional[ArchitectureEdge]:
        """Get an architecture edge by its unique identifiers.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            source_node_id: Source node UUID
            target_node_id: Target node UUID
            edge_type: Edge type
            
        Returns:
            ArchitectureEdge if found, None otherwise
        """
        return (
            db.query(ArchitectureEdge)
            .filter(
                ArchitectureEdge.repository_id == repository_id,
                ArchitectureEdge.source_node_id == source_node_id,
                ArchitectureEdge.target_node_id == target_node_id,
                ArchitectureEdge.edge_type == edge_type,
            )
            .first()
        )

    @classmethod
    def get_outgoing_edges(
        cls,
        db: Session,
        repository_id: UUID,
        source_node_id: UUID,
    ) -> List[ArchitectureEdge]:
        """Get all outgoing edges from a specific node.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            source_node_id: Source node UUID
            
        Returns:
            List of outgoing ArchitectureEdges
        """
        return (
            db.query(ArchitectureEdge)
            .filter(
                ArchitectureEdge.repository_id == repository_id,
                ArchitectureEdge.source_node_id == source_node_id,
            )
            .all()
        )

    @classmethod
    def get_incoming_edges(
        cls,
        db: Session,
        repository_id: UUID,
        target_node_id: UUID,
    ) -> List[ArchitectureEdge]:
        """Get all incoming edges to a specific node.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            target_node_id: Target node UUID
            
        Returns:
            List of incoming ArchitectureEdges
        """
        return (
            db.query(ArchitectureEdge)
            .filter(
                ArchitectureEdge.repository_id == repository_id,
                ArchitectureEdge.target_node_id == target_node_id,
            )
            .all()
        )

    @classmethod
    def delete_edge(cls, db: Session, edge_id: UUID) -> bool:
        """Delete an architecture edge by ID.
        
        Args:
            db: Database session
            edge_id: Edge UUID
            
        Returns:
            True if deleted, False if not found
        """
        result = (
            db.query(ArchitectureEdge)
            .filter(ArchitectureEdge.id == edge_id)
            .delete()
        )
        db.commit()
        return result > 0

    @classmethod
    def delete_edges_by_repository(cls, db: Session, repository_id: UUID) -> int:
        """Delete all architecture edges for a repository.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            
        Returns:
            Number of edges deleted
        """
        result = (
            db.query(ArchitectureEdge)
            .filter(ArchitectureEdge.repository_id == repository_id)
            .delete()
        )
        db.commit()
        return result
