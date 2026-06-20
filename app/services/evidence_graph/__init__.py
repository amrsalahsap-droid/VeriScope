"""Recommendation services module.

This module contains organized services for:
- AC extraction
- Scenario signature generation
- Evidence matching
- Missing test mapping
- View model building
- Requirement evidence graph orchestration
"""

from app.services.evidence_graph.ac_extraction_service import ACExtractionService, ExtractionResult, ExtractionCategory, ExtractionAudit
from app.services.evidence_graph.scenario_signature_service import ScenarioSignatureService, SignatureGenerationResult
from app.services.evidence_graph.evidence_matching_service import EvidenceMatchingService, MatchResult, MatchTableEntry
from app.services.evidence_graph.missing_test_mapper import MissingTestMapper, MissingTestCard
from app.services.evidence_graph.recommendation_view_model_builder import (
    RecommendationViewModelBuilder,
    RecommendationEvidenceViewModel,
    TestCard,
    CoverageGapCard,
    ACTraceabilityRow,
    DecisionCopy,
)
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService

__all__ = [
    "ACExtractionService",
    "ExtractionResult",
    "ExtractionCategory",
    "ExtractionAudit",
    "ScenarioSignatureService",
    "SignatureGenerationResult",
    "EvidenceMatchingService",
    "MatchResult",
    "MatchTableEntry",
    "MissingTestMapper",
    "MissingTestCard",
    "RecommendationViewModelBuilder",
    "RecommendationEvidenceViewModel",
    "TestCard",
    "CoverageGapCard",
    "ACTraceabilityRow",
    "DecisionCopy",
    "RequirementEvidenceGraphService",
]
