from app.services.organization import OrganizationService
from app.services.repository import RepositoryService
from app.services.degradation import DegradationEngine
from app.services.recommendation import RecommendationService
from app.services.flaky_test_service import FlakyTestService
from app.services.recommendation_evidence_collector import RecommendationEvidenceCollector
from app.services.coverage_evidence_resolver import CoverageEvidenceResolver
from app.services.path_heuristic_resolver import PathHeuristicResolver
from app.services.dependency_expansion_resolver import DependencyExpansionResolver
from app.services.historical_failure_resolver import HistoricalFailureResolver
from app.services.flaky_adjustment_service import FlakyAdjustmentService
from app.services.recommendation_ranking_service import RecommendationRankingService
from app.services.fallback_policy_engine import FallbackPolicyEngine
from app.services.skipped_reasoning_service import SkippedReasoningService
from app.services.failure_evidence_aggregator import FailureEvidenceAggregator
from app.services.file_failure_frequency_engine import FileFailureFrequencyEngine
from app.services.failure_neighborhood_correlation_engine import FailureNeighborhoodCorrelationEngine
from app.services.dependency_proximity_fragility_engine import DependencyProximityFragilityEngine
from app.services.escaped_defect_linkage_engine import EscapedDefectLinkageEngine
from app.services.risky_combination_detector import RiskyCombinationDetector
from app.services.pr_comment_service import PRCommentService, deliver_pr_comment_task_wrapper
from app.services.recommendation_explanation_builder import RecommendationExplanationBuilder
from app.services.risk_reasoning_builder import RiskReasoningBuilder
from app.services.pull_request_comment_formatter import PullRequestCommentFormatter
from app.services.github_comment_lifecycle_manager import GitHubCommentLifecycleManager
from app.services.comment_deduplication_engine import CommentDeduplicationEngine
from app.services.pr_comment_update_strategy import PRCommentUpdateStrategy, UpdateAction, UpdateDecision
from app.services.recommendation_warning_rules import (
    RecommendationWarningRules,
    RecommendationWarning,
    WarningResult,
    WarningSeverity,
)
from app.services.pr_comment_runtime_safeguards import (
    PRCommentRuntimeSafeguards,
    MinimalCommentBuilder,
    DeliveryOutcome,
    SafeguardResult,
    isolated_enqueue,
)
from app.services.recommendation_action_generator import (
    RecommendationActionGenerator,
    ActionResult,
)
from app.services.recommendation_exposure_tracker import RecommendationExposureTracker
from app.services.recommendation_executed_test_collector import (
    RecommendationExecutedTestCollector,
    CollectionResult,
)
from app.services.recommendation_override_tracker import (
    RecommendationOverrideTracker,
    OverrideResult,
)
from app.services.recommendation_ignore_detector import RecommendationIgnoreDetector
from app.services.escaped_defect_linker import EscapedDefectLinker
from app.services.rollback_outcome_tracker import RollbackOutcomeTracker
from app.services.recommendation_engineer_feedback_capture import RecommendationEngineerFeedbackCapture
from app.services.recommendation_outcome_classifier import RecommendationOutcomeClassifier
from app.services.recommendation_outcome_evidence_integrity import RecommendationOutcomeEvidenceIntegrity
from app.services.recommendation_calibration_signal_generator import RecommendationCalibrationSignalGenerator
from app.services.recommendation_outcome_snapshot import RecommendationOutcomeSnapshotService
from app.services.pilot_metrics_aggregator import PilotMetricsAggregator
from app.services.regression_savings_calculator import RegressionSavingsCalculator
from app.services.fragility_pilot_summary_builder import FragilityPilotSummaryBuilder
from app.services.escaped_defect_safety_analyzer import EscapedDefectSafetyAnalyzer
from app.services.pilot_report_generator import PilotReportGenerator
from app.services.pilot_executive_summary_renderer import PilotExecutiveSummaryRenderer
from app.services.recommendation_trust_metrics_builder import RecommendationTrustMetricsBuilder
from app.services.pilot_engineer_feedback_aggregator import PilotEngineerFeedbackAggregator
from app.services.pilot_conversion_narrative_builder import PilotConversionNarrativeBuilder
from app.services.pilot_packaging_policy import PilotPackagingPolicy
from app.services.module_risk_scoring_engine import ModuleRiskScoringEngine, ModuleRiskInputs, ModuleRiskResult
from app.services.recommendation_reasoning_engine import RecommendationReasoningEngine
from app.services.pr_impact_analyzer import PRImpactAnalyzer
from app.services.architectural_impact_engine import ArchitecturalImpactEngine
from app.services.dependency_impact_engine import DependencyImpactEngine
from app.services.recommendation_quality_evaluator import RecommendationQualityEvaluator
from app.services.learning_engine_v2 import LearningEngineV2
from app.services.recommendation_report_generator import RecommendationReportGenerator
from app.services.github_recommendation_comment_builder import GitHubRecommendationCommentBuilder


__all__ = [
    "OrganizationService",
    "RepositoryService",
    "DegradationEngine",
    "RecommendationService",
    "FlakyTestService",
    "RecommendationEvidenceCollector",
    "CoverageEvidenceResolver",
    "PathHeuristicResolver",
    "DependencyExpansionResolver",
    "HistoricalFailureResolver",
    "FlakyAdjustmentService",
    "RecommendationRankingService",
    "FallbackPolicyEngine",
    "SkippedReasoningService",
    "FailureEvidenceAggregator",
    "FileFailureFrequencyEngine",
    "FailureNeighborhoodCorrelationEngine",
    "DependencyProximityFragilityEngine",
    "EscapedDefectLinkageEngine",
    "RiskyCombinationDetector",
    "PRCommentService",
    "RecommendationExplanationBuilder",
    "RiskReasoningBuilder",
    "PullRequestCommentFormatter",
    "GitHubCommentLifecycleManager",
    "CommentDeduplicationEngine",
    "PRCommentUpdateStrategy",
    "RecommendationWarningRules",
    "PRCommentRuntimeSafeguards",
    "RecommendationActionGenerator",
    "RecommendationExposureTracker",
    "RecommendationExecutedTestCollector",
    "RecommendationOverrideTracker",
    "RecommendationIgnoreDetector",
    "EscapedDefectLinker",
    "RollbackOutcomeTracker",
    "RecommendationEngineerFeedbackCapture",
    "RecommendationOutcomeClassifier",
    "RecommendationOutcomeEvidenceIntegrity",
    "RecommendationCalibrationSignalGenerator",
    "RecommendationOutcomeSnapshotService",
    "PilotMetricsAggregator",
    "RegressionSavingsCalculator",
    "FragilityPilotSummaryBuilder",
    "EscapedDefectSafetyAnalyzer",
    "PilotReportGenerator",
    "PilotExecutiveSummaryRenderer",
    "RecommendationTrustMetricsBuilder",
    "PilotEngineerFeedbackAggregator",
    "PilotConversionNarrativeBuilder",
    "PilotPackagingPolicy",
    "ModuleRiskScoringEngine",
    "ModuleRiskInputs",
    "ModuleRiskResult",
    "RecommendationReasoningEngine",
    "PRImpactAnalyzer",
    "ArchitecturalImpactEngine",
    "DependencyImpactEngine",
    "RecommendationQualityEvaluator",
    "LearningEngineV2",
    "RecommendationReportGenerator",
    "GitHubRecommendationCommentBuilder",
]
