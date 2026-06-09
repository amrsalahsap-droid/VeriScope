from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.services.organization import OrganizationService

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(org_in: OrganizationCreate, db: Session = Depends(get_db)):
    """Create a new multi-tenant organization."""
    service = OrganizationService(db)
    return service.create_organization(org_in)

@router.get("/{id}", response_model=OrganizationResponse)
def get_organization(id: UUID, db: Session = Depends(get_db)):
    """Retrieve an active organization by ID."""
    service = OrganizationService(db)
    return service.get_organization(id)
