"""
TestMatchingV4
==============
Matches test cases to a pull request using the eight ordered signal layers
defined in the V4 specification.  Produces RecommendedTestCandidate objects
with a fully explainable score and signal breakdown.

Matching order and point values
--------------------------------
1. Coverage Links     +50  (FileTestLink — direct coverage trace)
2. Knowledge Graph    +40  (TestCoverageLink — execution correlation graph)
3. Domain Match       +30  (DomainMap — business domain alignment)
4. Module Match       +20  (ModuleRiskProfile — module-path prefix match)
5. Token Similarity   +10  (path token overlap between test identity and changed paths)
6. Historical Failure +10  (TestResult failure in the last 30 days)
7. Manual Override    +15  (TestCoverageLink.override_count > 0)
8. Fallback            +0  (conservative inclusion when zero other signals fire)

Additional adjustments
----------------------
- Escaped defect link: +15 (TestCoverageLink.defect_count > 0)
- Runtime cost: -1 per second of average historical duration
- Quarantined tests: excluded entirely

Design rules
------------
- All scores fully explainable through the `signals` field.
- No hidden ranking.  The `score` is the arithmetic sum of visible signals.
- Deterministic: same inputs → same output.
- No AI calls.  No fake percentages.

Output
------
Each candidate is a RecommendedTestCandidate dataclass:
  test_identifier   str   stable_identity of the TestCase
  test_name         str
  suite_name        str
  score             float arithmetic sum of all signals
  signals           dict  {signal_name: points}  — persisted as-is
  reason            str   human-readable bullets (max 4)
  source_signal     str   primary signal that qualified this test
  confidence        str   HIGH / MEDIUM / LOW based on total score
  estimated_duration_seconds  float
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.coverage import FileTestLink
from app.models.domain_map import DomainMap
from app.models.flaky_test import FlakyTestProfile
from app.models.module_risk_profile import ModuleRiskProfile
from app.models.pull_request import PullRequestChangedFile
from app.models.test_coverage_link import TestCoverageLink
from app.models.test_result import TestCase, TestResult, TestRun
from app.services.domain_intelligence_engine import DomainIntelligenceEngine


# ---------------------------------------------------------------------------
# Score constants — single source of truth
# ---------------------------------------------------------------------------

SCORE_COVERAGE_LINK     = 50   # 1. Direct coverage trace (FileTestLink)
SCORE_KNOWLEDGE_GRAPH   = 40   # 2. Execution correlation (TestCoverageLink)
SCORE_DOMAIN_MATCH      = 30   # 3. Business domain alignment
SCORE_MODULE_MATCH      = 20   # 4. Module-path prefix match
SCORE_TOKEN_SIMILARITY  = 10   # 5. Path-token overlap
SCORE_HISTORICAL_FAILURE = 10  # 6. Recent test failure (last 30 days)
SCORE_MANUAL_OVERRIDE   = 15   # 7. Engineer manually added this test before
SCORE_ESCAPED_DEFECT    = 15   # Supporting: production defect escaped via this gap

# Fallback signal (no direct points — qualifies test that would otherwise be skipped)
SCORE_FALLBACK          = 0

# Confidence thresholds
_CONFIDENCE_HIGH   = 80
_CONFIDENCE_MEDIUM = 40

# Historical failure look-back window
FAILURE_LOOKBACK_DAYS = 30


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class RecommendedTestCandidate:
    """
    A single test candidate produced by TestMatchingV4.

    All fields are populated by the matcher — no post-processing required.
    """
    test_identifier: str
    test_name: str
    suite_name: str
    score: float
    signals: Dict[str, int]      # {signal_name: points} — persisted verbatim
    reason: str                  # Formatted bullet string (max 4 bullets)
    source_signal: str           # Primary signal that qualified this test
    confidence: str              # HIGH | MEDIUM | LOW
    estimated_duration_seconds: float
    is_fallback: bool = False


# ---------------------------------------------------------------------------
# Token-similarity helper
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def _tokenise(text: str) -> Set[str]:
    """Split a path/identifier into lowercase alpha-numeric tokens."""
    return set(t for t in _TOKEN_RE.split(text.lower()) if len(t) >= 3)


def _token_overlap(a: str, b: str) -> bool:
    """Return True if the two strings share at least one meaningful token."""
    return bool(_tokenise(a) & _tokenise(b))


def _any_token_overlap(test_identity: str, paths: List[str]) -> bool:
    tc_tokens = _tokenise(test_identity)
    for path in paths:
        if tc_tokens & _tokenise(path):
            return True
    return False


# ---------------------------------------------------------------------------
# Reason formatter
# ---------------------------------------------------------------------------

def _build_reason(signals: Dict[str, int]) -> str:
    """
    Produce at most 4 factual bullet points from the active signals dict.
    Order: highest-value signals first.
    """
    _SIGNAL_LABELS: Dict[str, str] = {
        "coverage_link":       "Direct code coverage: Coverage report confirms this test covers the changed file.",
        "knowledge_graph":     "Knowledge graph link: Execution traces correlate this test to the modified path.",
        "domain_match":        "Domain match: Test and changed files share the same business domain.",
        "module_match":        "Module match: Test is associated with a high-risk module that was changed.",
        "token_similarity":    "Token similarity: Test identifier shares path tokens with changed files.",
        "historical_failure":  "Recent failure: This test has failed in the last 30 days.",
        "manual_override":     "Manual override history: Engineers repeatedly added this test manually.",
        "escaped_defect":      "Escaped defect: A production defect escaped through a gap this test covers.",
        "fallback":            "Fallback selection: No direct signal matched; test included for baseline coverage.",
    }

    # Sort by score descending, excluding zero and runtime_cost (negative)
    ranked = sorted(
        [(name, pts) for name, pts in signals.items() if pts > 0 and name != "runtime_cost"],
        key=lambda x: -x[1],
    )
    bullets = []
    for name, _ in ranked:
        label = _SIGNAL_LABELS.get(name)
        if label and label not in bullets:
            bullets.append(label)
        if len(bullets) == 4:
            break

    if not bullets:
        bullets.append("Selected based on pipeline fallback rules.")

    return "\n".join(f"- {b}" for b in bullets)


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class TestMatchingV4:
    """
    Matches test cases to changed files using eight ordered signal layers.

    Usage
    -----
    ::

        candidates = TestMatchingV4.match(
            db=db,
            repository_id=repo_id,
            pull_request_id=pr_id,
        )
        for c in candidates:
            print(c.score, c.test_identifier)
            print(c.signals)
            print(c.reason)
    """

    @classmethod
    def match(
        cls,
        db: Session,
        repository_id: UUID,
        pull_request_id: UUID,
        failure_lookback_days: int = FAILURE_LOOKBACK_DAYS,
    ) -> List[RecommendedTestCandidate]:
        """
        Run all eight matching layers and return ranked candidates.

        Parameters
        ----------
        db:
            Active SQLAlchemy session.
        repository_id:
            Repository UUID.
        pull_request_id:
            Pull request UUID — used to load changed files.
        failure_lookback_days:
            How far back to look for historical failures (default 30 days).

        Returns
        -------
        List[RecommendedTestCandidate] sorted by (score DESC, duration ASC, identifier ASC).
        """
        # ----------------------------------------------------------------
        # 0. Load inputs
        # ----------------------------------------------------------------
        changed_files_db = (
            db.query(PullRequestChangedFile)
            .filter(PullRequestChangedFile.pull_request_id == pull_request_id)
            .order_by(PullRequestChangedFile.file_path.asc())
            .all()
        )
        changed_paths: List[str] = [f.file_path for f in changed_files_db]

        test_cases: List[TestCase] = (
            db.query(TestCase)
            .filter(TestCase.repository_id == repository_id)
            .order_by(TestCase.stable_identity.asc())
            .all()
        )

        if not test_cases:
            return []

        # ----------------------------------------------------------------
        # 0a. Flaky / quarantine map
        # ----------------------------------------------------------------
        flaky_rows = (
            db.query(FlakyTestProfile)
            .filter(FlakyTestProfile.repository_id == repository_id)
            .all()
        )
        flaky_map: Dict[str, str] = {str(p.test_case_id): p.status for p in flaky_rows}

        # ----------------------------------------------------------------
        # 0b. Historical failures (last N days)
        # ----------------------------------------------------------------
        cutoff = datetime.utcnow() - timedelta(days=failure_lookback_days)
        recent_failure_rows = (
            db.query(TestResult.test_case_id)
            .join(TestRun, TestResult.test_run_id == TestRun.id)
            .filter(
                TestRun.repository_id == repository_id,
                TestResult.status == "failed",
                TestResult.created_at >= cutoff,
            )
            .all()
        )
        failed_ids: Set[str] = {str(row[0]) for row in recent_failure_rows}

        # ----------------------------------------------------------------
        # 0c. Average runtime per test case
        # ----------------------------------------------------------------
        duration_rows = (
            db.query(TestResult.test_case_id, func.avg(TestResult.duration))
            .join(TestRun, TestResult.test_run_id == TestRun.id)
            .filter(TestRun.repository_id == repository_id)
            .group_by(TestResult.test_case_id)
            .all()
        )
        duration_map: Dict[str, float] = {
            str(row[0]): float(row[1]) for row in duration_rows if row[1] is not None
        }

        # ----------------------------------------------------------------
        # Signal layer 1: Coverage links (FileTestLink)
        # ----------------------------------------------------------------
        coverage_link_test_ids: Set[str] = set()
        if changed_paths:
            cov_rows = (
                db.query(FileTestLink.test_case_id)
                .filter(FileTestLink.file_path.in_(changed_paths))
                .all()
            )
            coverage_link_test_ids = {str(row[0]) for row in cov_rows}

        # ----------------------------------------------------------------
        # Signal layer 2: Knowledge graph (TestCoverageLink)
        # ----------------------------------------------------------------
        tcl_map: Dict[str, Dict[str, TestCoverageLink]] = {}
        if changed_paths:
            tcl_edges = (
                db.query(TestCoverageLink)
                .filter(
                    TestCoverageLink.repository_id == repository_id,
                    TestCoverageLink.file_path.in_(changed_paths),
                )
                .all()
            )
            for edge in tcl_edges:
                tcl_map.setdefault(edge.test_identifier, {})[edge.file_path] = edge

        # ----------------------------------------------------------------
        # Signal layer 3: Domain match (DomainMap)
        # ----------------------------------------------------------------
        domains: List[DomainMap] = (
            db.query(DomainMap)
            .filter(DomainMap.repository_id == repository_id)
            .all()
        )
        if not domains:
            domains = DomainIntelligenceEngine.learn_domains(db, repository_id)

        # Determine which domains are "active" for this PR's changed files
        active_domain_names: Set[str] = set()
        for changed_path in changed_paths:
            cp_lower = changed_path.lower()
            for d_map in domains:
                for df in d_map.files:
                    if df.lower() in cp_lower or cp_lower in df.lower():
                        active_domain_names.add(d_map.domain)
                        break
                else:
                    for dm in d_map.modules:
                        if dm.lower() in cp_lower or cp_lower in dm.lower():
                            active_domain_names.add(d_map.domain)
                            break

        # Build a quick lookup: domain_name → (files set, modules set)
        domain_lookup: Dict[str, Dict[str, Set[str]]] = {}
        for d_map in domains:
            if d_map.domain in active_domain_names:
                domain_lookup[d_map.domain] = {
                    "files":   set(f.lower() for f in (d_map.files or [])),
                    "modules": set(m.lower() for m in (d_map.modules or [])),
                }

        # ----------------------------------------------------------------
        # Signal layer 4: Module match (ModuleRiskProfile)
        # ----------------------------------------------------------------
        risk_profiles: List[ModuleRiskProfile] = (
            db.query(ModuleRiskProfile)
            .filter(ModuleRiskProfile.repository_id == repository_id)
            .all()
        )
        # Map module_path → risk_score (only positive-scoring modules matter)
        module_risk_map: Dict[str, float] = {
            p.module_path: p.risk_score
            for p in risk_profiles
            if p.risk_score > 0
        }

        # ----------------------------------------------------------------
        # Score every test case
        # ----------------------------------------------------------------
        candidates: List[RecommendedTestCandidate] = []

        for tc in test_cases:
            tc_id_str = str(tc.id)

            # Quarantined tests are excluded entirely
            if flaky_map.get(tc_id_str) == "quarantined":
                continue

            tc_id_lower     = tc.stable_identity.lower()
            tc_suite_lower  = tc.suite_name.lower()

            signals: Dict[str, int] = {
                "coverage_link":      0,
                "knowledge_graph":    0,
                "domain_match":       0,
                "module_match":       0,
                "token_similarity":   0,
                "historical_failure": 0,
                "manual_override":    0,
                "escaped_defect":     0,
                "runtime_cost":       0,
                "fallback":           0,
            }
            matched_domain: str = ""
            source_signal: str  = "FALLBACK"

            # -- Layer 1: Coverage link ----------------------------------
            if tc_id_str in coverage_link_test_ids:
                signals["coverage_link"] = SCORE_COVERAGE_LINK
                source_signal = "DIRECT_COVERAGE"

            # -- Layer 2: Knowledge graph --------------------------------
            tc_edges = tcl_map.get(tc.stable_identity, {})
            if tc_edges:
                signals["knowledge_graph"] = SCORE_KNOWLEDGE_GRAPH
                if source_signal == "FALLBACK":
                    source_signal = "KNOWLEDGE_GRAPH"
                # Derive override and escaped-defect sub-signals from edges
                for edge in tc_edges.values():
                    if edge.override_count > 0:
                        signals["manual_override"] = SCORE_MANUAL_OVERRIDE
                    if edge.defect_count > 0:
                        signals["escaped_defect"] = SCORE_ESCAPED_DEFECT

            # -- Layer 3: Domain match -----------------------------------
            for d_name, d_data in domain_lookup.items():
                for df in d_data["files"]:
                    if df in tc_id_lower or tc_id_lower in df or df in tc_suite_lower or tc_suite_lower in df:
                        signals["domain_match"] = SCORE_DOMAIN_MATCH
                        matched_domain = d_name
                        break
                else:
                    for dm in d_data["modules"]:
                        if dm in tc_id_lower or tc_id_lower in dm or dm in tc_suite_lower or tc_suite_lower in dm:
                            signals["domain_match"] = SCORE_DOMAIN_MATCH
                            matched_domain = d_name
                            break
                if signals["domain_match"]:
                    if source_signal == "FALLBACK":
                        source_signal = "DOMAIN_MATCH"
                    break

            # -- Layer 4: Module match -----------------------------------
            # Test is module-matched if any changed file falls under a
            # risk-profiled module that also appears in the test identity
            if not signals["module_match"]:
                for mod_path, risk_score in module_risk_map.items():
                    mod_lower = mod_path.lower()
                    # Changed file must be under this module
                    file_matches_module = any(
                        cp.lower() == mod_lower or cp.lower().startswith(mod_lower + "/")
                        for cp in changed_paths
                    )
                    # Test identity must reference this module
                    test_matches_module = (
                        mod_lower in tc_id_lower
                        or mod_lower in tc_suite_lower
                    )
                    if file_matches_module and test_matches_module:
                        signals["module_match"] = SCORE_MODULE_MATCH
                        if source_signal == "FALLBACK":
                            source_signal = "MODULE_MATCH"
                        break

            # -- Layer 5: Token similarity --------------------------------
            if not signals["token_similarity"] and changed_paths:
                if _any_token_overlap(tc.stable_identity, changed_paths) or \
                   _any_token_overlap(tc.suite_name, changed_paths):
                    signals["token_similarity"] = SCORE_TOKEN_SIMILARITY
                    if source_signal == "FALLBACK":
                        source_signal = "TOKEN_SIMILARITY"

            # -- Layer 6: Historical failure ------------------------------
            if tc_id_str in failed_ids:
                signals["historical_failure"] = SCORE_HISTORICAL_FAILURE
                if source_signal == "FALLBACK":
                    source_signal = "HISTORICAL_FAILURE"

            # -- Layer 7: Manual override ---------------------------------
            # (already set from Layer 2 edge traversal above)
            if signals["manual_override"] and source_signal == "FALLBACK":
                source_signal = "MANUAL_OVERRIDE"

            # ----------------------------------------------------------------
            # Layer 8: Fallback gate
            # ----------------------------------------------------------------
            # If no positive signal has fired, skip this test entirely.
            # The fallback batch is handled separately after the main loop.
            has_any_signal = any(
                v > 0 for k, v in signals.items()
                if k not in ("runtime_cost", "fallback")
            )
            if not has_any_signal:
                continue

            # -- Runtime cost adjustment ---------------------------------
            avg_dur = duration_map.get(tc_id_str)
            estimated_duration = avg_dur if (avg_dur is not None and avg_dur > 0) else 5.0
            signals["runtime_cost"] = -int(round(estimated_duration))

            # -- Total score ---------------------------------------------
            total = sum(signals.values())  # runtime_cost is already negative

            # -- Confidence ----------------------------------------------
            if flaky_map.get(tc_id_str) == "unstable":
                confidence = "MEDIUM"
            elif total >= _CONFIDENCE_HIGH:
                confidence = "HIGH"
            elif total >= _CONFIDENCE_MEDIUM:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            reason = _build_reason(signals)
            if flaky_map.get(tc_id_str) == "unstable":
                reason += "\n- [UNSTABLE] This test is flagged as flaky; treat result with caution."

            # Annotate domain in reason if matched
            if matched_domain and f"'{matched_domain}'" not in reason:
                reason = reason.replace(
                    "Domain match: Test and changed files share the same business domain.",
                    f"Domain match: Test and changed files both reside in the '{matched_domain}' business domain.",
                )

            candidates.append(RecommendedTestCandidate(
                test_identifier=tc.stable_identity,
                test_name=tc.test_name,
                suite_name=tc.suite_name,
                score=float(total),
                signals=signals,
                reason=reason,
                source_signal=source_signal,
                confidence=confidence,
                estimated_duration_seconds=round(estimated_duration, 2),
                is_fallback=False,
            ))

        # ----------------------------------------------------------------
        # Layer 8: Fallback — if no candidates at all, include up to 5
        # test cases with purely historical/duration grounding
        # ----------------------------------------------------------------
        if not candidates and test_cases:
            fallback_cases = test_cases[:5]
            for tc in fallback_cases:
                if flaky_map.get(str(tc.id)) == "quarantined":
                    continue
                tc_id_str = str(tc.id)
                avg_dur = duration_map.get(tc_id_str)
                estimated_duration = avg_dur if avg_dur and avg_dur > 0 else 5.0

                fb_signals: Dict[str, int] = {
                    "coverage_link":      0,
                    "knowledge_graph":    0,
                    "domain_match":       0,
                    "module_match":       0,
                    "token_similarity":   0,
                    "historical_failure": SCORE_HISTORICAL_FAILURE if tc_id_str in failed_ids else 0,
                    "manual_override":    0,
                    "escaped_defect":     0,
                    "runtime_cost":       -int(round(estimated_duration)),
                    "fallback":           SCORE_FALLBACK,
                }
                total = sum(fb_signals.values())
                candidates.append(RecommendedTestCandidate(
                    test_identifier=tc.stable_identity,
                    test_name=tc.test_name,
                    suite_name=tc.suite_name,
                    score=float(total),
                    signals=fb_signals,
                    reason=(
                        "- Fallback selection: No direct signal matched; "
                        "test included for baseline coverage."
                    ),
                    source_signal="FALLBACK",
                    confidence="LOW",
                    estimated_duration_seconds=round(estimated_duration, 2),
                    is_fallback=True,
                ))

        # ----------------------------------------------------------------
        # Sort: score DESC, duration ASC, identifier ASC (deterministic)
        # ----------------------------------------------------------------
        candidates.sort(key=lambda c: (-c.score, c.estimated_duration_seconds, c.test_identifier))
        return candidates

    @classmethod
    def to_dict(cls, candidate: RecommendedTestCandidate) -> Dict[str, Any]:
        """
        Serialise a RecommendedTestCandidate to a plain dict for API responses
        and persistence layers (e.g. RecommendationLogicV3 result format).
        """
        return {
            "test_identifier":            candidate.test_identifier,
            "test_name":                  candidate.test_name,
            "class_name/module":          candidate.suite_name,
            "priority":                   candidate.score,
            "estimated_duration_seconds": candidate.estimated_duration_seconds,
            "reason":                     candidate.reason,
            "confidence":                 candidate.confidence,
            "source_signal":              candidate.source_signal,
            "is_fallback":                candidate.is_fallback,
            "reason_details":             {
                **candidate.signals,
                "total": candidate.score,
            },
        }
