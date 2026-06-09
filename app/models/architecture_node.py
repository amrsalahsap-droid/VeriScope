"""Architecture node model for representing repository structure as a graph.

This model provides a unified graph representation of repository architecture,
enabling structural analysis, dependency visualization, and impact analysis.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class ArchitectureNodeType(str, PyEnum):
    """Types of architecture nodes in the repository graph."""
    FILE = "FILE"
    ROUTE = "ROUTE"
    PAGE = "PAGE"
    COMPONENT = "COMPONENT"
    SERVICE = "SERVICE"
    MODULE = "MODULE"
    API_ENDPOINT = "API_ENDPOINT"
    DATABASE_MODEL = "DATABASE_MODEL"
    CONFIG = "CONFIG"
    TEST = "TEST"
    UNKNOWN = "UNKNOWN"


class ArchitectureLayer(str, PyEnum):
    """Architectural layers for node classification."""
    UI = "UI"
    API = "API"
    DOMAIN = "DOMAIN"
    DATA = "DATA"
    INFRA = "INFRA"
    TEST = "TEST"
    CONFIG = "CONFIG"
    UNKNOWN = "UNKNOWN"


class ArchitectureNode(Base):
    """Represents a node in the repository architecture graph.
    
    Each node represents a structural element (file, route, component, etc.)
    within the repository, enabling graph-based analysis and visualization.
    
    Attributes:
        id: Unique identifier for the node
        repository_id: Foreign key to the repository
        node_type: Classification of the node (FILE, ROUTE, etc.)
        path: Original file path or identifier
        name: Human-readable name of the node
        normalized_path: Normalized path for consistent lookups
        module_name: Optional module/system classification
        framework_hint: Optional framework detection hint
        layer: Architectural layer classification
        metadata: Flexible JSONB storage for additional attributes
        confidence: Confidence level in node classification
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    
    __tablename__ = "architecture_nodes"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Repository scoping
    repository_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("repositories.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Node classification
    node_type = Column(
        Enum(ArchitectureNodeType, name="architecture_node_type"), 
        nullable=False, 
        index=True
    )
    
    # Path and naming
    path = Column(Text, nullable=False, index=True)
    name = Column(String(500), nullable=False)
    normalized_path = Column(Text, nullable=False, index=True)
    
    # Optional classifications
    module_name = Column(String(255), nullable=True, index=True)
    framework_hint = Column(String(100), nullable=True)
    layer = Column(
        Enum(ArchitectureLayer, name="architecture_layer"), 
        nullable=False, 
        index=True
    )
    
    # Flexible metadata storage (note: 'node_metadata' not 'metadata' as that's reserved)
    node_metadata = Column(JSONB, nullable=True)
    
    # Confidence scoring
    confidence = Column(String(20), nullable=False, default="HIGH")
    
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
        # Unique constraint: one node per normalized path per repository
        Index(
            "ix_architecture_nodes_repo_path", 
            "repository_id", 
            "normalized_path", 
            unique=True
        ),
        # Composite index for common query patterns
        Index(
            "ix_architecture_nodes_repo_type_layer",
            "repository_id",
            "node_type",
            "layer"
        ),
        # Index for module-based lookups
        Index(
            "ix_architecture_nodes_module",
            "repository_id",
            "module_name"
        ),
    )
    
    # Relationships
    repository = relationship("Repository", back_populates="architecture_nodes")
    outgoing_edges = relationship(
        "ArchitectureEdge",
        foreign_keys="[ArchitectureEdge.source_node_id]",
        back_populates="source_node",
        cascade="all, delete-orphan"
    )
    incoming_edges = relationship(
        "ArchitectureEdge",
        foreign_keys="[ArchitectureEdge.target_node_id]",
        back_populates="target_node",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return (
            f"<ArchitectureNode("
            f"id={self.id}, "
            f"repository_id={self.repository_id}, "
            f"type={self.node_type.value}, "
            f"path={self.path!r}, "
            f"layer={self.layer.value}"
            f")>"
        )
    
    def to_dict(self) -> dict:
        """Convert node to dictionary representation."""
        return {
            "id": str(self.id),
            "repository_id": str(self.repository_id),
            "node_type": self.node_type.value,
            "path": self.path,
            "name": self.name,
            "normalized_path": self.normalized_path,
            "module_name": self.module_name,
            "framework_hint": self.framework_hint,
            "layer": self.layer.value,
            "node_metadata": self.node_metadata,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
