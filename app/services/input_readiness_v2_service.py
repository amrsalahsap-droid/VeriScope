"""Input Readiness V2 Service — 12-Input Contract for Recommendation Readiness."""
import logging
import re
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.services.ac_test_mapping_service import ACTestMappingService
from app.utils.file_classifier import classify_changed_file
from app.config import settings
from app.schemas.input_readiness_v2 import (
    InputReadinessV2Response,
    InputReadinessItem,
    InputReadinessAction,
    InputReadinessBlocker,
    InputReadinessWarning,
    NextBestAction,
    INPUT_WEIGHTS,
    HARD_BLOCKER_INPUTS,
    INPUT_LABELS,
)

logger = logging.getLogger(__name__)

# Confidence thresholds
CONFIDENT_READY_THRESHOLD = 75.0
MINIMUM_READY_THRESHOLD = 50.0

# Confidence label to numeric score mapping
CONFIDENCE_LABEL_TO_SCORE = {
    "HIGH": 0.9,
    "MODERATE": 0.6,
    "MEDIUM": 0.6,
    "LOW": 0.3,
    "NONE": 0.0,
    None: None,
}

def get_confidence_score_and_label(label: str | None) -> tuple[float | None, str | None]:
    """Convert confidence label to numeric score and return both."""
    if label is None:
        return None, None
    score = CONFIDENCE_LABEL_TO_SCORE.get(label.upper(), 0.5)  # Default to 0.5 for unknown
    return score, label.upper()


