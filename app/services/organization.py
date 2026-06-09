from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate, OrganizationUpdate
from app.repositories.organization import OrganizationRepository

class OrganizationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OrganizationRepository(db)

    def create_organization(self, org_in: OrganizationCreate) -> Organization:
        """Create an organization and enforce slug uniqueness."""
        existing = self.repo.get_by_slug(org_in.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization with slug '{org_in.slug}' already exists."
            )
        
        db_org = Organization(
            name=org_in.name,
            slug=org_in.slug
        )
        return self.repo.create(db_org)

    def get_organization(self, org_id: UUID) -> Organization:
        """Retrieve organization or raise 404."""
        org = self.repo.get_active(org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found or has been deleted."
            )
        return org

    def update_organization(self, org_id: UUID, org_in: OrganizationUpdate) -> Organization:
        """Update an organization's fields."""
        org = self.get_organization(org_id)
        
        update_data = org_in.dict(exclude_unset=True)
        if "slug" in update_data and update_data["slug"] != org.slug:
            existing = self.repo.get_by_slug(update_data["slug"])
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Organization with slug '{update_data['slug']}' already exists."
                )

        return self.repo.update(org, update_data)

    def delete_organization(self, org_id: UUID) -> Organization:
        """Soft delete organization."""
        org = self.get_organization(org_id)
        return self.repo.soft_delete(org_id)
