from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.dependency import FileDependency

class DependencyRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_dependency(self, dep: FileDependency) -> FileDependency:
        """Create a new file dependency mapping entry."""
        self.db.add(dep)
        self.db.commit()
        self.db.refresh(dep)
        return dep

    def get_dependencies_by_repo_and_sha(self, repository_id: UUID, commit_sha: str) -> List[FileDependency]:
        """Fetch all dependency mappings for a given repository and commit anchor."""
        return self.db.query(FileDependency).filter(
            FileDependency.repository_id == repository_id,
            FileDependency.commit_sha == commit_sha
        ).all()
