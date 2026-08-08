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

    AC_TEST_MAPPING_AI_ENABLED: bool = False
    AC_TEST_MAPPING_AI_PROVIDER: str = "disabled"
    AC_TEST_MAPPING_AI_MODEL: Optional[str] = None
    AC_TEST_MAPPING_AI_API_KEY: Optional[str] = None
    AC_TEST_MAPPING_AI_BASE_URL: Optional[str] = None
    AC_TEST_MAPPING_AI_TIMEOUT_SECONDS: int = 15
    AC_TEST_MAPPING_AI_MAX_CANDIDATES: int = 8
    AC_TEST_MAPPING_AI_CONFIDENCE_THRESHOLD_STRONG: float = 0.85
    AC_TEST_MAPPING_AI_CONFIDENCE_THRESHOLD_WEAK: float = 0.55
    AC_TEST_MAPPING_AI_CACHE_ENABLED: bool = True
    AC_TEST_MAPPING_AI_AUDIT_LOG_ENABLED: bool = True

    # AC → Test Mapping auto-trust policy
    AC_MAPPING_AUTO_TRUST_VERISCOPE_KEY: bool = True
    AC_MAPPING_AUTO_TRUST_EVIDENCE_ALIGNED: bool = True
    AC_MAPPING_AUTO_TRUST_MIN_CONFIDENCE: float = 0.85
    AC_MAPPING_REQUIRE_REVIEW_FOR_METADATA_CONFLICT: bool = True
    AC_MAPPING_REQUIRE_REVIEW_FOR_PARTIAL_SUPPORT: bool = True
    AC_MAPPING_REQUIRE_REVIEW_FOR_NO_CANDIDATE: bool = True

    # Architecture V2 Feature Flag
    USE_ARCHITECTURE_V2: bool = False

    # Business Context Feature Flag
    BUSINESS_CONTEXT_ENABLED: bool = True

    # CI/CD Pipeline Configuration
    CI_FAIL_ON_PARTIAL: bool = False  # Default: PARTIAL quality gate does not fail CI
    PIPELINE_TRIGGER_TIMEOUT_SECONDS: int = 30  # Timeout for pipeline trigger endpoint

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
