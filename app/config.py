from typing import Optional
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    DATABASE_URL: str
    APP_ENV: str = "development"

    GITHUB_APP_ID: Optional[str] = None
    GITHUB_PRIVATE_KEY: Optional[str] = None
    GITHUB_APP_PRIVATE_KEY_PATH: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: Optional[str] = None
    STATE_SECRET_KEY: str = "veriscope-state-secret-key-change-in-prod"
    REDIS_URL: str = "redis://localhost:6379/0"
    GITHUB_WEBHOOK_MAX_AGE_SECONDS: int = 600
    PR_EVIDENCE_MAX_AGE_HOURS: int = 24

    # JUnit XML & Object Storage configurations
    ALLOW_LOCAL_OBJECT_STORAGE: bool = False
    MAX_JUNIT_XML_SIZE_MB: float = 25.0
    MAX_LCOV_SIZE_MB: float = 25.0
    S3_BUCKET_NAME: Optional[str] = "veriscope-junit-artifacts"
    S3_ENDPOINT_URL: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None

    # Architecture V2 Feature Flag
    USE_ARCHITECTURE_V2: bool = False

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

    @property
    def github_private_key(self) -> Optional[str]:
        """Get GitHub private key from either direct value or file path."""
        if self.GITHUB_PRIVATE_KEY:
            return self.GITHUB_PRIVATE_KEY
        if self.GITHUB_APP_PRIVATE_KEY_PATH and os.path.exists(self.GITHUB_APP_PRIVATE_KEY_PATH):
            with open(self.GITHUB_APP_PRIVATE_KEY_PATH, 'r') as f:
                return f.read()
        return None

settings = Settings()
