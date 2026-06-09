from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.schemas.repository import RepositoryCreate
from app.repositories.repository import RepositoryRepository
from app.repositories.organization import OrganizationRepository

class RepositoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repo_repository = RepositoryRepository(db)
        self.org_repository = OrganizationRepository(db)

    def create_repository(self, repo_in: RepositoryCreate) -> Repository:
        """Create a repository ensuring org existence and github_repo_id uniqueness."""
        # Ensure organization exists and is active
        org = self.org_repository.get_active(repo_in.organization_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization with ID {repo_in.organization_id} not found."
            )

        # Enforce unique github_repo_id
        existing = self.repo_repository.get_by_github_repo_id(repo_in.github_repo_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Repository with GitHub repo ID {repo_in.github_repo_id} already registered."
            )

        db_repo = Repository(
            organization_id=repo_in.organization_id,
            github_repo_id=repo_in.github_repo_id,
            name=repo_in.name,
            full_name=repo_in.full_name,
            default_branch=repo_in.default_branch,
            is_active=repo_in.is_active
        )
        return self.repo_repository.create(db_repo)

    def get_repository(self, repo_id: UUID) -> Repository:
        """Retrieve repository or raise 404."""
        repo = self.repo_repository.get(repo_id)
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found."
            )
        return repo
