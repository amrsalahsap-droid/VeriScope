"""Indexer for repository architecture.

Scans repository files and classifies them into architecture nodes
based on path patterns, extensions, and framework hints.
"""

import os
import re
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.architecture_node import (
    ArchitectureNode,
    ArchitectureNodeType,
    ArchitectureLayer,
)
from app.services.architecture_node_service import ArchitectureNodeService


class RepositoryArchitectureIndexer:
    """Indexes repository files into architecture nodes."""

    @classmethod
    def index_repository(
        cls,
        db: Session,
        repository_id: UUID,
        file_paths: List[str],
        framework_hints: Optional[List[str]] = None
    ) -> List[ArchitectureNode]:
        """Index all files in a repository into architecture nodes.
        
        Args:
            db: Database session
            repository_id: Repository UUID
            file_paths: List of file paths from GitHub sync
            framework_hints: Optional list of framework hints (e.g., ["nextjs", "react"])
            
        Returns:
            List of created or updated ArchitectureNodes
        """
        nodes = []
        
        # Determine main framework for classification context
        primary_framework = cls._detect_primary_framework(file_paths, framework_hints)
        
        for path in file_paths:
            # Skip common ignored directories if they somehow got in
            if any(part in path.split("/") for part in [".git", "node_modules", "dist", "build", ".next"]):
                continue
                
            node_type, layer = cls.classify_file(path, primary_framework)
            
            node = ArchitectureNodeService.create_or_update_node(
                db=db,
                repository_id=repository_id,
                path=path,
                node_type=node_type,
                layer=layer,
                framework_hint=primary_framework,
                confidence="HIGH"
            )
            nodes.append(node)
            
        return nodes

    @classmethod
    def classify_file(cls, path: str, framework: Optional[str] = None) -> (ArchitectureNodeType, ArchitectureLayer):
        """Classify a file based on its path and the repository framework.
        
        Args:
            path: File path
            framework: Primary framework of the repository
            
        Returns:
            Tuple of (ArchitectureNodeType, ArchitectureLayer)
        """
        path_lower = path.lower()
        normalized_path = ArchitectureNodeService.normalize_path(path)
        
        # Next.js / React Specific Rules
        if framework in ["nextjs", "react"]:
            # app/**/page.tsx → PAGE, UI
            if re.search(r"^app/.*page\.(tsx|jsx|js|ts)$", normalized_path):
                return ArchitectureNodeType.PAGE, ArchitectureLayer.UI
                
            # app/**/route.ts → ROUTE/API_ENDPOINT, API
            if re.search(r"^app/.*route\.(ts|js)$", normalized_path):
                return ArchitectureNodeType.API_ENDPOINT, ArchitectureLayer.API
                
            # components/** → COMPONENT, UI
            if normalized_path.startswith("components/"):
                return ArchitectureNodeType.COMPONENT, ArchitectureLayer.UI
                
            # modules/** → MODULE, DOMAIN
            if normalized_path.startswith("modules/"):
                return ArchitectureNodeType.MODULE, ArchitectureLayer.DOMAIN
                
            # lib/** → SERVICE or INFRA
            if normalized_path.startswith("lib/"):
                # Heuristic: if it's likely infra (db, config, api clients, storage, etc.)
                infra_keywords = ["db", "config", "api", "client", "storage", "aws", "gcp", "redis", "cache", "email", "sms"]
                if any(k in normalized_path for k in infra_keywords):
                    return ArchitectureNodeType.SERVICE, ArchitectureLayer.INFRA
                return ArchitectureNodeType.SERVICE, ArchitectureLayer.DOMAIN
                
            # prisma/schema.prisma → DATABASE_MODEL, DATA
            if normalized_path == "prisma/schema.prisma":
                return ArchitectureNodeType.DATABASE_MODEL, ArchitectureLayer.DATA
                
            # tests/** or __tests__/** → TEST, TEST
            if normalized_path.startswith("tests/") or "/__tests__/" in normalized_path or normalized_path.startswith("__tests__/"):
                return ArchitectureNodeType.TEST, ArchitectureLayer.TEST

        # Generic Rules
        # services/** → SERVICE, DOMAIN
        if normalized_path.startswith("services/"):
            return ArchitectureNodeType.SERVICE, ArchitectureLayer.DOMAIN
            
        # controllers/** → API
        if normalized_path.startswith("controllers/"):
            return ArchitectureNodeType.API_ENDPOINT, ArchitectureLayer.API
            
        # models/** → DATA
        if normalized_path.startswith("models/"):
            return ArchitectureNodeType.DATABASE_MODEL, ArchitectureLayer.DATA
            
        # config/** → CONFIG
        if normalized_path.startswith("config/"):
            return ArchitectureNodeType.CONFIG, ArchitectureLayer.CONFIG

        # Fallback to general detection in ArchitectureNodeService
        node_type = ArchitectureNodeService.detect_node_type(path)
        layer = ArchitectureNodeService.detect_layer(path, node_type)
        
        return node_type, layer

    @classmethod
    def _detect_primary_framework(cls, file_paths: List[str], hints: Optional[List[str]] = None) -> Optional[str]:
        """Detect the primary framework of the repository.
        
        Args:
            file_paths: List of file paths
            hints: Optional hints
            
        Returns:
            Primary framework name or None
        """
        if hints:
            # Prefer common frameworks if hinted
            for hint in hints:
                if hint in ["nextjs", "react", "fastapi", "django"]:
                    return hint
        
        # Scan files for framework indicators
        for path in file_paths:
            if "next.config" in path:
                return "nextjs"
            if "package.json" in path:
                # We could read content here, but rule says no content required in V1
                # so we stick to path-based hints
                pass
            if "manage.py" in path:
                return "django"
            if "requirements.txt" in path or "pyproject.toml" in path:
                # Could be many things
                pass
                
        return None
