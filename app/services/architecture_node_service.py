"""Service for managing repository architecture nodes.

Provides functionality to create, update, and query architecture nodes
for repository graph representation.
"""

import os
import re
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.architecture_node import (
    ArchitectureNode,
    ArchitectureNodeType,
    ArchitectureLayer,
)
from app.models.repository import Repository


class ArchitectureNodeService:
    """Service for managing repository architecture nodes."""

    # File extension to node type mapping
    EXTENSION_NODE_TYPES: Dict[str, ArchitectureNodeType] = {
        # JavaScript/TypeScript
        ".js": ArchitectureNodeType.FILE,
        ".jsx": ArchitectureNodeType.COMPONENT,
        ".ts": ArchitectureNodeType.FILE,
        ".tsx": ArchitectureNodeType.COMPONENT,
        # Python
        ".py": ArchitectureNodeType.FILE,
        # Config files
        ".json": ArchitectureNodeType.CONFIG,
        ".yml": ArchitectureNodeType.CONFIG,
        ".yaml": ArchitectureNodeType.CONFIG,
        ".toml": ArchitectureNodeType.CONFIG,
        # Documentation
        ".md": ArchitectureNodeType.FILE,
        ".mdx": ArchitectureNodeType.FILE,
        # Styles
        ".css": ArchitectureNodeType.FILE,
        ".scss": ArchitectureNodeType.FILE,
        ".sass": ArchitectureNodeType.FILE,
        ".less": ArchitectureNodeType.FILE,
    }

    # Framework detection patterns
    FRAMEWORK_PATTERNS: Dict[str, str] = {
        r"next\.config": "nextjs",
        r"nuxt\.config": "nuxt",
        r"vue\.config": "vue",
        r"react": "react",
        r"angular": "angular",
        r"express": "express",
        r"fastapi": "fastapi",
        r"flask": "flask",
        r"django": "django",
        r"spring": "spring",
        r"laravel": "laravel",
    }

    # Layer detection patterns based on path
    LAYER_PATTERNS: Dict[ArchitectureLayer, List[str]] = {
        ArchitectureLayer.UI: [
            r"/ui/",
            r"/components?/",
            r"/views?/",
            r"/pages?/",
            r"/screens?/",
            r"/widgets?/",
            r"\.jsx$",
            r"\.tsx$",
            r"\.vue$",
        ],
        ArchitectureLayer.API: [
            r"/api/",
            r"/routes?/",
            r"/endpoints?/",
            r"/controllers?/",
            r"/handlers?/",
        ],
        ArchitectureLayer.DOMAIN: [
            r"/domain/",
            r"/services?/",
            r"/business/",
            r"/logic/",
            r"/core/",
        ],
        ArchitectureLayer.DATA: [
            r"/data/",
            r"/models?/",
            r"/entities?/",
            r"/repositories?/",
            r"/db/",
            r"/database/",
            r"/migrations?/",
        ],
        ArchitectureLayer.INFRA: [
            r"/infra/",
            r"/infrastructure/",
            r"/config/",
            r"/deploy/",
            r"/ops/",
            r"/ci/",
            r"/cd/",
            r"\.yml$",
            r"\.yaml$",
            r"docker",
            r"kubernetes",
        ],
        ArchitectureLayer.TEST: [
            r"/test/",
            r"/tests?/",
            r"/spec/",
            r"/__tests?__/",
            r"\.spec\.",
            r"\.test\.",
        ],
        ArchitectureLayer.CONFIG: [
            r"/config/",
            r"config\.",
            r"settings\.",
            r"\.env",
            r"\.ini$",
            r"\.toml$",
        ],
    }

    @classmethod
    def normalize_path(cls, path: str) -> str:
        """Normalize a file path for consistent lookups.
        
        Args:
            path: The file path to normalize
            
        Returns:
            Normalized path (lowercase, forward slashes, no trailing slash)
        """
        # Convert to lowercase for case-insensitive matching
        normalized = path.lower()
        # Normalize to forward slashes
        normalized = normalized.replace("\\", "/")
        # Remove leading slash
        normalized = normalized.lstrip("/")
        # Remove trailing slash if present
        normalized = normalized.rstrip("/")
        # Remove duplicate slashes
        while "//" in normalized:
            normalized = normalized.replace("//", "/")
        return normalized

    @classmethod
    def detect_node_type(cls, path: str, content_hint: Optional[str] = None) -> ArchitectureNodeType:
        """Detect the node type from a file path.
        
        Args:
            path: The file path
            content_hint: Optional content hint for detection
            
        Returns:
            Detected ArchitectureNodeType
        """
        path_lower = path.lower()
        
        # Check for route patterns
        if any(pattern in path_lower for pattern in ["route", "router", "endpoint", "handler"]):
            return ArchitectureNodeType.ROUTE
        
        # Check for page patterns
        if "/page" in path_lower or path_lower.endswith(("page.jsx", "page.tsx", "page.js", "page.ts")):
            return ArchitectureNodeType.PAGE
        
        # Check for API patterns
        if "/api/" in path_lower or "api." in path_lower:
            return ArchitectureNodeType.API_ENDPOINT
        
        # Check for model/database patterns
        if any(pattern in path_lower for pattern in ["/model", "/entity", "/schema", "/db/", "/database/"]):
            return ArchitectureNodeType.DATABASE_MODEL
        
        # Check for service patterns
        if "/service" in path_lower or path_lower.endswith(("service.js", "service.ts", "service.py")):
            return ArchitectureNodeType.SERVICE
        
        # Check for component patterns
        if "/component" in path_lower or path_lower.endswith(("component.jsx", "component.tsx", ".vue")):
            return ArchitectureNodeType.COMPONENT
        
        # Check for config patterns
        if "/config" in path_lower or path_lower.endswith((".json", ".yml", ".yaml", ".toml", ".ini", ".env")):
            return ArchitectureNodeType.CONFIG
        
        # Check for test patterns
        if any(pattern in path_lower for pattern in ["/test", "/spec", ".test.", ".spec."]):
            return ArchitectureNodeType.TEST
        
        # Check file extension
        _, ext = os.path.splitext(path_lower)
        if ext in cls.EXTENSION_NODE_TYPES:
            return cls.EXTENSION_NODE_TYPES[ext]
        
        return ArchitectureNodeType.FILE

    @classmethod
    def detect_framework_hint(cls, path: str, content_hint: Optional[str] = None) -> Optional[str]:
        """Detect framework hint from path or content.
        
        Args:
            path: The file path
            content_hint: Optional content hint
            
        Returns:
            Framework hint string or None
        """
        path_lower = path.lower()
        
        for pattern, framework in cls.FRAMEWORK_PATTERNS.items():
            if re.search(pattern, path_lower):
                return framework
        
        return None

    @classmethod
    def detect_layer(cls, path: str, node_type: ArchitectureNodeType) -> ArchitectureLayer:
        """Detect architectural layer from path and node type.
        
        Args:
            path: The file path
            node_type: The detected node type
            
        Returns:
            Detected ArchitectureLayer
        """
        path_lower = path.lower()
        
        # Check layer patterns
        for layer, patterns in cls.LAYER_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, path_lower):
                    return layer
        
        # Fallback to node type mapping
        layer_mapping = {
            ArchitectureNodeType.PAGE: ArchitectureLayer.UI,
            ArchitectureNodeType.COMPONENT: ArchitectureLayer.UI,
            ArchitectureNodeType.ROUTE: ArchitectureLayer.API,
            ArchitectureNodeType.API_ENDPOINT: ArchitectureLayer.API,
            ArchitectureNodeType.SERVICE: ArchitectureLayer.DOMAIN,
            ArchitectureNodeType.DATABASE_MODEL: ArchitectureLayer.DATA,
            ArchitectureNodeType.CONFIG: ArchitectureLayer.CONFIG,
            ArchitectureNodeType.TEST: ArchitectureLayer.TEST,
        }
        
        return layer_mapping.get(node_type, ArchitectureLayer.UNKNOWN)

    @classmethod
    def create_or_update_node(
        cls,
        db: Session,
        repository_id: UUID,
        path: str,
        node_type: Optional[ArchitectureNodeType] = None,
        name: Optional[str] = None,
        module_name: Optional[str] = None,
        framework_hint: Optional[str] = None,
        layer: Optional[ArchitectureLayer] = None,
        node_metadata: Optional[Dict[str, Any]] = None,
        confidence: str = "HIGH",
    ) -> ArchitectureNode:
        """Create or update an architecture node.
        
        This method uses upsert logic to ensure idempotent operations:
        - If a node with the same repository_id and normalized_path exists, update it
        - Otherwise, create a new node
        
        Args:
            db: Database session
            repository_id: Repository UUID
            path: File path or identifier
            node_type: Node type (auto-detected if None)
            name: Human-readable name (auto-derived if None)
            module_name: Optional module/system classification
            framework_hint: Optional framework hint (auto-detected if None)
            layer: Architectural layer (auto-detected if None)
            node_metadata: Optional metadata dict
            confidence: Confidence level
            
        Returns:
            Created or updated ArchitectureNode
        """
        # Normalize the path
        normalized_path = cls.normalize_path(path)
        
        # Auto-detect node type if not provided
        if node_type is None:
            node_type = cls.detect_node_type(path)
        
        # Derive name if not provided
        if name is None:
            name = os.path.basename(path) or path
        
        # Auto-detect framework hint if not provided
        if framework_hint is None:
            framework_hint = cls.detect_framework_hint(path)
        
        # Auto-detect layer if not provided
        if layer is None:
            layer = cls.detect_layer(path, node_type)
        
        # Prepare the insert statement with upsert logic
        stmt = insert(ArchitectureNode).values(
            repository_id=repository_id,
            node_type=node_type,
            path=path,
            name=name,
            normalized_path=normalized_path,
            module_name=module_name,
            framework_hint=framework_hint,
            layer=layer,
            node_metadata=node_metadata,
            confidence=confidence,
        )
        
        # Define the on_conflict_do_update (upsert) behavior
        update_stmt = stmt.on_conflict_do_update(
            index_elements=["repository_id", "normalized_path"],
            set_={
                "node_type": stmt.excluded.node_type,
                "name": stmt.excluded.name,
                "module_name": stmt.excluded.module_name,
                "framework_hint": stmt.excluded.framework_hint,
                "layer": stmt.excluded.layer,
                "node_metadata": stmt.excluded.node_metadata,
                "confidence": stmt.excluded.confidence,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        
        # Execute the upsert
        db.execute(update_stmt)
        db.commit()
        
        # Fetch and return the created/updated node
        node = (
            db.query(ArchitectureNode)
            .filter(
                ArchitectureNode.repository_id == repository_id,
                ArchitectureNode.normalized_path == normalized_path,
            )
            .first()
        )
        
        return node

    @classmethod
    def get_node_by_path(
        cls,
        db: Session,
        repository_id: UUID,
        path: str,
    ) -> Optional[ArchitectureNode]:
        """Get an architecture node by its path.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            path: File path or identifier
            
        Returns:
            ArchitectureNode if found, None otherwise
        """
        normalized_path = cls.normalize_path(path)
        
        return (
            db.query(ArchitectureNode)
            .filter(
                ArchitectureNode.repository_id == repository_id,
                ArchitectureNode.normalized_path == normalized_path,
            )
            .first()
        )

    @classmethod
    def get_nodes_by_repository(
        cls,
        db: Session,
        repository_id: UUID,
        node_type: Optional[ArchitectureNodeType] = None,
        layer: Optional[ArchitectureLayer] = None,
        module_name: Optional[str] = None,
    ) -> List[ArchitectureNode]:
        """Get architecture nodes for a repository with optional filtering.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            node_type: Optional filter by node type
            layer: Optional filter by layer
            module_name: Optional filter by module name
            
        Returns:
            List of matching ArchitectureNodes
        """
        query = (
            db.query(ArchitectureNode)
            .filter(ArchitectureNode.repository_id == repository_id)
        )
        
        if node_type:
            query = query.filter(ArchitectureNode.node_type == node_type)
        
        if layer:
            query = query.filter(ArchitectureNode.layer == layer)
        
        if module_name:
            query = query.filter(ArchitectureNode.module_name == module_name)
        
        return query.all()

    @classmethod
    def delete_node(cls, db: Session, node_id: UUID) -> bool:
        """Delete an architecture node by ID.
        
        Args:
            db: Database session
            node_id: Node UUID
            
        Returns:
            True if deleted, False if not found
        """
        result = (
            db.query(ArchitectureNode)
            .filter(ArchitectureNode.id == node_id)
            .delete()
        )
        db.commit()
        return result > 0

    @classmethod
    def delete_nodes_by_repository(cls, db: Session, repository_id: UUID) -> int:
        """Delete all architecture nodes for a repository.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            
        Returns:
            Number of nodes deleted
        """
        result = (
            db.query(ArchitectureNode)
            .filter(ArchitectureNode.repository_id == repository_id)
            .delete()
        )
        db.commit()
        return result
