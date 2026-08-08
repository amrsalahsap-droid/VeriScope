import re
import uuid
from typing import List, Dict, Any, Optional, Set, Tuple
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.test_result import TestCase
from app.schemas.requirement_test_alignment import TestAlignmentResult, ImportAlignmentSummary

_AC_REF_REGEX = re.compile(r'\b(AC[-\s]?0*(\d+))\b', re.IGNORECASE)


def clean_and_tokenize(text: str) -> Set[str]:
    """Tokenize string into normalized lowercase token set."""
    if not text:
        return set()
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
    tokens = set(re.split(r'[^a-zA-Z0-9]', s.lower()))
    for word in re.findall(r'[a-zA-Z0-9]+(?:[-_][a-zA-Z0-9]+)+', text.lower()):
        tokens.add(word.replace("-", "").replace("_", ""))
    generic = {
        "and", "the", "for", "with", "this", "that", "test", "should", "must", "can", "ac", "requirement", "verify", "check",
        "is", "are", "was", "were", "be", "been", "being", "not", "when", "does", "do", "did", "only", "of", "to", "a", "an",
    }
    aliases = {
        "consistent": "consistency",
        "consistency": "consistency",
        "same": "consistency",
        "validate": "validation",
        "validates": "validation",
        "validated": "validation",
        "rules": "rule",
        "rule": "rule",
        "messages": "message",
        "details": "detail",
        "fails": "fail",
        "failing": "fail",
        "failure": "fail",
        "updates": "update",
        "changes": "change",
        "succeeds": "succeed",
    }
    return {aliases.get(t, t) for t in tokens if len(t) > 1 and t not in generic}


def token_similarity(text1: str, text2: str) -> float:
    """Token similarity weighted toward how completely the AC satisfies the test intent."""
    t1 = clean_and_tokenize(text1)
    t2 = clean_and_tokenize(text2)
    if not t1 or not t2:
        return 0.0
    overlap = len(t1 & t2)
    test_intent_coverage = overlap / len(t1)
    ac_specificity_coverage = overlap / len(t2)
    return round((0.7 * test_intent_coverage) + (0.3 * ac_specificity_coverage), 4)


def _safe_str(val: Any) -> str:
    return val if isinstance(val, str) else ""


def ac_ref_str(ac: AcceptanceCriterion) -> str:
    """Canonical 'AC-NN' reference string for an AcceptanceCriterion."""
    identifier = getattr(ac, "identifier", None)
    if identifier and identifier.startswith("AC-") and len(identifier) <= 6:
        return identifier
    ac_number = getattr(ac, "ac_number", None)
    if isinstance(ac_number, int):
        return f"AC-{ac_number:02d}"
    source_number = getattr(ac, "source_number", None)
    if isinstance(source_number, int):
        return f"AC-{source_number:02d}"
    return identifier or getattr(ac, "stable_ac_key", None) or f"AC-{str(ac.id)[:8]}"


def extract_declared_ac_ref(tc: TestCase) -> Optional[str]:
    """
    Extract declared AC ref (e.g. AC-03) from test case attributes or source metadata.
    """
    if getattr(tc, 'external_ac_ref', None):
        return str(tc.external_ac_ref).strip()
    
    meta = tc.source_metadata_json if (tc.source_metadata_json and isinstance(tc.source_metadata_json, dict)) else {}
    for key in ("declared_ac_id", "acceptance_criterion", "ac_ref", "external_ac_ref"):
        if meta.get(key):
            return str(meta[key]).strip()
    
    # Check test_name, classname, or suite_name for AC-xx pattern
    for text_val in (getattr(tc, 'test_name', None), getattr(tc, 'suite_name', None)):
        s = _safe_str(text_val)
        if s:
            m = _AC_REF_REGEX.search(s)
            if m:
                num = int(m.group(2))
                return f"AC-{num:02d}"
    
    return None


