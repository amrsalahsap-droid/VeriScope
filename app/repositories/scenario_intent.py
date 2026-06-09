"""
ScenarioIntent Repository
=========================
Database operations for ScenarioIntent model.
"""

import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import ScenarioIntent, RecommendationRun


class ScenarioIntentRepository:
    """Repository for ScenarioIntent database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_intent(
        self,
        recommendation_run_id: uuid.UUID,
        domain: str,
        feature: str,
        behavior: str,
        layer: str,
        case_type: str,
        canonical_key: str,
        title: str,
        priority: str,
        risk_category: str,
        related_changed_files: List[str]
    ) -> ScenarioIntent:
        """
        Create a new ScenarioIntent.
        
        Args:
            recommendation_run_id: The recommendation run ID
            domain: The domain (e.g., "authentication", "billing")
            feature: The feature (e.g., "reset-password", "signup")
            behavior: The behavior (e.g., "expired-token-rejected", "weak-password-rejected")
            layer: The layer (e.g., "api", "ui", "integration")
            case_type: The case type (e.g., "positive", "negative", "edge")
            canonical_key: The deterministic canonical key
            title: The human-readable title
            priority: The priority (MUST, SHOULD, OPTIONAL)
            risk_category: The risk category (Security, Functional, Regression)
            related_changed_files: List of related changed files
        
        Returns:
            The created ScenarioIntent
        """
        intent = ScenarioIntent(
            recommendation_run_id=recommendation_run_id,
            domain=domain,
            feature=feature,
            behavior=behavior,
            layer=layer,
            case_type=case_type,
            canonical_key=canonical_key,
            title=title,
            priority=priority,
            risk_category=risk_category,
            related_changed_files=related_changed_files
        )
        self.db.add(intent)
        try:
            self.db.commit()
            self.db.refresh(intent)
            return intent
        except Exception:
            self.db.rollback()
            # If duplicate key error, return the existing intent
            existing = self.db.query(ScenarioIntent).filter(
                ScenarioIntent.canonical_key == canonical_key
            ).first()
            if existing:
                return existing
            raise

    def get_intent_by_id(self, intent_id: uuid.UUID) -> Optional[ScenarioIntent]:
        """Get a ScenarioIntent by ID."""
        return self.db.query(ScenarioIntent).filter(ScenarioIntent.id == intent_id).first()

    def get_intent_by_canonical_key(self, canonical_key: str) -> Optional[ScenarioIntent]:
        """Get a ScenarioIntent by canonical key."""
        return self.db.query(ScenarioIntent).filter(ScenarioIntent.canonical_key == canonical_key).first()

    def get_intents_by_run(self, recommendation_run_id: uuid.UUID) -> List[ScenarioIntent]:
        """Get all ScenarioIntents for a recommendation run."""
        return self.db.query(ScenarioIntent).filter(
            ScenarioIntent.recommendation_run_id == recommendation_run_id
        ).all()

    def check_intent_exists_in_run(
        self,
        recommendation_run_id: uuid.UUID,
        canonical_key: str
    ) -> bool:
        """
        Check if a ScenarioIntent with the given canonical key already exists in the run.
        
        Args:
            recommendation_run_id: The recommendation run ID
            canonical_key: The canonical key to check
        
        Returns:
            True if the intent exists, False otherwise
        """
        existing = self.db.query(ScenarioIntent).filter(
            ScenarioIntent.recommendation_run_id == recommendation_run_id,
            ScenarioIntent.canonical_key == canonical_key
        ).first()
        return existing is not None

    def get_intents_by_domain(self, domain: str) -> List[ScenarioIntent]:
        """Get all ScenarioIntents for a domain."""
        return self.db.query(ScenarioIntent).filter(ScenarioIntent.domain == domain).all()

    def get_intents_by_feature(self, feature: str) -> List[ScenarioIntent]:
        """Get all ScenarioIntents for a feature."""
        return self.db.query(ScenarioIntent).filter(ScenarioIntent.feature == feature).all()

    def get_intents_by_priority(self, priority: str) -> List[ScenarioIntent]:
        """Get all ScenarioIntents for a priority."""
        return self.db.query(ScenarioIntent).filter(ScenarioIntent.priority == priority).all()

    def delete_intent(self, intent_id: uuid.UUID) -> bool:
        """
        Delete a ScenarioIntent by ID.
        
        Args:
            intent_id: The intent ID to delete
        
        Returns:
            True if deleted, False if not found
        """
        intent = self.get_intent_by_id(intent_id)
        if intent:
            self.db.delete(intent)
            self.db.commit()
            return True
        return False

    def get_or_create_intent(
        self,
        recommendation_run_id: uuid.UUID,
        domain: str,
        feature: str,
        behavior: str,
        layer: str,
        case_type: str,
        canonical_key: str,
        title: str,
        priority: str,
        risk_category: str,
        related_changed_files: List[str]
    ) -> ScenarioIntent:
        """
        Get an existing intent by canonical key or create a new one.
        
        This is useful for idempotent intent creation - if the intent already exists
        in the run, return it; otherwise, create it.
        
        Args:
            recommendation_run_id: The recommendation run ID
            domain: The domain
            feature: The feature
            behavior: The behavior
            layer: The layer
            case_type: The case type
            canonical_key: The canonical key
            title: The title
            priority: The priority
            risk_category: The risk category
            related_changed_files: List of related changed files
        
        Returns:
            The existing or newly created ScenarioIntent
        """
        existing = self.db.query(ScenarioIntent).filter(
            ScenarioIntent.canonical_key == canonical_key
        ).first()
        
        if existing:
            return existing
        
        return self.create_intent(
            recommendation_run_id=recommendation_run_id,
            domain=domain,
            feature=feature,
            behavior=behavior,
            layer=layer,
            case_type=case_type,
            canonical_key=canonical_key,
            title=title,
            priority=priority,
            risk_category=risk_category,
            related_changed_files=related_changed_files
        )
