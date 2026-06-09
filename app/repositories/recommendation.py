from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationOutcome,
    RecommendationReasoningEntry,
)

class RecommendationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(self, run: RecommendationRun) -> RecommendationRun:
        """Persist a new immutable RecommendationRun."""
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def create_test(self, test: RecommendationTest) -> RecommendationTest:
        """Persist a recommended test case."""
        self.db.add(test)
        self.db.commit()
        self.db.refresh(test)
        return test

    def create_reasoning_entry(self, entry: RecommendationReasoningEntry) -> RecommendationReasoningEntry:
        """Persist a reasoning explainability entry."""
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def create_outcome(self, outcome: RecommendationOutcome) -> RecommendationOutcome:
        """Persist or update a recommendation outcome/developer feedback."""
        self.db.add(outcome)
        self.db.commit()
        self.db.refresh(outcome)
        return outcome

    def get_run(self, run_id: UUID) -> Optional[RecommendationRun]:
        """Fetch a recommendation run by ID."""
        return self.db.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()

    def get_outcome_by_run_id(self, run_id: UUID) -> Optional[RecommendationOutcome]:
        """Fetch outcome associated with a recommendation run."""
        return self.db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == run_id
        ).first()

    def get_reasoning_entries(self, run_id: UUID) -> List[RecommendationReasoningEntry]:
        """Fetch reasoning entries for a run, sorted by CRITICAL > IMPORTANT > SUPPORTING."""
        entries = self.db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run_id
        ).all()
        
        # Explainability Hierarchy sorting
        priority_map = {"CRITICAL": 0, "IMPORTANT": 1, "SUPPORTING": 2}
        return sorted(entries, key=lambda x: priority_map.get(x.evidence_priority, 3))