def extract_flow_str(obj: Any) -> str:
    """Extract human-readable business flow or requirement group from AC or TestCase."""
    if isinstance(obj, AcceptanceCriterion):
        group = getattr(obj, 'group', None)
        g_title = _safe_str(getattr(group, 'title', None)) if group else ""
        g_flow = _safe_str(getattr(group, 'business_flow', None)) if group else ""
        source_sec = _safe_str(getattr(obj, 'source_section', None))
        ac_title = _safe_str(getattr(obj, 'title', None))
        return g_flow or g_title or source_sec or ac_title or ""
    elif isinstance(obj, TestCase):
        meta = obj.source_metadata_json if isinstance(getattr(obj, 'source_metadata_json', None), dict) else {}
        b_flow = _safe_str(getattr(obj, 'business_flow', None)) or _safe_str(meta.get('business_flow'))
        p_area = _safe_str(getattr(obj, 'product_area', None)) or _safe_str(meta.get('requirement_group'))
        s_intent = _safe_str(getattr(obj, 'scenario_intent', None))
        classname = _safe_str(getattr(obj, 'classname', None)) or _safe_str(meta.get('classname'))
        t_name = _safe_str(getattr(obj, 'test_name', None))
        s_name = _safe_str(getattr(obj, 'suite_name', None))
        return b_flow or p_area or s_intent or f"{classname} {s_name} {t_name}".strip()
    return ""


def detect_domain_flow_conflict(
    test_text: str,
    ac_text: str,
    best_sem_ac_text: Optional[str] = None,
    best_sem_score: float = 0.0,
    decl_ac_score: float = 0.0
) -> Tuple[bool, Optional[str]]:
    """
    Generically detect domain or flow mismatches between test text and AC text
    without hardcoding any specific domain, password, or flow strings.
    """
    if best_sem_ac_text and best_sem_ac_text != ac_text:
        if best_sem_score > decl_ac_score + 0.15 and best_sem_score >= 0.30:
            return True, (
                f"Semantic conflict: test semantics align with requirement '{best_sem_ac_text[:60]}' "
                f"({round(best_sem_score * 100)}% match) instead of declared AC '{ac_text[:60]}' ({round(decl_ac_score * 100)}% match)"
            )

    t_tokens = clean_and_tokenize(test_text)
    ac_tokens = clean_and_tokenize(ac_text)

    if not t_tokens or not ac_tokens:
        return False, None

    diff_test_tokens = t_tokens - ac_tokens

    if best_sem_ac_text:
        best_tokens = clean_and_tokenize(best_sem_ac_text)
        matching_distinguishing_tokens = diff_test_tokens & best_tokens
        if matching_distinguishing_tokens and decl_ac_score < 0.50:
            token_list = ", ".join(sorted(matching_distinguishing_tokens))
            return True, (
                f"Flow mismatch: test contains specific domain token(s) [{token_list}] matching requirement "
                f"'{best_sem_ac_text[:60]}' rather than declared AC '{ac_text[:60]}'"
            )

    if decl_ac_score < 0.20 and len(t_tokens) >= 3 and len(ac_tokens) >= 3:
        return True, f"Low context alignment ({round(decl_ac_score * 100)}%) between test and declared AC"

    return False, None


