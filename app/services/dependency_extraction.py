import os
import logging
from typing import List, Dict, Any, Tuple, Set
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import delete

from app.models.dependency import FileDependency
import tree_sitter
import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)

# Initialize tree-sitter languages
try:
    js_lang = Language(tree_sitter_javascript.language())
    ts_lang = Language(tree_sitter_typescript.language_typescript())
    tsx_lang = Language(tree_sitter_typescript.language_tsx())
except Exception as e:
    logger.error(f"Failed to initialize tree-sitter languages: {e}")
    js_lang = None
    ts_lang = None
    tsx_lang = None


class DependencyService:
    @staticmethod
    def get_parser_for_file(file_path: str) -> Tuple[Parser, Language]:
        """Returns a tree-sitter Parser and Language configured for the given file's extension."""
        parser = Parser()
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in (".js", ".jsx"):
            if not js_lang:
                raise ValueError("JavaScript grammar is not loaded")
            parser.language = js_lang
            return parser, js_lang
        elif ext in (".ts", ".d.ts"):
            if not ts_lang:
                raise ValueError("TypeScript grammar is not loaded")
            parser.language = ts_lang
            return parser, ts_lang
        elif ext in (".tsx",):
            if not tsx_lang:
                raise ValueError("TSX grammar is not loaded")
            parser.language = tsx_lang
            return parser, tsx_lang
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    @classmethod
    def extract_specifiers_from_content(cls, content: str, file_path: str) -> List[Tuple[str, str]]:
        """
        Parses source file content using tree-sitter and returns raw dependency specifiers.
        Returns:
            List of tuples: (specifier, dependency_type)
            e.g. [('./utils', 'import'), ('../Button', 'export')]
        """
        try:
            parser, lang = cls.get_parser_for_file(file_path)
        except ValueError:
            # File type not supported or parser not loaded
            return []

        tree = parser.parse(content.encode("utf-8"))
        specifiers = []

        def walk(n):
            if n.type == "import_statement":
                # Find direct string import (e.g. import { x } from './foo')
                for child in n.children:
                    if child.type == "string":
                        for sub in child.children:
                            if sub.type == "string_fragment":
                                specifiers.append((sub.text.decode("utf-8", errors="ignore"), "import"))
            elif n.type == "export_statement":
                # Find direct string export re-exports (e.g. export { x } from './foo')
                for child in n.children:
                    if child.type == "string":
                        for sub in child.children:
                            if sub.type == "string_fragment":
                                specifiers.append((sub.text.decode("utf-8", errors="ignore"), "export"))
            elif n.type == "call_expression":
                # Check for require('...') or dynamic import('...')
                fn_node = None
                if hasattr(n, 'child_by_field_name'):
                    fn_node = n.child_by_field_name("function")
                if not fn_node and n.children:
                    fn_node = n.children[0]
                    
                if fn_node:
                    is_require = (fn_node.type == "identifier" and fn_node.text == b"require")
                    is_dynamic_import = (fn_node.type == "import")
                    if is_require or is_dynamic_import:
                        args_node = None
                        if hasattr(n, 'child_by_field_name'):
                            args_node = n.child_by_field_name("arguments")
                        if not args_node:
                            for child in n.children:
                                if child.type == "arguments":
                                    args_node = child
                                    break
                        if args_node:
                            # We inspect arguments children to find string literals
                            for child in args_node.children:
                                if child.type == "string":
                                    for sub in child.children:
                                        if sub.type == "string_fragment":
                                            dep_type = "import" if is_dynamic_import else "require"
                                            specifiers.append((sub.text.decode("utf-8", errors="ignore"), dep_type))
            
            for child in n.children:
                walk(child)

        walk(tree.root_node)
        return specifiers

    @staticmethod
    def resolve_specifier(
        checkout_dir: str,
        source_file: str,
        specifier: str
    ) -> str:
        """
        Resolves a relative import/export specifier to a repository-relative path with heuristics.
        Returns:
            Repository-relative path of the target file (with forward slashes),
            or empty string if not resolvable or escapes checkout_dir.
        """
        # We only care about relative imports/exports
        if not (specifier.startswith("./") or specifier.startswith("../")):
            return ""

        checkout_abs = os.path.abspath(checkout_dir)
        source_abs_dir = os.path.dirname(os.path.abspath(os.path.join(checkout_abs, source_file)))
        target_abs_base = os.path.normpath(os.path.join(source_abs_dir, specifier))

        # Check path safety (cannot escape checkout_dir)
        if not target_abs_base.startswith(checkout_abs):
            return ""

        extensions = [".ts", ".tsx", ".js", ".jsx", ".d.ts"]

        # Heuristic 1: Exact match on disk (in case extension is already specified)
        if os.path.isfile(target_abs_base):
            rel_path = os.path.relpath(target_abs_base, checkout_abs)
            return rel_path.replace("\\", "/")

        # Heuristic 2: Fuzzy extensions
        for ext in extensions:
            candidate = target_abs_base + ext
            if os.path.isfile(candidate):
                rel_path = os.path.relpath(candidate, checkout_abs)
                return rel_path.replace("\\", "/")

        # Heuristic 3: Directory index mapping
        if os.path.isdir(target_abs_base):
            for ext in extensions:
                candidate = os.path.join(target_abs_base, "index" + ext)
                if os.path.isfile(candidate):
                    rel_path = os.path.relpath(candidate, checkout_abs)
                    return rel_path.replace("\\", "/")

        # Heuristic 4: Fallback to base target name relative to checkout directory if file does not exist physically on disk
        rel_path = os.path.relpath(target_abs_base, checkout_abs)
        return rel_path.replace("\\", "/")

    @classmethod
    def extract_and_persist_dependencies(
        cls,
        db: Session,
        repository_id: UUID,
        commit_sha: str,
        checkout_dir: str
    ) -> int:
        """
        Scans a repository workspace checkout, extracts relative JS/TS file-level dependencies,
        and idempotently commits them to the database.
        Returns:
            The number of dependency edges persisted.
        """
        if not os.path.isdir(checkout_dir):
            raise ValueError(f"Checkout directory {checkout_dir} does not exist.")

        checkout_abs = os.path.abspath(checkout_dir)
        edges_to_save: Set[Tuple[str, str, str]] = set() # (source_file, target_file, dependency_type)

        supported_extensions = (".js", ".jsx", ".ts", ".tsx", ".d.ts")

        # Walk repository files
        for root, dirs, files in os.walk(checkout_abs):
            # Ignore dependency and control directories
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist", "build", "coverage", ".venv", "venv")]

            for file in files:
                if not file.endswith(supported_extensions):
                    continue

                abs_filepath = os.path.join(root, file)
                source_file = os.path.relpath(abs_filepath, checkout_abs).replace("\\", "/")

                # Read source content
                try:
                    with open(abs_filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read file {abs_filepath}: {e}")
                    continue

                # Parse specifiers
                specifiers = cls.extract_specifiers_from_content(content, source_file)

                # Resolve specifiers
                for specifier, dep_type in specifiers:
                    resolved_target = cls.resolve_specifier(checkout_abs, source_file, specifier)
                    if resolved_target and resolved_target != source_file:
                        edges_to_save.add((source_file, resolved_target, dep_type))

        # Idempotent write: Delete old dependencies for the same commit
        db.query(FileDependency).filter(
            FileDependency.repository_id == repository_id,
            FileDependency.commit_sha == commit_sha
        ).delete()
        db.commit()

        # Insert new dependencies
        db_objs = []
        for src, tgt, dep_type in edges_to_save:
            db_objs.append(
                FileDependency(
                    repository_id=repository_id,
                    file_path=src,
                    depends_on_file_path=tgt,
                    dependency_type=dep_type,
                    commit_sha=commit_sha
                )
            )

        if db_objs:
            db.bulk_save_objects(db_objs)
            db.commit()

        return len(db_objs)

    @staticmethod
    def expand_impacted_files(
        db: Session,
        repository_id: UUID,
        commit_sha: str,
        changed_files: List[str]
    ) -> Dict[str, Any]:
        """
        Computes 1-level lightweight dependency expansion for changed files.
        Returns:
            Dict:
                - directly_dependent_files: List of files that import/depend on the changed files (incoming)
                - imported_neighbors: List of files that the changed files import/depend on (outgoing)
        """
        deps = db.query(FileDependency).filter(
            FileDependency.repository_id == repository_id,
            FileDependency.commit_sha == commit_sha
        ).all()

        incoming: Dict[str, List[str]] = {}
        outgoing: Dict[str, List[str]] = {}

        for dep in deps:
            src = dep.file_path
            tgt = dep.depends_on_file_path

            if tgt not in incoming:
                incoming[tgt] = []
            incoming[tgt].append(src)

            if src not in outgoing:
                outgoing[src] = []
            outgoing[src].append(tgt)

        directly_dependent = set()
        imported_neighbors = set()

        for f in changed_files:
            # Normalize changed file separator for lookup
            fn = f.replace("\\", "/")
            
            # Directly dependent files: files that import/depend on fn (incoming)
            if fn in incoming:
                for dep_file in incoming[fn]:
                    directly_dependent.add(dep_file)
            
            # Imported neighbors: files that fn imports/depends on (outgoing)
            if fn in outgoing:
                for neighbor_file in outgoing[fn]:
                    imported_neighbors.add(neighbor_file)

        return {
            "directly_dependent_files": sorted(list(directly_dependent)),
            "imported_neighbors": sorted(list(imported_neighbors))
        }
