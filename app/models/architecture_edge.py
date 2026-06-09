"""Architecture edge model for representing dependencies between architecture nodes.

This model defines directed edges between nodes in the repository architecture graph,
enabling dependency tracing, impact expansion, and structural integrity analysis.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class ArchitectureEdgeType(str, PyEnum):
    """Types of architecture edges in the repository graph."""
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    RENDERS = "RENDERS"
    ROUTES_TO = "ROUTES_TO"
    USES_MODEL = "USES_MODEL"
    USES_CONFIG = "USES_CONFIG"
    TESTS = "TESTS"
    DEPENDS_ON = "DEPENDS_ON"
    UNKNOWN = "UNKNOWN"


class ArchitectureEdge(Base):
    """Represents a directed edge between two architecture nodes.
    
    Attributes:
        id: Unique identifier for the edge
        repository_id: Foreign key to the repository
        source_node_id: Foreign key to the source ArchitectureNode
        target_node_id: Foreign key to the target ArchitectureNode
        edge_type: Classification of the dependency (IMPORTS, CALLS, etc.)
        confidence: Confidence level in the edge detection (0.0 - 1.0)
        evidence: Evidence backing the existence of this edge (e.g., import statement)
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    
    __tablename__ = "architecture_edges"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Repository scoping
    repository_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("repositories.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Source and Target nodes
    source_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("architecture_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    target_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("architecture_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Edge classification
    edge_type = Column(
        Enum(ArchitectureEdgeType, name="architecture_edge_type"), 
        nullable=False, 
        index=True
    )
    
    # Confidence scoring (Float)
    confidence = Column(String(20), nullable=False, default="HIGH")
    
    # Evidence required - stores specific proof (e.g., source code snippet, import line)
    evidence = Column(JSONB, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, 
        nullable=False, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Constraints and indexes
    __table_args__ = (
        # Unique constraint: unique directed edge of a specific type per repository
        Index(
            "ix_architecture_edges_unique_directed", 
            "repository_id", 
            "source_node_id", 
            "target_node_id", 
            "edge_type",
            unique=True
        ),
        # Index for looking up outgoing edges from a node
        Index(
            "ix_architecture_edges_source",
            "repository_id",
            "source_node_id"
        ),
        # Index for looking up incoming edges to a node
        Index(
            "ix_architecture_edges_target",
            "repository_id",
            "target_node_id"
        ),
    )
    
    # Relationships
    repository = relationship("Repository", back_populates="architecture_edges")
    source_node = relationship(
        "ArchitectureNode", 
        foreign_keys=[source_node_id], 
        back_populates="outgoing_edges"
    )
    target_node = relationship(
        "ArchitectureNode", 
        foreign_keys=[target_node_id], 
        back_populates="incoming_edges"
    )
    
    def __repr__(self) -> str:
        return (
            f"<ArchitectureEdge("
            f"id={self.id}, "
            f"type={self.edge_type.value}, "
            f"source={self.source_node_id}, "
            f"target={self.target_node_id}"
            f")>"
        )
    
    def to_dict(self) -> dict:
        """Convert edge to dictionary representation."""
        return {
            "id": str(self.id),
            "repository_id": str(self.repository_id),
            "source_node_id": str(self.source_node_id),
            "target_node_id": str(self.target_node_id),
            "edge_type": self.edge_type.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
