import hashlib
import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.requirement_test_alignment_gate import extract_flow_str, token_similarity


@dataclass(frozen=True)
class CandidateEvidence:
    ac_id: str
    ac_ref: str
    ac_text: str
    retrieval_source: str
    retrieval_score: float
    retrieval_reason: str


class ACTestSemanticEvaluator:
    prompt_version = "ac-test-semantic-evaluator.v1"

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}

    def retrieve_candidates(self, test_case: Any, acs: List[Any], declared_ac: Optional[Any] = None) -> List[CandidateEvidence]:
        metadata = getattr(test_case, "source_metadata_json", None) or {}
        title = metadata.get("title", "") if isinstance(metadata, dict) else ""
        classname = metadata.get("classname", "") if isinstance(metadata, dict) else ""
        test_intent = " ".join(filter(None, [getattr(test_case, "test_name", ""), title, classname, extract_flow_str(test_case)]))
        values = []
        for ac in acs:
            ac_intent = " ".join(filter(None, [getattr(ac, "title", ""), getattr(ac, "text", ""), extract_flow_str(ac)]))
            number = getattr(ac, "ac_number", None) or getattr(ac, "source_number", None)
            ac_ref = f"AC-{number:02d}" if isinstance(number, int) else str(getattr(ac, "identifier", None) or getattr(ac, "stable_ac_key", ""))
            is_declared = declared_ac is not None and getattr(declared_ac, "id", None) == getattr(ac, "id", None)
            values.append(CandidateEvidence(str(getattr(ac, "id", "")), ac_ref, getattr(ac, "text", None) or getattr(ac, "title", "") or "", "declared_xml_ref" if is_declared else "semantic_text", float(token_similarity(test_intent, ac_intent)), "Declared XML reference" if is_declared else "Normalized semantic intent similarity"))
        values.sort(key=lambda candidate: (candidate.retrieval_source == "declared_xml_ref", candidate.retrieval_score), reverse=True)
        return values[:settings.AC_TEST_MAPPING_AI_MAX_CANDIDATES]

    def evaluate_test_against_candidates(self, test_case: Any, candidate_acs: List[CandidateEvidence], declared_ac: Optional[Any], execution_status: Optional[str], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cache_key = hashlib.sha256(repr((self.prompt_version, getattr(test_case, "id", None), execution_status, candidate_acs)).encode()).hexdigest()
        if settings.AC_TEST_MAPPING_AI_CACHE_ENABLED and cache_key in self._cache:
            return self._cache[cache_key]
        provider_decision = self._evaluate_with_provider(test_case, candidate_acs, declared_ac, execution_status)
        if provider_decision is not None:
            result = provider_decision
            result["audit"] = {"prompt_version": self.prompt_version, "provider": settings.AC_TEST_MAPPING_AI_PROVIDER, "model": settings.AC_TEST_MAPPING_AI_MODEL, "ai_status": "available", "fallback_used": False, "candidate_refs": [item.ac_ref for item in candidate_acs], "cache_key": cache_key}
            if settings.AC_TEST_MAPPING_AI_CACHE_ENABLED:
                self._cache[cache_key] = result
            return result
        alignment = (context or {}).get("alignment_result")
        if alignment is not None:
            result = self._evaluate_alignment_signals(alignment, candidate_acs, execution_status)
            result["audit"] = {"prompt_version": self.prompt_version, "provider": "deterministic_alignment_signals", "ai_status": "disabled" if not settings.AC_TEST_MAPPING_AI_ENABLED else "unavailable", "fallback_used": True, "candidate_refs": [item.ac_ref for item in candidate_acs], "cache_key": cache_key}
            if settings.AC_TEST_MAPPING_AI_CACHE_ENABLED:
                self._cache[cache_key] = result
            return result
        best = max(candidate_acs, key=lambda candidate: candidate.retrieval_score, default=None)
        declared = next((candidate for candidate in candidate_acs if candidate.retrieval_source == "declared_xml_ref"), None)
        score = best.retrieval_score if best else 0.0
        same_declared = bool(best and declared and best.ac_id == declared.ac_id)
        passed = str(execution_status or "unknown").lower() == "passed"
        if best and declared and not same_declared and score >= 0.75:
            status, coverage = "METADATA_CONFLICT_SEMANTIC_MATCH", "full"
        elif best and same_declared and score >= 0.85 and passed:
            status, coverage = "EVIDENCE_VERIFIED_ALIGNED", "full"
        elif best and score >= 0.55:
            status, coverage = "SUGGESTED", "partial" if score < 0.7 else "full"
        else:
            status, coverage = "NO_CANDIDATE", "none"
        partial = [{"ac_ref": item.ac_ref, "confidence": item.retrieval_score, "reason": "Evidence overlaps this AC but does not establish its full requirement."} for item in candidate_acs if item != best and item.retrieval_score >= 0.55]
        result = {"semantic_best_match": {"ac_ref": best.ac_ref if best else None, "coverage_type": coverage, "confidence": score, "reason": best.retrieval_reason if best else "No candidate met the evidence threshold."}, "declared_ref_assessment": {"declared_ref": declared.ac_ref if declared else None, "declared_ref_resolves": declared is not None, "declared_ref_matches_semantic_meaning": same_declared, "reason": "Declared metadata is evaluated independently from semantic meaning."}, "status_recommendation": {"status": status, "requires_user_review": status != "EVIDENCE_VERIFIED_ALIGNED", "reason": "Deterministic fallback evaluation."}, "partial_support": partial, "evidence": {"test_name_signal": getattr(test_case, "test_name", ""), "flow_signal": extract_flow_str(test_case), "execution_signal": execution_status or "unknown"}, "risks": [], "audit": {"prompt_version": self.prompt_version, "provider": "deterministic_fallback", "ai_status": "disabled" if not settings.AC_TEST_MAPPING_AI_ENABLED else "unavailable", "fallback_used": True, "candidate_refs": [item.ac_ref for item in candidate_acs], "cache_key": cache_key}}
        if settings.AC_TEST_MAPPING_AI_CACHE_ENABLED:
            self._cache[cache_key] = result
        return result

    def _evaluate_alignment_signals(self, alignment: Any, candidates: List[CandidateEvidence], execution_status: Optional[str]) -> Dict[str, Any]:
        status = str(getattr(alignment, "review_status", "unresolved")).upper()
        status = {"VERIFIED": "VERISCOPE_KEY_VERIFIED", "CONFLICTED": "METADATA_CONFLICT_SEMANTIC_MATCH", "SUGGESTED_STRONG": "SUGGESTED", "SUGGESTED_WEAK": "SUGGESTED", "UNRESOLVED": "NO_CANDIDATE"}.get(status, status)
        semantic_ref = getattr(alignment, "semantic_ac_ref_for_conflict", None) or getattr(alignment, "semantic_best_match_ac_ref", None)
        candidate_refs = {candidate.ac_ref for candidate in candidates}
        if semantic_ref not in candidate_refs:
            status = "NO_CANDIDATE"
            semantic_ref = None
        coverage = "partial" if status == "PARTIAL_SUPPORT" else ("full" if status in {"VERISCOPE_KEY_VERIFIED", "EVIDENCE_VERIFIED_ALIGNED", "METADATA_CONFLICT_SEMANTIC_MATCH"} else "none")
        return {"semantic_best_match": {"ac_ref": semantic_ref, "coverage_type": coverage, "confidence": float(getattr(alignment, "confidence_score", 0.0)), "reason": getattr(alignment, "reason", "Deterministic alignment evaluation.")}, "declared_ref_assessment": {"declared_ref": getattr(alignment, "declared_ac_ref", None), "declared_ref_resolves": bool(getattr(alignment, "declared_ac_exists", False)), "declared_ref_matches_semantic_meaning": bool(getattr(alignment, "declared_ref_matches_semantics", False)), "reason": "Normalized declared-reference evidence."}, "status_recommendation": {"status": status, "requires_user_review": status not in {"VERISCOPE_KEY_VERIFIED", "EVIDENCE_VERIFIED_ALIGNED"}, "reason": getattr(alignment, "reason", "Deterministic alignment evaluation.")}, "partial_support": [{"ac_ref": ref, "confidence": 0.55, "reason": getattr(alignment, "partial_support_reason", None) or "Partial support identified."} for ref in getattr(alignment, "partial_support_ac_refs", []) if ref in candidate_refs], "evidence": {"execution_signal": execution_status or "unknown"}, "risks": []}

    def _evaluate_with_provider(self, test_case: Any, candidates: List[CandidateEvidence], declared_ac: Optional[Any], execution_status: Optional[str]) -> Optional[Dict[str, Any]]:
        if not settings.AC_TEST_MAPPING_AI_ENABLED or settings.AC_TEST_MAPPING_AI_PROVIDER.lower() not in {"openai", "openrouter"} or not settings.AC_TEST_MAPPING_AI_API_KEY:
            return None
        payload = {"model": settings.AC_TEST_MAPPING_AI_MODEL or "gpt-4o-mini", "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": "You are a QA traceability reviewer. Return only JSON with semantic_best_match, declared_ref_assessment, status_recommendation, partial_support, evidence, and risks. Only select AC refs supplied by the user."}, {"role": "user", "content": json.dumps({"test_case": {"test_name": getattr(test_case, "test_name", ""), "test_title": (getattr(test_case, "source_metadata_json", None) or {}).get("title", ""), "classname": (getattr(test_case, "source_metadata_json", None) or {}).get("classname", ""), "declared_xml_ref": self._display_ref(declared_ac) if declared_ac else None, "execution_status": execution_status or "unknown"}, "candidate_acs": [{"display_ref": item.ac_ref, "text": item.ac_text, "retrieval_source": item.retrieval_source, "retrieval_score": item.retrieval_score} for item in candidates]})}]}
        url = (settings.AC_TEST_MAPPING_AI_BASE_URL or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        request = Request(url, data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {settings.AC_TEST_MAPPING_AI_API_KEY}", "Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=settings.AC_TEST_MAPPING_AI_TIMEOUT_SECONDS) as response:
                parsed = json.loads(response.read().decode())
            content = parsed["choices"][0]["message"]["content"]
            decision = json.loads(content)
            return decision if self._is_valid_decision(decision, candidates) else None
        except (KeyError, TypeError, ValueError, URLError, TimeoutError):
            return None

    @staticmethod
    def _display_ref(ac: Optional[Any]) -> Optional[str]:
        if not ac:
            return None
        number = getattr(ac, "ac_number", None) or getattr(ac, "source_number", None)
        return f"AC-{number:02d}" if isinstance(number, int) else getattr(ac, "identifier", None) or getattr(ac, "stable_ac_key", None)

    @staticmethod
    def _is_valid_decision(decision: Dict[str, Any], candidates: List[CandidateEvidence]) -> bool:
        semantic = decision.get("semantic_best_match") or {}
        recommendation = decision.get("status_recommendation") or {}
        refs = {item.ac_ref for item in candidates}
        try:
            confidence = float(semantic.get("confidence"))
        except (TypeError, ValueError):
            return False
        return recommendation.get("status") in {"EVIDENCE_VERIFIED_ALIGNED", "METADATA_CONFLICT_SEMANTIC_MATCH", "PARTIAL_SUPPORT", "SUGGESTED", "NO_CANDIDATE"} and 0 <= confidence <= 1 and bool(semantic.get("reason")) and (semantic.get("ac_ref") is None or semantic.get("ac_ref") in refs) and all(item.get("ac_ref") in refs and bool(item.get("reason")) for item in decision.get("partial_support", []))
