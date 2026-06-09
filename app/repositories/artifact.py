from sqlalchemy.orm import Session
from app.models.artifact import RawArtifact
from app.repositories.base import BaseRepository

class ArtifactRepository(BaseRepository[RawArtifact]):
    def __init__(self, db: Session):
        super().__init__(RawArtifact, db)
