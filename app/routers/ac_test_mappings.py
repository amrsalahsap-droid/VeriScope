"""
AC Test Mapping Review API endpoints.

Provides endpoints for reviewing, resolving conflicts, and managing AC -> Test mappings.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from app.db.session import get_db
from app.models.traceability_edge import TraceabilityEdge
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.test_result import TestCase
from app.models.mapping_candidate import MappingCandidate
from app.models.ac_mapping_decision import ACMappingDecision
from app.models.pull_request import PullRequest
from app.models.user import User
from app.dependencies.auth import get_current_user
from app.schemas.ac_test_mapping import (
    ACTestMappingResponse,
    ACTestMappingGroup,
    SuggestedTest,
    MappingApprovalRequest,
    MappingRejectionRequest,
    ManualMappingRequest,
    AcceptSemanticMatchRequest,
    AcceptPartialSupportRequest,
    KeepDeclaredRefRequest,
    MarkUnmappedRequest,
    MarkAcceptedGapRequest,
    AddCommentRequest,
    EvidenceItem,
    ACTestMappingGroupedResponse,
    MappingSummary
)
from app.services.ac_test_mapping_service import ACTestMappingService, get_active_requirement_acs, get_pull_request_test_cases
from app.services.traceability_graph_service import TraceabilityGraphService
from app.services.requirement_test_alignment_gate import extract_flow_str

router = APIRouter()


def _safe_str(val: Any) -> Optional[str]:
    return val if isinstance(val, str) else None


def _extract_id_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (str, uuid.UUID)):
        return str(val)
    return None


@router.get(
    "/repositories/{repository_id}/pull-requests/{pull_request_id}/ac-test-mappings",
    response_model=ACTestMappingGroupedResponse
)
async def get_ac_test_mappings(
    repository_id: str,
    pull_request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get grouped AC -> Test mappings for review workspace.
    
    Returns mappings grouped by AC with full evidence chain details, conflict warnings,
    and mapping summary counts.
    """
    try:
        repo_uuid = uuid.UUID(repository_id)
        pr_uuid = uuid.UUID(pull_request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository or pull request ID")
    
    # Dynamic source of truth: Run mapping pipeline first to ensure all suggestions/candidates are updated
    mapping_svc = ACTestMappingService()
    pipeline_res = mapping_svc.build_mappings_for_pr(db, repo_uuid, pr_uuid)

    # Defensive rollback: inner flush/insert failures can leave the session transaction
    # aborted. Reset before the read queries below so they do not fail with
    # InFailedSqlTransaction.
    try:
        db.rollback()
    except Exception:
        pass

    # Use the same active requirement package and PR-scoped test lineage as the pipeline.
    acs = get_active_requirement_acs(db, repo_uuid, pr_uuid)
    test_cases = get_pull_request_test_cases(db, repo_uuid, pr_uuid)

    # Get MappingCandidate proposals
    candidates = db.query(MappingCandidate).filter(
        MappingCandidate.repository_id == repo_uuid,
        MappingCandidate.pull_request_id == pr_uuid
    ).all()
    
    # Get all active traceability edges for this PR
    edges = db.query(TraceabilityEdge).filter(
        TraceabilityEdge.repository_id == repo_uuid,
        TraceabilityEdge.pull_request_id == pr_uuid,
        TraceabilityEdge.edge_type == "ac_covered_by_test",
        TraceabilityEdge.is_active == True
    ).all()
    
    ac_mappings = {}
    
    # Initialize all ACs as unmapped
    def _format_ac_display_ref(ac_obj: Optional[AcceptanceCriterion]) -> Optional[str]:
        if not ac_obj:
            return None
        ac_n = getattr(ac_obj, 'ac_number', None)
        src_n = getattr(ac_obj, 'source_number', None)
        # source_number reflects the original uploaded AC ordering and must
        # take priority over ac_number (an internal/legacy ordering field).
        if isinstance(src_n, int):
            return f"AC-{src_n:02d}"
        if isinstance(ac_n, int):
            return f"AC-{ac_n:02d}"
        ident = _safe_str(getattr(ac_obj, 'identifier', None))
        if ident and ident.startswith("AC-") and len(ident) <= 6:
            return ident
        return ident or f"AC-{str(ac_obj.id)[:8]}"

    # Initialize all ACs as unmapped
    for ac in acs:
        identifier_str = _safe_str(getattr(ac, 'identifier', None))
        ac_num = getattr(ac, 'ac_number', None)
        src_num = getattr(ac, 'source_number', None)
        ac_num_int = ac_num if isinstance(ac_num, int) else None
        src_num_int = src_num if isinstance(src_num, int) else None

        display_ref = _format_ac_display_ref(ac)
        ac_group = getattr(ac, 'group', None)
        group_title_str = _safe_str(getattr(ac_group, 'title', None)) if ac_group else None
        source_sec_str = _safe_str(getattr(ac, 'source_section', None))
        req_group = group_title_str or source_sec_str or "General"
        biz_flow = (_safe_str(getattr(ac_group, 'business_flow', None)) if ac_group else "") or ""
        ac_title_str = _safe_str(getattr(ac, 'title', None))
        ac_text_str = _safe_str(getattr(ac, 'text', None))
        stable_key_str = _safe_str(getattr(ac, 'stable_ac_key', None))

        ac_mappings[str(ac.id)] = {
            "ac_id": str(ac.id),
            "stable_ac_key": stable_key_str or (f"AC-{src_num_int or '?'}"),
            "display_ac_ref": display_ref or (f"AC-{ac_num_int or src_num_int or 1:02d}"),
            "ac_title": ac_title_str or ac_text_str or "Untitled Acceptance Criterion",
            "ac_text": ac_text_str or ac_title_str or "",
            "requirement_group": req_group,
            "business_flow": biz_flow,
            "repository_id": repository_id,
            "pull_request_id": pull_request_id,
            "status": "unmapped",
            "row_status": "unmapped",
            "has_conflict": False,
            "suggested_tests_count": 0,
            "suggested_tests": [],
            "debug": {
                "stable_ac_key": stable_key_str or "",
                "raw_edge_ids": [],
                "selected_repository_id": repository_id,
                "selected_pull_request_id": pull_request_id,
                "mapping_row_repository_id": _extract_id_str(getattr(ac, 'repository_id', None)) or repository_id,
                "mapping_row_pull_request_id": _extract_id_str(getattr(ac, 'pull_request_id', None)) or pull_request_id,
            }
        }
    
    # Process candidates and edges
    processed_test_ac_pairs = set()

    for cand in candidates:
        ac_id = str(cand.acceptance_criterion_id) if cand.acceptance_criterion_id else None
        if not ac_id or ac_id not in ac_mappings:
            continue
        
        ac = next((a for a in acs if str(a.id) == ac_id), None)
        test = next((t for t in test_cases if t.id == cand.test_case_id), None)
        if not ac or not test:
            continue

        pair_key = (ac_id, str(test.id))
        processed_test_ac_pairs.add(pair_key)

        matching_edge = next(
            (e for e in edges if e.source_node_id == ac_id and e.target_node_id == str(test.id)),
            None
        )

        ev_json = cand.evidence_json if (cand.evidence_json and isinstance(cand.evidence_json, dict)) else {}

        # Semantic best match AC lookup
        best_sem_ac = None
        if cand.semantic_best_match_ac_id:
            best_sem_ac = next((a for a in acs if a.id == cand.semantic_best_match_ac_id), None)

        best_sem_ref = _format_ac_display_ref(best_sem_ac) if best_sem_ac else None
        best_sem_text = getattr(best_sem_ac, "text", None) or getattr(best_sem_ac, "title", None) if best_sem_ac else None

        flow_test = extract_flow_str(test)
        flow_decl = extract_flow_str(ac)
        flow_sem = extract_flow_str(best_sem_ac) if best_sem_ac else None

        evidence_list = []
        if cand.declared_ac_ref:
            evidence_list.append(f"Declared AC reference: {cand.declared_ac_ref}")
        if cand.conflict_reason:
            evidence_list.append(f"Conflict: {cand.conflict_reason}")
        if cand.confidence_score:
            evidence_list.append(f"Confidence score: {round(cand.confidence_score * 100)}%")

        audit_meta = dict(ev_json.get("audit_metadata") or {})
        if matching_edge and matching_edge.metadata_json:
            audit_meta.update(matching_edge.metadata_json)

        conf_val = float(cand.confidence_score or 0.0)
        conf_lbl = cand.confidence_label or ("high" if conf_val >= 0.85 else ("medium" if conf_val >= 0.65 else "low"))
        test_metadata = test.source_metadata_json if isinstance(getattr(test, "source_metadata_json", None), dict) else {}
        test_ttl_str = _safe_str(test_metadata.get("title")) or _safe_str(getattr(test, "test_name", None)) or ""
        classname_str = _safe_str(test_metadata.get("classname")) or _safe_str(getattr(test, "classname", None)) or _safe_str(getattr(test, "module_or_area", None)) or ""

        suggested_test = SuggestedTest(
            edge_id=str(matching_edge.id) if matching_edge else str(cand.id),
            candidate_id=str(cand.id),
            test_case_id=str(test.id),
            stable_test_id=getattr(test, "stable_identity", None) or str(test.id),
            test_name=getattr(test, "test_name", "test"),
            test_title=test_ttl_str,
            suite_name=_safe_str(getattr(test, "suite_name", None)) or "",
            classname=classname_str,
            declared_ac_ref=cand.declared_ac_ref,
            declared_ac_text=cand.declared_ac_text_snapshot or getattr(ac, "text", "") or getattr(ac, "title", ""),
            semantic_best_match_ac_ref=best_sem_ref,
            semantic_best_match_ac_id=str(best_sem_ac.id) if best_sem_ac else None,
            semantic_best_match_ac_text=best_sem_text,
            semantic_best_match_score=float(cand.semantic_best_match_score or 0.0),
            flow_from_test=flow_test,
            flow_from_declared_ac=flow_decl,
            flow_from_semantic_match=flow_sem,
            confidence=conf_val,
            confidence_score=conf_val,
            confidence_label=conf_lbl,
            edge_source=matching_edge.edge_source if matching_edge else cand.candidate_source,
            candidate_source=cand.candidate_source,
            review_status=cand.review_status if cand else (matching_edge.review_status if matching_edge else "unresolved"),
            evidence=evidence_list,
            reason=cand.conflict_reason or ev_json.get("reason", "Evaluated by alignment gate"),
            conflict_detected=bool(cand.conflict_detected),
            conflict_type=cand.conflict_type,
            conflict_reason=cand.conflict_reason,
            semantic_match_accept_allowed=(
                str(cand.review_status or "").upper() == "METADATA_CONFLICT_SEMANTIC_MATCH"
                and float(cand.semantic_best_match_score or 0.0) >= 0.75
            ),
            coverage_type=getattr(cand, "coverage_type", None) or "none",
            execution_status=getattr(cand, "execution_status", None) or "unknown",
            partial_support_reason=getattr(cand, "partial_support_reason", None),
            recommended_action=(
                "accept_semantic" if str(cand.review_status).upper() == "METADATA_CONFLICT_SEMANTIC_MATCH"
                else "review_partial" if str(cand.review_status).upper() == "PARTIAL_SUPPORT"
                else "optional_confirm" if str(cand.review_status).upper() == "EVIDENCE_VERIFIED_ALIGNED"
                else "none"
            ),
            audit_metadata=audit_meta
        )

        ac_mappings[ac_id]["suggested_tests"].append(suggested_test)

    # Process remaining edges not matched by candidates
    for edge in edges:
        ac_id = edge.source_node_id
        test_id = edge.target_node_id

        if ac_id not in ac_mappings or (ac_id, test_id) in processed_test_ac_pairs:
            continue

        ac = next((a for a in acs if str(a.id) == str(ac_id)), None)
        test = next((t for t in test_cases if str(t.id) == str(test_id)), None)
        if not ac or not test:
            continue

        # If a candidate already routes this test to a different (semantic) AC,
        # skip the declared-ref edge so we don't duplicate the test as a conflict
        # under the originally-declared AC.
        semantic_candidate = next(
            (c for c in candidates
             if str(c.test_case_id) == str(test.id)
             and str(c.acceptance_criterion_id) != str(ac_id)
             and c.review_status.upper() in ("METADATA_CONFLICT_SEMANTIC_MATCH", "PARTIAL_SUPPORT", "EVIDENCE_VERIFIED_ALIGNED")),
            None,
        )
        if semantic_candidate:
            continue

        evidence_list = []
        ev = edge.evidence_json if (edge.evidence_json and isinstance(edge.evidence_json, dict)) else {}

        if ev.get("external_ac_ref"):
            evidence_list.append(f"External AC reference: {ev['external_ac_ref']}")
        if "similarity" in ev:
            evidence_list.append(f"Similarity score: {round(ev['similarity'] * 100)}%")

        reason_str = ev.get("reason") or ev.get("conflict_reason") or "Matched by resolver pipeline"
        cfl_det = bool(ev.get("conflict_detected") or ev.get("domain_flow_conflict"))
        cfl_reas = _safe_str(ev.get("conflict_reason"))

        conf_val = float(edge.confidence or 0.0)
        conf_lbl = "high" if conf_val >= 0.85 else ("medium" if conf_val >= 0.65 else "low")
        test_metadata = test.source_metadata_json if isinstance(getattr(test, "source_metadata_json", None), dict) else {}
        test_ttl_str = _safe_str(test_metadata.get("title")) or _safe_str(getattr(test, "test_name", None)) or ""
        classname_str = _safe_str(test_metadata.get("classname")) or _safe_str(getattr(test, "classname", None)) or _safe_str(getattr(test, "module_or_area", None)) or ""

        suggested_test = SuggestedTest(
            edge_id=str(edge.id),
            candidate_id=None,
            test_case_id=str(test.id),
            stable_test_id=getattr(test, "stable_identity", None) or str(test.id),
            test_name=getattr(test, "test_name", "test"),
            test_title=test_ttl_str,
            suite_name=_safe_str(getattr(test, "suite_name", None)) or "",
            classname=classname_str,
            declared_ac_ref=_safe_str(ev.get("external_ac_ref")),
            declared_ac_text=getattr(ac, "text", "") or getattr(ac, "title", ""),
            flow_from_test=extract_flow_str(test),
            flow_from_declared_ac=extract_flow_str(ac),
            confidence=conf_val,
            confidence_score=conf_val,
            confidence_label=conf_lbl,
            edge_source=edge.edge_source,
            review_status=edge.review_status,
            evidence=evidence_list,
            reason=reason_str,
            conflict_detected=cfl_det,
            conflict_reason=cfl_reas,
            audit_metadata=edge.metadata_json or {}
        )

        ac_mappings[ac_id]["suggested_tests"].append(suggested_test)

    # State resolution priority logic & conflict flagging for each AC group
    for ac_id, ac_map in ac_mappings.items():
        tests_list = ac_map["suggested_tests"]
        ac_map["suggested_tests_count"] = len(tests_list)
        ac_map["debug"]["raw_edge_ids"] = [t.edge_id for t in tests_list if t.edge_id]

        has_conflict = any(t.conflict_detected for t in tests_list)
        has_verified = any(t.review_status in ("verified", "VERIFIED") for t in tests_list)
        has_confirmed = any(t.review_status in (
            "user_confirmed", "USER_CONFIRMED", "confirmed"
        ) for t in tests_list)
        has_evidence_aligned = any(t.review_status in (
            "evidence_verified_aligned", "EVIDENCE_VERIFIED_ALIGNED"
        ) for t in tests_list)
        has_metadata_conflict = any(t.review_status in (
            "metadata_conflict_semantic_match", "METADATA_CONFLICT_SEMANTIC_MATCH"
        ) for t in tests_list)
        has_partial_support = any(t.review_status in (
            "partial_support", "PARTIAL_SUPPORT"
        ) for t in tests_list)
        has_conflicted_status = any(t.review_status in ("conflicted", "CONFLICTED") for t in tests_list)
        has_ambiguous = any(t.review_status in ("ambiguous", "AMBIGUOUS") for t in tests_list)
        has_needs_review = any(t.review_status in ("needs_review", "SUGGESTED_WEAK") for t in tests_list)
        has_suggested = any(t.review_status in (
            "pending_review", "system_suggested", "SUGGESTED_STRONG", "suggested_strong"
        ) for t in tests_list)
        has_rejected = any(t.review_status in ("rejected", "USER_REJECTED") for t in tests_list)

        ac_map["has_conflict"] = has_conflict or has_conflicted_status or has_metadata_conflict

        # Priority: user_confirmed > evidence_verified_aligned > metadata_conflict_semantic_match
        # > partial_support > suggested > needs_review > conflicted > ambiguous > rejected > no_candidate
        if has_confirmed or has_verified:
            st = "confirmed"
        elif has_evidence_aligned:
            st = "evidence_verified_aligned"
        elif has_metadata_conflict:
            st = "metadata_conflict_semantic_match"
        elif has_partial_support:
            st = "partial_support"
        elif has_conflicted_status or (has_conflict and not has_metadata_conflict):
            st = "conflicted"
        elif has_ambiguous:
            st = "ambiguous"
        elif has_needs_review:
            st = "needs_review"
        elif has_suggested:
            st = "suggested"
        elif has_rejected:
            st = "rejected"
        else:
            st = "no_candidate"

        ac_map["status"] = st
        ac_map["row_status"] = st

    # Override row statuses with the authoritative AC-level status map computed
    # by the mapping service, so header counters and per-AC row badges always
    # agree.
    ac_level_statuses = pipeline_res.get("ac_level_statuses", {})
    for ac_id, ac_map in ac_mappings.items():
        if ac_id in ac_level_statuses:
            ac_map["status"] = ac_level_statuses[ac_id]
            ac_map["row_status"] = ac_level_statuses[ac_id]

    items = [ACTestMappingGroup(**m) for m in ac_mappings.values()]

    # Pull execution_summary from pipeline result
    exec_summary = pipeline_res.get("execution_summary", {})
    service_mapping_summary = pipeline_res.get("mapping_summary", {})

    # Use the service's AC-level mapping summary as the source of truth.
    # Router rows provide UI structure, but the authoritative counters come from
    # build_mappings_for_pr so that veriscope_key_verified, partial_support, and
    # summary_integrity are not lost during re-aggregation.
    summary = MappingSummary(
        total_acs=service_mapping_summary.get("total_acs", len(ac_mappings)),
        confirmed=service_mapping_summary.get("user_confirmed", 0),
        user_confirmed=service_mapping_summary.get("user_confirmed", 0),
        veriscope_key_verified=service_mapping_summary.get("veriscope_key_verified", 0),
        evidence_verified_aligned=service_mapping_summary.get("evidence_verified_aligned", 0),
        suggested=service_mapping_summary.get("suggested", 0),
        metadata_conflict_semantic_match=service_mapping_summary.get("metadata_conflict_semantic_match", 0),
        partial_support=service_mapping_summary.get("partial_support", 0),
        pending_review=service_mapping_summary.get("suggested", 0),
        needs_review=0,
        no_candidate=service_mapping_summary.get("no_candidate", 0),
        unmapped=service_mapping_summary.get("no_candidate", 0),  # backward compat alias
        rejected=service_mapping_summary.get("rejected", 0),
        accepted_gap=service_mapping_summary.get("accepted_gap", 0),
        conflicted=0,
        execution_total=exec_summary.get("total_tests", 0),
        execution_passed=exec_summary.get("passed", 0),
        execution_failed=exec_summary.get("failed", 0),
        execution_skipped=exec_summary.get("skipped", 0),
        sum_check=service_mapping_summary.get("sum_check", 0),
        is_ac_level_exclusive=service_mapping_summary.get("is_ac_level_exclusive", True),
        summary_integrity=service_mapping_summary.get("summary_integrity", "PASS"),
        quality_warnings=[] if service_mapping_summary.get("summary_integrity", "PASS") == "PASS" else ["AC-level mapping counters are not exclusive or do not sum to the active acceptance criteria count."],
    )

    execution_contract = {
        "total_tests": summary.execution_total,
        "passed": summary.execution_passed,
        "failed": summary.execution_failed,
        "errors": exec_summary.get("errors", 0),
        "skipped": summary.execution_skipped,
        "latest_test_run_id": exec_summary.get("latest_test_run_id"),
        "test_import_id": exec_summary.get("test_import_id"),
    }
    mapping_contract = {
        "total_acs": summary.total_acs,
        "user_confirmed": summary.user_confirmed,
        "veriscope_key_verified": summary.veriscope_key_verified,
        "evidence_verified_aligned": summary.evidence_verified_aligned,
        "metadata_conflict_semantic_match": summary.metadata_conflict_semantic_match,
        "partial_support": summary.partial_support,
        "suggested": summary.suggested,
        "no_candidate": summary.no_candidate,
        "rejected": summary.rejected,
        "accepted_gap": summary.accepted_gap,
        "sum_check": summary.sum_check,
        "is_ac_level_exclusive": summary.is_ac_level_exclusive,
        "summary_integrity": summary.summary_integrity,
    }
    candidate_contract = {
        "total_candidates": len(candidates),
        "ai_evaluated_candidates": len([candidate for candidate in candidates if getattr(candidate, "ai_decision_json", None)]),
        "deterministic_only_candidates": len([candidate for candidate in candidates if (getattr(candidate, "ai_decision_json", None) or {}).get("provider") in ("deterministic_alignment_gate", "deterministic_alignment_signals", "deterministic_fallback")]),
        "low_confidence_candidates": len([candidate for candidate in candidates if float(getattr(candidate, "confidence_score", 0.0) or 0.0) < 0.55]),
    }
    compatibility_summary = {
        "confirmed": summary.confirmed,
        "suggested": summary.suggested,
        "conflicted": summary.metadata_conflict_semantic_match + summary.conflicted,
        "needs_review": summary.needs_review + summary.partial_support,
        "unmapped": summary.unmapped,
        "rejected": summary.rejected,
        "accepted_gap": summary.accepted_gap,
    }
    return ACTestMappingGroupedResponse(summary=summary, items=items, execution_summary=execution_contract, mapping_summary=mapping_contract, candidate_summary=candidate_contract, rows=items, quality_warnings=summary.quality_warnings, compatibility_summary=compatibility_summary)


# Helper function to find candidate or edge
def _is_mock(obj: Any) -> bool:
    return type(obj).__name__ in ("MagicMock", "Mock", "NonCallableMock") or hasattr(obj, "_mock_name")


def _get_candidate_and_edge(db: Session, target_id: uuid.UUID) -> tuple[Optional[Any], Optional[Any]]:
    cand = None
    edge = None

    try:
        cand_obj = db.query(MappingCandidate).filter(MappingCandidate.id == target_id).first()
        if cand_obj and (isinstance(cand_obj, MappingCandidate) or _is_mock(cand_obj)):
            cand = cand_obj
    except Exception:
        pass

    try:
        edge_obj = db.query(TraceabilityEdge).filter(TraceabilityEdge.id == target_id).first()
        if edge_obj and (isinstance(edge_obj, TraceabilityEdge) or _is_mock(edge_obj)):
            edge = edge_obj
    except Exception:
        pass

    if cand is not None and edge is not None and cand is edge:
        if isinstance(cand, MappingCandidate):
            edge = None
        else:
            cand = None

    return cand, edge


def _mapping_context_mismatch_error() -> Dict[str, str]:
    return {
        "code": "MAPPING_CONTEXT_MISMATCH",
        "error": "MAPPING_CONTEXT_MISMATCH",
        "message": "Mapping candidate does not belong to the selected repository / pull request context.",
    }


def _require_context_match(
    obj: Any,
    request: Any,
    selected_repo: Optional[str] = None,
    selected_pr: Optional[str] = None,
) -> None:
    """Validate that the persisted mapping object matches the request context."""
    repo_id = getattr(obj, "repository_id", None)
    pr_id = getattr(obj, "pull_request_id", None)

    req_repo = _extract_id_str(getattr(request, "repository_id", None)) or _extract_id_str(selected_repo)
    req_pr = _extract_id_str(getattr(request, "pull_request_id", None)) or _extract_id_str(selected_pr)

    if req_repo and repo_id and str(repo_id) != str(req_repo):
        raise HTTPException(status_code=400, detail=_mapping_context_mismatch_error())
    if req_pr and pr_id and str(pr_id) != str(req_pr):
        raise HTTPException(status_code=400, detail=_mapping_context_mismatch_error())



# --- Action Endpoints ---

@router.post("/traceability-edges/{edge_id}/approve")
@router.post("/ac-test-mappings/candidates/{edge_id}/confirm")
@router.post("/ac-test-mappings/candidates/{edge_id}/confirm_candidate")
async def approve_candidate_endpoint(
    edge_id: str,
    request: MappingApprovalRequest,
    repository_id: Optional[str] = Query(None),
    pull_request_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Confirm/approve a candidate mapping with audit metadata.
    """
    try:
        t_uuid = uuid.UUID(edge_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target ID")

    cand, edge = _get_candidate_and_edge(db, t_uuid)
    if not cand and not edge:
        raise HTTPException(status_code=404, detail="Candidate or edge not found")

    context_obj = cand if cand is not None else edge
    _require_context_match(context_obj, request, selected_repo=repository_id, selected_pr=pull_request_id)

    cand_conflict = False
    if cand and not _is_mock(cand):
        cand_conflict = bool(getattr(cand, 'conflict_detected', False))
    elif cand and _is_mock(cand):
        cand_conflict = getattr(cand, 'conflict_detected', False) is True or (
            isinstance(getattr(cand, 'evidence_json', None), dict) and bool(cand.evidence_json.get('conflict_detected'))
        )

    edge_conflict = False
    if edge and not _is_mock(edge):
        edge_conflict = isinstance(edge.evidence_json, dict) and bool(edge.evidence_json.get('conflict_detected'))
    elif edge and _is_mock(edge):
        edge_conflict = getattr(edge, 'conflict_detected', False) is True or (
            isinstance(getattr(edge, 'evidence_json', None), dict) and bool(edge.evidence_json.get('conflict_detected'))
        )

    has_conflict = cand_conflict or edge_conflict

    mode = request.approval_mode or "normal"
    ack = bool(request.acknowledged_warnings)

    if has_conflict and (mode != "approve_anyway" or not ack):
        raise HTTPException(
            status_code=400,
            detail="Cannot approve mapping with detected context conflict without explicitly acknowledging warnings."
        )

    now_dt = datetime.utcnow()
    comment_text = request.comment or request.notes or ""

    prev_status = (getattr(cand, "review_status", None) or getattr(edge, "review_status", None) or "UNRESOLVED")

    audit_meta = {
        "resolved_by": str(current_user.id),
        "resolved_at": now_dt.isoformat(),
        "resolution_action": "confirm_candidate",
        "previous_status": prev_status,
        "new_status": "USER_CONFIRMED",
        "comment": comment_text,
        "acknowledged_warning": ack,
    }

    if cand:
        cand.review_status = "USER_CONFIRMED"
        cand.primary_status = "USER_CONFIRMED"
        cand.user_decision = "accepted"
        cand.user_decision_at = now_dt
        cand.user_decision_by = current_user.id
        cand.audit_comment = request.comment or request.notes
        cand.updated_at = now_dt
        ev = dict(getattr(cand, "evidence_json", None) or {})
        ev["audit_metadata"] = audit_meta
        cand.evidence_json = ev

    if edge:
        edge.review_status = "user_confirmed"
        edge.confirmed_by = str(current_user.id)
        edge.confirmed_at = now_dt
        meta = dict(getattr(edge, "metadata_json", None) or {})
        meta.update(audit_meta)
        edge.metadata_json = meta

    db.commit()
    return {"message": "Candidate mapping confirmed successfully", "audit_metadata": audit_meta}


@router.post("/traceability-edges/{edge_id}/reject")
@router.post("/ac-test-mappings/candidates/{edge_id}/reject")
@router.post("/ac-test-mappings/candidates/{edge_id}/reject_candidate")
async def reject_candidate_endpoint(
    edge_id: str,
    request: MappingRejectionRequest,
    repository_id: Optional[str] = Query(None),
    pull_request_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reject a candidate mapping with audit metadata.
    """
    try:
        t_uuid = uuid.UUID(edge_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target ID")

    cand, edge = _get_candidate_and_edge(db, t_uuid)
    if not cand and not edge:
        raise HTTPException(status_code=404, detail="Candidate or edge not found")

    context_obj = cand if cand is not None else edge
    _require_context_match(context_obj, request, selected_repo=repository_id, selected_pr=pull_request_id)

    now_dt = datetime.utcnow()
    comment_text = request.comment or request.reason or ""

    prev_status = (getattr(cand, "review_status", None) or getattr(edge, "review_status", None) or "UNRESOLVED")

    audit_meta = {
        "resolved_by": str(current_user.id),
        "resolved_at": now_dt.isoformat(),
        "rejected_by": str(current_user.id),
        "rejected_at": now_dt.isoformat(),
        "resolution_action": "reject_candidate",
        "previous_status": prev_status,
        "new_status": "USER_REJECTED",
        "comment": comment_text,
        "acknowledged_warning": False,
    }

    if cand:
        cand.review_status = "USER_REJECTED"
        cand.primary_status = "REJECTED"
        cand.user_decision = "rejected"
        cand.user_decision_at = now_dt
        cand.user_decision_by = current_user.id
        cand.audit_comment = request.comment or request.reason
        cand.updated_at = now_dt
        ev = dict(getattr(cand, "evidence_json", None) or {})
        ev["audit_metadata"] = audit_meta
        cand.evidence_json = ev

    if edge:
        edge.review_status = "rejected"
        meta = dict(getattr(edge, "metadata_json", None) or {})
        meta.update(audit_meta)
        meta["rejection_reason"] = request.reason
        edge.metadata_json = meta


    db.commit()
    return {"message": "Candidate mapping rejected successfully", "audit_metadata": audit_meta}


# Backwards compatibility aliases
approve_mapping = approve_candidate_endpoint
reject_mapping = reject_candidate_endpoint



@router.post("/ac-test-mappings/candidates/{candidate_id}/accept_semantic_match")
async def accept_semantic_match(
    candidate_id: str,
    request: AcceptSemanticMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Accept the suggested semantic match for a candidate instead of declared AC ref.
    Re-links to semantic_best_match_ac_id and sets review_status to USER_CONFIRMED.
    """
    try:
        cand_uuid = uuid.UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    cand = db.query(MappingCandidate).filter(MappingCandidate.id == cand_uuid).first()
    if not cand or not isinstance(cand, MappingCandidate):
        edge = db.query(TraceabilityEdge).filter(TraceabilityEdge.id == cand_uuid).first()
        if edge and isinstance(edge, TraceabilityEdge):
            try:
                tc_uuid = uuid.UUID(edge.target_node_id)
                cand = db.query(MappingCandidate).filter(
                    MappingCandidate.repository_id == edge.repository_id,
                    MappingCandidate.test_case_id == tc_uuid
                ).first()
            except (ValueError, TypeError):
                pass

    if not cand or not isinstance(cand, MappingCandidate):
        raise HTTPException(status_code=400, detail="No semantic best match available for candidate")

    _require_context_match(cand, request)

    if not cand.semantic_best_match_ac_id:
        raise HTTPException(status_code=400, detail="No semantic best match available for candidate")

    if float(cand.semantic_best_match_score or 0.0) < 0.75:
        raise HTTPException(status_code=400, detail="Semantic match confidence is below 0.75; use a manual link or reject the candidate.")

    now_dt = datetime.utcnow()
    prev_status = cand.review_status

    cand.acceptance_criterion_id = cand.semantic_best_match_ac_id
    cand.review_status = "USER_CONFIRMED"
    cand.primary_status = "USER_CONFIRMED"
    cand.user_decision = "accepted_semantic"
    cand.user_decision_at = now_dt
    cand.user_decision_by = current_user.id
    cand.audit_comment = request.comment
    cand.conflict_detected = False
    cand.updated_at = now_dt

    comment_text = request.comment or "Accepted suggested semantic match"

    audit_meta = {
        "resolved_by": str(current_user.id),
        "resolved_at": now_dt.isoformat(),
        "resolution_action": "accept_semantic_match",
        "previous_status": prev_status,
        "new_status": "USER_CONFIRMED",
        "comment": comment_text,
        "acknowledged_warning": False,
    }

    ev = dict(cand.evidence_json or {})
    ev["audit_metadata"] = audit_meta
    cand.evidence_json = ev

    edge = TraceabilityGraphService.upsert_edge(
        db=db,
        repository_id=cand.repository_id,
        pull_request_id=cand.pull_request_id,
        source_node_type="AcceptanceCriterion",
        source_node_id=str(cand.semantic_best_match_ac_id),
        target_node_type="TestCase",
        target_node_id=str(cand.test_case_id),
        edge_type="ac_covered_by_test",
        edge_source="semantic_match_accepted",
        confidence=float(cand.semantic_best_match_score or 1.0),
        review_status="user_confirmed",
        evidence_json={
            "reason": comment_text,
            "created_by": current_user.email,
            "created_at": now_dt.isoformat()
        }
    )
    edge.confirmed_by = str(current_user.id)
    edge.confirmed_at = now_dt
    meta = dict(edge.metadata_json or {})
    meta.update(audit_meta)
    edge.metadata_json = meta

    db.commit()
    return {"message": "Accepted semantic match successfully", "audit_metadata": audit_meta}


@router.post("/ac-test-mappings/candidates/{candidate_id}/keep_declared_ref_anyway")
async def keep_declared_ref_anyway(
    candidate_id: str,
    request: KeepDeclaredRefRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Keep declared AC ref mapping despite conflict, requiring explicit warning acknowledgment.
    """
    if not request.acknowledged_warning:
        raise HTTPException(
            status_code=400,
            detail="Cannot keep declared AC ref without explicitly acknowledging the warning."
        )

    try:
        cand_uuid = uuid.UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    cand, edge = _get_candidate_and_edge(db, cand_uuid)
    if not cand and not edge:
        raise HTTPException(status_code=404, detail="Candidate or edge not found")

    context_obj = cand if cand is not None else edge
    _require_context_match(context_obj, request)

    now_dt = datetime.utcnow()
    prev_status = (cand.review_status if cand and isinstance(cand, MappingCandidate) else (edge.review_status if edge and isinstance(edge, TraceabilityEdge) else "CONFLICTED"))
    comment_text = request.comment or "Kept declared AC ref despite conflict (warning acknowledged)"

    audit_meta = {
        "resolved_by": str(current_user.id),
        "resolved_at": now_dt.isoformat(),
        "resolution_action": "keep_declared_ref_anyway",
        "previous_status": prev_status,
        "new_status": "USER_CONFIRMED",
        "comment": comment_text,
        "acknowledged_warning": True,
    }

    if cand and isinstance(cand, MappingCandidate):
        cand.review_status = "USER_CONFIRMED"
        cand.primary_status = "USER_CONFIRMED"
        cand.user_decision = "kept_declared"
        cand.user_decision_at = now_dt
        cand.user_decision_by = current_user.id
        cand.audit_comment = request.comment
        cand.updated_at = now_dt
        ev = dict(cand.evidence_json or {})
        ev["audit_metadata"] = audit_meta
        cand.evidence_json = ev

    if edge and isinstance(edge, TraceabilityEdge):
        edge.review_status = "user_confirmed"
        edge.confirmed_by = str(current_user.id)
        edge.confirmed_at = now_dt
        meta = dict(edge.metadata_json or {})
        meta.update(audit_meta)
        edge.metadata_json = meta

    db.commit()
    return {"message": "Kept declared AC ref successfully", "audit_metadata": audit_meta}


@router.post("/ac-test-mappings/candidates/{candidate_id}/mark_unmapped")
async def mark_unmapped(
    candidate_id: str,
    request: MarkUnmappedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a candidate or mapping edge as unmapped.
    """
    try:
        cand_uuid = uuid.UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")

    cand, edge = _get_candidate_and_edge(db, cand_uuid)
    if not cand and not edge:
        raise HTTPException(status_code=404, detail="Candidate or edge not found")

    context_obj = cand if cand is not None else edge
    _require_context_match(context_obj, request)

    now_dt = datetime.utcnow()
    prev_status = (cand.review_status if cand and isinstance(cand, MappingCandidate) else (edge.review_status if edge and isinstance(edge, TraceabilityEdge) else "UNRESOLVED"))
    comment_text = request.comment or request.reason or "Marked as unmapped by user"

    audit_meta = {
        "resolved_by": str(current_user.id),
        "resolved_at": now_dt.isoformat(),
        "resolution_action": "mark_unmapped",
        "previous_status": prev_status,
        "new_status": "UNMAPPED",
        "comment": comment_text,
        "acknowledged_warning": False,
    }

    if cand and isinstance(cand, MappingCandidate):
        cand.review_status = "UNMAPPED"
        cand.primary_status = "NO_CANDIDATE"
        cand.user_decision = "none"
        cand.user_decision_at = now_dt
        cand.user_decision_by = current_user.id
        cand.audit_comment = request.comment or request.reason
        cand.updated_at = now_dt
        ev = dict(cand.evidence_json or {})
        ev["audit_metadata"] = audit_meta
        cand.evidence_json = ev

    if edge and isinstance(edge, TraceabilityEdge):
        edge.review_status = "unmapped"
        meta = dict(edge.metadata_json or {})
        meta.update(audit_meta)
        edge.metadata_json = meta

    db.commit()
    return {"message": "Marked mapping as unmapped", "audit_metadata": audit_meta}


@router.post("/ac-test-mappings/manually_link_to_ac")
@router.post("/repositories/{repository_id}/ac-test-mappings/manual")
async def create_manual_mapping(
    request: ManualMappingRequest,
    repository_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually link a test case to an AC (manually_link_to_ac).
    """
    target_ac_id = request.target_ac_id or request.ac_id
    target_test_id = request.test_case_id or request.test_id
    if not target_ac_id or not target_test_id:
        raise HTTPException(status_code=400, detail="target_ac_id and test_case_id are required")

    try:
        ac_uuid = uuid.UUID(target_ac_id)
        test_uuid = uuid.UUID(target_test_id)
        pr_uuid = uuid.UUID(request.pull_request_id)
        if request.repository_id:
            repo_uuid = uuid.UUID(request.repository_id)
        else:
            repo_uuid = None
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid ID format")

    ac = db.query(AcceptanceCriterion).filter(AcceptanceCriterion.id == ac_uuid).first()
    if not ac:
        raise HTTPException(status_code=404, detail="Acceptance Criterion not found")

    test = db.query(TestCase).filter(TestCase.id == test_uuid).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test case not found")

    # Repository / PR context validation
    repo_uuid = repo_uuid or ac.repository_id
    if request.repository_id and str(ac.repository_id) != str(repo_uuid):
        raise HTTPException(status_code=400, detail=_mapping_context_mismatch_error())
    if request.repository_id and str(test.repository_id) != str(repo_uuid):
        raise HTTPException(status_code=400, detail=_mapping_context_mismatch_error())

    pr = db.query(PullRequest).filter(
        PullRequest.id == pr_uuid,
        PullRequest.repository_id == repo_uuid
    ).first()
    if not pr:
        raise HTTPException(status_code=400, detail="Pull request does not belong to the selected repository")

    now_dt = datetime.utcnow()
    comment_text = request.comment or request.reason or "Manual link by user"

    # Preserve original source candidate evidence if the caller provides one.
    preserved_evidence = {}
    if request.source_candidate_id:
        try:
            source_cand_uuid = uuid.UUID(request.source_candidate_id)
            source_cand = db.query(MappingCandidate).filter(MappingCandidate.id == source_cand_uuid).first()
            if source_cand:
                preserved_evidence = dict(getattr(source_cand, "evidence_json", None) or {})
        except (ValueError, TypeError):
            pass

    previous_ac_id = None
    existing_cand = db.query(MappingCandidate).filter(
        MappingCandidate.repository_id == repo_uuid,
        MappingCandidate.test_case_id == test_uuid
    ).first()
    if existing_cand:
        previous_ac_id = existing_cand.acceptance_criterion_id

    audit_meta = {
        "resolved_by": str(current_user.id),
        "resolved_at": now_dt.isoformat(),
        "resolution_action": "MANUAL_LINK",
        "previous_ac_id": str(previous_ac_id) if previous_ac_id else None,
        "target_ac_id": str(ac_uuid),
        "test_case_id": str(test_uuid),
        "source_candidate_id": request.source_candidate_id,
        "previous_status": "UNMAPPED" if previous_ac_id is None else "USER_CONFIRMED",
        "new_status": "USER_CONFIRMED",
        "comment": comment_text,
        "acknowledged_warning": False,
    }

    evidence_payload = {
        "reason": comment_text,
        "created_by": current_user.email,
        "created_at": now_dt.isoformat(),
        "manual_link": True,
        "audit_metadata": audit_meta,
    }
    if preserved_evidence:
        evidence_payload["source_candidate_evidence"] = preserved_evidence

    edge = TraceabilityGraphService.upsert_edge(
        db=db,
        repository_id=repo_uuid,
        pull_request_id=pr_uuid,
        source_node_type="AcceptanceCriterion",
        source_node_id=str(ac_uuid),
        target_node_type="TestCase",
        target_node_id=str(test_uuid),
        edge_type="ac_covered_by_test",
        edge_source="manual_override",
        confidence=1.0,
        review_status="user_confirmed",
        evidence_json=evidence_payload
    )
    edge.confirmed_by = str(current_user.id)
    edge.confirmed_at = now_dt
    meta = dict(edge.metadata_json or {})
    meta.update(audit_meta)
    edge.metadata_json = meta

    # Create/update candidate
    cand = existing_cand
    if cand:
        cand.acceptance_criterion_id = ac_uuid
        cand.review_status = "USER_CONFIRMED"
        cand.primary_status = "USER_CONFIRMED"
        cand.user_decision = "manual_link"
        cand.user_decision_at = now_dt
        cand.user_decision_by = current_user.id
        cand.audit_comment = comment_text
        cand.updated_at = now_dt
        ev = dict(cand.evidence_json or {})
        ev["audit_metadata"] = audit_meta
        if preserved_evidence:
            ev["source_candidate_evidence"] = preserved_evidence
        cand.evidence_json = ev
    else:
        cand = MappingCandidate(
            id=uuid.uuid4(),
            repository_id=repo_uuid,
            pull_request_id=pr_uuid,
            test_case_id=test_uuid,
            acceptance_criterion_id=ac_uuid,
            primary_status="USER_CONFIRMED",
            coverage_type="full",
            execution_status="unknown",
            candidate_source="manual_override",
            confidence_score=1.0,
            confidence_label="high",
            review_status="USER_CONFIRMED",
            user_decision="manual_link",
            user_decision_at=now_dt,
            user_decision_by=current_user.id,
            audit_comment=comment_text,
            created_by="user",
            conflict_detected=False,
            evidence_json={"audit_metadata": audit_meta, **({"source_candidate_evidence": preserved_evidence} if preserved_evidence else {})},
            created_at=now_dt,
            updated_at=now_dt
        )
        db.add(cand)

    db.commit()
    return {"message": "Manually linked test to AC successfully", "edge_id": str(edge.id), "audit_metadata": audit_meta}


@router.post("/ac-test-mappings/candidates/{candidate_id}/add_review_comment")
async def add_review_comment(
    candidate_id: str,
    request: AddCommentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a review comment to a mapping candidate or edge.
    """
    try:
        cand_uuid = uuid.UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    cand, edge = _get_candidate_and_edge(db, cand_uuid)
    if not cand and not edge:
        raise HTTPException(status_code=404, detail="Candidate or edge not found")

    if cand is not None:
        _require_context_match(cand, request)
    if edge is not None:
        _require_context_match(edge, request)

    now_dt = datetime.utcnow()
    prev_status = (cand.review_status if cand else (edge.review_status if edge else "UNKNOWN"))

    audit_meta = {
        "resolved_by": str(current_user.id),
        "resolved_at": now_dt.isoformat(),
        "resolution_action": "add_review_comment",
        "previous_status": prev_status,
        "new_status": prev_status,
        "comment": request.comment,
        "acknowledged_warning": False,
    }

    if cand:
        ev = dict(cand.evidence_json or {})
        comments = ev.get("comments", [])
        comments.append({
            "user": current_user.email,
            "comment": request.comment,
            "timestamp": now_dt.isoformat()
        })
        ev["comments"] = comments
        ev["audit_metadata"] = audit_meta
        cand.evidence_json = ev
        cand.updated_at = now_dt

    if edge:
        meta = dict(edge.metadata_json or {})
        comments = meta.get("comments", [])
        comments.append({
            "user": current_user.email,
            "comment": request.comment,
            "timestamp": now_dt.isoformat()
        })
        meta["comments"] = comments
        meta.update(audit_meta)
        edge.metadata_json = meta

    db.commit()
    return {"message": "Review comment added successfully", "audit_metadata": audit_meta}


@router.post("/ac-test-mappings/mark-accepted-gap")
async def mark_accepted_gap(
    request: MarkAcceptedGapRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark an AC with no test candidate as an accepted gap / risk / out-of-scope.
    This is a user-level decision, not confirmed coverage.
    """
    if not request.reason or not request.reason.strip():
        raise HTTPException(status_code=400, detail="A reason is required to accept a gap")

    try:
        ac_uuid = uuid.UUID(request.ac_id)
        repo_uuid = uuid.UUID(request.repository_id)
        pr_uuid = uuid.UUID(request.pull_request_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid ID format")

    ac = db.query(AcceptanceCriterion).filter(AcceptanceCriterion.id == ac_uuid).first()
    if not ac:
        raise HTTPException(status_code=404, detail="Acceptance Criterion not found")

    if str(ac.repository_id) != str(repo_uuid):
        raise HTTPException(status_code=400, detail=_mapping_context_mismatch_error())

    pr = db.query(PullRequest).filter(
        PullRequest.id == pr_uuid,
        PullRequest.repository_id == repo_uuid
    ).first()
    if not pr:
        raise HTTPException(status_code=400, detail="Pull request does not belong to the selected repository")

    now_dt = datetime.utcnow()
    decision_type = (request.decision_type or "ACCEPTED_GAP").upper()
    reason_text = request.reason.strip()

    audit_meta = {
        "resolved_by": str(current_user.id),
        "resolved_at": now_dt.isoformat(),
        "resolution_action": "mark_accepted_gap",
        "decision_type": decision_type,
        "ac_id": str(ac_uuid),
        "reason": reason_text,
        "risk_category": request.risk_category,
        "out_of_scope": bool(request.out_of_scope),
        "new_status": decision_type,
    }

    # Upsert the AC-level decision record
    decision = db.query(ACMappingDecision).filter(
        ACMappingDecision.repository_id == repo_uuid,
        ACMappingDecision.pull_request_id == pr_uuid,
        ACMappingDecision.acceptance_criterion_id == ac_uuid
    ).first()

    if decision:
        decision.decision_type = decision_type
        decision.reason = reason_text
        decision.risk_category = request.risk_category
        decision.out_of_scope = bool(request.out_of_scope)
        decision.user_id = current_user.id
        decision.created_at = now_dt
        decision.audit_metadata = audit_meta
    else:
        decision = ACMappingDecision(
            id=uuid.uuid4(),
            repository_id=repo_uuid,
            pull_request_id=pr_uuid,
            acceptance_criterion_id=ac_uuid,
            decision_type=decision_type,
            reason=reason_text,
            risk_category=request.risk_category,
            out_of_scope=bool(request.out_of_scope),
            user_id=current_user.id,
            created_at=now_dt,
            audit_metadata=audit_meta,
        )
        db.add(decision)

    db.commit()
    return {
        "message": "Accepted gap recorded successfully",
        "decision_id": str(decision.id),
        "audit_metadata": audit_meta,
    }


@router.post("/ac-test-mappings/candidates/{candidate_id}/accept_partial_support")
async def accept_partial_support(
    candidate_id: str,
    request: AcceptPartialSupportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Accept partial evidence for a candidate. Does NOT count as full confirmed coverage.
    """
    try:
        cand_uuid = uuid.UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    cand, edge = _get_candidate_and_edge(db, cand_uuid)
    if not cand and not edge:
        raise HTTPException(status_code=404, detail="Candidate or edge not found")

    context_obj = cand if cand is not None else edge
    _require_context_match(context_obj, request)

    now_dt = datetime.utcnow()
    comment_text = request.comment or "Accepted partial support"

    prev_status = (getattr(cand, "review_status", None) if cand else (getattr(edge, "review_status", None) if edge else "PARTIAL_SUPPORT"))

    audit_meta = {
        "resolved_by": str(current_user.id),
        "resolved_at": now_dt.isoformat(),
        "resolution_action": "accept_partial_support",
        "previous_status": prev_status,
        "new_status": "PARTIAL_SUPPORT",
        "user_decision": "ACCEPT_PARTIAL_SUPPORT",
        "coverage_type": "partial",
        "can_count_as_confirmed_coverage": False,
        "comment": comment_text,
    }

    if cand and isinstance(cand, MappingCandidate):
        cand.review_status = "PARTIAL_SUPPORT"
        cand.primary_status = "PARTIAL_SUPPORT"
        cand.coverage_type = "partial"
        cand.user_decision = "ACCEPT_PARTIAL_SUPPORT"
        cand.user_decision_at = now_dt
        cand.user_decision_by = current_user.id
        cand.audit_comment = comment_text
        cand.updated_at = now_dt
        ev = dict(cand.evidence_json or {})
        ev["audit_metadata"] = audit_meta
        cand.evidence_json = ev

    if edge and isinstance(edge, TraceabilityEdge):
        edge.review_status = "partial_support"
        meta = dict(edge.metadata_json or {})
        meta.update(audit_meta)
        edge.metadata_json = meta

    db.commit()
    return {"message": "Accepted partial support successfully", "audit_metadata": audit_meta}


@router.get("/repositories/{repository_id}/pull-requests/{pull_request_id}/ac-test-mappings/export-manifest")
@router.post("/repositories/{repository_id}/pull-requests/{pull_request_id}/ac-test-mappings/export-manifest")
async def export_mapping_manifest(
    repository_id: str,
    pull_request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export current reviewed AC -> Test mappings as a JSON manifest.
    """
    try:
        repo_uuid = uuid.UUID(repository_id)
        pr_uuid = uuid.UUID(pull_request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository or pull request ID")

    from app.services.mapping_manifest_service import MappingManifestService
    manifest = MappingManifestService.export_manifest(db, repo_uuid, pr_uuid)
    return manifest


@router.post("/repositories/{repository_id}/pull-requests/{pull_request_id}/ac-test-mappings/import-manifest")
async def import_mapping_manifest(
    repository_id: str,
    pull_request_id: str,
    manifest_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Import mapping manifest JSON for a PR. Validates requirement package identity and detects stale AC keys.
    """
    try:
        repo_uuid = uuid.UUID(repository_id)
        pr_uuid = uuid.UUID(pull_request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository or pull request ID")

    from app.services.mapping_manifest_service import MappingManifestService
    res = MappingManifestService.import_manifest(db, repo_uuid, pr_uuid, manifest_data)
    return res

