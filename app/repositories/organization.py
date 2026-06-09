from typing import Optional
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.repositories.base import BaseRepository

class OrganizationRepository(BaseRepository[Organization]):
    def __init__(self, db: Session):
        super().__init__(Organization, db)

    def get_by_slug(self, slug: str) -> Optional[Organization]:
        """Fetch active organization by its slug (ignoring soft-deleted)."""
        return self.db.query(self.model).filter(
            self.model.slug == slug,
            self.model.deleted_at.is_(None)
        ).first()

    def get_active(self, id: UUID) -> Optional[Organization]:
        """Fetch active organization by ID."""
        return self.db.query(self.model).filter(
            self.model.id == id,
            self.model.deleted_at.is_(None)
        ).first()

    def soft_delete(self, id: UUID) -> Optional[Organization]:
        """Perform soft delete by setting deleted_at."""
        org = self.get_active(id)
        if org:
            org.deleted_at = datetime.utcnow()
            self.db.add(org)
            self.db.commit()
            self.db.refresh(org)
        return org
