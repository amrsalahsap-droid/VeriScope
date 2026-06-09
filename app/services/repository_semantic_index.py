from typing import List, Optional, Dict, Set
from pathlib import Path
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.repository_semantic_entry import RepositorySemanticEntry
from app.services.tokenizer import Tokenizer


class RepositorySemanticIndex:
    """Service to build and maintain semantic index for repositories."""
    
    # Directories to exclude from scanning
    EXCLUDED_DIRS: Set[str] = {
        "node_modules",
        ".next",
        "dist",
        "build",
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        "target",
        "bin",
        "obj",
        "out",
        "coverage",
        ".idea",
        ".vscode",
    }
    
    # File patterns to exclude
    EXCLUDED_PATTERNS: Set[str] = {
        "*.min.js",
        "*.min.css",
        "*.map",
        "*.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "*.log",
    }
    
    def __init__(self, db: Session, repository: Repository):
        """Initialize the semantic index with database session and repository."""
        self.db = db
        self.repository = repository
        # Handle missing workspace_path attribute gracefully
        workspace_path = getattr(repository, 'workspace_path', None) or ""
        self.repository_path = Path(workspace_path)
    
    def build_index(
        self,
        incremental: bool = True,
        force_rebuild: bool = False,
    ) -> Dict[str, int]:
        """Build semantic index for the repository."""
        stats = {
            "routes": 0,
            "pages": 0,
            "modules": 0,
            "services": 0,
            "tests": 0,
            "readme": 0,
            "docs": 0,
            "configs": 0,
            "total": 0,
        }
        
        if not self.repository_path.exists():
            return stats
        
        # Clear existing entries if force rebuild
        if force_rebuild:
            self.db.query(RepositorySemanticEntry).filter(
                RepositorySemanticEntry.repository_id == self.repository.id
            ).delete()
            self.db.commit()
        
        # Scan and index different entry types
        stats["routes"] = self._index_routes(incremental)
        stats["pages"] = self._index_pages(incremental)
        stats["modules"] = self._index_modules(incremental)
        stats["services"] = self._index_services(incremental)
        stats["tests"] = self._index_tests(incremental)
        stats["readme"] = self._index_readme(incremental)
        stats["docs"] = self._index_docs(incremental)
        stats["configs"] = self._index_configs(incremental)
        
        stats["total"] = sum(stats.values())
        
        self.db.commit()
        
        return stats
    
    def _should_exclude_path(self, path: Path) -> bool:
        """Check if a path should be excluded from scanning."""
        # Check if any parent directory is in excluded list
        for part in path.parts:
            if part.lower() in self.EXCLUDED_DIRS:
                return True
        
        # Check file patterns
        for pattern in self.EXCLUDED_PATTERNS:
            if path.match(pattern):
                return True
        
        return False
    
    def _index_routes(self, incremental: bool) -> int:
        """Index route files."""
        count = 0
        
        # Scan for route files (Next.js app router, Express, etc.)
        for route_file in self.repository_path.rglob("*route*"):
            if not route_file.is_file() or self._should_exclude_path(route_file):
                continue
            
            path_str = str(route_file.relative_to(self.repository_path))
            
            # Check if already exists (incremental)
            if incremental:
                existing = self.db.query(RepositorySemanticEntry).filter(
                    RepositorySemanticEntry.repository_id == self.repository.id,
                    RepositorySemanticEntry.entry_type == "ROUTE",
                    RepositorySemanticEntry.path == path_str,
                ).first()
                if existing:
                    continue
            
            # Tokenize
            tokens = Tokenizer.tokenize(path_str)
            
            # Create entry
            entry = RepositorySemanticEntry(
                id=uuid.uuid4(),
                repository_id=self.repository.id,
                entry_type="ROUTE",
                path=path_str,
                normalized_tokens=tokens,
                confidence="HIGH",
                entry_metadata={"file_size": route_file.stat().st_size},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
            self.db.add(entry)
            count += 1
        
        return count
    
    def _index_pages(self, incremental: bool) -> int:
        """Index page files."""
        count = 0
        
        # Scan for page files (Next.js, React, etc.)
        for page_file in self.repository_path.rglob("*page*"):
            if not page_file.is_file() or self._should_exclude_path(page_file):
                continue
            
            path_str = str(page_file.relative_to(self.repository_path))
            
            # Check if already exists (incremental)
            if incremental:
                existing = self.db.query(RepositorySemanticEntry).filter(
                    RepositorySemanticEntry.repository_id == self.repository.id,
                    RepositorySemanticEntry.entry_type == "PAGE",
                    RepositorySemanticEntry.path == path_str,
                ).first()
                if existing:
                    continue
            
            # Tokenize
            tokens = Tokenizer.tokenize(path_str)
            
            # Create entry
            entry = RepositorySemanticEntry(
                id=uuid.uuid4(),
                repository_id=self.repository.id,
                entry_type="PAGE",
                path=path_str,
                normalized_tokens=tokens,
                confidence="HIGH",
                entry_metadata={"file_size": page_file.stat().st_size},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
            self.db.add(entry)
            count += 1
        
        return count
    
    def _index_modules(self, incremental: bool) -> int:
        """Index module files (Python, JavaScript, TypeScript, etc.)."""
        count = 0
        
        # Scan for module files
        extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".php"}
        
        for ext in extensions:
            for module_file in self.repository_path.rglob(f"*{ext}"):
                if not module_file.is_file() or self._should_exclude_path(module_file):
                    continue
                
                path_str = str(module_file.relative_to(self.repository_path))
                
                # Check if already exists (incremental)
                if incremental:
                    existing = self.db.query(RepositorySemanticEntry).filter(
                        RepositorySemanticEntry.repository_id == self.repository.id,
                        RepositorySemanticEntry.entry_type == "MODULE",
                        RepositorySemanticEntry.path == path_str,
                    ).first()
                    if existing:
                        continue
                
                # Tokenize
                tokens = Tokenizer.tokenize(path_str)
                
                # Create entry
                entry = RepositorySemanticEntry(
                    id=uuid.uuid4(),
                    repository_id=self.repository.id,
                    entry_type="MODULE",
                    path=path_str,
                    normalized_tokens=tokens,
                    confidence="MODERATE",
                    entry_metadata={"file_size": module_file.stat().st_size, "extension": ext},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                
                self.db.add(entry)
                count += 1
        
        return count
    
    def _index_services(self, incremental: bool) -> int:
        """Index service files."""
        count = 0
        
        # Scan for service files
        for service_file in self.repository_path.rglob("*service*"):
            if not service_file.is_file() or self._should_exclude_path(service_file):
                continue
            
            path_str = str(service_file.relative_to(self.repository_path))
            
            # Check if already exists (incremental)
            if incremental:
                existing = self.db.query(RepositorySemanticEntry).filter(
                    RepositorySemanticEntry.repository_id == self.repository.id,
                    RepositorySemanticEntry.entry_type == "SERVICE",
                    RepositorySemanticEntry.path == path_str,
                ).first()
                if existing:
                    continue
            
            # Tokenize
            tokens = Tokenizer.tokenize(path_str)
            
            # Create entry
            entry = RepositorySemanticEntry(
                id=uuid.uuid4(),
                repository_id=self.repository.id,
                entry_type="SERVICE",
                path=path_str,
                normalized_tokens=tokens,
                confidence="HIGH",
                entry_metadata={"file_size": service_file.stat().st_size},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
            self.db.add(entry)
            count += 1
        
        return count
    
    def _index_tests(self, incremental: bool) -> int:
        """Index test files."""
        count = 0
        
        # Scan for test files
        for test_file in self.repository_path.rglob("*test*"):
            if not test_file.is_file() or self._should_exclude_path(test_file):
                continue
            
            path_str = str(test_file.relative_to(self.repository_path))
            
            # Check if already exists (incremental)
            if incremental:
                existing = self.db.query(RepositorySemanticEntry).filter(
                    RepositorySemanticEntry.repository_id == self.repository.id,
                    RepositorySemanticEntry.entry_type == "TEST",
                    RepositorySemanticEntry.path == path_str,
                ).first()
                if existing:
                    continue
            
            # Tokenize
            tokens = Tokenizer.tokenize(path_str)
            
            # Create entry
            entry = RepositorySemanticEntry(
                id=uuid.uuid4(),
                repository_id=self.repository.id,
                entry_type="TEST",
                path=path_str,
                normalized_tokens=tokens,
                confidence="HIGH",
                entry_metadata={"file_size": test_file.stat().st_size},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
            self.db.add(entry)
            count += 1
        
        return count
    
    def _index_readme(self, incremental: bool) -> int:
        """Index README files."""
        count = 0
        
        # Scan for README files
        for readme_file in self.repository_path.rglob("README*"):
            if not readme_file.is_file() or self._should_exclude_path(readme_file):
                continue
            
            path_str = str(readme_file.relative_to(self.repository_path))
            
            # Check if already exists (incremental)
            if incremental:
                existing = self.db.query(RepositorySemanticEntry).filter(
                    RepositorySemanticEntry.repository_id == self.repository.id,
                    RepositorySemanticEntry.entry_type == "README",
                    RepositorySemanticEntry.path == path_str,
                ).first()
                if existing:
                    continue
            
            # Tokenize
            tokens = Tokenizer.tokenize(path_str)
            
            # Create entry
            entry = RepositorySemanticEntry(
                id=uuid.uuid4(),
                repository_id=self.repository.id,
                entry_type="README",
                path=path_str,
                normalized_tokens=tokens,
                confidence="HIGH",
                entry_metadata={"file_size": readme_file.stat().st_size},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
            self.db.add(entry)
            count += 1
        
        return count
    
    def _index_docs(self, incremental: bool) -> int:
        """Index documentation files."""
        count = 0
        
        # Scan for doc files
        doc_extensions = {".md", ".rst", ".txt"}
        
        for ext in doc_extensions:
            for doc_file in self.repository_path.rglob(f"*{ext}"):
                if not doc_file.is_file() or self._should_exclude_path(doc_file):
                    continue
                
                # Skip README files (already indexed)
                if doc_file.name.upper().startswith("README"):
                    continue
                
                path_str = str(doc_file.relative_to(self.repository_path))
                
                # Check if already exists (incremental)
                if incremental:
                    existing = self.db.query(RepositorySemanticEntry).filter(
                        RepositorySemanticEntry.repository_id == self.repository.id,
                        RepositorySemanticEntry.entry_type == "DOC",
                        RepositorySemanticEntry.path == path_str,
                    ).first()
                    if existing:
                        continue
                
                # Tokenize
                tokens = Tokenizer.tokenize(path_str)
                
                # Create entry
                entry = RepositorySemanticEntry(
                    id=uuid.uuid4(),
                    repository_id=self.repository.id,
                    entry_type="DOC",
                    path=path_str,
                    normalized_tokens=tokens,
                    confidence="MODERATE",
                    entry_metadata={"file_size": doc_file.stat().st_size, "extension": ext},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                
                self.db.add(entry)
                count += 1
        
        return count
    
    def _index_configs(self, incremental: bool) -> int:
        """Index configuration files."""
        count = 0
        
        # Scan for config files
        config_patterns = [
            "*.json",
            "*.yaml",
            "*.yml",
            "*.toml",
            "*.ini",
            "*.cfg",
            "*.env*",
            "config.*",
        ]
        
        for pattern in config_patterns:
            for config_file in self.repository_path.rglob(pattern):
                if not config_file.is_file() or self._should_exclude_path(config_file):
                    continue
                
                # Skip package-lock files
                if "lock" in config_file.name.lower():
                    continue
                
                path_str = str(config_file.relative_to(self.repository_path))
                
                # Check if already exists (incremental)
                if incremental:
                    existing = self.db.query(RepositorySemanticEntry).filter(
                        RepositorySemanticEntry.repository_id == self.repository.id,
                        RepositorySemanticEntry.entry_type == "CONFIG",
                        RepositorySemanticEntry.path == path_str,
                    ).first()
                    if existing:
                        continue
                
                # Tokenize
                tokens = Tokenizer.tokenize(path_str)
                
                # Create entry
                entry = RepositorySemanticEntry(
                    id=uuid.uuid4(),
                    repository_id=self.repository.id,
                    entry_type="CONFIG",
                    path=path_str,
                    normalized_tokens=tokens,
                    confidence="MODERATE",
                    entry_metadata={"file_size": config_file.stat().st_size},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                
                self.db.add(entry)
                count += 1
        
        return count
    
    def search_by_tokens(self, tokens: List[str], entry_types: Optional[List[str]] = None) -> List[RepositorySemanticEntry]:
        """Search semantic index by tokens."""
        query = self.db.query(RepositorySemanticEntry).filter(
            RepositorySemanticEntry.repository_id == self.repository.id
        )
        
        if entry_types:
            query = query.filter(RepositorySemanticEntry.entry_type.in_(entry_types))
        
        # Filter by token overlap (simple containment check)
        results = []
        for entry in query.all():
            entry_tokens = set(entry.normalized_tokens)
            query_tokens = set(tokens)
            if entry_tokens & query_tokens:  # Intersection
                results.append(entry)
        
        return results
    
    def get_entry_count_by_type(self) -> Dict[str, int]:
        """Get count of entries by type."""
        counts = {}
        
        for entry_type in ["ROUTE", "PAGE", "MODULE", "SERVICE", "TEST", "README", "DOC", "CONFIG"]:
            count = self.db.query(RepositorySemanticEntry).filter(
                RepositorySemanticEntry.repository_id == self.repository.id,
                RepositorySemanticEntry.entry_type == entry_type,
            ).count()
            counts[entry_type] = count
        
        return counts
