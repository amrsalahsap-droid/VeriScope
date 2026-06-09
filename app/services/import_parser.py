"""
ImportParserV1 for extracting dependency edges from file content.
"""

import os
import ast
import json
import logging
import re
from typing import List, Dict, Any, Tuple, Set, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.architecture_edge import ArchitectureEdgeType
from app.services.architecture_edge_service import ArchitectureEdgeService
from app.services.architecture_node_service import ArchitectureNodeService
from app.services.dependency_extraction import DependencyService
from app.services.path_alias_resolver import PathAliasResolver

logger = logging.getLogger(__name__)

class ImportParserV1:
    """
    Extracts dependency edges from file content.
    Supports JS/TS (import/export, require) and Python (import/from).
    Handles relative imports and path aliases.
    """
    
    @classmethod
    def parse_python_imports(cls, content: str) -> List[Tuple[str, str]]:
        """
        Extracts imports from Python content using the ast module.
        Returns: List of tuples (specifier, type)
        """
        specifiers = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        specifiers.append((alias.name, "import"))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module if node.module else ""
                    # For relative imports, we record the level (dots)
                    level = node.level
                    prefix = "." * level if level > 0 else ""
                    specifiers.append((prefix + module, "import"))
        except Exception as e:
            logger.debug(f"Failed to parse Python content: {e}")
        return specifiers

    @classmethod
    def resolve_python_path(cls, checkout_dir: str, source_file_path: str, specifier: str) -> str:
        """
        Resolves a Python import specifier to a repo-relative path.
        """
        source_file_path = source_file_path.replace("\\", "/")
        
        resolved_path = ""
        if specifier.startswith("."):
            # Relative import
            level = 0
            while specifier.startswith("."):
                level += 1
                specifier = specifier[1:]
            
            # Split and remove filename and then 'level-1' parent directories
            # e.g. . (level 1) means same directory as file
            # e.g. .. (level 2) means parent directory
            parts = source_file_path.split("/")[:-level]
            if specifier:
                parts.extend(specifier.split("."))
            resolved_path = "/".join(parts)
        else:
            # Absolute-ish within repo
            resolved_path = specifier.replace(".", "/")

        # Try .py or /__init__.py
        for suffix in [".py", "/__init__.py"]:
            if os.path.isfile(os.path.join(checkout_dir, resolved_path + suffix)):
                return (resolved_path + suffix).replace("\\", "/")
        
        # If it's a directory, it might be a package
        if os.path.isdir(os.path.join(checkout_dir, resolved_path)):
            if os.path.isfile(os.path.join(checkout_dir, resolved_path, "__init__.py")):
                return (resolved_path + "/__init__.py").replace("\\", "/")
                
        return (resolved_path + ".py").replace("\\", "/") # Fallback

    @classmethod
    def extract_and_persist(
        cls,
        db: Session,
        repository_id: UUID,
        source_file_path: str,
        content: str,
        checkout_dir: str,
        alias_resolver: Optional[PathAliasResolver] = None
    ) -> int:
        """
        Extracts imports from a file and persists them as ArchitectureEdges.
        """
        ext = os.path.splitext(source_file_path)[1].lower()
        specifiers = []

        if ext in (".py",):
            specifiers = cls.parse_python_imports(content)
        elif ext in (".js", ".jsx", ".ts", ".tsx"):
            specifiers = DependencyService.extract_specifiers_from_content(content, source_file_path)
            if alias_resolver:
                new_specifiers = []
                for spec, dtype in specifiers:
                    # Don't try to resolve relative imports via aliases
                    if not spec.startswith("."):
                        resolved_alias = alias_resolver.resolve(spec)
                        if resolved_alias:
                            new_specifiers.append((resolved_alias, dtype))
                        else:
                            new_specifiers.append((spec, dtype))
                    else:
                        new_specifiers.append((spec, dtype))
                specifiers = new_specifiers

        if not specifiers:
            return 0

        source_node = ArchitectureNodeService.get_node_by_path(db, repository_id, source_file_path)
        if not source_node:
            logger.debug(f"Source node not found for {source_file_path}")
            return 0

        edges_created = 0
        for specifier, dep_type in specifiers:
            resolved_path = ""
            if ext in (".py",):
                resolved_path = cls.resolve_python_path(checkout_dir, source_file_path, specifier)
            else:
                # JS/TS resolution
                # If it's already a repo-relative path (from alias), try to validate it
                if not specifier.startswith("."):
                    resolved_path = specifier
                    found = False
                    for e in [".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"]:
                        if os.path.isfile(os.path.join(checkout_dir, resolved_path + e)):
                            resolved_path = resolved_path + e
                            found = True
                            break
                    
                    if not found:
                        # Fallback to standard resolver if not found via alias/absolute path
                        resolved_path = DependencyService.resolve_specifier(checkout_dir, source_file_path, specifier)
                else:
                    resolved_path = DependencyService.resolve_specifier(checkout_dir, source_file_path, specifier)

            target_node = None
            if resolved_path:
                target_node = ArchitectureNodeService.get_node_by_path(db, repository_id, resolved_path)
            
            evidence = {
                "specifier": specifier,
                "dependency_type": dep_type,
                "resolved_path": resolved_path,
                "is_external": target_node is None
            }

            if target_node:
                try:
                    ArchitectureEdgeService.create_or_update_edge(
                        db=db,
                        repository_id=repository_id,
                        source_node_id=source_node.id,
                        target_node_id=target_node.id,
                        edge_type=ArchitectureEdgeType.IMPORTS,
                        evidence=evidence,
                        confidence="HIGH"
                    )
                    edges_created += 1
                except Exception as e:
                    logger.error(f"Failed to create edge: {e}")
            else:
                # Unresolved internal or external package
                # For V1 we don't create edges for external packages unless requested
                pass

        return edges_created
