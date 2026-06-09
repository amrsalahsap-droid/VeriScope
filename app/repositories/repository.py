from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.repositories.base import BaseRepository

class RepositoryRepository(BaseRepository[Repository]):
    def __init__(self, db: Session):
        super().__init__(Repository, db)

    def get_by_github_repo_id(self, github_repo_id: int) -> Optional[Repository]:
        """Fetch repository by its unique GitHub repository ID."""
        return self.db.query(self.model).filter(
            self.model.github_repo_id == github_repo_id
        ).first()

    def get_by_organization(self, organization_id: UUID) -> List[Repository]:
        """Fetch all repositories registered under a given organization."""
        return self.db.query(self.model).filter(
            self.model.organization_id == organization_id
        ).all()