class InputReadinessV2Service:
    """Evaluates all 12 inputs independently and produces a deterministic readiness response."""

    def __init__(self, db: Session):
        self.db = db

    def assess(
        self,
        repository_id: str,
        pull_request_id: Optional[str] = None,
    ) -> InputReadinessV2Response:
        if isinstance(repository_id, str):
            try:
                repository_id = UUID(repository_id)
            except ValueError:
                pass
        if isinstance(pull_request_id, str) and pull_request_id:
            try:
                pull_request_id = UUID(pull_request_id)
            except ValueError:
                pass

        # Evaluate each input
        i1 = self._evaluate_input_1(repository_id, pull_request_id)
        i2 = self._evaluate_input_2(repository_id, pull_request_id)
        i3 = self._evaluate_input_3(repository_id, pull_request_id)
        i4 = self._evaluate_input_4(repository_id, pull_request_id)
        i5 = self._evaluate_input_5(repository_id, pull_request_id)
        i6 = self._evaluate_input_6(repository_id, pull_request_id)
        i7 = self._evaluate_input_7(repository_id, pull_request_id)
        i8 = self._evaluate_input_8(repository_id, pull_request_id)
        i9 = self._evaluate_input_9(repository_id, pull_request_id)
        i10 = self._evaluate_input_10(repository_id, pull_request_id)
        i11 = self._evaluate_input_11(repository_id, pull_request_id)
        i12 = self._evaluate_input_12(repository_id, pull_request_id)

        all_inputs = [i1, i2, i3, i4, i5, i6, i7, i8, i9, i10, i11, i12]

        # Calculate confidence score
        confidence_score = sum(inp.earned_score for inp in all_inputs)

        # Determine generation status (deterministic, score cannot override blockers)
        blockers: list[InputReadinessBlocker] = []
        warnings: list[InputReadinessWarning] = []
        confident_generation = False

        # Hard-blocker rules — evaluated in priority order
        i1_ok = i1.status in ("READY", "PARTIAL")
        i2_ok = i2.status in ("READY", "PARTIAL")
        i4_ok = i4.status in ("READY", "PARTIAL")
        i5_ok = i5.status in ("READY", "PARTIAL")
        i6_ok = i6.status in ("READY", "PARTIAL", "STALE")

        any_hard_blocker_missing = (
            i1.status in ("MISSING", "BLOCKED") or
            i2.status in ("MISSING", "BLOCKED") or
            i4.status in ("MISSING", "BLOCKED") or
            i5.status in ("MISSING", "BLOCKED", "BLOCKED_METADATA_CONFLICTS") or
            i6.status in ("MISSING", "BLOCKED")
        )

        any_hard_blocker_review = (
            i2.status in ("NEEDS_REVIEW", "REVIEW_NEEDED") or
            i4.status in ("NEEDS_REVIEW", "REVIEW_NEEDED") or
            i5.status in ("NEEDS_REVIEW", "REVIEW_NEEDED", "REVIEW_REQUIRED") or
            i6.status in ("NEEDS_REVIEW", "REVIEW_NEEDED")
        )

        any_hard_blocker_partial = (
            i1.status == "PARTIAL" or
            i2.status == "PARTIAL" or
            i4.status == "PARTIAL" or
            i5.status == "PARTIAL" or
            i6.status in ("PARTIAL", "STALE")
        )

        if not i1_ok:
            generation_status = "BLOCKED"
            can_generate = "NO"
            confident_generation = False
            primary_message = "PR change package is missing or invalid. No generation is possible."
            blockers.append(InputReadinessBlocker(
                input_id="INPUT_1",
                code="PR_CHANGE_PACKAGE_MISSING",
                message="Sync PR changes before attempting to generate a regression plan.",
            ))

        elif any_hard_blocker_missing:
            generation_status = "BLOCKED"
            can_generate = "NO"
            confident_generation = False
            primary_message = "Core inputs are missing or blocked. No generation is possible."
            if i2.status in ("MISSING", "BLOCKED"):
                blockers.append(InputReadinessBlocker(
                    input_id="INPUT_2",
                    code="BUSINESS_REQUIREMENTS_MISSING",
                    message="Add requirement groups and acceptance criteria before generating a confident regression plan.",
                ))
            if i4.status in ("MISSING", "BLOCKED"):
                blockers.append(InputReadinessBlocker(
                    input_id="INPUT_4",
                    code="TEST_INVENTORY_MISSING",
                    message="Import test cases with stable test IDs to enable confident generation.",
                ))
            if i5.status in ("MISSING", "BLOCKED", "BLOCKED_METADATA_CONFLICTS"):
                blockers.append(InputReadinessBlocker(
                    input_id="INPUT_5",
                    code="AC_TEST_MAPPING_CONFLICTS" if i5.status == "BLOCKED_METADATA_CONFLICTS" else "AC_TEST_MAPPING_MISSING",
                    message=i5.summary or "Map acceptance criteria to test cases to enable confident generation.",
                ))
            if i6.status in ("MISSING", "BLOCKED"):
                blockers.append(InputReadinessBlocker(
                    input_id="INPUT_6",
                    code="PR_TEST_EXECUTION_MISSING",
                    message="Upload current PR test execution results to enable confident generation.",
                ))

        elif any_hard_blocker_review:
            generation_status = "REVIEW_NEEDED"
            can_generate = "DRAFT_ONLY"
            confident_generation = False
            primary_message = "Business requirements or mappings need review. Review them before confident generation."
            if i2.status in ("NEEDS_REVIEW", "REVIEW_NEEDED"):
                blockers.append(InputReadinessBlocker(
                    input_id="INPUT_2",
                    code="BUSINESS_REQUIREMENTS_NEEDS_REVIEW",
                    message="Review and confirm acceptance criteria stable IDs before confident generation.",
                ))
            if i5.status in ("NEEDS_REVIEW", "REVIEW_NEEDED", "REVIEW_REQUIRED"):
                blockers.append(InputReadinessBlocker(
                    input_id="INPUT_5",
                    code="AC_TEST_MAPPING_NEEDS_REVIEW",
                    message="Review AC → Test mappings to resolve suggestions or ambiguities.",
                ))

        elif any_hard_blocker_partial:
            generation_status = "DRAFT_ONLY"
            can_generate = "DRAFT_ONLY"
            confident_generation = False
            primary_message = "Hard blocker inputs are partial. Only a draft plan can be generated."
            if i4.status == "PARTIAL":
                blockers.append(InputReadinessBlocker(
                    input_id="INPUT_4",
                    code="TEST_INVENTORY_PARTIAL",
                    message="Test case inventory is partial. Fix stable ID or source metadata issues.",
                ))
            if i5.status == "PARTIAL":
                blockers.append(InputReadinessBlocker(
                    input_id="INPUT_5",
                    code="AC_TEST_MAPPING_PARTIAL",
                    message="AC → Test Mapping is partial. Map all acceptance criteria before confident generation.",
                ))

        else:
            # All hard blockers are READY!
            # Optional confidence/governance boosters (Inputs 8, 9, 10, 11, 12) may reduce
            # confidence ceiling and produce warnings, but they do not force DRAFT_ONLY
            # when all hard evidence is READY and the score is above the confident threshold.
            has_missing_boosters = (
                i8.status in ("MISSING", "BLOCKED") or
                i9.status in ("MISSING", "BLOCKED") or
                i11.status in ("MISSING", "BLOCKED") or
                i10.status in ("MISSING", "BLOCKED") or
                i12.status in ("MISSING", "BLOCKED")
            )

            if confidence_score >= CONFIDENT_READY_THRESHOLD:
                generation_status = "HIGH_CONFIDENCE_READY"
                can_generate = "YES"
                confident_generation = True
                primary_message = "All critical inputs are ready. High-confidence regression planning is available."
            elif confidence_score >= MINIMUM_READY_THRESHOLD:
                generation_status = "DRAFT_ONLY"
                can_generate = "DRAFT_ONLY"
                confident_generation = False
                primary_message = "Core inputs ready but confidence is limited. Only draft recommendations can be generated."
            else:
                generation_status = "MINIMUM_READY"
                can_generate = "YES"
                confident_generation = False
                primary_message = "Minimum inputs ready. Regression plan can be generated but confidence is limited."

        # Guard: never return BLOCKED without blockers
        if generation_status == "BLOCKED" and not blockers:
            logger.error("READINESS CONTRACT VIOLATION: BLOCKED status with no blockers. Adding system blocker.")
            blockers.append(InputReadinessBlocker(
                input_id="INPUT_1",
                code="SYSTEM_INCONSISTENT_READINESS",
                message="Readiness assessment produced a BLOCKED status without identifiable blockers. Contact support.",
            ))

        # Confidence ceiling
        confidence_ceiling = self._calculate_confidence_ceiling(i1, i2, i3, i4, i5, i6, i7, i8, i9, i10, i11, i12)
        confidence_level = self._score_to_level(confidence_score)

        if generation_status == "HIGH_CONFIDENCE_READY" and confidence_ceiling != "HIGH":
            generation_status = "CONFIDENT_READY"
            primary_message = "Core inputs ready. Capped at Confident Ready due to missing confidence boosters."

        # Add warnings for missing confidence boosters
        booster_map = {
            "INPUT_3": (i3, "PRODUCT_BEHAVIOR_MAP_MISSING", "Product behavior map is missing. Impact analysis may be less precise."),
            "INPUT_7": (i7, "TEST_COVERAGE_MAPPING_MISSING", "Test coverage mapping is missing. Coverage analysis will be estimated."),
            "INPUT_8": (i8, "RELEASE_CONTEXT_MISSING", "Release context is missing. Risk tolerance cannot be assessed."),
            "INPUT_9": (i9, "ENVIRONMENT_MATRIX_MISSING", "Environment support matrix is missing. Cross-environment gaps cannot be detected."),
            "INPUT_10": (i10, "QUALITY_GATE_MISSING", "Quality gate profile is missing. Pass/fail thresholds cannot be enforced."),
            "INPUT_11": (i11, "KNOWN_DEFECTS_MISSING", "Known defects and accepted risks are not captured."),
            "INPUT_12": (i12, "OUT_OF_SCOPE_MISSING", "Out-of-scope declaration is missing. Scope boundaries are undefined."),
        }
        for inp_id, (inp, code, msg) in booster_map.items():
            if inp.status == "MISSING":
                warnings.append(InputReadinessWarning(input_id=inp_id, code=code, message=msg))
            elif inp.status == "STALE":
                warnings.append(InputReadinessWarning(
                    input_id=inp_id,
                    code=code.replace("MISSING", "STALE"),
                    message=msg.replace("is missing", "is stale"),
                ))
            elif inp.status == "HISTORICAL_ONLY":
                warnings.append(InputReadinessWarning(
                    input_id=inp_id,
                    code=code.replace("MISSING", "HISTORICAL_ONLY"),
                    message=msg.replace("is missing", "is historical only (SHA mismatch) and cannot boost current confidence"),
                ))

        # Guard against contradictory warnings: a READY input should never be flagged as missing.
        warnings = self._filter_contradictory_warnings(all_inputs, warnings)

        # Build next-best-actions (prioritized)
        next_best_actions = self._build_next_best_actions(all_inputs, blockers)

        # Build strict 12-input response fields
        INPUT_KEY_TO_SLUG = {
            "INPUT_1": "input_1_pr_change_package",
            "INPUT_2": "input_2_business_requirements",
            "INPUT_3": "input_3_product_behavior_map",
            "INPUT_4": "input_4_test_inventory",
            "INPUT_5": "input_5_ac_test_mapping",
            "INPUT_6": "input_6_test_execution_results",
            "INPUT_7": "input_7_test_coverage_mapping",
            "INPUT_8": "release_context",
            "INPUT_9": "environment_matrix",
            "INPUT_10": "quality_gate_profile",
            "INPUT_11": "known_risks",
            "INPUT_12": "out_of_scope",
        }

        blocking_inputs_list = []
        partial_inputs_list = []
        review_needed_inputs_list = []
        missing_confidence_boosters_list = []

        for inp in all_inputs:
            slug = INPUT_KEY_TO_SLUG.get(inp.input_id, inp.input_id.lower())
            items_to_add = [inp.input_id, slug]
            if inp.status in ("MISSING", "BLOCKED"):
                if inp.is_hard_blocker:
                    blocking_inputs_list.extend(items_to_add)
                else:
                    missing_confidence_boosters_list.extend(items_to_add)
            elif inp.status == "PARTIAL":
                partial_inputs_list.extend(items_to_add)
            elif inp.status in ("NEEDS_REVIEW", "REVIEW_NEEDED"):
                review_needed_inputs_list.extend(items_to_add)

        can_generate_draft = not any_hard_blocker_missing

        # Confident generation only allowed if:
        # 1. All hard blockers are READY (not PARTIAL or REVIEW_NEEDED)
        # 2. Confidence score is at or above the confident threshold
        # 3. Confirmed AC -> Test mappings > 0
        # Optional confidence/governance boosters (Inputs 8, 9, 10, 11, 12) do not block
        # confident generation; they only reduce the confidence ceiling and emit warnings.
        can_generate_confident = False
        hard_blockers_ready = (
            i1.status == "READY" and 
            i2.status == "READY" and 
            i4.status == "READY" and 
            i5.status == "READY" and 
            i6.status == "READY"
        )
        confirmed_mappings_positive = True
        if hasattr(i5, "details") and isinstance(i5.details, dict):
            confirmed_mappings_positive = i5.details.get("confirmed_mapping_count", 1) > 0

        if (hard_blockers_ready and
            confirmed_mappings_positive and
            confidence_score >= CONFIDENT_READY_THRESHOLD):
            can_generate_confident = True

        # Determine primary reason
        primary_reason = "All core inputs are ready."
        if i1.status not in ("READY", "PARTIAL"):
            primary_reason = "PR change package is missing or invalid."
        elif i2.status in ("MISSING", "BLOCKED"):
            primary_reason = "Business requirements are missing."
        elif i2.status in ("NEEDS_REVIEW", "REVIEW_NEEDED"):
            primary_reason = "Business requirements require review."
        elif i4.status in ("MISSING", "BLOCKED"):
            primary_reason = "Test inventory is missing."
        elif i4.status in ("NEEDS_REVIEW", "REVIEW_NEEDED"):
            primary_reason = "Test inventory requires review."
        elif i5.status in ("MISSING", "BLOCKED"):
            primary_reason = "AC → Test Mapping is missing."
        elif i5.status in ("NEEDS_REVIEW", "REVIEW_NEEDED"):
            primary_reason = "AC → Test Mapping requires review."
        elif i5.status == "PARTIAL":
            confirmed_zero = False
            if hasattr(i5, "details") and isinstance(i5.details, dict):
                confirmed_zero = i5.details.get("confirmed_mapping_count", 0) == 0
            if confirmed_zero:
                primary_reason = "AC → Test Mapping is partial and unconfirmed."
            else:
                primary_reason = "AC → Test Mapping is partial."
        elif i6.status in ("MISSING", "BLOCKED"):
            primary_reason = "Test execution results are missing."
        elif i6.status == "STALE":
            primary_reason = "PR test results are stale."
        # Optional confidence/governance boosters (Inputs 8-12) do not become the
        # primary generation-failure reason; they are reported as warnings only.

        # Calculate separate confidence concepts
        evidence_completeness = self._calculate_evidence_completeness(all_inputs)
        release_confidence = self._calculate_release_confidence(i1, i2, i3, i4, i5, i6, i7, i8, i9, i10, i11, i12)
        confidence_ceiling_reason = self._calculate_confidence_ceiling_reason(i1, i2, i3, i4, i5, i6, i7, i8, i9, i10, i11, i12)

        return InputReadinessV2Response(
            generation_status=generation_status,
            can_generate=can_generate,
            confident_generation=confident_generation,
            confidence_score=round(confidence_score, 1),
            confidence_level=confidence_level,
            confidence_ceiling=confidence_ceiling,
            primary_message=primary_message,
            blockers=blockers,
            warnings=warnings,
            inputs=all_inputs,
            next_best_actions=next_best_actions,
            can_generate_draft=can_generate_draft,
            can_generate_confident=can_generate_confident,
            blocking_inputs=blocking_inputs_list,
            partial_inputs=partial_inputs_list,
            review_needed_inputs=review_needed_inputs_list,
            missing_confidence_boosters=missing_confidence_boosters_list,
            primary_reason=primary_reason,
            evidence_completeness=evidence_completeness,
            release_confidence=release_confidence,
            confidence_ceiling_reason=confidence_ceiling_reason,
        )


    # ─── Input evaluators ────────────────────────────────────────────────────

    @staticmethod
    def get_changed_files_evidence(db: Session, pr) -> dict:
        from app.models.pull_request import PullRequestChangedFile, PullRequestSyncJob

        stored_files = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).order_by(PullRequestChangedFile.file_path.asc()).all()
        changed_files = [
            {
                "path": changed_file.file_path,
                "status": changed_file.status,
                "additions": changed_file.additions,
                "deletions": changed_file.deletions,
            }
            for changed_file in stored_files
            if changed_file.file_path and changed_file.file_path.strip()
        ]
        latest_sync = db.query(PullRequestSyncJob).filter(
            PullRequestSyncJob.pull_request_id == pr.id
        ).order_by(PullRequestSyncJob.created_at.desc()).first()
        paths_available = bool(changed_files)
        files_fetch_succeeded = bool(
            latest_sync
            and latest_sync.files_fetch_status == "SUCCESS"
            and latest_sync.status == "COMPLETED"
        )
        if paths_available and files_fetch_succeeded:
            source = "github_api"
        elif paths_available:
            source = "cached_pr_package"
        else:
            source = None
        error = None
        if not paths_available:
            error = (
                latest_sync.error_message if latest_sync and latest_sync.error_message
                else pr.last_sync_error
                or "Changed file paths are unavailable from the PR evidence store."
            )
        return {
            "changed_files_count": pr.changed_files_count if pr.changed_files_count is not None else len(changed_files),
            "changed_file_paths_available": paths_available,
            "changed_files": changed_files,
            "changed_files_source": source,
            "head_commit_sha": pr.head_commit_sha,
            "evidence_successful": paths_available,
            "evidence_error": error,
        }

    def _evaluate_input_1(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 1 — PR Change Package."""
        from app.models.pull_request import PullRequest

        weight = INPUT_WEIGHTS["INPUT_1"]

        if not pull_request_id:
            return self._missing_item("INPUT_1", weight, "No pull request selected.", [
                InputReadinessAction(label="Select Pull Request", action="SELECT_PULL_REQUEST")
            ])

        pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
        if not pr:
            return self._missing_item("INPUT_1", weight, "Pull request not found.", [])

        evidence = self.get_changed_files_evidence(self.db, pr)
        changed_files_count = evidence["changed_files_count"]

        if not pr.head_commit_sha:
            return self._blocked_item("INPUT_1", weight, "HEAD SHA is missing — PR not fully synced.", evidence, [
                InputReadinessAction(label="Sync PR Changes", action="SYNC_PR")
            ])

        if changed_files_count == 0:
            return self._blocked_item("INPUT_1", weight, "No changed files detected in PR.", evidence, [
                InputReadinessAction(label="Sync PR Changes", action="SYNC_PR")
            ])

        if not evidence["changed_file_paths_available"]:
            return InputReadinessItem(
                input_id="INPUT_1",
                label=INPUT_LABELS["INPUT_1"],
                status="PARTIAL",
                weight=weight,
                earned_score=weight * 0.7,
                max_score=weight,
                is_hard_blocker=True,
                summary="Changed file details unavailable. PR impact analysis may be incomplete.",
                details=evidence,
                actions=[InputReadinessAction(label="Sync PR Changes", action="SYNC_PR")],
            )

        stale = pr.evidence_truncated or False
        status = "PARTIAL" if stale else "READY"
        summary = f"{changed_files_count} changed files, head {pr.head_commit_sha[:7]}."
        if evidence["changed_files_source"] == "cached_pr_package":
            summary += " Changed files loaded from cached PR package."
        if stale:
            summary += " Large diff — some context truncated."

        return InputReadinessItem(
            input_id="INPUT_1",
            label=INPUT_LABELS["INPUT_1"],
            status=status,
            weight=weight,
            earned_score=weight if status == "READY" else weight * 0.7,
            max_score=weight,
            is_hard_blocker=True,
            summary=summary,
            details={**evidence, "evidence_truncated": stale},
            actions=[],
        )

    def _evaluate_input_2(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 2 — Business Requirements / Stable ACs."""
        from app.models.requirement_package import RequirementPackage
        from app.models.requirement_group import RequirementGroup
        from app.models.acceptance_criterion import AcceptanceCriterion
        from app.models.business_intent import BusinessIntentOverride

        weight = INPUT_WEIGHTS["INPUT_2"]

        if not pull_request_id:
            return self._missing_item("INPUT_2", weight, "No pull request selected.", [])

        pkg = self.db.query(RequirementPackage).filter(
            RequirementPackage.repository_id == repository_id,
            RequirementPackage.pull_request_id == pull_request_id,
        ).first()

        if not pkg:
            # Check legacy flat ACs
            legacy_count = int(self.db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.repository_id == repository_id,
                AcceptanceCriterion.pull_request_id == pull_request_id,
            ).count())
            bio_count = int(self.db.query(BusinessIntentOverride).filter(
                BusinessIntentOverride.pull_request_id == pull_request_id,
                BusinessIntentOverride.is_active == True,
                BusinessIntentOverride.acceptance_criteria.isnot(None),
            ).count())
            if legacy_count > 0 or bio_count > 0:
                return InputReadinessItem(
                    input_id="INPUT_2",
                    label=INPUT_LABELS["INPUT_2"],
                    status="PARTIAL",
                    weight=weight,
                    earned_score=weight * 0.4,
                    max_score=weight,
                    is_hard_blocker=True,
                    summary=f"Legacy flat ACs found ({legacy_count} criteria). Upgrade to grouped requirements for full score.",
                    details={"requirement_groups_count": 0, "acceptance_criteria_count": legacy_count, "stable_ac_ids": 0},
                    actions=[InputReadinessAction(label="Manage Business Requirements", action="OPEN_BUSINESS_REQUIREMENTS_MODAL")],
                )
            return self._missing_item("INPUT_2", weight, "No requirement groups or acceptance criteria found.", [
                InputReadinessAction(label="Add Requirements", action="OPEN_BUSINESS_REQUIREMENTS_MODAL")
            ])

        groups = self.db.query(RequirementGroup).filter(
            RequirementGroup.requirement_package_id == pkg.id
        ).all()

        if not groups:
            return self._missing_item("INPUT_2", weight, "Requirement package exists but has no groups.", [
                InputReadinessAction(label="Add Requirement Groups", action="OPEN_BUSINESS_REQUIREMENTS_MODAL")
            ])

        all_acs = self.db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == pull_request_id,
        ).all()

        ac_count = len(all_acs)
        if ac_count == 0:
            return self._missing_item("INPUT_2", weight, "Requirement groups exist but have no acceptance criteria.", [
                InputReadinessAction(label="Add Acceptance Criteria", action="OPEN_BUSINESS_REQUIREMENTS_MODAL")
            ])

        # Evaluate quality
        groups_with_stable_key = sum(1 for g in groups if g.stable_group_key)
        acs_with_stable_key = sum(1 for ac in all_acs if ac.stable_ac_key)
        generated_unaccepted = sum(1 for ac in all_acs if getattr(ac, "source", "") == "GENERATED" and ac.status == "NEEDS_REVIEW")
        duplicate_keys: list[str] = []
        for g in groups:
            keys = [ac.stable_ac_key for ac in g.acceptance_criteria if ac.stable_ac_key]
            seen: set = set()
            for k in keys:
                if k in seen:
                    duplicate_keys.append(k)
                seen.add(k)

        needs_review_count = generated_unaccepted + len(duplicate_keys)

        # Score breakdown for transparency
        score_breakdown = {
            "base_score": weight,
            "groups_present": len(groups) > 0,
            "acs_present": ac_count > 0,
            "stable_group_keys_complete": groups_with_stable_key == len(groups),
            "stable_ac_keys_complete": acs_with_stable_key == ac_count,
            "duplicates": len(duplicate_keys),
            "needs_review": needs_review_count,
            "generated_unaccepted": generated_unaccepted,
        }

        details = {
            "requirement_groups_count": len(groups),
            "acceptance_criteria_count": ac_count,
            "stable_group_keys_count": groups_with_stable_key,
            "stable_ac_keys_count": acs_with_stable_key,
            "duplicates": len(duplicate_keys),
            "needs_review": needs_review_count,
            "generated_unaccepted": generated_unaccepted,
            "score_breakdown": score_breakdown,
        }

        if needs_review_count > 0 or acs_with_stable_key < ac_count:
            status = "NEEDS_REVIEW"
            # Calculate earned score based on quality
            earned = weight
            if acs_with_stable_key < ac_count:
                earned -= weight * 0.2  # Deduct for missing stable keys
            if len(duplicate_keys) > 0:
                earned -= weight * 0.1  # Deduct for duplicates
            if generated_unaccepted > 0:
                earned -= weight * 0.1  # Deduct for generated unaccepted
            earned = max(weight * 0.4, earned)  # Minimum 40% if ACs exist
            
            # Dynamic CTA label based on specific issues
            if len(duplicate_keys) > 0 and needs_review_count == len(duplicate_keys):
                cta_label = f"Resolve {len(duplicate_keys)} Duplicates"
            elif needs_review_count > 0:
                cta_label = f"Review {needs_review_count} Items"
            else:
                cta_label = "Review Requirements"
            
            summary = f"{len(groups)} groups, {ac_count} ACs — {needs_review_count} need review, {ac_count - acs_with_stable_key} missing stable IDs."
            actions = [InputReadinessAction(label=cta_label, action="OPEN_BUSINESS_REQUIREMENTS_MODAL")]
        else:
            status = "READY"
            earned = weight
            summary = f"{len(groups)} requirement groups, {ac_count} acceptance criteria with stable IDs."
            actions = [InputReadinessAction(label="Manage Requirements", action="OPEN_BUSINESS_REQUIREMENTS_MODAL")]

        return InputReadinessItem(
            input_id="INPUT_2",
            label=INPUT_LABELS["INPUT_2"],
            status=status,
            weight=weight,
            earned_score=earned,
            max_score=weight,
            is_hard_blocker=True,
            summary=summary,
            details=details,
            actions=actions,
        )

    def _evaluate_input_3(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 3 — Product Behavior Map."""
        from app.models.behavior import Behavior
        from app.models.journey import Journey
        from app.models.behavior_evidence import BehaviorEvidence
        from app.models.journey_behavior import JourneyBehavior
        from app.models.business_behavior_mapping import BusinessBehaviorMapping
        from app.models.pull_request import PullRequest, PullRequestCommit
        from app.services.changed_file_behavior_matcher import ChangedFileBehaviorMatcher
        from sqlalchemy import func

        weight = INPUT_WEIGHTS["INPUT_3"]

        behaviors = self.db.query(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False,
        ).all()

        journeys = self.db.query(Journey).filter(
            Journey.repository_id == repository_id,
            Journey.is_deleted == False,
        ).all()

        # 1. MISSING Check: No behaviors and no journeys
        if not behaviors and not journeys:
            return self._missing_item("INPUT_3", weight, "No product behaviors or user journeys mapped.", [
                InputReadinessAction(label="Run Repository Intelligence", action="RUN_REPOSITORY_INTELLIGENCE")
            ])

        # 2. STALE Check: Check if behavior map snapshot does not match selected PR/head SHA
        is_stale = False
        stale_reason = None
        
        pr = None
        if pull_request_id:
            pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()

        if pr:
            # Check commit dates to determine staleness
            latest_commit = self.db.query(PullRequestCommit).filter(
                PullRequestCommit.pull_request_id == pull_request_id
            ).order_by(PullRequestCommit.commit_date.desc()).first()
            
            latest_behavior_update = self.db.query(func.max(Behavior.updated_at)).filter(
                Behavior.repository_id == repository_id
            ).scalar()
            
            if latest_commit and latest_behavior_update and latest_commit.commit_date > latest_behavior_update:
                is_stale = True
                stale_reason = f"Behavior map (last updated {latest_behavior_update}) is older than PR commit {latest_commit.sha[:7]} ({latest_commit.commit_date})."
            
            # Explicit staleness flag support for testing
            if hasattr(pr, 'behavior_map_stale') and pr.behavior_map_stale:
                is_stale = True
                stale_reason = getattr(pr, 'behavior_map_stale_reason', "Behavior map snapshot does not match current PR head SHA.")

        # 3. Check for generic behaviors (Verify: Behavior areas are meaningful, not generic)
        GENERIC_BEHAVIORS = {
            "auth", "frontend", "backend", "tests", "components", "repository intelligence",
            "user management", "notifications", "billing", "authentication",
            "administration", "reporting", "search", "file upload", "api integration",
            "integration",
        }
        
        meaningful_behaviors = [
            b for b in behaviors 
            if b.name.lower().strip() not in GENERIC_BEHAVIORS and b.slug.lower().strip() not in GENERIC_BEHAVIORS
        ]
        
        has_generic_only = len(behaviors) > 0 and len(meaningful_behaviors) == 0

        # 4. Changed-file mapping is permitted only with usable, persisted PR paths.
        changed_files_evidence = {
            "changed_files_count": 0,
            "changed_file_paths_available": False,
            "changed_files": [],
            "changed_files_source": None,
            "head_commit_sha": None,
            "evidence_successful": False,
            "evidence_error": "No pull request selected.",
        }
        if pr:
            changed_files_evidence = self.get_changed_files_evidence(self.db, pr)
        changed_paths = [changed_file["path"] for changed_file in changed_files_evidence["changed_files"]]
        
        # Helper to identify product files (exclude tests, config, docs)
        def is_product_file(file_path: str) -> bool:
            path_lower = file_path.lower()
            if any(p in path_lower for p in ["test", "spec", "mock", "fixture", "docs", "config", "eslint", "prettier"]):
                return False
            if path_lower.endswith((".md", ".json", ".yml", ".yaml", ".config.js", ".config.ts", ".gitignore", ".env", "tsconfig.json")):
                return False
            return path_lower.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".java", ".rb", ".cpp", ".h", ".cs"))

        changed_product_files = [p for p in changed_paths if is_product_file(p)]
        
        mapped_files = set()
        low_confidence_files = set()
        mapping_reasons = {}
        matched_files = []
        
        if behaviors and changed_paths:
            behavior_evidences = self.db.query(BehaviorEvidence).filter(
                BehaviorEvidence.behavior_id.in_([b.id for b in behaviors])
            ).all()
            journey_behaviors = self.db.query(JourneyBehavior).all()
            
            matcher = ChangedFileBehaviorMatcher(db=self.db)
            matches = matcher.match_changed_files(
                changed_files=changed_paths,
                behaviors=behaviors,
                evidences=behavior_evidences,
                journey_behaviors=journey_behaviors,
                journeys=journeys
            )
            
            MIN_CONFIDENCE_THRESHOLD = 0.6
            
            for m in matches:
                if m["score"] >= MIN_CONFIDENCE_THRESHOLD:
                    mapped_files.add(m["file_path"])
                    mapping_reasons.setdefault(m["file_path"], {
                        "behavior": m["behavior_name"],
                        "confidence": m["confidence"],
                        "reason": m["reason"],
                        "signal_type": m["signal_type"],
                    })
                else:
                    low_confidence_files.add(m["file_path"])

        unmapped_product_files = [p for p in changed_product_files if p not in mapped_files]
        for file_path in sorted(mapped_files):
            match = mapping_reasons[file_path]
            signal_type = match["signal_type"]
            match_source = (
                "exact_path" if signal_type in ("DIRECT_EVIDENCE", "PATH_SUFFIX")
                else "architecture_graph" if signal_type == "ROUTE_PAGE_MODULE"
                else "semantic"
            )
            matched_files.append({
                "path": file_path,
                "matched_behavior_key": match["behavior"],
                "match_source": match_source,
                "confidence": match["confidence"],
                "reason": match["reason"],
            })

        # 5. Requirement groups mapping check
        has_requirement_mapping = False
        requirement_mappings_count = 0
        unmapped_requirement_groups = []
        excluded_requirement_groups = []
        
        if pull_request_id:
            from app.models.requirement_package import RequirementPackage
            from app.models.requirement_group import RequirementGroup
            from app.models.acceptance_criterion import AcceptanceCriterion
            
            req_pkg = self.db.query(RequirementPackage).filter(
                RequirementPackage.pull_request_id == pull_request_id
            ).first()
            
            if req_pkg:
                req_groups = self.db.query(RequirementGroup).filter(
                    RequirementGroup.requirement_package_id == req_pkg.id
                ).all()
                
                ac_ids = [
                    ac.id for ac in self.db.query(AcceptanceCriterion).filter(
                        AcceptanceCriterion.pull_request_id == pull_request_id
                    ).all()
                ]
                
                if ac_ids:
                    mappings_count = self.db.query(BusinessBehaviorMapping).filter(
                        BusinessBehaviorMapping.acceptance_criterion_id.in_(ac_ids)
                    ).count()
                    
                    if mappings_count > 0:
                        has_requirement_mapping = True
                        requirement_mappings_count = mappings_count
                    
                    def classify_requirement_group(group, active_acs):
                        if not active_acs:
                            return "NO_ACTIVE_BEHAVIORAL_ACCEPTANCE_CRITERIA"
                        
                        non_behavioral_keywords = ["leftover", "parser metadata", "test data example", "junk", "placeholder"]
                        is_all_non_behavioral = True
                        for ac in active_acs:
                            ac_text_lower = ac.text.lower() if ac.text else ""
                            if any(k in ac_text_lower for k in non_behavioral_keywords):
                                pass
                            else:
                                is_all_non_behavioral = False
                                break
                        if is_all_non_behavioral:
                            return "NON_BEHAVIORAL_METADATA_GROUP"
                            
                        if group.title.lower().strip() in {"parser leftovers", "metadata bucket", "parser metadata"}:
                            return "PARSER_METADATA_BUCKET"
                        return None

                    for group in req_groups:
                        group_active_acs = self.db.query(AcceptanceCriterion).filter(
                            AcceptanceCriterion.requirement_group_id == group.id,
                            AcceptanceCriterion.status == "ACTIVE"
                        ).all()
                        
                        exclusion_reason = classify_requirement_group(group, group_active_acs)
                        if exclusion_reason:
                            excluded_requirement_groups.append({
                                "group_key": group.stable_group_key,
                                "group_name": group.title,
                                "reason": exclusion_reason
                            })
                        else:
                            group_ac_ids = [ac.id for ac in group_active_acs]
                            if group_ac_ids:
                                group_mappings = self.db.query(BusinessBehaviorMapping).filter(
                                    BusinessBehaviorMapping.acceptance_criterion_id.in_(group_ac_ids)
                                ).count()
                                if group_mappings == 0:
                                    unmapped_requirement_groups.append(group.title)
                            else:
                                unmapped_requirement_groups.append(group.title)

        # 6. Status resolution logic
        if pr and not changed_files_evidence["changed_file_paths_available"]:
            status = "PARTIAL"
            earned_score = weight * 0.5
            summary = "Changed file paths are unavailable, so current PR behavior matching cannot be verified."
        elif is_stale:
            status = "PARTIAL"
            earned_score = weight * 0.3
            summary = stale_reason or "Behavior map is stale for the current PR."
        elif has_generic_only:
            status = "PARTIAL"
            earned_score = weight * 0.4
            summary = "Behavior map contains only generic technical categories."
        elif not mapped_files:
            status = "PARTIAL"
            earned_score = weight * 0.5
            summary = "Behavior map exists but no changed files are mapped."
        elif not has_requirement_mapping:
            status = "PARTIAL"
            earned_score = weight * 0.7
            summary = "Changed files are mapped, but requirement groups are not linked."
        elif unmapped_requirement_groups:
            status = "PARTIAL"
            earned_score = weight * 0.7
            summary = f"Behavior map exists, but {len(unmapped_requirement_groups)} requirement groups are unmapped."
        elif unmapped_product_files:
            status = "PARTIAL"
            earned_score = weight * 0.8
            summary = f"Behavior map exists, but {len(unmapped_product_files)} product files are unmapped."
        else:
            status = "READY"
            earned_score = weight
            summary = f"{len(behaviors)} behaviors mapped, {len(mapped_files)} files matched, requirements integrated."

        details = {
            "behaviors_count": len(behaviors),
            "journeys_count": len(journeys),
            "meaningful_behaviors_count": len(meaningful_behaviors),
            "generic_only": has_generic_only,
            "pr_head_sha": changed_files_evidence["head_commit_sha"],
            "changed_files_count": changed_files_evidence["changed_files_count"],
            "changed_file_paths_loaded": changed_files_evidence["changed_file_paths_available"],
            "changed_file_paths": changed_paths,
            "changed_files_source": changed_files_evidence["changed_files_source"],
            "evidence_successful": changed_files_evidence["evidence_successful"],
            "evidence_error": changed_files_evidence["evidence_error"],
            "mapped_changed_files_count": len(mapped_files),
            "matched_file_count": len(matched_files),
            "matched_files": matched_files,
            "unmapped_product_files": unmapped_product_files,
            "low_confidence_files": list(low_confidence_files),
            "requirement_mappings_count": requirement_mappings_count,
            "unmapped_requirement_groups": unmapped_requirement_groups,
            "excluded_requirement_groups": excluded_requirement_groups,
            "is_stale": is_stale,
            "stale_reason": stale_reason
        }

        actions = []
        if status in ("MISSING", "PARTIAL", "STALE"):
            actions.append(InputReadinessAction(label="Refresh Behavior Catalog", action="RUN_REPOSITORY_INTELLIGENCE"))
        if status == "PARTIAL" and not has_requirement_mapping:
            actions.append(InputReadinessAction(label="Map Business Requirements", action="OPEN_BUSINESS_REQUIREMENTS_MODAL"))

        return InputReadinessItem(
            input_id="INPUT_3",
            label=INPUT_LABELS["INPUT_3"],
            status=status,
            weight=weight,
            earned_score=round(earned_score, 1),
            max_score=weight,
            is_hard_blocker=False,
            summary=summary,
            details=details,
            actions=actions
        )

    def _evaluate_input_4(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 4 — Test Case Inventory with stable test IDs and source traceability."""
        from app.models.test_result import TestCase, TestRun
        from app.models.pull_request import PullRequest, PullRequestCommit
        from sqlalchemy import func

        weight = INPUT_WEIGHTS["INPUT_4"]

        # Query active test inventory (not test execution runs)
        test_cases = (
            self.db.query(TestCase)
            .filter(
                TestCase.repository_id == repository_id,
                TestCase.is_active == True,
            )
            .all()
        )

        total_tests = len(test_cases)

        if total_tests == 0:
            return self._missing_item("INPUT_4", weight, "No test cases found in the repository.", [
                InputReadinessAction(label="Import Test Cases", action="IMPORT_TEST_CASES")
            ])

        # Validate stable IDs
        missing_stable_id = [tc for tc in test_cases if not tc.stable_identity or not tc.canonical_identity_hash]

        # Validate duplicate stable IDs
        stable_identity_counts: dict[str, int] = {}
        for tc in test_cases:
            stable_identity_counts[tc.stable_identity] = stable_identity_counts.get(tc.stable_identity, 0) + 1
        duplicate_stable_ids = [sid for sid, count in stable_identity_counts.items() if count > 1]

        # Validate missing source/type metadata
        missing_source = [
            tc for tc in test_cases 
            if not tc.source or tc.source == "unknown" or not getattr(tc, "import_source", None) or tc.import_source == "unknown"
        ]
        missing_type = [
            tc for tc in test_cases 
            if not tc.test_type or tc.test_type == "unknown" or
               not getattr(tc, "test_nature", None) or tc.test_nature == "unknown" or
               not getattr(tc, "primary_test_category", None) or tc.primary_test_category == "unknown" or
               not getattr(tc, "suite_purpose", None) or tc.suite_purpose == "unknown"
        ]

        # Validate deduplication
        dedupe_key_counts: dict[str, int] = {}
        for tc in test_cases:
            key = tc.dedupe_key or tc.stable_identity
            dedupe_key_counts[key] = dedupe_key_counts.get(key, 0) + 1
        duplicate_dedupe_keys = [k for k, count in dedupe_key_counts.items() if count > 1]

        # Freshness check: inventory should be at least as recent as PR head commit
        is_stale = False
        stale_reason = None
        pr = None
        if pull_request_id:
            pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()

        latest_inventory_update = self.db.query(func.max(TestCase.updated_at)).filter(
            TestCase.repository_id == repository_id,
            TestCase.is_active == True,
        ).scalar()

        if pr:
            latest_commit = self.db.query(PullRequestCommit).filter(
                PullRequestCommit.pull_request_id == pull_request_id
            ).order_by(PullRequestCommit.commit_date.desc()).first()

            if latest_commit and latest_inventory_update and latest_commit.commit_date > latest_inventory_update:
                is_stale = True
                stale_reason = (
                    f"Test inventory (last updated {latest_inventory_update}) is older than "
                    f"PR commit {latest_commit.sha[:7]} ({latest_commit.commit_date})."
                )

        # Check semantic classification fields
        missing_semantic = [
            tc for tc in test_cases
            if not tc.product_area or not tc.business_flow or not tc.scenario_intent or not tc.scenario_type or not tc.validation_target or not tc.regression_role
        ]
        needs_review = [
            tc for tc in test_cases
            if tc.classification_review_status == "REVIEW_NEEDED"
        ]

        # Build score and status
        details = {
            "total_tests": total_tests,
            "missing_stable_id_count": len(missing_stable_id),
            "duplicate_stable_id_count": len(duplicate_stable_ids),
            "missing_source_count": len(missing_source),
            "missing_type_count": len(missing_type),
            "duplicate_dedupe_key_count": len(duplicate_dedupe_keys),
            "missing_semantic_classification_count": len(missing_semantic),
            "needs_review_semantic_classification_count": len(needs_review),
            "is_stale": is_stale,
            "stale_reason": stale_reason,
            "test_type_breakdown": {},
            "automation_status_breakdown": {},
            "source_breakdown": {},
            "test_nature_breakdown": {},
            "primary_test_category_breakdown": {},
            "suite_purpose_breakdown": {},
            "risk_tags_breakdown": {},
            "execution_layer_breakdown": {},
            "import_source_breakdown": {},
            "execution_method_breakdown": {},
            "product_area_breakdown": {},
            "business_flow_breakdown": {},
            "scenario_intent_breakdown": {},
            "scenario_type_breakdown": {},
            "validation_target_breakdown": {},
            "regression_role_breakdown": {},
            "behavior_mapping_status_breakdown": {},
        }

        for tc in test_cases:
            ttype = tc.test_type or "unknown"
            details["test_type_breakdown"][ttype] = details["test_type_breakdown"].get(ttype, 0) + 1
            auto = tc.automation_status or "UNKNOWN"
            details["automation_status_breakdown"][auto] = details["automation_status_breakdown"].get(auto, 0) + 1
            src = tc.source or "unknown"
            details["source_breakdown"][src] = details["source_breakdown"].get(src, 0) + 1

            nature = getattr(tc, "test_nature", None) or "unknown"
            details["test_nature_breakdown"][nature] = details["test_nature_breakdown"].get(nature, 0) + 1

            category = getattr(tc, "primary_test_category", None) or "unknown"
            details["primary_test_category_breakdown"][category] = details["primary_test_category_breakdown"].get(category, 0) + 1

            purpose = getattr(tc, "suite_purpose", None) or "unknown"
            details["suite_purpose_breakdown"][purpose] = details["suite_purpose_breakdown"].get(purpose, 0) + 1

            elayer = getattr(tc, "execution_layer", None) or "unknown"
            details["execution_layer_breakdown"][elayer] = details["execution_layer_breakdown"].get(elayer, 0) + 1

            isrc = getattr(tc, "import_source", None) or "unknown"
            details["import_source_breakdown"][isrc] = details["import_source_breakdown"].get(isrc, 0) + 1

            emethod = getattr(tc, "execution_method", None) or "unknown"
            details["execution_method_breakdown"][emethod] = details["execution_method_breakdown"].get(emethod, 0) + 1

            rtags = getattr(tc, "risk_tags", None) or []
            if not rtags:
                details["risk_tags_breakdown"]["none"] = details["risk_tags_breakdown"].get("none", 0) + 1
            else:
                for tag in rtags:
                    details["risk_tags_breakdown"][tag] = details["risk_tags_breakdown"].get(tag, 0) + 1

            # Semantic classification breakdowns
            parea = getattr(tc, "product_area", None) or "unknown"
            details["product_area_breakdown"][parea] = details["product_area_breakdown"].get(parea, 0) + 1

            bflow = getattr(tc, "business_flow", None) or "unknown"
            details["business_flow_breakdown"][bflow] = details["business_flow_breakdown"].get(bflow, 0) + 1

            sintent = getattr(tc, "scenario_intent", None) or "unknown"
            details["scenario_intent_breakdown"][sintent] = details["scenario_intent_breakdown"].get(sintent, 0) + 1

            stype = getattr(tc, "scenario_type", None) or "unknown"
            details["scenario_type_breakdown"][stype] = details["scenario_type_breakdown"].get(stype, 0) + 1

            vtarget = getattr(tc, "validation_target", None) or "unknown"
            details["validation_target_breakdown"][vtarget] = details["validation_target_breakdown"].get(vtarget, 0) + 1

            rrole = getattr(tc, "regression_role", None) or "unknown"
            details["regression_role_breakdown"][rrole] = details["regression_role_breakdown"].get(rrole, 0) + 1

            bm_status = getattr(tc, "behavior_mapping_status", None) or "unknown"
            details["behavior_mapping_status_breakdown"][bm_status] = details["behavior_mapping_status_breakdown"].get(bm_status, 0) + 1

        # Determine sub-statuses
        basic_inventory_status = "READY"
        if missing_stable_id or duplicate_stable_ids or duplicate_dedupe_keys or missing_source or missing_type:
            basic_inventory_status = "PARTIAL"

        semantic_classification_status = "READY"
        if len(missing_semantic) > 0:
            semantic_classification_status = "PARTIAL"
        elif len(needs_review) > 0:
            semantic_classification_status = "REVIEW_NEEDED"

        # Behavior mapping status
        behavior_mapping_status = "READY"
        missing_behavior_mapping = [
            tc for tc in test_cases
            if not getattr(tc, "behavior_mapping_status", None) or tc.behavior_mapping_status == "unknown"
        ]
        if len(missing_behavior_mapping) > 0:
            behavior_mapping_status = "PARTIAL"

        overall_intelligence_status = "READY"
        if basic_inventory_status == "PARTIAL" or semantic_classification_status == "PARTIAL" or behavior_mapping_status == "PARTIAL":
            overall_intelligence_status = "PARTIAL"

        # Hard blocker status should only depend on basic inventory requirements
        hard_blocker_status = basic_inventory_status

        details["basic_inventory_status"] = basic_inventory_status
        details["semantic_classification_status"] = semantic_classification_status
        details["semantic_intelligence_status"] = semantic_classification_status
        details["behavior_mapping_status"] = behavior_mapping_status
        details["overall_intelligence_status"] = overall_intelligence_status
        details["hard_blocker_status"] = hard_blocker_status

        # Determine overall status and score
        # Hard blocker status determines the main status for readiness calculation
        if is_stale:
            status = "STALE"
            earned = weight * 0.5
            summary = f"{total_tests} test cases, but inventory is stale. {stale_reason}"
            actions = [InputReadinessAction(label="Refresh Test Inventory", action="REFRESH_TEST_INVENTORY")]
        elif basic_inventory_status == "PARTIAL":
            status = "PARTIAL"
            if missing_stable_id or duplicate_stable_ids or duplicate_dedupe_keys:
                earned = weight * 0.3
                summary = (
                    f"{total_tests} test cases, but stable identity issues found: "
                    f"{len(missing_stable_id)} missing IDs, {len(duplicate_stable_ids)} duplicate stable IDs, "
                    f"{len(duplicate_dedupe_keys)} duplicate dedupe keys."
                )
                actions = [InputReadinessAction(label="Fix Stable IDs", action="OPEN_TEST_INVENTORY_REVIEW")]
            else:
                earned = weight * 0.6
                summary = (
                    f"{total_tests} test cases with stable IDs, but "
                    f"{len(missing_source)} missing source/import source and {len(missing_type)} missing type/classification."
                )
                actions = [InputReadinessAction(label="Complete Test Metadata", action="OPEN_TEST_INVENTORY_REVIEW")]
        else:
            # Basic inventory is ready, so hard blocker status is READY
            status = "READY"
            earned = weight
            
            # Provide detailed summary based on semantic intelligence status
            if semantic_classification_status == "PARTIAL":
                summary = (
                    f"{total_tests} test cases have complete basic inventory (READY), but "
                    f"{len(missing_semantic)} tests are missing product-aware semantic classification (PARTIAL)."
                )
                actions = [InputReadinessAction(label="Run Semantic Classifier", action="RUN_SEMANTIC_CLASSIFIER")]
            elif semantic_classification_status == "REVIEW_NEEDED":
                summary = (
                    f"{total_tests} test cases have complete basic inventory (READY), but "
                    f"{len(needs_review)} tests need semantic classification review (REVIEW_NEEDED)."
                )
                actions = [InputReadinessAction(label="Review Semantic Classification", action="REVIEW_SEMANTIC_CLASSIFICATION")]
            elif behavior_mapping_status == "PARTIAL":
                summary = (
                    f"{total_tests} test cases have complete basic inventory (READY), but "
                    f"{len(missing_behavior_mapping)} tests are missing behavior mapping (PARTIAL)."
                )
                actions = [InputReadinessAction(label="Run Behavior Mapping", action="RUN_BEHAVIOR_MAPPING")]
            else:
                summary = f"{total_tests} active test cases with stable IDs, source, classification, and complete semantic metadata."
                actions = []

        return InputReadinessItem(
            input_id="INPUT_4",
            label=INPUT_LABELS["INPUT_4"],
            status=status,
            weight=weight,
            earned_score=earned,
            max_score=weight,
            is_hard_blocker=True,
            summary=summary,
            details=details,
            actions=actions,
        )

    def _evaluate_input_5(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 5 — AC → Test Mapping."""
        from app.models.acceptance_criterion import AcceptanceCriterion
        from app.models.test_result import TestCase
        from app.models.mapping_candidate import MappingCandidate
        from app.models.traceability_edge import TraceabilityEdge

        weight = INPUT_WEIGHTS["INPUT_5"]  # 15.0

        if not pull_request_id:
            return self._missing_item("INPUT_5", weight, "No pull request selected.", [])

        acs = self.db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == pull_request_id,
            AcceptanceCriterion.status != "REJECTED"
        ).all()

        test_cases = self.db.query(TestCase).filter(
            TestCase.repository_id == repository_id,
            TestCase.is_active == True
        ).all()

        from app.services.ac_test_mapping_service import ACTestMappingService
        mapping_svc = ACTestMappingService()
        res = mapping_svc.build_mappings_for_pr(self.db, repository_id, pull_request_id)

        # Defensive rollback: build_mappings_for_pr may leave the transaction in an
        # aborted state if an inner flush/insert failed and was swallowed. A rollback
        # here resets the session so the subsequent candidate query can run.
        try:
            self.db.rollback()
        except Exception:
            pass

        accepted_ac_count = len(acs) if (isinstance(acs, list) and len(acs) > 0) else (res.get("accepted_ac_count") or res.get("total_accepted_acs") or 0)
        test_case_count = len(test_cases) if (isinstance(test_cases, list) and len(test_cases) > 0) else (res.get("test_case_count") or res.get("mapped_tests_count") or 0)

        candidates = self.db.query(MappingCandidate).filter(
            MappingCandidate.repository_id == repository_id
        ).all()
        if pull_request_id and isinstance(candidates, list):
            candidates = [c for c in candidates if str(getattr(c, 'pull_request_id', None)) == str(pull_request_id) or getattr(c, 'pull_request_id', None) is None]
        else:
            candidates = candidates if isinstance(candidates, list) else []

        edges = self.db.query(TraceabilityEdge).filter(
            TraceabilityEdge.repository_id == repository_id,
            TraceabilityEdge.source_node_type == "AcceptanceCriterion",
            TraceabilityEdge.target_node_type == "TestCase"
        ).all()
        if pull_request_id and isinstance(edges, list):
            edges = [e for e in edges if str(getattr(e, 'pull_request_id', None)) == str(pull_request_id) or getattr(e, 'pull_request_id', None) is None]
        else:
            edges = edges if isinstance(edges, list) else []

        if accepted_ac_count == 0 or (test_case_count == 0 and len(candidates) == 0 and len(edges) == 0 and res.get("suggested_mapping_count", 0) == 0 and res.get("suggested_mapped_ac_count", 0) == 0 and res.get("confirmed_mapping_count", 0) == 0):
            details = {
                "input_key": "ac_test_mapping",
                "status": "MISSING",
                "confirmed_coverage_percent": 0.0,
                "mapping_discovery_score": 0.0,
                "mapping_discovery_max_score": weight,
                "metadata_quality_score": 0.0,
                "metadata_quality_status": "FAIL",
                "confidence_impact": "NONE",
                "accepted_ac_count": accepted_ac_count,
                "test_case_count": test_case_count,
                "tests_with_declared_ac_refs": 0,
                "tests_with_external_ac_refs": 0,
                "verified_mapping_count": 0,
                "user_confirmed_mapping_count": 0,
                "suggested_strong_count": 0,
                "suggested_weak_count": 0,
                "conflicted_mapping_count": 0,
                "ambiguous_mapping_count": 0,
                "unresolved_mapping_count": 0,
                "rejected_mapping_count": 0,
                "acs_with_confirmed_mapping": 0,
                "acs_with_strong_suggestion": 0,
                "acs_with_conflicts": 0,
                "acs_with_no_candidate": accepted_ac_count,
                "acs_without_confirmed_mapping": accepted_ac_count,
                "unmapped_no_confirmed_mapping_ac_count": accepted_ac_count,
                "unmapped_no_candidate_ac_count": accepted_ac_count,
                "reason": "No acceptance criteria or test cases found to establish AC → Test mappings.",
            }
            return self._missing_item("INPUT_5", weight, details["reason"], [
                InputReadinessAction(label="Add Requirements", action="OPEN_BUSINESS_REQUIREMENTS_MODAL")
            ], details=details)

        tests_with_declared_ac_refs = len([
            tc for tc in test_cases
            if getattr(tc, 'external_ac_ref', None) or (isinstance(getattr(tc, 'source_metadata_json', None), dict) and getattr(tc, 'source_metadata_json', {}).get("declared_ac_id")) or any(c.test_case_id == tc.id and c.declared_ac_ref for c in candidates)
        ]) if isinstance(test_cases, list) else res.get("tests_with_external_ac_refs", 0)

        verified_mapping_count = len([c for c in candidates if c.review_status == "VERIFIED"]) + len([e for e in edges if e.review_status == "verified"])
        user_confirmed_mapping_count = len([c for c in candidates if c.review_status == "USER_CONFIRMED"]) + len([e for e in edges if e.review_status == "user_confirmed"])

        # ── New 7-state AC-level counts from mapping engine ────────────────────
        ms = res.get("mapping_summary", {})
        if ms and "metadata_conflict_semantic_match" in ms:
            user_confirmed_mapping_count = ms.get("user_confirmed", 0)
            veriscope_key_verified_mapping_count = ms.get("veriscope_key_verified", 0)
            evidence_aligned_count = ms.get("evidence_verified_aligned", 0)
            metadata_conflict_count = ms.get("metadata_conflict_semantic_match", 0)
            partial_support_count = ms.get("partial_support", 0)
            suggested_count = ms.get("suggested", 0)
            acs_with_no_candidate = ms.get("no_candidate", 0)
            rejected_mapping_count = ms.get("rejected", 0)
            accepted_gap_count = ms.get("accepted_gap", 0)
            summary_integrity = ms.get("summary_integrity", "FAIL")
        else:
            user_confirmed_mapping_count = len([c for c in candidates if c.review_status == "USER_CONFIRMED"]) + len([e for e in edges if e.review_status == "user_confirmed"])
            veriscope_key_verified_mapping_count = len([c for c in candidates if c.review_status == "VERIFIED"]) + len([e for e in edges if e.review_status == "verified"])
            evidence_aligned_count = len([c for c in candidates if c.review_status == "EVIDENCE_VERIFIED_ALIGNED"]) + len([e for e in edges if e.review_status == "evidence_verified_aligned"])
            metadata_conflict_count = len([c for c in candidates if c.review_status == "METADATA_CONFLICT_SEMANTIC_MATCH"]) + len([e for e in edges if e.review_status == "metadata_conflict_semantic_match"])
            partial_support_count = len([c for c in candidates if c.review_status == "PARTIAL_SUPPORT"]) + len([e for e in edges if e.review_status == "partial_support"])
            suggested_count = len([c for c in candidates if c.review_status == "SUGGESTED_STRONG"]) + len([e for e in edges if e.review_status == "suggested_strong"])
            acs_with_no_candidate = res.get("unmapped_no_candidate_ac_count", 0)
            rejected_mapping_count = len([c for c in candidates if c.review_status in ("USER_REJECTED", "REJECTED")]) + len([e for e in edges if e.review_status == "rejected"])
            accepted_gap_count = 0
            sum_check = (
                user_confirmed_mapping_count +
                veriscope_key_verified_mapping_count +
                evidence_aligned_count +
                metadata_conflict_count +
                partial_support_count +
                suggested_count +
                acs_with_no_candidate +
                rejected_mapping_count +
                accepted_gap_count
            )
            summary_integrity = "PASS" if accepted_ac_count == sum_check else "FAIL"

        # ── Auto-trust policy: evidence-aligned and Veriscope-key matches can be
        # trusted without forcing the user to press "Confirm".
        auto_trust_evidence = getattr(settings, "AC_MAPPING_AUTO_TRUST_EVIDENCE_ALIGNED", True)
        auto_trust_key = getattr(settings, "AC_MAPPING_AUTO_TRUST_VERISCOPE_KEY", True)
        min_confidence = getattr(settings, "AC_MAPPING_AUTO_TRUST_MIN_CONFIDENCE", 0.85)

        def _confident_evidence(c):
            try:
                return float(c.confidence_score or 0.0) >= min_confidence
            except Exception:
                return True

        evidence_aligned_trusted_ids = set()
        if auto_trust_evidence:
            for c in candidates:
                if c.review_status == "EVIDENCE_VERIFIED_ALIGNED" and c.acceptance_criterion_id and _confident_evidence(c):
                    evidence_aligned_trusted_ids.add(str(c.acceptance_criterion_id))
            for e in edges:
                if e.review_status == "evidence_verified_aligned" and e.source_node_id:
                    evidence_aligned_trusted_ids.add(str(e.source_node_id))

        veriscope_key_trusted_ids = set()
        if auto_trust_key:
            for c in candidates:
                if c.review_status == "VERIFIED" and c.acceptance_criterion_id:
                    veriscope_key_trusted_ids.add(str(c.acceptance_criterion_id))
            for e in edges:
                if e.review_status == "verified" and e.source_node_id:
                    veriscope_key_trusted_ids.add(str(e.source_node_id))

        user_confirmed_ids = set()
        for c in candidates:
            if c.review_status == "USER_CONFIRMED" and c.acceptance_criterion_id:
                user_confirmed_ids.add(str(c.acceptance_criterion_id))
        for e in edges:
            if e.review_status == "user_confirmed" and e.source_node_id:
                user_confirmed_ids.add(str(e.source_node_id))

        auto_trusted_evidence_aligned_count = min(evidence_aligned_count, len(evidence_aligned_trusted_ids))
        auto_trusted_veriscope_key_count = min(veriscope_key_verified_mapping_count, len(veriscope_key_trusted_ids))
        auto_trusted_coverage_count = auto_trusted_evidence_aligned_count + auto_trusted_veriscope_key_count
        trusted_coverage_count = len(user_confirmed_ids) + auto_trusted_coverage_count
        trusted_coverage_percent = round((trusted_coverage_count / accepted_ac_count) * 100.0, 1) if accepted_ac_count > 0 else 0.0

        review_required_count = (
            metadata_conflict_count +
            partial_support_count +
            suggested_count +
            acs_with_no_candidate +
            rejected_mapping_count
        )
        missing_candidate_count = acs_with_no_candidate

        # ── Metadata quality: driven by the current 7-state mapping_summary.
        # Legacy compatibility / conflicted_mapping_count must not produce false FAIL.
        conflicted_mapping_count = 0
        if metadata_conflict_count > 0:
            metadata_quality_status = "FAIL"
            metadata_quality_score = 0.0
        elif partial_support_count > 0 or suggested_count > 0 or acs_with_no_candidate > 0:
            # These are coverage gaps, not metadata corruption, but metadata quality
            # cannot be considered fully clean until they are resolved.
            metadata_quality_status = "PARTIAL"
            metadata_quality_score = 0.5
        elif test_case_count > 0 and tests_with_declared_ac_refs < test_case_count:
            metadata_quality_status = "PARTIAL"
            metadata_quality_score = 0.5
        else:
            metadata_quality_status = "PASS"
            metadata_quality_score = 1.0

        # ── Discovery score (mapping-coverage signal, scaled to input weight)
        total_discovery_credits = 0.0
        if isinstance(acs, list) and acs:
            for ac in acs:
                ac_id_str = str(ac.id)
                if ac_id_str in user_confirmed_ids:
                    total_discovery_credits += 1.0
                elif ac_id_str in veriscope_key_trusted_ids:
                    total_discovery_credits += 1.0
                elif ac_id_str in evidence_aligned_trusted_ids:
                    total_discovery_credits += 1.0
                elif any(
                    c.review_status == "EVIDENCE_VERIFIED_ALIGNED" and
                    str(getattr(c, 'acceptance_criterion_id', '')) == ac_id_str
                    for c in candidates
                ):
                    total_discovery_credits += 0.85
                elif any(c.acceptance_criterion_id == ac.id and c.review_status in ("SUGGESTED_STRONG", "system_suggested") for c in candidates):
                    total_discovery_credits += 0.6
                elif any(c.acceptance_criterion_id == ac.id and c.review_status in ("SUGGESTED_WEAK", "pending_review") for c in candidates):
                    total_discovery_credits += 0.2
                elif any(c.acceptance_criterion_id == ac.id and c.review_status == "PARTIAL_SUPPORT" for c in candidates):
                    total_discovery_credits += 0.1

        discovery_score = round(min(weight, (total_discovery_credits / accepted_ac_count) * weight), 1) if accepted_ac_count > 0 else 0.0

        # ── Status determination using coverage categories
        require_review_metadata = getattr(settings, "AC_MAPPING_REQUIRE_REVIEW_FOR_METADATA_CONFLICT", True)
        require_review_partial = getattr(settings, "AC_MAPPING_REQUIRE_REVIEW_FOR_PARTIAL_SUPPORT", True)
        require_review_no_candidate = getattr(settings, "AC_MAPPING_REQUIRE_REVIEW_FOR_NO_CANDIDATE", True)

        active_review_required_count = 0
        if require_review_metadata:
            active_review_required_count += metadata_conflict_count
        if require_review_partial:
            active_review_required_count += partial_support_count
        if require_review_no_candidate:
            active_review_required_count += acs_with_no_candidate
        active_review_required_count += suggested_count + rejected_mapping_count
        # If auto-trust is disabled for a normally-trusted category, it must be
        # treated as requiring user review before readiness.
        if not auto_trust_key:
            active_review_required_count += veriscope_key_verified_mapping_count
        if not auto_trust_evidence:
            active_review_required_count += evidence_aligned_count

        if accepted_ac_count == 0:
            status = "MISSING"
            reason = "No acceptance criteria found for this pull request."
            confidence_impact = "NONE"
            earned_score = 0.0
        elif summary_integrity != "PASS":
            status = "REVIEW_REQUIRED"
            reason = "Mapping summary integrity check failed; review the AC → Test mapping workspace."
            confidence_impact = "NONE"
            earned_score = 0.0
        elif metadata_quality_status == "FAIL":
            status = "REVIEW_REQUIRED"
            reason = f"Metadata quality check failed: {metadata_conflict_count} metadata conflict(s) require resolution."
            confidence_impact = "NONE"
            earned_score = min(discovery_score, 4.5)
        elif active_review_required_count > 0:
            status = "REVIEW_REQUIRED"
            reasons = []
            if metadata_conflict_count > 0:
                reasons.append(f"{metadata_conflict_count} metadata conflict(s)")
            if partial_support_count > 0:
                reasons.append(f"{partial_support_count} partial support mapping(s)")
            if suggested_count > 0:
                reasons.append(f"{suggested_count} system suggestion(s)")
            if acs_with_no_candidate > 0:
                reasons.append(f"{acs_with_no_candidate} AC(s) with no candidate test(s)")
            if rejected_mapping_count > 0:
                reasons.append(f"{rejected_mapping_count} rejected mapping(s)")
            reason = "Review required before generation: " + "; ".join(reasons) + "."
            confidence_impact = "NONE"
            earned_score = min(discovery_score, 4.5)
        elif trusted_coverage_percent == 100.0 and metadata_quality_status == "PASS":
            status = "READY"
            reason = "All acceptance criteria have trusted test mappings and metadata quality is verified."
            confidence_impact = "HIGH"
            earned_score = weight
        elif trusted_coverage_count > 0:
            status = "PARTIAL"
            reason = f"Trusted AC coverage is {trusted_coverage_percent}%. {accepted_ac_count - trusted_coverage_count} AC(s) remain untrusted."
            confidence_impact = "LOW" if trusted_coverage_percent < 50.0 else "MEDIUM"
            earned_score = discovery_score
        else:
            status = "MISSING"
            reason = "No trusted AC → Test mappings found."
            confidence_impact = "NONE"
            earned_score = 0.0

        if metadata_quality_status == "FAIL" and metadata_conflict_count > 0:
            metadata_quality_detail = f"FAIL — {metadata_conflict_count} JUnit AC refs conflict with semantic evidence."
        elif metadata_quality_status == "PARTIAL":
            metadata_quality_detail = "PARTIAL — some ACs lack trusted coverage."
        else:
            metadata_quality_detail = "PASS — all test refs align with accepted ACs."

        summary = (
            f"Trusted coverage: {trusted_coverage_percent}%. "
            f"Auto-trusted: {auto_trusted_coverage_count}. "
            f"User-confirmed: {len(user_confirmed_ids)}. "
            f"Review required: {active_review_required_count}. "
            f"Metadata quality: {metadata_quality_detail} "
            f"Summary integrity: {summary_integrity}."
        )

        blocking_reasons = []
        if metadata_conflict_count > 0:
            blocking_reasons.append(f"{metadata_conflict_count} metadata conflicts require resolution")
        if partial_support_count > 0:
            blocking_reasons.append(f"{partial_support_count} partial support mappings require review")
        if acs_with_no_candidate > 0:
            blocking_reasons.append(f"{acs_with_no_candidate} ACs have no candidate tests")
        if rejected_mapping_count > 0:
            blocking_reasons.append(f"{rejected_mapping_count} rejected mapping(s) need review")

        details = {
            "input": "AC_TEST_MAPPING",
            "input_key": "ac_test_mapping",
            "status": status,
            "total_acs": accepted_ac_count,
            "trusted_coverage_percent": trusted_coverage_percent,
            "confirmed_coverage_percent": trusted_coverage_percent,
            "coverage_progress_pct": trusted_coverage_percent,
            "user_confirmed_count": user_confirmed_mapping_count,
            "veriscope_key_verified_count": veriscope_key_verified_mapping_count,
            "auto_trusted_coverage_count": auto_trusted_coverage_count,
            "auto_trusted_evidence_aligned_count": auto_trusted_evidence_aligned_count,
            "auto_trusted_veriscope_key_count": auto_trusted_veriscope_key_count,
            "trusted_coverage_count": trusted_coverage_count,
            "evidence_verified_aligned_count": evidence_aligned_count,
            "metadata_conflict_semantic_match_count": metadata_conflict_count,
            "metadata_conflict_count": metadata_conflict_count,
            "partial_support_count": partial_support_count,
            "suggested_count": suggested_count,
            "no_candidate_count": acs_with_no_candidate,
            "missing_candidate_count": missing_candidate_count,
            "rejected_count": rejected_mapping_count,
            "accepted_gap_count": accepted_gap_count,
            "review_required_count": active_review_required_count,
            "summary_integrity": summary_integrity,
            "blocking_reasons": blocking_reasons,
            "mapping_discovery_score": discovery_score,
            "mapping_discovery_max_score": weight,
            "metadata_quality_score": metadata_quality_score,
            "metadata_quality_status": metadata_quality_status,
            "metadata_quality_detail": metadata_quality_detail,
            "confidence_impact": confidence_impact,
            "accepted_ac_count": accepted_ac_count,
            "test_case_count": test_case_count,
            "tests_with_declared_ac_refs": tests_with_declared_ac_refs,
            "tests_with_external_ac_refs": tests_with_declared_ac_refs,
            "mapping_attempt_count": len(candidates) or res.get("mapping_attempt_count", accepted_ac_count),
            "candidate_edge_count": len(candidates) + len(edges) or res.get("candidate_edge_count", accepted_ac_count),
            "verified_mapping_count": veriscope_key_verified_mapping_count,
            "user_confirmed_mapping_count": user_confirmed_mapping_count,
            "evidence_aligned_count": evidence_aligned_count,
            "suggested_strong_count": suggested_count,
            "suggested_weak_count": 0,
            "conflicted_mapping_count": conflicted_mapping_count,
            "ambiguous_mapping_count": 0,
            "unresolved_mapping_count": 0,
            "rejected_mapping_count": rejected_mapping_count,
            "acs_with_confirmed_mapping": len(user_confirmed_ids),
            "acs_with_strong_suggestion": suggested_count,
            "acs_with_conflicts": metadata_conflict_count,
            "acs_with_no_candidate": acs_with_no_candidate,
            "acs_without_confirmed_mapping": accepted_ac_count - len(user_confirmed_ids),
            "unmapped_no_confirmed_mapping_ac_count": accepted_ac_count - len(user_confirmed_ids),
            "unmapped_no_candidate_ac_count": acs_with_no_candidate,
            "reason": reason,
            "total_accepted_acs": accepted_ac_count,
            "confirmed_mapping_count": len(user_confirmed_ids),
            "suggested_mapping_count": suggested_count,
            "pending_review_mapping_count": 0,
            "needs_review_mapping_count": 0,
            "confirmed_mapped_ac_count": len(user_confirmed_ids),
            "confirmed_mapped_acs_count": len(user_confirmed_ids),
            "suggested_mapped_ac_count": suggested_count,
            "suggested_mapped_acs_count": suggested_count,
            "ambiguous_candidate_ac_count": 0,
            "unmapped_ac_count": acs_with_no_candidate,
            "unmapped_acs_count": acs_with_no_candidate,
            "unmapped_no_confirmed_ac_count": accepted_ac_count - len(user_confirmed_ids),
            "coverage_progress_pct": trusted_coverage_percent,
            "unmapped_ac_list": res.get("unmapped_ac_list", []),
            "unresolved_external_ac_refs": res.get("unresolved_external_ac_refs", []),
            "import_alignment_summary": res.get("import_alignment_summary", {}),
            "execution_summary": res.get("execution_summary", {}),
        }

        actions = []
        if active_review_required_count > 0:
            actions.append(InputReadinessAction(label="Review Mappings", action="OPEN_MAPPING_REVIEW"))
        else:
            actions.append(InputReadinessAction(label="View Mappings", action="OPEN_MAPPING_REVIEW"))

        return InputReadinessItem(
            input_id="INPUT_5",
            label=INPUT_LABELS["INPUT_5"],
            status=status,
            weight=weight,
            earned_score=round(earned_score, 1),
            max_score=weight,
            is_hard_blocker=True,
            summary=summary,
            details=details,
            actions=actions,
        )

    def _evaluate_input_6(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 6 — Current PR Test Execution Results."""
        from app.models.test_result import TestRun
        from app.models.pull_request import PullRequest

        weight = INPUT_WEIGHTS["INPUT_6"]

        if not pull_request_id:
            return self._missing_item("INPUT_6", weight, "No pull request selected.", [])

        pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()

        runs = self.db.query(TestRun).filter(
            TestRun.pull_request_id == pull_request_id,
        ).order_by(TestRun.created_at.desc()).first()

        if not runs:
            return self._missing_item("INPUT_6", weight, "No test execution results for this PR.", [
                InputReadinessAction(label="Upload Test Results", action="UPLOAD_TEST_RESULTS")
            ])

        # Check staleness vs PR head SHA
        is_stale = False
        if pr and pr.head_commit_sha and hasattr(runs, "commit_sha") and runs.commit_sha:
            is_stale = runs.commit_sha != pr.head_commit_sha

        if is_stale:
            return InputReadinessItem(
                input_id="INPUT_6", label=INPUT_LABELS["INPUT_6"], status="STALE",
                weight=weight, earned_score=weight * 0.5, max_score=weight, is_hard_blocker=True,
                summary="Test results exist but are from an older commit. Results may not reflect current changes.",
                details={"has_execution": True, "is_stale": True},
                actions=[InputReadinessAction(label="Upload Current Results", action="UPLOAD_TEST_RESULTS")],
            )

        return InputReadinessItem(
            input_id="INPUT_6", label=INPUT_LABELS["INPUT_6"], status="READY",
            weight=weight, earned_score=weight, max_score=weight, is_hard_blocker=True,
            summary="Current PR test execution results are available.",
            details={"has_execution": True, "is_stale": False},
            actions=[],
        )

    def _evaluate_input_7(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 7 — Test → Code/Coverage Mapping."""
        from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
        from app.models.pull_request import PullRequest
        from app.models.pull_request import PullRequestChangedFile
        from app.constants.evidence import CoverageLevel

        weight = INPUT_WEIGHTS["INPUT_7"]

        # Remove only known legacy pseudo-coverage before evaluating real artifacts.
        from app.services.coverage_ingestion import CoverageIngestionService
        cleanup_result = CoverageIngestionService.cleanup_fake_coverage_artifacts(self.db, repository_id)
        coverage_reports = self.db.query(CoverageReport).filter(
            CoverageReport.repository_id == repository_id,
        ).order_by(CoverageReport.created_at.desc()).all()
        real_reports = [
            report for report in coverage_reports
            if not CoverageIngestionService.is_fake_coverage_report(report)
        ]
        coverage = real_reports[0] if real_reports else None
        coverage_records_count = len(real_reports)

        if not coverage:
            missing_details = {
                "coverage_records_count": 0,
                "coverage_report_count": 0,
                "coverage_source": None,
                "coverage_commit_sha": None,
                "current_pr_head_sha": None,
                "is_current": False,
                "linked_test_count": 0,
                "unresolved_test_count": 0,
                "covered_file_count": 0,
                "changed_file_overlap_count": 0,
                "changed_file_coverage_overlap_count": 0,
                "coverage_artifact_health": None,
                "coverage_confidence": None,
                "coverage_level": None,
                "current_pr_coverage_confidence": "NONE",
                "confidence_impact": 0,
                "status_reason": "No coverage report uploaded.",
                "fake_coverage_reports_removed": cleanup_result["fake_coverage_reports_removed"],
                "fake_file_test_links_removed": cleanup_result["fake_file_test_links_removed"],
            }
            return InputReadinessItem(
                input_id="INPUT_7", label=INPUT_LABELS["INPUT_7"], status="MISSING",
                weight=weight, earned_score=0, max_score=weight, is_hard_blocker=False,
                summary="No code coverage mapping available.",
                details=missing_details,
                actions=[InputReadinessAction(label="Upload Coverage Report", action="UPLOAD_COVERAGE_REPORT")],
            )

        # Initialize details — current_pr_coverage_confidence starts as NONE;
        # it is only set to the real artifact value when SHA matches and data is non-empty.
        details = {
            "coverage_records_count": coverage_records_count,
            "coverage_report_count": coverage_records_count,
            "fake_coverage_reports_removed": cleanup_result["fake_coverage_reports_removed"],
            "fake_file_test_links_removed": cleanup_result["fake_file_test_links_removed"],
            "coverage_commit_sha": coverage.commit_sha,
            "coverage_source": coverage.source,
            "coverage_format": coverage.format,
            "coverage_level": coverage.coverage_level,
            "overall_coverage_pct": coverage.overall_coverage_pct,
            "coverage_artifact_health": coverage.coverage_confidence,
            "coverage_confidence": coverage.coverage_confidence,
            "evidence_health_status": coverage.evidence_health_status,
            "files_total": coverage.files_total,
            "covered_lines_total": coverage.covered_lines_total,
            "total_lines": coverage.total_lines,
            # New fields for better coverage status tracking
            "coverage_file_count": 0,  # Will be populated below
            "file_to_test_link_count": 0,  # Will be populated below
            "coverage_currentness": None,  # Will be populated below
            "current_pr_confidence_impact": 0,  # Will be populated below
            "status_reason": None,  # Will be populated below
            # PR SHA context and changed-file coverage
            "commit_sha_source": coverage.commit_sha_source,
            "changed_files_total": coverage.changed_files_total,
            "changed_files_with_coverage": coverage.changed_files_with_coverage,
            "changed_files_without_coverage": coverage.changed_files_without_coverage,
            # Populated below once we know freshness:
            "current_pr_coverage_confidence": coverage.current_pr_coverage_confidence or "NONE",
            "confidence_impact": 0,
        }

        # Get PR information for freshness validation
        pr = None
        current_pr_head_sha = None
        changed_files = set()

        if pull_request_id:
            pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
            if pr:
                current_pr_head_sha = pr.head_commit_sha
                # Get changed files for this PR
                changed_file_records = self.db.query(PullRequestChangedFile).filter(
                    PullRequestChangedFile.pull_request_id == pull_request_id
                ).all()
                changed_files = {cf.file_path for cf in changed_file_records}

                logger.info("[INPUT 7 READINESS] PR changed files loaded", {
                    "pr_id": str(pull_request_id),
                    "changed_files_count": len(changed_files),
                    "changed_files_sample": list(changed_files)[:5] if changed_files else [],
                })

        details["current_pr_head_sha"] = current_pr_head_sha
        details["is_current"] = (coverage.commit_sha == current_pr_head_sha) if current_pr_head_sha else False

        # Coverage freshness validation — SHA mismatch means this is not current evidence.
        # HISTORICAL_ONLY: coverage exists but does not match the current PR head SHA.
        # STALE: same, but coverage is also older than 7 days (even more degraded signal).
        if current_pr_head_sha and coverage.commit_sha != current_pr_head_sha:
            from datetime import datetime, timezone, timedelta
            cov_sha_short = (coverage.commit_sha or "unknown")[:7]
            pr_sha_short = current_pr_head_sha[:7]
            age_days = None
            stale_status = "HISTORICAL_ONLY"
            if coverage.created_at:
                try:
                    created = coverage.created_at.replace(tzinfo=timezone.utc) if coverage.created_at.tzinfo is None else coverage.created_at
                    age_days = (datetime.now(timezone.utc) - created).days
                    if age_days >= 7:
                        stale_status = "STALE"
                except Exception:
                    pass

            status_reason = (
                f"Coverage commit SHA ({cov_sha_short}) does not match current PR head SHA ({pr_sha_short}). "
                f"This coverage cannot be used as current evidence for this PR."
            )
            if age_days is not None:
                status_reason += f" Coverage is {age_days} day(s) old."

            details["status_reason"] = status_reason
            details["stale_reason"] = status_reason
            details["sha_mismatch"] = True
            details["coverage_age_days"] = age_days
            # SHA mismatch: all current-PR linkage counts are 0 and confidence is NONE
            details["linked_test_count"] = 0
            details["unresolved_test_count"] = 0
            details["covered_file_count"] = 0
            details["changed_file_overlap_count"] = 0
            details["current_pr_coverage_confidence"] = "NONE"
            details["confidence_impact"] = 0
            # earned_score = 0: stale/historical coverage must NOT boost current confidence
            summary = (
                f"Historical coverage exists but does not match current PR (SHA mismatch: "
                f"{cov_sha_short} vs {pr_sha_short}). "
                f"Upload current coverage to get accurate signal."
            )
            return InputReadinessItem(
                input_id="INPUT_7", label=INPUT_LABELS["INPUT_7"], status=stale_status,
                weight=weight, earned_score=0, max_score=weight, is_hard_blocker=False,
                summary=summary,
                details=details,
                actions=[
                    InputReadinessAction(label="Upload Current Coverage", action="UPLOAD_COVERAGE_REPORT")
                ],
            )

        # Get coverage file entries and test links
        file_entries = self.db.query(CoverageFileEntry).filter(
            CoverageFileEntry.coverage_report_id == coverage.id
        ).all()

        test_links = self.db.query(FileTestLink).filter(
            FileTestLink.coverage_report_id == coverage.id
        ).all()

        # Calculate covered_file_count: files with at least one covered line
        covered_file_count = sum(1 for fe in file_entries if fe.covered_lines and len(fe.covered_lines) > 0)

        details["covered_file_count"] = covered_file_count
        details["linked_test_count"] = len(test_links)
        details["coverage_file_count"] = len(file_entries)
        details["file_to_test_link_count"] = len(test_links)

        # Determine coverage currentness
        if current_pr_head_sha and coverage.commit_sha == current_pr_head_sha:
            details["coverage_currentness"] = "CURRENT"
        elif current_pr_head_sha:
            details["coverage_currentness"] = "HISTORICAL_ONLY"
        else:
            details["coverage_currentness"] = "UNKNOWN"

        # Check for empty coverage when SHA matches
        is_empty_coverage = (
            details["coverage_currentness"] == "CURRENT" and
            len(file_entries) == 0 and
            len(test_links) == 0
        )

        if is_empty_coverage:
            # SHA matches but no coverage data - this is PARTIAL_EMPTY or INVALID_COVERAGE_ARTIFACT
            status = "PARTIAL_EMPTY"
            earned_score = 0
            details["current_pr_confidence_impact"] = 0
            details["status_reason"] = "Coverage SHA matches current PR but no coverage files or test links were parsed. Coverage artifact may be invalid or empty."
            details["coverage_artifact_health"] = "INVALID_COVERAGE_ARTIFACT"
            summary = "Coverage uploaded but no file coverage records were parsed. Coverage artifact may be invalid or empty."
            return InputReadinessItem(
                input_id="INPUT_7", label=INPUT_LABELS["INPUT_7"], status=status,
                weight=weight, earned_score=earned_score, max_score=weight, is_hard_blocker=False,
                summary=summary,
                details=details,
                actions=[
                    InputReadinessAction(label="Re-upload Valid Coverage Report", action="UPLOAD_COVERAGE_REPORT")
                ],
            )

        # File linkage validation — a file only counts as "covered" if it has at
        # least one actually-covered line. A file entry with zero covered lines
        # (0% coverage) must NOT be treated as covered just because a row exists.
        covered_files = {fe.file_path for fe in file_entries if fe.covered_lines and len(fe.covered_lines) > 0}
        details["covered_files"] = list(covered_files)

        logger.info("[INPUT 7 READINESS] Coverage file entries", {
            "file_entries_count": len(file_entries),
            "covered_files_count": len(covered_files),
            "covered_files_sample": list(covered_files)[:5] if covered_files else [],
        })

        # Classify changed files into coverable source, test, and non-coverable files
        coverable_source_changed_files = set()
        changed_test_files = set()
        non_coverable_changed_files = set()

        for file_path in changed_files:
            classification = classify_changed_file(file_path)
            if classification == "source":
                coverable_source_changed_files.add(file_path)
            elif classification == "test":
                changed_test_files.add(file_path)
            else:
                non_coverable_changed_files.add(file_path)

        # Calculate coverage for coverable source files only
        coverable_source_overlap = coverable_source_changed_files.intersection(covered_files)
        coverable_source_overlap_count = len(coverable_source_overlap)
        uncovered_coverable_source_files = coverable_source_changed_files - covered_files

        # Store classification results
        details["changed_files_total"] = len(changed_files)
        details["coverable_changed_files_total"] = len(coverable_source_changed_files)
        details["coverable_changed_files_covered"] = coverable_source_overlap_count
        details["changed_test_files_total"] = len(changed_test_files)
        details["changed_test_files"] = list(changed_test_files)
        details["non_coverable_changed_files_total"] = len(non_coverable_changed_files)
        details["non_coverable_changed_files"] = list(non_coverable_changed_files)
        details["uncovered_coverable_changed_files"] = list(uncovered_coverable_source_files)

        # Legacy fields for backward compatibility
        details["changed_files_with_coverage"] = len(covered_files.intersection(changed_files))
        details["changed_files_without_coverage"] = len(changed_files) - len(covered_files.intersection(changed_files))

        logger.info("[INPUT 7 READINESS] Changed file classification", {
            "total_changed_files": len(changed_files),
            "coverable_source_files": len(coverable_source_changed_files),
            "coverable_source_covered": coverable_source_overlap_count,
            "changed_test_files": len(changed_test_files),
            "non_coverable_files": len(non_coverable_changed_files),
            "uncovered_source_files": list(uncovered_coverable_source_files)[:5] if uncovered_coverable_source_files else [],
        })

        # Use coverable source files for overlap calculation
        overlap_count = coverable_source_overlap_count if coverable_source_changed_files else 0
        details["changed_file_coverage_overlap_count"] = overlap_count
        details["changed_files"] = list(changed_files)
        details["overlap_files"] = list(coverable_source_overlap)

        # Canonical alias — consistent key used by UI and tests
        details["changed_file_overlap_count"] = overlap_count

        # Test linkage validation — check if test_case_id refs resolve to real TestCases
        from app.models.test_result import TestCase
        linked_test_ids = {tl.test_case_id for tl in test_links}
        resolved_tests = self.db.query(TestCase).filter(TestCase.id.in_(linked_test_ids)).all() if linked_test_ids else []
        details["resolved_test_count"] = len(resolved_tests)
        details["unresolved_test_count"] = len(linked_test_ids) - len(resolved_tests)

        # ─── Simplified status classification (single source of truth) ───────
        # MISSING only when: no coverage report / cannot be parsed / no file-level
        # coverage records exist (covered_file_count == 0 or files_total == 0).
        # HISTORICAL_ONLY is handled by the SHA-mismatch early-return above, so by
        # this point is_current is always True and sha_mismatch is always False.
        # READY / PARTIAL_READY / NO_CHANGED_FILE_COVERAGE are decided purely by
        # coverable-source-file overlap. Coverage level (RUN_LEVEL / TEST_FILE_LEVEL /
        # TEST_CASE_LEVEL) and test-to-file link resolution are surfaced as
        # informational `issues` only — they must never downgrade status to MISSING
        # or PARTIAL, since file-level coverage that matches the PR is real, current
        # evidence regardless of link granularity.
        coverage_level = coverage.coverage_level or CoverageLevel.RUN_LEVEL
        issues = []

        if covered_file_count == 0 or not coverage.files_total:
            status = "MISSING"
            earned_score = 0
            issues.append("No file-level coverage records found")
        elif coverable_source_changed_files:
            if coverable_source_overlap_count == 0:
                status = "NO_CHANGED_FILE_COVERAGE"
                earned_score = weight * 0.3
                issues.append("No coverage overlap with coverable source files")
            elif coverable_source_overlap_count < len(coverable_source_changed_files):
                status = "PARTIAL_READY"
                earned_score = weight * 0.7
                issues.append(
                    f"Partial coverable source file coverage: {coverable_source_overlap_count} of "
                    f"{len(coverable_source_changed_files)} source files covered"
                )
            else:
                status = "READY"
                earned_score = weight
        else:
            # No coverable source files changed — only test files (and/or non-coverable
            # files) changed. Verified by current PR test execution, so READY.
            status = "READY"
            earned_score = weight
            if changed_test_files:
                issues.append("No coverable source files changed; only test files changed")

        # Test-to-file linkage / coverage-level granularity — informational only.
        if coverage_level == CoverageLevel.TEST_CASE_LEVEL:
            if not test_links:
                issues.append("No test-to-file linkage (expected for TEST_CASE_LEVEL)")
            elif details["unresolved_test_count"] > 0:
                issues.append(f"{details['unresolved_test_count']} test links unresolved")

        # Relevance — informational signal only, does not affect status.
        is_relevant = bool((changed_files and overlap_count > 0) or (test_links and len(resolved_tests) > 0))
        relevance_reasons = []
        if changed_files and overlap_count > 0:
            relevance_reasons.append(f"Coverage overlaps {overlap_count} changed files")
        if test_links and len(resolved_tests) > 0:
            relevance_reasons.append(f"Coverage linked to {len(resolved_tests)} resolved tests")
        details["is_relevant"] = is_relevant
        details["relevance_reasons"] = relevance_reasons

        # current_pr_coverage_confidence: derived directly from status.
        # HIGH when all coverable source files are covered (READY).
        # PARTIAL when some are covered (PARTIAL_READY).
        # LOW when current coverage exists but has no changed-file overlap.
        # NONE only when MISSING.
        if status == "READY":
            current_pr_cov_confidence = "HIGH"
        elif status == "PARTIAL_READY":
            current_pr_cov_confidence = "PARTIAL"
        elif status == "NO_CHANGED_FILE_COVERAGE":
            current_pr_cov_confidence = "LOW"
        elif status == "MISSING":
            current_pr_cov_confidence = "NONE"
        else:
            current_pr_cov_confidence = "LOW"

        details["current_pr_coverage_confidence"] = current_pr_cov_confidence
        details["confidence_impact"] = round(earned_score / weight, 2) if weight else 0
        details["current_pr_confidence_impact"] = round(earned_score / weight, 2) if weight else 0
        details["issues"] = issues
        details["sha_mismatch"] = False
        details["is_current"] = True

        # Calculate confidence score and label
        confidence_score, confidence_label = get_confidence_score_and_label(current_pr_cov_confidence)

        # Build summary and status_reason
        if status == "READY":
            if coverable_source_changed_files:
                summary = (
                    f"Coverage is current and all {len(coverable_source_changed_files)} coverable changed "
                    f"source files are covered ({coverage.overall_coverage_pct * 100:.1f}% overall)."
                )
                if changed_test_files:
                    summary += f" {len(changed_test_files)} changed test files are verified by current PR test execution."
                details["status_reason"] = (
                    f"Coverage is current and all {len(coverable_source_changed_files)} coverable changed source "
                    f"files are covered."
                    + (f" {len(changed_test_files)} changed test files are verified by current PR test execution." if changed_test_files else "")
                )
            else:
                summary = f"Current coverage available ({coverage.overall_coverage_pct * 100:.1f}% overall, {coverage_level})."
                if changed_test_files:
                    summary += f" No coverable source files changed; {len(changed_test_files)} test files are verified by current PR test execution."
                details["status_reason"] = "Coverage is current; no coverable source files changed in this PR."
            if issues:
                summary += f" ({', '.join(issues)})"
        elif status == "PARTIAL_READY":
            summary = (
                f"Coverage is current and linked to the active PR ({coverage.overall_coverage_pct * 100:.1f}% overall). "
                f"{coverable_source_overlap_count} of {len(coverable_source_changed_files)} coverable source files "
                f"covered; {len(coverable_source_changed_files) - coverable_source_overlap_count} source files still need review."
            )
            if changed_test_files:
                summary += f" {len(changed_test_files)} test files changed."
            details["status_reason"] = (
                f"Coverage is current but only partially covers coverable source files "
                f"({coverable_source_overlap_count}/{len(coverable_source_changed_files)})."
            )
        elif status == "NO_CHANGED_FILE_COVERAGE":
            summary = f"Coverage is current but does not overlap with any coverable source files. ({coverage.overall_coverage_pct * 100:.1f}% overall)."
            if changed_test_files:
                summary += f" {len(changed_test_files)} test files changed."
            details["status_reason"] = "Coverage is current but has no overlap with coverable source files."
        elif status == "MISSING":
            summary = "Coverage report exists but no file-level coverage records were found."
            details["status_reason"] = "No file-level coverage records exist for this coverage report."
        else:
            summary = "Coverage mapping incomplete."
            details["status_reason"] = "Coverage state could not be determined."

        return InputReadinessItem(
            input_id="INPUT_7", label=INPUT_LABELS["INPUT_7"], status=status,
            weight=weight, earned_score=earned_score, max_score=weight, is_hard_blocker=False,
            summary=summary,
            details=details,
            confidence_score=confidence_score,
            confidence_label=confidence_label,
            actions=[
                InputReadinessAction(label="Upload Coverage Report", action="UPLOAD_COVERAGE_REPORT")
            ],
        )

    def _evaluate_input_8(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 8 — Release Context."""
        weight = INPUT_WEIGHTS["INPUT_8"]
        from app.models.external_work_item import ExternalWorkItem
        from app.models.pull_request_work_item_link import PullRequestWorkItemLink

        if pull_request_id:
            try:
                work_items = int(
                    self.db.query(ExternalWorkItem).join(
                        PullRequestWorkItemLink,
                        PullRequestWorkItemLink.external_work_item_id == ExternalWorkItem.id,
                    ).filter(PullRequestWorkItemLink.pull_request_id == pull_request_id).count()
                )
            except Exception:
                work_items = 0

            if work_items > 0:
                return InputReadinessItem(
                    input_id="INPUT_8", label=INPUT_LABELS["INPUT_8"], status="PARTIAL",
                    weight=weight, earned_score=weight * 0.7, max_score=weight, is_hard_blocker=False,
                    summary=f"{work_items} linked work items provide partial release context.",
                    details={"linked_work_items": work_items},
                    actions=[],
                )

        return self._missing_item("INPUT_8", weight, "No release context defined.", [
            InputReadinessAction(label="Link Work Item", action="LINK_WORK_ITEM")
        ])

    def _evaluate_input_9(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 9 — Environment Support Matrix."""
        weight = INPUT_WEIGHTS["INPUT_9"]
        # No dedicated model yet — always MISSING with NOT_APPLICABLE fallback
        return self._missing_item("INPUT_9", weight, "No environment support matrix defined.", [
            InputReadinessAction(label="Define Environment Matrix", action="DEFINE_ENVIRONMENT_MATRIX")
        ])

    def _evaluate_input_10(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 10 — Quality Gate Profile."""
        weight = INPUT_WEIGHTS["INPUT_10"]
        from app.models.ci_cd_policy_audit import CICDPolicyAuditEvent
        try:
            has_policy = int(self.db.query(CICDPolicyAuditEvent).filter(
                CICDPolicyAuditEvent.repository_id == repository_id,
            ).count()) > 0
        except Exception:
            has_policy = False

        if has_policy:
            return InputReadinessItem(
                input_id="INPUT_10", label=INPUT_LABELS["INPUT_10"], status="READY",
                weight=weight, earned_score=weight, max_score=weight, is_hard_blocker=False,
                summary="CI/CD quality gate profile is configured.",
                details={"has_quality_gate": True},
                actions=[],
            )
        return self._missing_item("INPUT_10", weight, "No quality gate profile configured.", [
            InputReadinessAction(label="Configure Quality Gates", action="CONFIGURE_QUALITY_GATES")
        ])

    def _evaluate_input_11(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 11 — Known Defects / Accepted Risks."""
        weight = INPUT_WEIGHTS["INPUT_11"]
        from app.models.fragility_pattern import FragilityPattern

        try:
            defect_count = int(self.db.query(FragilityPattern).filter(
                FragilityPattern.repository_id == repository_id,
            ).count())
        except Exception:
            defect_count = 0

        if defect_count > 0:
            return InputReadinessItem(
                input_id="INPUT_11", label=INPUT_LABELS["INPUT_11"], status="READY",
                weight=weight, earned_score=weight, max_score=weight, is_hard_blocker=False,
                summary=f"{defect_count} known fragility patterns recorded.",
                details={"fragility_patterns": defect_count},
                actions=[],
            )
        return self._missing_item("INPUT_11", weight, "No known defects or accepted risks captured.", [])

    def _evaluate_input_12(self, repository_id, pull_request_id) -> InputReadinessItem:
        """Input 12 — Out-of-Scope Declaration."""
        weight = INPUT_WEIGHTS["INPUT_12"]
        # No dedicated model — always MISSING
        return self._missing_item("INPUT_12", weight, "No out-of-scope declaration defined.", [
            InputReadinessAction(label="Declare Out-of-Scope", action="DECLARE_OUT_OF_SCOPE")
        ])

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _filter_contradictory_warnings(
        self,
        inputs: list[InputReadinessItem],
        warnings: list[InputReadinessWarning],
    ) -> list[InputReadinessWarning]:
        """Remove any warning that claims a READY input is missing or stale."""
        input_status_by_id = {i.input_id: i.status for i in inputs}
        filtered: list[InputReadinessWarning] = []
        for w in warnings:
            status = input_status_by_id.get(w.input_id)
            if status == "READY" and w.code.endswith(("_MISSING", "_STALE")):
                logger.warning(
                    "READINESS CONTRADICTION GUARD: input_id=%s is READY but warning %s was emitted. "
                    "Filtering warning from V2 response.",
                    w.input_id,
                    w.code,
                )
                continue
            filtered.append(w)
        return filtered

    def _missing_item(self, input_id: str, weight: float, summary: str, actions: list, details: dict = None) -> InputReadinessItem:
        return InputReadinessItem(
            input_id=input_id,
            label=INPUT_LABELS[input_id],
            status="MISSING",
            weight=weight,
            earned_score=0.0,
            max_score=weight,
            is_hard_blocker=input_id in HARD_BLOCKER_INPUTS,
            summary=summary,
            details=details or {},
            actions=actions,
        )

    def _blocked_item(self, input_id: str, weight: float, summary: str, details: dict, actions: list) -> InputReadinessItem:
        return InputReadinessItem(
            input_id=input_id,
            label=INPUT_LABELS[input_id],
            status="BLOCKED",
            weight=weight,
            earned_score=0.0,
            max_score=weight,
            is_hard_blocker=input_id in HARD_BLOCKER_INPUTS,
            summary=summary,
            details=details,
            actions=actions,
        )

    def _score_to_level(self, score: float) -> str:
        if score >= 75:
            return "HIGH"
        if score >= 45:
            return "MEDIUM"
        return "LOW"

    def _calculate_evidence_completeness(self, all_inputs) -> float:
        """Calculate evidence completeness as a percentage (0-100)."""
        total_weight = sum(inp.weight for inp in all_inputs)
        earned_weight = sum(inp.earned_score for inp in all_inputs)
        
        if total_weight == 0:
            return 0.0
        
        return round((earned_weight / total_weight) * 100, 1)

    def _calculate_release_confidence(self, i1, i2, i3, i4, i5, i6, i7, i8, i9, i10, i11, i12) -> str:
        """Calculate release confidence based on critical inputs and confirmed mappings."""
        # Rule 1: If Input 5 is partial/unconfirmed, release confidence is LOW or MEDIUM
        input_5_not_ready = i5.status in ("MISSING", "BLOCKED", "PARTIAL", "NEEDS_REVIEW", "REVIEW_NEEDED")
        
        # Rule 2: If confirmed AC -> Test mappings == 0, release confidence is LOW
        confirmed_mappings_zero = False
        if hasattr(i5, "details") and isinstance(i5.details, dict):
            confirmed_mappings_zero = i5.details.get("confirmed_mapping_count", 0) == 0
        elif isinstance(i5, dict) and "details" in i5:
            confirmed_mappings_zero = i5["details"].get("confirmed_mapping_count", 0) == 0
        
        # Rule 3: Check other critical inputs
        critical_inputs_ready = all(
            inp.status == "READY" 
            for inp in [i1, i2, i4, i6]  # Core hard blockers excluding Input 5
        )
        
        if confirmed_mappings_zero:
            return "LOW"
        elif input_5_not_ready and not critical_inputs_ready:
            return "LOW"
        elif input_5_not_ready:
            return "MEDIUM"
        elif not critical_inputs_ready:
            return "LOW"
        else:
            return "HIGH"

    def _calculate_confidence_ceiling_reason(self, i1, i2, i3, i4, i5, i6, i7, i8, i9, i10, i11, i12) -> str:
        """Calculate the reason for confidence ceiling limitation."""
        reasons = []
        
        # Check Input 5 status
        if i5.status in ("PARTIAL", "NEEDS_REVIEW", "REVIEW_NEEDED"):
            reasons.append("AC → Test Mapping is partial and has no confirmed coverage")
        elif i5.status in ("MISSING", "BLOCKED"):
            reasons.append("AC → Test Mapping is missing")
        
        # Check confirmed mappings
        confirmed_mappings_zero = False
        if hasattr(i5, "details") and isinstance(i5.details, dict):
            confirmed_mappings_zero = i5.details.get("confirmed_mapping_count", 0) == 0
        elif isinstance(i5, dict) and "details" in i5:
            confirmed_mappings_zero = i5["details"].get("confirmed_mapping_count", 0) == 0
        
        if confirmed_mappings_zero:
            reasons.append("No confirmed AC → Test mappings available")
        
        # Check other critical inputs
        critical_issues = []
        if i1.status in ("PARTIAL", "STALE", "NEEDS_REVIEW", "REVIEW_NEEDED"):
            critical_issues.append("PR Change Package is partial")
        elif i1.status in ("MISSING", "BLOCKED"):
            critical_issues.append("PR Change Package is missing")
        
        if i2.status in ("PARTIAL", "NEEDS_REVIEW", "REVIEW_NEEDED"):
            critical_issues.append("Business Requirements are partial")
        elif i2.status in ("MISSING", "BLOCKED"):
            critical_issues.append("Business Requirements are missing")
        
        if i4.status in ("PARTIAL", "NEEDS_REVIEW", "REVIEW_NEEDED"):
            critical_issues.append("Test Inventory is partial")
        elif i4.status in ("MISSING", "BLOCKED"):
            critical_issues.append("Test Inventory is missing")
        
        if i6.status in ("PARTIAL", "STALE", "NEEDS_REVIEW", "REVIEW_NEEDED"):
            critical_issues.append("Test Results are partial")
        elif i6.status in ("MISSING", "BLOCKED"):
            critical_issues.append("Test Results are missing")
        
        reasons.extend(critical_issues)
        
        return "; ".join(reasons) if reasons else "All critical inputs are ready"

    def _calculate_confidence_ceiling(self, i1, i2, i3, i4, i5, i6, i7, i8, i9, i10, i11, i12) -> str:
        # If PR change package is missing or invalid:
        if i1.status not in ("READY", "PARTIAL"):
            return "NONE"

        # 1. If any hard blocker is MISSING: confidence_ceiling <= LOW
        any_hard_blocker_missing = (
            i1.status in ("MISSING", "BLOCKED") or
            i2.status in ("MISSING", "BLOCKED") or
            i4.status in ("MISSING", "BLOCKED") or
            i5.status in ("MISSING", "BLOCKED") or
            i6.status in ("MISSING", "BLOCKED")
        )
        if any_hard_blocker_missing:
            return "LOW"

        # 2. If any hard blocker is PARTIAL or REVIEW_NEEDED: confidence_ceiling <= MEDIUM
        i4_is_partial = False
        if hasattr(i4, "details") and isinstance(i4.details, dict):
            i4_is_partial = i4.details.get("overall_intelligence_status") == "PARTIAL" or i4.details.get("semantic_classification_status") == "PARTIAL" or i4.details.get("semantic_intelligence_status") == "PARTIAL"
        elif isinstance(i4, dict) and "details" in i4 and isinstance(i4["details"], dict):
            i4_is_partial = i4["details"].get("overall_intelligence_status") == "PARTIAL" or i4["details"].get("semantic_classification_status") == "PARTIAL" or i4["details"].get("semantic_intelligence_status") == "PARTIAL"

        any_hard_blocker_partial_or_review = (
            i1.status == "PARTIAL" or
            i2.status in ("PARTIAL", "NEEDS_REVIEW", "REVIEW_NEEDED") or
            i4.status in ("PARTIAL", "NEEDS_REVIEW", "REVIEW_NEEDED") or
            i4_is_partial or
            i5.status in ("PARTIAL", "NEEDS_REVIEW", "REVIEW_NEEDED") or
            i6.status in ("PARTIAL", "STALE", "NEEDS_REVIEW", "REVIEW_NEEDED")
        )

        # 3. If Input 5 is PARTIAL / MISSING / REVIEW_NEEDED: confidence_ceiling <= MEDIUM
        input_5_not_ready = i5.status in ("MISSING", "BLOCKED", "PARTIAL", "NEEDS_REVIEW", "REVIEW_NEEDED")

        # 4. If confirmed AC -> Test mappings == 0: confidence_ceiling <= MEDIUM
        confirmed_mappings_zero = False
        if hasattr(i5, "details") and isinstance(i5.details, dict):
            confirmed_mappings_zero = i5.details.get("confirmed_mapping_count", 0) == 0
        elif isinstance(i5, dict) and "details" in i5:
            confirmed_mappings_zero = i5["details"].get("confirmed_mapping_count", 0) == 0

        # 5. If Quality Gate Profile (Input 10) is missing: confidence_ceiling <= MEDIUM
        quality_gate_missing = i10.status in ("MISSING", "BLOCKED")

        # 6. If Out-of-Scope Declaration (Input 12) is missing: confidence_ceiling <= MEDIUM
        out_of_scope_missing = i12.status in ("MISSING", "BLOCKED")

        # 7. If Input 7 (Test Coverage Mapping) is missing or historical: confidence_ceiling <= MEDIUM
        coverage_missing = i7.status in ("MISSING", "BLOCKED", "HISTORICAL_ONLY")

        if (
            any_hard_blocker_partial_or_review or
            input_5_not_ready or
            confirmed_mappings_zero or
            quality_gate_missing or
            out_of_scope_missing or
            coverage_missing
        ):
            return "MEDIUM"

        return "HIGH"


    def _build_next_best_actions(self, inputs: list, blockers: list) -> list[NextBestAction]:
        actions = []
        priority = 1

        action_map = {
            "INPUT_1": ("Sync PR Changes", "Required for any generation."),
            "INPUT_2": ("Add Business Requirements", "Required for confident regression planning."),
            "INPUT_4": ("Import Test Cases", "Required to identify which tests to run."),
            "INPUT_5": ("Map ACs to Tests", "Required to link requirements to test coverage."),
            "INPUT_6": ("Upload Test Results", "Required to verify tests passed on current PR."),
            "INPUT_3": ("Map Product Behaviors", "Improves impact analysis precision."),
            "INPUT_7": ("Upload Coverage Report", "Improves coverage-based prioritization."),
            "INPUT_8": ("Add Release Context", "Improves risk assessment accuracy."),
            "INPUT_9": ("Define Environment Matrix", "Enables cross-environment gap detection."),
            "INPUT_10": ("Configure Quality Gates", "Enables policy-based pass/fail decisions."),
            "INPUT_11": ("Capture Known Defects", "Improves risk-aware recommendations."),
            "INPUT_12": ("Declare Out-of-Scope", "Reduces false positives in recommendations."),
        }

        blocker_ids = {b.input_id for b in blockers}

        # Blockers first
        for inp in inputs:
            if inp.input_id in blocker_ids and inp.input_id in action_map:
                label, reason = action_map[inp.input_id]
                actions.append(NextBestAction(priority=priority, input_id=inp.input_id, label=label, reason=reason))
                priority += 1

        # Then missing non-blockers by weight descending
        for inp in sorted(inputs, key=lambda x: x.weight, reverse=True):
            if inp.input_id not in blocker_ids and inp.status in ("MISSING", "STALE", "NEEDS_REVIEW") and inp.input_id in action_map:
                label, reason = action_map[inp.input_id]
                actions.append(NextBestAction(priority=priority, input_id=inp.input_id, label=label, reason=reason))
                priority += 1

        return actions
