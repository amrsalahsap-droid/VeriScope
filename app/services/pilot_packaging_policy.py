import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.pilot import (
    PilotWorkspaceProfile,
    PilotRepositoryEnrollment
)

logger = logging.getLogger("veriscope.pilot_packaging_policy")

class PilotPackagingPolicy:
    """
    PilotPackagingPolicy
    ====================
    Standardizes early paid pilot packaging configs and pricing policies.
    Guards repository enrollment boundaries, pricing schemas, and features
    without enterprise procurement complexity or seat/usage-based models.
    """

    PRICING_VERSION = "1.0.0"
    DEFAULT_MONTHLY_PRICE_USD = 1500.00
    DEFAULT_REPO_LIMIT = 3
    DEFAULT_PRICING_MODEL = "FIXED_MONTHLY"
    DEFAULT_PILOT_STATUS = "ACTIVE"

    @classmethod
    def get_default_packaging_config(cls) -> Dict[str, Any]:
        """
        Retrieve standard baseline early paid pilot packaging rules and feature toggles.
        """
        return {
            "pricing_version": cls.PRICING_VERSION,
            "monthly_price_usd": cls.DEFAULT_MONTHLY_PRICE_USD,
            "repo_limit": cls.DEFAULT_REPO_LIMIT,
            "pricing_model": cls.DEFAULT_PRICING_MODEL,
            "pilot_status": cls.DEFAULT_PILOT_STATUS,
            "features": {
                "non_blocking_advisory_mode": True,
                "pr_comment_integration": True,
                "fragility_memory": True,
                "pilot_reporting": True
            }
        }

    @classmethod
    def create_default_profile(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        pilot_name: str,
        *,
        repo_limit: Optional[int] = None,
        monthly_price_usd: Optional[float] = None,
        pricing_model: Optional[str] = None,
        notes: Optional[str] = None
    ) -> PilotWorkspaceProfile:
        """
        Instantiate a new organization pilot profile utilizing policy-defined defaults
        or custom overrides to support configuration updates later.
        """
        # Exclude enterprise procurement complexity (Rules 1-3)
        limit = repo_limit if repo_limit is not None else cls.DEFAULT_REPO_LIMIT
        price = monthly_price_usd if monthly_price_usd is not None else cls.DEFAULT_MONTHLY_PRICE_USD
        model = pricing_model if pricing_model is not None else cls.DEFAULT_PRICING_MODEL

        # Create structured profile
        profile = PilotWorkspaceProfile(
            id=uuid.uuid4(),
            workspace_id=organization_id,
            pilot_name=pilot_name,
            pilot_status=cls.DEFAULT_PILOT_STATUS,
            pilot_start_date=datetime.utcnow(),
            pricing_model=model,
            monthly_price_usd=price,
            repo_limit=limit,
            notes=notes or f"Pricing Version: {cls.PRICING_VERSION}"
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        logger.info(
            f"Successfully created pilot packaging profile '{pilot_name}' for organization {organization_id} "
            f"(Limit: {limit} repos, Price: ${price:.2f}/mo, Pricing Version: {cls.PRICING_VERSION})."
        )
        return profile

    @classmethod
    def can_enroll_repository(cls, db: Session, pilot_profile_id: uuid.UUID) -> bool:
        """
        Check if a new repository can be enrolled without violating the pilot's repo limit constraint,
        preserving repository enrollment lineage and pilot boundaries (Rule 4).
        """
        profile = db.query(PilotWorkspaceProfile).filter(
            PilotWorkspaceProfile.id == pilot_profile_id
        ).first()
        if not profile:
            return False

        # Count active enrollments
        active_enrollments = db.query(PilotRepositoryEnrollment).filter(
            PilotRepositoryEnrollment.pilot_profile_id == pilot_profile_id,
            PilotRepositoryEnrollment.enrollment_status == "ACTIVE"
        ).count()

        # If repo_limit is None (unlimited), always allow
        if profile.repo_limit is None:
            return True

        return active_enrollments < profile.repo_limit
