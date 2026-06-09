import os
import uuid
import hashlib
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.models.artifact import RawArtifact
from app.models.observability import SystemEvent

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None
    BotoCoreError = Exception
    ClientError = Exception

class ObjectStorageService:
    def __init__(self, db: Session):
        self.db = db

    def upload_artifact(
        self,
        file_bytes: bytes,
        filename: str,
        repository_id: uuid.UUID,
        correlation_id: Optional[str] = None
    ) -> RawArtifact:
        """
        Uploads an artifact (JUnit XML, etc.) to S3 or a local filesystem fallback.
        Enforces a production guard that fails hard if S3 is misconfigured and APP_ENV is production.
        """
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        size_bytes = len(file_bytes)
        
        # Check if S3 credentials and bucket name are fully configured
        s3_configured = all([
            settings.S3_BUCKET_NAME,
            settings.S3_ACCESS_KEY,
            settings.S3_SECRET_KEY
        ])
        
        storage_backend = "s3"
        storage_path = ""
        
        if s3_configured and boto3 is not None:
            # S3 Ingestion path
            try:
                s3_client = boto3.client(
                    "s3",
                    endpoint_url=settings.S3_ENDPOINT_URL,
                    aws_access_key_id=settings.S3_ACCESS_KEY,
                    aws_secret_access_key=settings.S3_SECRET_KEY
                )
                object_key = f"junit_xmls/{repository_id}/{filename}"
                s3_client.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=object_key,
                    Body=file_bytes,
                    ContentType="application/xml"
                )
                storage_path = f"s3://{settings.S3_BUCKET_NAME}/{object_key}"
            except (BotoCoreError, ClientError) as e:
                # If S3 fails, check environment before falling back
                if settings.APP_ENV == "production" and not settings.ALLOW_LOCAL_OBJECT_STORAGE:
                    # In production, we fail hard and reject silent disk writes
                    self._emit_local_rejected_event(repository_id, size_bytes, correlation_id)
                    raise RuntimeError(f"S3 upload failed in production environment: {str(e)}")
                else:
                    # Fallback to local
                    storage_backend = "local"
        else:
            # S3 is not configured
            if settings.APP_ENV == "production" and not settings.ALLOW_LOCAL_OBJECT_STORAGE:
                # S3 is missing in production, fail hard!
                self._emit_local_rejected_event(repository_id, size_bytes, correlation_id)
                raise RuntimeError("Object storage S3 credentials are not configured in production environment.")
            else:
                storage_backend = "local"
                
        if storage_backend == "local":
            # Local disk path falling back under workspace storage folder
            storage_dir = os.path.join("storage", "junit_xmls", str(repository_id))
            os.makedirs(storage_dir, exist_ok=True)
            local_path = os.path.join(storage_dir, filename)
            with open(local_path, "wb") as f:
                f.write(file_bytes)
            storage_path = os.path.abspath(local_path)

        # Build RawArtifact record
        artifact_metadata = {
            "file_hash": file_hash,
            "artifact_size_bytes": size_bytes,
            "content_type": "application/xml",
            "storage_backend": storage_backend,
            "parser_context": {"correlation_id": correlation_id} if correlation_id else {}
        }
        
        artifact = RawArtifact(
            id=uuid.uuid4(),
            artifact_type="junit_xml",
            repository_id=repository_id,
            storage_path=storage_path,
            artifact_metadata=artifact_metadata,
            created_at=datetime.utcnow()
        )
        self.db.add(artifact)
        self.db.flush() # Keep it in transaction
        return artifact

    def upload_coverage_report(
        self,
        file_bytes: bytes,
        filename: str,
        repository_id: uuid.UUID,
        correlation_id: Optional[str] = None
    ) -> RawArtifact:
        """
        Uploads an LCOV coverage report artifact to S3 or a local filesystem fallback.
        Enforces a production guard that fails hard if S3 is misconfigured and APP_ENV is production.
        """
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        size_bytes = len(file_bytes)
        
        # Check if S3 credentials and bucket name are fully configured
        s3_configured = all([
            settings.S3_BUCKET_NAME,
            settings.S3_ACCESS_KEY,
            settings.S3_SECRET_KEY
        ])
        
        storage_backend = "s3"
        storage_path = ""
        
        if s3_configured and boto3 is not None:
            # S3 Ingestion path
            try:
                s3_client = boto3.client(
                    "s3",
                    endpoint_url=settings.S3_ENDPOINT_URL,
                    aws_access_key_id=settings.S3_ACCESS_KEY,
                    aws_secret_access_key=settings.S3_SECRET_KEY
                )
                object_key = f"coverage_reports/{repository_id}/{filename}"
                s3_client.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=object_key,
                    Body=file_bytes,
                    ContentType="text/plain"
                )
                storage_path = f"s3://{settings.S3_BUCKET_NAME}/{object_key}"
            except (BotoCoreError, ClientError) as e:
                # If S3 fails, check environment before falling back
                if settings.APP_ENV == "production" and not settings.ALLOW_LOCAL_OBJECT_STORAGE:
                    # In production, we fail hard and reject silent disk writes
                    self._emit_local_rejected_event(repository_id, size_bytes, correlation_id)
                    raise RuntimeError(f"S3 upload failed in production environment: {str(e)}")
                else:
                    # Fallback to local
                    storage_backend = "local"
        else:
            # S3 is not configured
            if settings.APP_ENV == "production" and not settings.ALLOW_LOCAL_OBJECT_STORAGE:
                # S3 is missing in production, fail hard!
                self._emit_local_rejected_event(repository_id, size_bytes, correlation_id)
                raise RuntimeError("Object storage S3 credentials are not configured in production environment.")
            else:
                storage_backend = "local"
                
        if storage_backend == "local":
            # Local disk path falling back under workspace storage folder
            storage_dir = os.path.join("storage", "coverage_reports", str(repository_id))
            os.makedirs(storage_dir, exist_ok=True)
            local_path = os.path.join(storage_dir, filename)
            with open(local_path, "wb") as f:
                f.write(file_bytes)
            storage_path = os.path.abspath(local_path)

        # Build RawArtifact record
        artifact_metadata = {
            "file_hash": file_hash,
            "artifact_size_bytes": size_bytes,
            "content_type": "text/plain",
            "storage_backend": storage_backend,
            "parser_context": {"correlation_id": correlation_id} if correlation_id else {}
        }
        
        artifact = RawArtifact(
            id=uuid.uuid4(),
            artifact_type="coverage_report",
            repository_id=repository_id,
            storage_path=storage_path,
            artifact_metadata=artifact_metadata,
            created_at=datetime.utcnow()
        )
        self.db.add(artifact)
        self.db.flush() # Keep it in transaction
        return artifact

    def _emit_local_rejected_event(
        self,
        repository_id: uuid.UUID,
        size_bytes: int,
        correlation_id: Optional[str] = None
    ):
        """Emits a junit_local_storage_rejected_in_production SystemEvent in a dedicated session."""
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            event = SystemEvent(
                id=uuid.uuid4(),
                entity_type="repository",
                entity_id=str(repository_id),
                event_type="junit_local_storage_rejected_in_production",
                payload={
                    "message": "Local disk storage rejected in production mode.",
                    "size_bytes": size_bytes,
                    "correlation_id": correlation_id
                },
                created_at=datetime.utcnow()
            )
            db.add(event)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
