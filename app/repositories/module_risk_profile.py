import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.module_risk_profile import ModuleRiskProfile
from app.repositories.base import BaseRepository
from app.services.module_risk_scoring_engine import ModuleRiskScoringEngine


class ModuleRiskProfileRepository(BaseRepository[ModuleRiskProfile]):
    """
    Data-access layer for ModuleRiskProfile.

    Extends BaseRepository with module-specific queries and the upsert pattern
    used when ingesting new evidence events.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(ModuleRiskProfile, db)

    # ------------------------------------------------------------------ #
    # Lookups                                                              #
    # ------------------------------------------------------------------ #

    def get_by_module(
        self,
        repository_id: uuid.UUID,
        module_path: str,
    ) -> Optional[ModuleRiskProfile]:
        """Return the profile for a specific module, or None if not yet tracked."""
        normalised = module_path.strip().replace("\\", "/")
        return (
            self.db.query(ModuleRiskProfile)
            .filter(
                ModuleRiskProfile.repository_id == repository_id,
                ModuleRiskProfile.module_path   == normalised,
            )
            .first()
        )

    def get_all_for_repo(
        self,
        repository_id: uuid.UUID,
        *,
        order_by_risk: bool = True,
        limit: int = 500,
    ) -> List[ModuleRiskProfile]:
        """
        Return all profiles for a repository.

        Parameters
        ----------
        order_by_risk : bool
            When True (default), results are ordered by risk_score descending
            so the caller gets the most fragile modules first.
        limit : int
            Hard cap to prevent accidental full-table scans on large repos.
        """
        q = self.db.query(ModuleRiskProfile).filter(
            ModuleRiskProfile.repository_id == repository_id
        )
        if order_by_risk:
            q = q.order_by(desc(ModuleRiskProfile.risk_score))
        return q.limit(limit).all()

    def get_top_risk_modules(
        self,
        repository_id: uuid.UUID,
        top_n: int = 20,
    ) -> List[ModuleRiskProfile]:
        """
        Return the top-N riskiest modules for a repository, ordered by
        risk_score descending.  Used by the recommendation ranking service.
        """
        return (
            self.db.query(ModuleRiskProfile)
            .filter(ModuleRiskProfile.repository_id == repository_id)
            .order_by(desc(ModuleRiskProfile.risk_score))
            .limit(top_n)
            .all()
        )

    # ------------------------------------------------------------------ #
    # Upsert — the primary write path for evidence ingestion              #
    # ------------------------------------------------------------------ #

    def get_or_create(
        self,
        repository_id: uuid.UUID,
        module_path: str,
    ) -> ModuleRiskProfile:
        """
        Return the existing profile for a module, or create a zeroed one.

        The caller is responsible for committing after applying any counter
        increments.
        """
        profile = self.get_by_module(repository_id, module_path)
        if profile is None:
            profile = ModuleRiskProfile(
                repository_id=repository_id,
                module_path=module_path,
            )
            self.db.add(profile)
            self.db.flush()  # Obtain PK without committing the outer transaction
        return profile

    # ------------------------------------------------------------------ #
    # Counter increment helpers                                            #
    # ------------------------------------------------------------------ #

    def record_change(
        self,
        repository_id: uuid.UUID,
        module_path: str,
    ) -> ModuleRiskProfile:
        """Increment change_frequency for a module and rescore."""
        profile = self.get_or_create(repository_id, module_path)
        profile.change_frequency += 1
        ModuleRiskScoringEngine.rescore_and_update(profile)
        self.db.add(profile)
        return profile

    def record_failure(
        self,
        repository_id: uuid.UUID,
        module_path: str,
    ) -> ModuleRiskProfile:
        """Increment failure_frequency for a module and rescore."""
        profile = self.get_or_create(repository_id, module_path)
        profile.failure_frequency += 1
        ModuleRiskScoringEngine.rescore_and_update(profile)
        self.db.add(profile)
        return profile

    def record_escaped_defect(
        self,
        repository_id: uuid.UUID,
        module_path: str,
    ) -> ModuleRiskProfile:
        """Increment escaped_defects for a module and rescore."""
        profile = self.get_or_create(repository_id, module_path)
        profile.escaped_defects += 1
        ModuleRiskScoringEngine.rescore_and_update(profile)
        self.db.add(profile)
        return profile

    def record_rollback(
        self,
        repository_id: uuid.UUID,
        module_path: str,
    ) -> ModuleRiskProfile:
        """Increment rollback_count for a module and rescore."""
        profile = self.get_or_create(repository_id, module_path)
        profile.rollback_count += 1
        ModuleRiskScoringEngine.rescore_and_update(profile)
        self.db.add(profile)
        return profile

    def record_recommendation_outcome(
        self,
        repository_id: uuid.UUID,
        module_path: str,
        *,
        was_accepted: bool,
    ) -> ModuleRiskProfile:
        """
        Increment recommendation tracking counters and rescore.

        Parameters
        ----------
        was_accepted : bool
            True if the engineer followed the recommendation for this module;
            False if it was ignored / overridden.
        """
        profile = self.get_or_create(repository_id, module_path)
        profile.recommendations_presented += 1
        if was_accepted:
            profile.recommendations_accepted += 1
        ModuleRiskScoringEngine.rescore_and_update(profile)
        self.db.add(profile)
        return profile

    def rescore_all_for_repo(
        self,
        repository_id: uuid.UUID,
    ) -> int:
        """
        Rescore every profile for a repository in a single pass.

        Returns the number of profiles rescored.  The caller is responsible for
        committing.
        """
        profiles = self.get_all_for_repo(repository_id, order_by_risk=False, limit=10_000)
        for profile in profiles:
            ModuleRiskScoringEngine.rescore_and_update(profile)
            self.db.add(profile)
        return len(profiles)
