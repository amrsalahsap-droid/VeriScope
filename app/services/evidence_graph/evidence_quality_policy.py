import os
from typing import Tuple, Dict, Any

class EvidenceQualityPolicy:
    def __init__(
        self,
        policy_name: str = "default",
        policy_version: str = "v1",
        min_verified_ratio_for_ready: float = 0.85,
        max_not_mapped_ratio_for_ready: float = 0.20,
        max_not_mapped_count_for_ready: int = 5,
        max_missing_ratio_for_ready: float = 0.0,
        allow_ready_with_partial_coverage: bool = False,
        allow_ready_with_required_not_run: bool = False,
        allow_ready_with_coverage_unavailable: bool = True,
        minimum_parent_requirements_for_ratio_rules: int = 10,
        severity_bands: dict = None,
        # Partial classification policy flags
        enable_partial_classification: bool = True,
        partial_classification_min_coverage_threshold: float = 50.0,
        partial_classification_require_test_execution: bool = True,
        partial_classification_allow_coverage_only: bool = False,
    ):
        self.policy_name = policy_name
        self.policy_version = policy_version
        self.min_verified_ratio_for_ready = min_verified_ratio_for_ready
        self.max_not_mapped_ratio_for_ready = max_not_mapped_ratio_for_ready
        self.max_not_mapped_count_for_ready = max_not_mapped_count_for_ready
        self.max_missing_ratio_for_ready = max_missing_ratio_for_ready
        self.allow_ready_with_partial_coverage = allow_ready_with_partial_coverage
        self.allow_ready_with_required_not_run = allow_ready_with_required_not_run
        self.allow_ready_with_coverage_unavailable = allow_ready_with_coverage_unavailable
        self.minimum_parent_requirements_for_ratio_rules = minimum_parent_requirements_for_ratio_rules
        self.severity_bands = severity_bands or {"LOW": 0.1, "MEDIUM": 0.3, "HIGH": 0.5}
        # Partial classification policy flags
        self.enable_partial_classification = enable_partial_classification
        self.partial_classification_min_coverage_threshold = partial_classification_min_coverage_threshold
        self.partial_classification_require_test_execution = partial_classification_require_test_execution
        self.partial_classification_allow_coverage_only = partial_classification_allow_coverage_only

    @classmethod
    def load_policy(
        cls,
        recommendation_run_id: str = None,
        repository_id: str = None,
        workspace_id: str = None,
        db_session = None
    ) -> Tuple['EvidenceQualityPolicy', bool]:
        """Loads policy in priority order.
        
        Returns:
            Tuple of (policy, is_default_fallback_used)
        """
        # 1. RecommendationRun-specific policy
        if recommendation_run_id and db_session:
            from app.models.recommendation import RecommendationRun
            try:
                run = db_session.query(RecommendationRun).filter(RecommendationRun.id == recommendation_run_id).first()
                if run and run.readiness_dimensions and "quality_policy" in run.readiness_dimensions:
                    policy_dict = run.readiness_dimensions["quality_policy"]
                    return cls.from_dict(policy_dict), False
            except Exception:
                pass

        # 2. Project/repository policy
        if repository_id and db_session:
            from app.models.repository import Repository
            try:
                repo = db_session.query(Repository).filter(Repository.id == repository_id).first()
                if repo and repo.framework_hints and isinstance(repo.framework_hints, dict) and "quality_policy" in repo.framework_hints:
                    policy_dict = repo.framework_hints["quality_policy"]
                    return cls.from_dict(policy_dict), False
            except Exception:
                pass

        # 3. Organization/workspace policy
        # If we can query the workspace or repository's workspace
        if repository_id and db_session:
            from app.models.repository import Repository
            try:
                repo = db_session.query(Repository).filter(Repository.id == repository_id).first()
                if repo and repo.workspace and hasattr(repo.workspace, "slug") and repo.workspace.slug == "workspace-policy":
                    pass
            except Exception:
                pass

        # 4. Environment/default policy
        env_policy_name = os.getenv("VERISCOPE_QUALITY_POLICY_NAME")
        if env_policy_name:
            try:
                return cls(
                    policy_name=env_policy_name,
                    policy_version=os.getenv("VERISCOPE_QUALITY_POLICY_VERSION", "v1"),
                    min_verified_ratio_for_ready=float(os.getenv("VERISCOPE_POLICY_MIN_VERIFIED_RATIO", "0.85")),
                    max_not_mapped_ratio_for_ready=float(os.getenv("VERISCOPE_POLICY_MAX_NOT_MAPPED_RATIO", "0.20")),
                    max_not_mapped_count_for_ready=int(os.getenv("VERISCOPE_POLICY_MAX_NOT_MAPPED_COUNT", "5")),
                    max_missing_ratio_for_ready=float(os.getenv("VERISCOPE_POLICY_MAX_MISSING_RATIO", "0.0")),
                    allow_ready_with_partial_coverage=os.getenv("VERISCOPE_POLICY_ALLOW_PARTIAL", "false").lower() == "true",
                    allow_ready_with_required_not_run=os.getenv("VERISCOPE_POLICY_ALLOW_REQUIRED_NOT_RUN", "false").lower() == "true",
                    allow_ready_with_coverage_unavailable=os.getenv("VERISCOPE_POLICY_ALLOW_COVERAGE_UNAVAILABLE", "true").lower() == "true",
                    minimum_parent_requirements_for_ratio_rules=int(os.getenv("VERISCOPE_POLICY_MIN_PARENT_REQS", "10")),
                ), False
            except Exception:
                pass

        # 5. Built-in fallback policy
        return cls(
            policy_name="default",
            policy_version="v1",
            min_verified_ratio_for_ready=0.85,
            max_not_mapped_ratio_for_ready=0.20,
            max_not_mapped_count_for_ready=5,
            max_missing_ratio_for_ready=0.0,
            allow_ready_with_partial_coverage=False,
            allow_ready_with_required_not_run=False,
            allow_ready_with_coverage_unavailable=True,
            minimum_parent_requirements_for_ratio_rules=10
        ), True

    @classmethod
    def from_dict(cls, data: dict) -> 'EvidenceQualityPolicy':
        return cls(
            policy_name=data.get("policy_name", "custom"),
            policy_version=data.get("policy_version", "v1"),
            min_verified_ratio_for_ready=data.get("min_verified_ratio_for_ready", 0.85),
            max_not_mapped_ratio_for_ready=data.get("max_not_mapped_ratio_for_ready", 0.20),
            max_not_mapped_count_for_ready=data.get("max_not_mapped_count_for_ready", 5),
            max_missing_ratio_for_ready=data.get("max_missing_ratio_for_ready", 0.0),
            allow_ready_with_partial_coverage=data.get("allow_ready_with_partial_coverage", False),
            allow_ready_with_required_not_run=data.get("allow_ready_with_required_not_run", False),
            allow_ready_with_coverage_unavailable=data.get("allow_ready_with_coverage_unavailable", True),
            minimum_parent_requirements_for_ratio_rules=data.get("minimum_parent_requirements_for_ratio_rules", 10),
            severity_bands=data.get("severity_bands"),
            # Partial classification policy flags
            enable_partial_classification=data.get("enable_partial_classification", False),
            partial_classification_min_coverage_threshold=data.get("partial_classification_min_coverage_threshold", 50.0),
            partial_classification_require_test_execution=data.get("partial_classification_require_test_execution", True),
            partial_classification_allow_coverage_only=data.get("partial_classification_allow_coverage_only", False),
        )
