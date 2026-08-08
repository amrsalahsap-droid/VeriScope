"""
AC → Test Mapping State Consumer for the Recommendation Engine.

Consumes AC-level mapping states from build_mappings_for_pr() and MappingCandidate rows
to produce structured recommendation evidence with mapping_state and coverage_trust labels.

This is a production recommendation path — NOT a test mock.
All logic is derived from persisted rows; no fixture values are hardcoded.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from app.config import settings

# ─── Coverage trust levels ─────────────────────────────────────────────────────
# Ordered from most trusted to least trusted:
#   confirmed → auto_trusted → key_verified → evidence_aligned → partial → review_required → gap
COVERAGE_TRUST_CONFIRMED = "confirmed"
COVERAGE_TRUST_AUTO_TRUSTED = "auto_trusted"
COVERAGE_TRUST_KEY_VERIFIED = "key_verified"
COVERAGE_TRUST_EVIDENCE_ALIGNED = "evidence_aligned"
COVERAGE_TRUST_PARTIAL = "partial"
COVERAGE_TRUST_REVIEW_REQUIRED = "review_required"
COVERAGE_TRUST_GAP = "gap"
COVERAGE_TRUST_IGNORED = "ignored"


@dataclass
class MappingStateEvidence:
    """
    Structured recommendation evidence for a single AC → Test mapping.

    Produced by the recommendation consumer after processing a persisted
    MappingCandidate row or a synthesized no-candidate row.
    """
    ac_ref: str
    test_name: Optional[str]
    mapping_state: str          # The exact review_status from MappingCandidate (or "NO_CANDIDATE")
    coverage_trust: str         # One of the COVERAGE_TRUST_* constants
    can_count_as_confirmed_coverage: bool
    warning: Optional[str] = None
    gap_signal: Optional[str] = None
    recommended_action: Optional[str] = None
    declared_ac_ref: Optional[str] = None
    semantic_ac_ref: Optional[str] = None
    confidence: float = 0.0
    execution_status: Optional[str] = None
    partial_support_reason: Optional[str] = None


class ACMappingStateConsumer:
    """
    Recommendation engine consumer for AC → Test mapping states.

    Processes persisted MappingCandidate rows and AC-level mapping_summary
    from ACTestMappingService.build_mappings_for_pr() and produces structured
    MappingStateEvidence objects for downstream recommendation generation.

    Rules (product policy v1):
    - USER_CONFIRMED: confirmed trust, counts as coverage
    - VERIFIED: confirmed trust (legacy flow), counts as coverage
    - VERISCOPE_KEY_VERIFIED: key_verified trust, does NOT count as user-confirmed coverage
    - EVIDENCE_VERIFIED_ALIGNED: evidence_aligned trust, must NOT be labeled user-confirmed
    - METADATA_CONFLICT_SEMANTIC_MATCH: review_required, warning included, not confirmed
    - PARTIAL_SUPPORT: partial trust, not full coverage
    - SUGGESTED_STRONG | SUGGESTED_WEAK | SUGGESTED: review_required, awaiting user action
    - NO_CANDIDATE: gap signal generated
    - USER_REJECTED | REJECTED: ignored as positive evidence
    - Unknown states: gap/review_required, safe default
    """

    def consume_candidate(
        self,
        ac_ref: str,
        review_status: str,
        test_name: Optional[str] = None,
        declared_ac_ref: Optional[str] = None,
        semantic_ac_ref: Optional[str] = None,
        confidence: float = 0.0,
        execution_status: Optional[str] = None,
        partial_support_reason: Optional[str] = None,
        **kwargs: Any
    ) -> MappingStateEvidence:
        """
        Consume a single candidate mapping row and return structured evidence.

        Args:
            ac_ref: The target AC identifier (e.g. "AC-07")
            review_status: MappingCandidate.review_status from the database
            test_name: Name of the candidate test
            declared_ac_ref: XML-declared AC reference from JUnit properties
            semantic_ac_ref: Semantically matched AC reference
            confidence: Confidence score from the evaluator
            execution_status: "passed" | "failed" | "skipped" | "unknown"
            partial_support_reason: Human-readable reason for partial support
        """
        status = (review_status or "").upper()

        if status in ("USER_CONFIRMED", "VERIFIED"):
            return MappingStateEvidence(
                ac_ref=ac_ref,
                test_name=test_name,
                mapping_state=review_status,
                coverage_trust=COVERAGE_TRUST_CONFIRMED,
                can_count_as_confirmed_coverage=True,
                recommended_action="none",
                declared_ac_ref=declared_ac_ref,
                semantic_ac_ref=semantic_ac_ref,
                confidence=confidence,
                execution_status=execution_status,
            )

        elif status == "VERISCOPE_KEY_VERIFIED":
            auto_trust_key = getattr(settings, "AC_MAPPING_AUTO_TRUST_VERISCOPE_KEY", True)
            return MappingStateEvidence(
                ac_ref=ac_ref,
                test_name=test_name,
                mapping_state=review_status,
                coverage_trust=COVERAGE_TRUST_AUTO_TRUSTED if auto_trust_key else COVERAGE_TRUST_KEY_VERIFIED,
                can_count_as_confirmed_coverage=auto_trust_key,
                warning=None if auto_trust_key else "Key-verified mapping: policy does not auto-count as user-confirmed coverage.",
                recommended_action="none" if auto_trust_key else "review_key_verification_policy",
                declared_ac_ref=declared_ac_ref,
                semantic_ac_ref=semantic_ac_ref,
                confidence=confidence,
                execution_status=execution_status,
            )

        elif status == "EVIDENCE_VERIFIED_ALIGNED":
            auto_trust_evidence = getattr(settings, "AC_MAPPING_AUTO_TRUST_EVIDENCE_ALIGNED", True)
            return MappingStateEvidence(
                ac_ref=ac_ref,
                test_name=test_name,
                mapping_state=review_status,
                coverage_trust=COVERAGE_TRUST_AUTO_TRUSTED if auto_trust_evidence else COVERAGE_TRUST_EVIDENCE_ALIGNED,
                can_count_as_confirmed_coverage=auto_trust_evidence,
                warning=None if auto_trust_evidence else "Evidence-aligned mapping: user confirmation is optional under current policy.",
                recommended_action="optional_confirm" if auto_trust_evidence else "accept_as_confirmed",
                declared_ac_ref=declared_ac_ref,
                semantic_ac_ref=semantic_ac_ref,
                confidence=confidence,
                execution_status=execution_status,
            )

        elif status == "METADATA_CONFLICT_SEMANTIC_MATCH":
            warning = None
            if declared_ac_ref and semantic_ac_ref and declared_ac_ref != semantic_ac_ref:
                warning = (
                    f"Semantic evidence points to {semantic_ac_ref} "
                    f"but XML declared {declared_ac_ref}."
                )
            return MappingStateEvidence(
                ac_ref=ac_ref,
                test_name=test_name,
                mapping_state=review_status,
                coverage_trust=COVERAGE_TRUST_REVIEW_REQUIRED,
                can_count_as_confirmed_coverage=False,
                warning=warning or "Declared AC reference conflicts with semantic match. User resolution required.",
                recommended_action="resolve_conflict",
                declared_ac_ref=declared_ac_ref,
                semantic_ac_ref=semantic_ac_ref,
                confidence=confidence,
                execution_status=execution_status,
            )

        elif status == "PARTIAL_SUPPORT":
            return MappingStateEvidence(
                ac_ref=ac_ref,
                test_name=test_name,
                mapping_state=review_status,
                coverage_trust=COVERAGE_TRUST_PARTIAL,
                can_count_as_confirmed_coverage=False,
                warning="Partial evidence: test covers some but not all aspects of this AC.",
                recommended_action="review_partial",
                partial_support_reason=partial_support_reason,
                declared_ac_ref=declared_ac_ref,
                semantic_ac_ref=semantic_ac_ref,
                confidence=confidence,
                execution_status=execution_status,
            )

        elif status in ("SUGGESTED_STRONG", "SUGGESTED_WEAK", "SUGGESTED", "SYSTEM_SUGGESTED", "PENDING_REVIEW"):
            return MappingStateEvidence(
                ac_ref=ac_ref,
                test_name=test_name,
                mapping_state=review_status,
                coverage_trust=COVERAGE_TRUST_REVIEW_REQUIRED,
                can_count_as_confirmed_coverage=False,
                warning="System suggestion awaiting user review. Cannot count as confirmed coverage.",
                recommended_action="review_suggestion",
                declared_ac_ref=declared_ac_ref,
                semantic_ac_ref=semantic_ac_ref,
                confidence=confidence,
                execution_status=execution_status,
            )

        elif status in ("USER_REJECTED", "REJECTED"):
            return MappingStateEvidence(
                ac_ref=ac_ref,
                test_name=test_name,
                mapping_state=review_status,
                coverage_trust=COVERAGE_TRUST_IGNORED,
                can_count_as_confirmed_coverage=False,
                recommended_action="none",
                declared_ac_ref=declared_ac_ref,
                semantic_ac_ref=semantic_ac_ref,
                confidence=confidence,
                execution_status=execution_status,
            )

        else:
            # Safe default: unknown state → gap signal
            return MappingStateEvidence(
                ac_ref=ac_ref,
                test_name=test_name,
                mapping_state=review_status,
                coverage_trust=COVERAGE_TRUST_GAP,
                can_count_as_confirmed_coverage=False,
                gap_signal=f"Unknown mapping state '{review_status}' for {ac_ref}. Treated as coverage gap.",
                recommended_action="investigate",
                declared_ac_ref=declared_ac_ref,
                semantic_ac_ref=semantic_ac_ref,
                confidence=confidence,
                execution_status=execution_status,
            )

    def consume_no_candidate(self, ac_ref: str) -> MappingStateEvidence:
        """
        Generate a coverage gap signal for an AC that has no candidate test.

        Args:
            ac_ref: The AC identifier with no test candidate
        """
        return MappingStateEvidence(
            ac_ref=ac_ref,
            test_name=None,
            mapping_state="NO_CANDIDATE",
            coverage_trust=COVERAGE_TRUST_GAP,
            can_count_as_confirmed_coverage=False,
            gap_signal=f"No test candidate found for {ac_ref}. This AC has a missing or unmapped test.",
            recommended_action="create_missing_test",
        )

    def consume_mapping_summary(
        self,
        ac_refs_by_status: Dict[str, List[str]],
    ) -> Dict[str, List[str]]:
        """
        Consume an AC-level mapping summary and categorize ACs by coverage trust.

        Args:
            ac_refs_by_status: Dict mapping review_status → list of ac_refs

        Returns:
            Dict with keys: confirmed, auto_trusted, evidence_aligned, review_required,
                           partial, gap, ignored
        """
        result: Dict[str, List[str]] = {
            "confirmed": [],
            "auto_trusted": [],
            "evidence_aligned": [],
            "review_required": [],
            "partial": [],
            "gap": [],
            "ignored": [],
        }

        status_to_bucket = {
            "USER_CONFIRMED": "confirmed",
            "VERIFIED": "confirmed",
            "VERISCOPE_KEY_VERIFIED": "auto_trusted",
            "EVIDENCE_VERIFIED_ALIGNED": "auto_trusted",
            "METADATA_CONFLICT_SEMANTIC_MATCH": "review_required",
            "PARTIAL_SUPPORT": "partial",
            "SUGGESTED_STRONG": "review_required",
            "SUGGESTED_WEAK": "review_required",
            "SUGGESTED": "review_required",
            "NO_CANDIDATE": "gap",
            "USER_REJECTED": "ignored",
            "REJECTED": "ignored",
        }

        for status, refs in ac_refs_by_status.items():
            bucket = status_to_bucket.get(status.upper(), "gap")
            result[bucket].extend(refs)

        return result
