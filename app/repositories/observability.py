from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.observability import IngestionJob, SystemEvent

class ObservabilityRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_ingestion_job(self, job: IngestionJob) -> IngestionJob:
        """Create a new ingestion job entry."""
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_ingestion_job(self, job_id: UUID) -> Optional[IngestionJob]:
        """Fetch an ingestion job by ID."""
        return self.db.query(IngestionJob).filter(IngestionJob.id == job_id).first()

    def get_ingestion_jobs_by_repo(self, repository_id: UUID) -> List[IngestionJob]:
        """Fetch ingestion jobs associated with a repository."""
        return self.db.query(IngestionJob).filter(IngestionJob.repository_id == repository_id).all()

    def create_system_event(self, event: SystemEvent) -> SystemEvent:
        """Log a new system event."""
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_system_events_by_entity(self, entity_type: str, entity_id: str) -> List[SystemEvent]:
        """Retrieve system events filtered by entity type and ID."""
        return self.db.query(SystemEvent).filter(
            SystemEvent.entity_type == entity_type,
            SystemEvent.entity_id == entity_id
        ).all()