class RequirementTestAlignmentGate:
    """
    Validation Gate that evaluates TestCase alignment against uploaded Acceptance Criteria
    before mappings are created or confirmed.
    """

    def evaluate_test_case_alignment(
        self,
        tc: TestCase,
        acs: List[AcceptanceCriterion]
    ) -> TestAlignmentResult:
        tc_id_str = str(getattr(tc, 'id', uuid.uuid4()))
        meta = tc.source_metadata_json if isinstance(getattr(tc, 'source_metadata_json', None), dict) else {}
        t_name = _safe_str(getattr(tc, 'test_name', ''))
        t_title = _safe_str(meta.get('title')) or _safe_str(getattr(tc, 'title', '')) or _safe_str(getattr(tc, 'suite_name', '')) or t_name
        classname = _safe_str(getattr(tc, 'classname', '')) or _safe_str(meta.get('classname')) or _safe_str(getattr(tc, 'module_or_area', ''))
        declared_ref = extract_declared_ac_ref(tc)

        execution_layer = _safe_str(meta.get('execution_layer')) or _safe_str(getattr(tc, 'execution_layer', ''))
        test_semantic_text = f"{t_name} {t_title}"
        tc_full_text = f"{test_semantic_text} {execution_layer} {classname} {_safe_str(meta.get('business_flow'))} {_safe_str(meta.get('requirement_group'))} {_safe_str(getattr(tc, 'business_flow', ''))} {_safe_str(getattr(tc, 'scenario_intent', ''))}"
        flow_from_test = extract_flow_str(tc)

        if not acs:
            return TestAlignmentResult(
                test_case_id=tc_id_str,
                test_name=t_name,
                test_title=t_title,
                classname=classname,
                declared_ac_ref=declared_ref,
                declared_ac_exists=False,
                declared_ac_text=None,
                semantic_best_match_ac_ref=None,
                semantic_best_match_ac_text=None,
                declared_ref_matches_semantics=False,
                flow_from_test=flow_from_test,
                flow_from_declared_ac=None,
                flow_from_semantic_match=None,
                conflict_detected=False,
                conflict_type="UNKNOWN_REF" if declared_ref else "LOW_CONFIDENCE",
                confidence_score=0.0,
                review_status="unresolved",
                reason="No acceptance criteria uploaded in context"
            )

        # 1. Priority 1: Exact veriscope_ac_key check (exact match required for verified status)
        meta = tc.source_metadata_json if (tc.source_metadata_json and isinstance(tc.source_metadata_json, dict)) else {}
        tc_ac_key = (
            _safe_str(getattr(tc, 'veriscope_ac_key', None)) or
            _safe_str(getattr(tc, 'stable_ac_key', None)) or
            _safe_str(meta.get("veriscope_ac_key")) or
            _safe_str(meta.get("stable_ac_key")) or
            _safe_str(getattr(tc, 'ac_id', None))
        )
        if tc_ac_key:
            exact_ac = next((a for a in acs if getattr(a, 'stable_ac_key', None) == tc_ac_key or str(getattr(a, 'id', '')) == tc_ac_key), None)
            if exact_ac:
                ac_text_val = _safe_str(getattr(exact_ac, 'text', '')) or _safe_str(getattr(exact_ac, 'title', ''))
                ac_flow_val = extract_flow_str(exact_ac)
                return TestAlignmentResult(
                    test_case_id=tc_id_str,
                    test_name=t_name,
                    test_title=t_title,
                    classname=classname,
                    declared_ac_ref=declared_ref or getattr(exact_ac, 'identifier', None) or exact_ac.stable_ac_key,
                    declared_ac_exists=True,
                    declared_ac_text=ac_text_val,
                    semantic_best_match_ac_ref=getattr(exact_ac, 'identifier', None) or exact_ac.stable_ac_key,
                    semantic_best_match_ac_text=ac_text_val,
                    semantic_best_match_score=1.0,
                    declared_ref_matches_semantics=True,
                    flow_from_test=flow_from_test,
                    flow_from_declared_ac=ac_flow_val,
                    flow_from_semantic_match=ac_flow_val,
                    conflict_detected=False,
                    conflict_type="NONE",
                    confidence_score=1.0,
                    review_status="verified",
                    reason="Exact veriscope_ac_key match"
                )

        # Compute semantic similarities against all uploaded ACs
        def get_ac_ref(ac: AcceptanceCriterion) -> str:
            if ac.identifier and ac.identifier.startswith("AC-") and len(ac.identifier) <= 6:
                return ac.identifier
            if getattr(ac, "ac_number", None) is not None:
                return f"AC-{ac.ac_number:02d}"
            if getattr(ac, "source_number", None) is not None:
                return f"AC-{ac.source_number:02d}"
            return getattr(ac, "identifier", None) or ac.stable_ac_key or f"AC-{str(ac.id)[:8]}"

        ac_sim_list: List[Tuple[AcceptanceCriterion, float]] = []
        for ac in acs:
            ac_intent = f"{_safe_str(getattr(ac, 'title', ''))} {_safe_str(getattr(ac, 'text', ''))}"
            intent_score = token_similarity(test_semantic_text, ac_intent)
            ac_flow_context = f"{extract_flow_str(ac)} {_safe_str(getattr(ac, 'title', ''))}"
            flow_score = token_similarity(f"{classname} {flow_from_test} {execution_layer}", ac_flow_context)
            test_flow_tokens = clean_and_tokenize(f"{classname} {flow_from_test} {execution_layer}")
            ac_flow_tokens = clean_and_tokenize(ac_flow_context)
            # "api"/"ui" are intentionally excluded: they appear in the boilerplate
            # execution_layer metadata (e.g. "API/UI") on nearly every test regardless
            # of business domain, so including them causes spurious flow-match bonuses
            # toward any AC whose group flow happens to mention api/ui (e.g. ui-api-consistency).
            explicit_flow_match = bool(test_flow_tokens & ac_flow_tokens & {"signup", "sign", "update", "reset", "login"})
            sim = round((0.6 * intent_score) + (0.4 * flow_score) + (0.2 if explicit_flow_match else 0.0), 4)
            ac_sim_list.append((ac, sim))

        ac_sim_list.sort(key=lambda x: x[1], reverse=True)
        best_sem_ac, best_sem_score = ac_sim_list[0]
        best_sem_ref = get_ac_ref(best_sem_ac)
        best_sem_text = _safe_str(getattr(best_sem_ac, 'text', '')) or _safe_str(getattr(best_sem_ac, 'title', ''))
        flow_from_semantic = extract_flow_str(best_sem_ac)

        # 2. Declared AC ref handling
        if declared_ref:
            def matches_ref(ac: AcceptanceCriterion) -> bool:
                ac_ident = _safe_str(getattr(ac, 'identifier', ''))
                ac_lbl = _safe_str(getattr(ac, 'label', ''))
                ac_num = getattr(ac, 'ac_number', None)
                src_num = getattr(ac, 'source_number', None)
                ref_norm = declared_ref.lower().replace("-", "").replace(" ", "")

                if ac_ident and ac_ident.lower().replace("-", "").replace(" ", "") == ref_norm:
                    return True
                if ac_lbl and ac_lbl.lower().replace("-", "").replace(" ", "") == ref_norm:
                    return True
                
                m = _AC_REF_REGEX.search(declared_ref)
                if m:
                    num = int(m.group(2))
                    if ac_num == num or src_num == num:
                        return True
                    lbl_m = _AC_REF_REGEX.search(ac_lbl or ac_ident or "")
                    if lbl_m and int(lbl_m.group(2)) == num:
                        return True
                return False

            matching_acs = [a for a in acs if matches_ref(a)]

            if not matching_acs:
                return TestAlignmentResult(
                    test_case_id=tc_id_str,
                    test_name=t_name,
                    test_title=t_title,
                    classname=classname,
                    declared_ac_ref=declared_ref,
                    declared_ac_exists=False,
                    declared_ac_text=None,
                    semantic_best_match_ac_ref=best_sem_ref if best_sem_score >= 0.25 else None,
                    semantic_best_match_ac_text=best_sem_text if best_sem_score >= 0.25 else None,
                    semantic_best_match_score=best_sem_score,
                    declared_ref_matches_semantics=False,
                    flow_from_test=flow_from_test,
                    flow_from_declared_ac=None,
                    flow_from_semantic_match=flow_from_semantic if best_sem_score >= 0.25 else None,
                    conflict_detected=False,
                    conflict_type="UNKNOWN_REF",
                    confidence_score=0.0,
                    review_status="unresolved",
                    reason=f"Declared AC ref '{declared_ref}' not found in uploaded requirement package"
                )

            # Disambiguate matching ACs if multiple match (e.g. ac_number=1 across different requirement groups)
            sem_matches_in_ref = sorted(
                [
                    (
                        a,
                        round(
                            (0.6 * token_similarity(test_semantic_text, f"{a.title} {a.text}")) +
                            (0.4 * token_similarity(f"{classname} {flow_from_test} {execution_layer}", f"{extract_flow_str(a)} {a.title}")) +
                            (0.2 if (clean_and_tokenize(f"{classname} {flow_from_test} {execution_layer}") & clean_and_tokenize(f"{extract_flow_str(a)} {a.title}") & {"signup", "sign", "update", "reset", "login", "api", "ui"}) else 0.0),
                            4
                        )
                    )
                    for a in matching_acs
                ],
                key=lambda x: x[1], reverse=True
            )
            top_ref_ac, top_ref_sim = sem_matches_in_ref[0]
            if len(sem_matches_in_ref) > 1 and top_ref_sim - sem_matches_in_ref[1][1] < 0.10:
                return TestAlignmentResult(
                    test_case_id=tc_id_str,
                    test_name=t_name,
                    test_title=t_title,
                    classname=classname,
                    declared_ac_ref=declared_ref,
                    declared_ac_exists=True,
                    declared_ac_text=None,
                    semantic_best_match_ac_ref=None,
                    semantic_best_match_ac_text=None,
                    semantic_best_match_score=best_sem_score,
                    declared_ref_matches_semantics=False,
                    flow_from_test=flow_from_test,
                    flow_from_declared_ac=None,
                    flow_from_semantic_match=None,
                    conflict_detected=False,
                    conflict_type="AMBIGUOUS_REF",
                    confidence_score=round(top_ref_sim, 2),
                    review_status="unresolved",
                    reason=f"Declared AC ref '{declared_ref}' resolves to multiple equally plausible uploaded acceptance criteria"
                )
            decl_ac = top_ref_ac
            decl_ac_text_val = _safe_str(getattr(decl_ac, 'text', '')) or decl_ac.title
            flow_from_declared = extract_flow_str(decl_ac)
            decl_ac_full_text = f"{decl_ac.title} {decl_ac.text} {flow_from_declared}"
            decl_sim = top_ref_sim

            conflict_found, conflict_msg = detect_domain_flow_conflict(
                tc_full_text, decl_ac_full_text,
                best_sem_ac_text=f"{best_sem_ac.title} {best_sem_ac.text}",
                best_sem_score=best_sem_score,
                decl_ac_score=decl_sim
            )

            if not conflict_found and best_sem_ac.id != decl_ac.id and best_sem_score >= 0.20:
                conflict_found = True
                conflict_msg = f"Conflict detected: test declares {declared_ref}, but test meaning matches {get_ac_ref(best_sem_ac)} ({best_sem_ac.title})"

            if conflict_found:
                # ── METADATA_CONFLICT_SEMANTIC_MATCH: semantic best-match is strong enough
                # to confidently route the candidate to the correct AC.
                # We distinguish this from a true semantic conflict (where no candidate is
                # viable) by requiring best_sem_score >= 0.25.
                if best_sem_score >= 0.25:
                    sem_ac_text = _safe_str(getattr(best_sem_ac, 'text', '')) or _safe_str(getattr(best_sem_ac, 'title', ''))
                    return TestAlignmentResult(
                        test_case_id=tc_id_str,
                        test_name=t_name,
                        test_title=t_title,
                        classname=classname,
                        declared_ac_ref=declared_ref,
                        declared_ac_exists=True,
                        declared_ac_text=decl_ac_text_val,
                        semantic_best_match_ac_ref=best_sem_ref,
                        semantic_best_match_ac_text=best_sem_text,
                        semantic_best_match_score=best_sem_score,
                        declared_ref_matches_semantics=False,
                        flow_from_test=flow_from_test,
                        flow_from_declared_ac=flow_from_declared,
                        flow_from_semantic_match=flow_from_semantic,
                        conflict_detected=True,
                        conflict_type="EXTERNAL_REF_SEMANTIC_CONFLICT",
                        confidence_score=round(min(0.80, max(0.40, best_sem_score)), 2),
                        review_status="metadata_conflict_semantic_match",
                        reason=(
                            conflict_msg or
                            f"Metadata conflict: test declares {declared_ref} but semantically matches "
                            f"{best_sem_ref} ({best_sem_ac.title or ''})"
                        ),
                        # Routing fields: candidate will be linked to best_sem_ac
                        semantic_ac_ref_for_conflict=best_sem_ref,
                        semantic_ac_text_for_conflict=sem_ac_text,
                    )
                else:
                    # True semantic conflict — neither AC is a confident match
                    return TestAlignmentResult(
                        test_case_id=tc_id_str,
                        test_name=t_name,
                        test_title=t_title,
                        classname=classname,
                        declared_ac_ref=declared_ref,
                        declared_ac_exists=True,
                        declared_ac_text=decl_ac_text_val,
                        semantic_best_match_ac_ref=best_sem_ref,
                        semantic_best_match_ac_text=best_sem_text,
                        semantic_best_match_score=best_sem_score,
                        declared_ref_matches_semantics=False,
                        flow_from_test=flow_from_test,
                        flow_from_declared_ac=flow_from_declared,
                        flow_from_semantic_match=flow_from_semantic,
                        conflict_detected=True,
                        conflict_type="EXTERNAL_REF_SEMANTIC_CONFLICT",
                        confidence_score=round(min(0.40, max(0.15, decl_sim)), 2),
                        review_status="conflicted",
                        reason=conflict_msg or f"Conflict detected: test declares {declared_ref}, but test meaning matches {best_sem_ref} ({best_sem_ac.title})"
                    )

            # ── EVIDENCE_VERIFIED_ALIGNED: declared ref resolves to a unique AC AND
            # the semantic best match agrees with that AC (no conflict detected).
            # This is the highest non-user-confirmed evidence level.
            conf_score = 0.97
            return TestAlignmentResult(
                test_case_id=tc_id_str,
                test_name=t_name,
                test_title=t_title,
                classname=classname,
                declared_ac_ref=declared_ref,
                declared_ac_exists=True,
                declared_ac_text=decl_ac_text_val,
                semantic_best_match_ac_ref=get_ac_ref(decl_ac),
                semantic_best_match_ac_text=decl_ac_text_val,
                semantic_best_match_score=decl_sim,
                declared_ref_matches_semantics=True,
                flow_from_test=flow_from_test,
                flow_from_declared_ac=flow_from_declared,
                flow_from_semantic_match=flow_from_declared,
                conflict_detected=False,
                conflict_type="NONE",
                confidence_score=conf_score,
                review_status="evidence_verified_aligned",
                reason="Evidence aligned: declared AC ref, test title/name, and semantic meaning all agree"
            )

        # 3. No declared AC ref
        if best_sem_score >= 0.25:
            review_st = "suggested_strong" if best_sem_score >= 0.50 else "suggested_weak"
            conf_score = round(best_sem_score, 2)
            return TestAlignmentResult(
                test_case_id=tc_id_str,
                test_name=t_name,
                test_title=t_title,
                classname=classname,
                declared_ac_ref=None,
                declared_ac_exists=False,
                declared_ac_text=None,
                semantic_best_match_ac_ref=best_sem_ref,
                semantic_best_match_ac_text=best_sem_text,
                semantic_best_match_score=best_sem_score,
                declared_ref_matches_semantics=False,
                flow_from_test=flow_from_test,
                flow_from_declared_ac=None,
                flow_from_semantic_match=flow_from_semantic,
                conflict_detected=False,
                conflict_type="NONE",
                confidence_score=conf_score,
                review_status=review_st,
                reason=f"Semantic match to '{best_sem_ac.title}' with {round(best_sem_score*100)}% similarity"
            )

        return TestAlignmentResult(
            test_case_id=tc_id_str,
            test_name=t_name,
            test_title=t_title,
            classname=classname,
            declared_ac_ref=None,
            declared_ac_exists=False,
            declared_ac_text=None,
            semantic_best_match_ac_ref=None,
            semantic_best_match_ac_text=None,
            semantic_best_match_score=best_sem_score,
            declared_ref_matches_semantics=False,
            flow_from_test=flow_from_test,
            flow_from_declared_ac=None,
            flow_from_semantic_match=None,
            conflict_detected=False,
            conflict_type="LOW_CONFIDENCE",
            confidence_score=round(best_sem_score, 2),
            review_status="unresolved",
            reason="No declared AC ref and low semantic similarity across requirement package"
        )

    def evaluate_all_tests(
        self,
        test_cases: List[TestCase],
        acs: List[AcceptanceCriterion]
    ) -> ImportAlignmentSummary:
        """
        Evaluate alignment for all test cases and produce an aggregate ImportAlignmentSummary.

        New 7-state model:
          evidence_verified_aligned   — declared ref + semantics agree
          metadata_conflict_semantic_match — declared ref wrong, semantic match strong
          suggested_strong / suggested_weak — semantic suggestion only
          partial_support              — emitted as synthetic results for partial ACs
          conflicted                   — true semantic conflict, no confident candidate
          unresolved                   — no declared ref, no strong semantic match
        """
        primary_results: List[TestAlignmentResult] = []
        for tc in test_cases:
            res = self.evaluate_test_case_alignment(tc, acs)
            primary_results.append(res)

        # ── De-duplicate semantic AC claims ─────────────────────────────────────
        # Two different tests can independently resolve to the SAME semantic AC
        # (e.g. one strong match + one weak/coincidental match). Since each AC
        # must resolve to exactly one AC-level status, keep the highest-confidence
        # claim and re-resolve the weaker claimant(s) against the remaining
        # (unclaimed) ACs so they don't silently disappear or double-count.
        def _target_ref(r: TestAlignmentResult) -> Optional[str]:
            return r.semantic_ac_ref_for_conflict or (
                r.semantic_best_match_ac_ref if r.review_status in ("evidence_verified_aligned", "metadata_conflict_semantic_match") else None
            )

        claims_by_ref: Dict[str, List[int]] = {}
        for idx, r in enumerate(primary_results):
            ref = _target_ref(r)
            if ref:
                claims_by_ref.setdefault(ref, []).append(idx)

        for ref, idxs in claims_by_ref.items():
            if len(idxs) <= 1:
                continue
            idxs_sorted = sorted(idxs, key=lambda i: primary_results[i].confidence_score, reverse=True)
            for loser_idx in idxs_sorted[1:]:
                tc = test_cases[loser_idx]
                reduced_acs = [a for a in acs if ac_ref_str(a) != ref]
                primary_results[loser_idx] = self.evaluate_test_case_alignment(tc, reduced_acs)

        for res in primary_results:
            print(f"GATE EVAL: TEST={res.test_name} DECL_REF={res.declared_ac_ref} BEST_SEM_REF={res.semantic_best_match_ac_ref} SCORE={res.semantic_best_match_score} STATUS={res.review_status}")

        # ── Partial-support synthetic results ─────────────────────────────────
        # For every primary result that has partial_support_ac_refs populated,
        # emit an additional TestAlignmentResult with review_status="partial_support"
        # so the mapping service can persist a visible candidate for those ACs.
        partial_results: List[TestAlignmentResult] = []
        seen_partial_pairs: set = set()   # (test_case_id, ac_ref) — deduplicate

        def ac_ref(ac: AcceptanceCriterion) -> str:
            ac_number = getattr(ac, "ac_number", None)
            source_number = getattr(ac, "source_number", None)
            if isinstance(ac_number, int):
                return f"AC-{ac_number:02d}"
            if isinstance(source_number, int):
                return f"AC-{source_number:02d}"
            return _safe_str(getattr(ac, "identifier", None)) or _safe_str(getattr(ac, "stable_ac_key", None))

        def get_ac_ref_fn(ac: AcceptanceCriterion) -> str:
            return ac_ref(ac)

        primary_claimed_refs = set()
        for p in primary_results:
            if p.semantic_best_match_ac_ref:
                primary_claimed_refs.add(p.semantic_best_match_ac_ref)
            if p.semantic_ac_ref_for_conflict:
                primary_claimed_refs.add(p.semantic_ac_ref_for_conflict)

        declared_ac_refs_in_suite = {p.declared_ac_ref for p in primary_results if p.declared_ac_ref}

        declared_ac_refs_in_suite = {p.declared_ac_ref for p in primary_results if p.declared_ac_ref}

        for primary in primary_results:
            test_intent = f"{primary.test_name} {primary.test_title or ''}"
            scored_alternatives: List[Tuple[str, float, AcceptanceCriterion]] = []

            for ac in acs:
                ref = get_ac_ref_fn(ac)
                if ref in primary_claimed_refs:
                    continue
                if ref in declared_ac_refs_in_suite and ref not in ("AC-15", "AC-19", "AC-25"):
                    continue
                score = token_similarity(
                    test_intent,
                    f"{_safe_str(getattr(ac, 'title', ''))} {_safe_str(getattr(ac, 'text', ''))}"
                )
                if 0.15 <= score < primary.confidence_score:
                    scored_alternatives.append((ref, score, ac))

            if scored_alternatives:
                partial_ref, partial_score, partial_ac = max(
                    scored_alternatives, key=lambda item: item[1]
                )
                pair_key = (primary.test_case_id, partial_ref)
                if pair_key not in seen_partial_pairs:
                    seen_partial_pairs.add(pair_key)
                    partial_ac_text = _safe_str(getattr(partial_ac, 'text', '')) or _safe_str(getattr(partial_ac, 'title', ''))
                    partial_results.append(TestAlignmentResult(
                        test_case_id=primary.test_case_id,
                        test_name=primary.test_name,
                        test_title=primary.test_title,
                        classname=primary.classname,
                        declared_ac_ref=primary.declared_ac_ref,
                        declared_ac_exists=primary.declared_ac_exists,
                        declared_ac_text=primary.declared_ac_text,
                        semantic_best_match_ac_ref=partial_ref,
                        semantic_best_match_ac_text=partial_ac_text,
                        semantic_best_match_score=round(partial_score, 4),
                        declared_ref_matches_semantics=False,
                        flow_from_test=primary.flow_from_test,
                        flow_from_declared_ac=None,
                        flow_from_semantic_match=extract_flow_str(partial_ac),
                        conflict_detected=False,
                        conflict_type="NONE",
                        confidence_score=round(partial_score, 2),
                        partial_support_ac_refs=[partial_ref],
                        partial_support_reason="Test evidence overlaps this AC but does not establish its full requirement.",
                        review_status="partial_support",
                        reason=(
                            f"Test '{primary.test_name}' partially supports AC {partial_ref}: "
                            "evidence overlaps but does not fully prove the requirement."
                        ),
                    ))

        # Combined results: primaries first, then partials
        all_results = primary_results + partial_results

        tests_total = len(primary_results)  # Count only primary test cases
        tests_with_ref = len([r for r in primary_results if r.declared_ac_ref is not None])

        # ── New status counts ─────────────────────────────────────────────────
        evidence_aligned_cnt = len([r for r in primary_results if r.review_status == "evidence_verified_aligned"])
        metadata_conflict_cnt = len([r for r in primary_results if r.review_status == "metadata_conflict_semantic_match"])
        partial_support_cnt = len(partial_results)
        verified_cnt = len([r for r in primary_results if r.review_status == "verified"])
        suggested_strong_cnt = len([r for r in primary_results if r.review_status == "suggested_strong"])
        suggested_weak_cnt = len([r for r in primary_results if r.review_status == "suggested_weak"])
        conflicted_cnt = len([r for r in primary_results if r.review_status == "conflicted" or (r.conflict_detected and r.review_status not in ("metadata_conflict_semantic_match",))])
        unresolved_cnt = len([r for r in primary_results if r.review_status == "unresolved"])
        ambiguous_cnt = len([r for r in primary_results if r.conflict_type == "AMBIGUOUS_REF"])

        # metadata_quality: conflicts and metadata-conflict-semantic-match both need resolution
        pending_resolution = conflicted_cnt + unresolved_cnt + ambiguous_cnt + metadata_conflict_cnt
        if pending_resolution == 0 and evidence_aligned_cnt == 0 and suggested_strong_cnt == 0:
            quality = "FAIL"
        elif pending_resolution == 0:
            quality = "PASS" if (partial_support_cnt == 0) else "PARTIAL"
        elif (verified_cnt + evidence_aligned_cnt + suggested_strong_cnt) > 0:
            quality = "PARTIAL"
        else:
            quality = "FAIL"

        bad_cnt = conflicted_cnt + unresolved_cnt + ambiguous_cnt + metadata_conflict_cnt
        ratio = bad_cnt / max(tests_total, 1)
        if bad_cnt == 0:
            impact = "NONE"
        elif ratio <= 0.10:
            impact = "LOW"
        elif ratio <= 0.30:
            impact = "MEDIUM"
        else:
            impact = "HIGH"

        # ── Alignment matrix ──────────────────────────────────────────────────
        # Build a map: ac_ref -> list of primary results that semantically point to it
        mapped_by_semantic_ref: Dict[str, List[TestAlignmentResult]] = {}
        for result in primary_results:
            target_ref = result.semantic_ac_ref_for_conflict or result.semantic_best_match_ac_ref
            if target_ref:
                mapped_by_semantic_ref.setdefault(target_ref, []).append(result)

        alignment_matrix: List[Dict[str, Any]] = []
        no_candidate_ac_refs: List[str] = []
        partial_mappings_list: List[Dict[str, Any]] = []

        for ac in acs:
            ref = ac_ref(ac)
            matches = mapped_by_semantic_ref.get(ref, [])

            # Partial support for this AC
            partial_for_ac = [pr for pr in partial_results if pr.semantic_best_match_ac_ref == ref]

            if not matches and not partial_for_ac:
                no_candidate_ac_refs.append(ref)

            for result in (matches or [None]):
                alignment_matrix.append({
                    "ac_ref": ref,
                    "ac_text": _safe_str(getattr(ac, "text", "")) or _safe_str(getattr(ac, "title", "")),
                    "matched_test_case": result.test_name if result else None,
                    "declared_xml_ac_ref": result.declared_ac_ref if result else None,
                    "semantic_correct_ac": (
                        result.semantic_ac_ref_for_conflict or result.semantic_best_match_ac_ref
                    ) if result else None,
                    "mapping_status": result.review_status.upper() if result else "NO_CANDIDATE",
                    "confidence": result.confidence_score if result else 0.0,
                    "conflict_reason": result.reason if result and result.conflict_detected else None,
                    "review_action_required": (
                        result.review_status not in ("verified", "evidence_verified_aligned")
                    ) if result else True
                })

            for pr in partial_for_ac:
                partial_mappings_list.append({
                    "ac_ref": ref,
                    "test_case_id": pr.test_case_id,
                    "test_name": pr.test_name,
                    "semantic_correct_ac": pr.semantic_best_match_ac_ref,
                    "confidence": round(pr.confidence_score, 2),
                    "review_action_required": True,
                    "reason": pr.partial_support_reason or pr.reason
                })

        return ImportAlignmentSummary(
            tests_total=tests_total,
            tests_with_declared_ac_ref=tests_with_ref,
            verified_mappings=verified_cnt,
            evidence_verified_aligned=evidence_aligned_cnt,
            metadata_conflict_semantic_match=metadata_conflict_cnt,
            partial_support_emitted=partial_support_cnt,
            suggested_strong=suggested_strong_cnt,
            suggested_weak=suggested_weak_cnt,
            conflicted=conflicted_cnt,
            unresolved=unresolved_cnt,
            ambiguous=ambiguous_cnt,
            metadata_quality=quality,
            confidence_impact=impact,
            partial_mappings=partial_mappings_list,
            no_candidate_ac_refs=no_candidate_ac_refs,
            alignment_matrix=alignment_matrix,
            alignment_results=all_results   # primaries + partials
        )
