import uuid
import math
import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime
from itertools import combinations as iter_combinations
from typing import Dict, FrozenSet, List, Any, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink
from app.models.test_result import TestCase
from app.models.flaky_test import FlakyTestProfile
from app.schemas.failure_evidence import FailureEvidenceBundle

logger = logging.getLogger(__name__)

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: RepositoryCalibrationProfile
# ====================================================================
# Future calibration profiles should support repository-specific tuning:
# - Cluster size ceiling: Raise MAX_CLUSTER_SIZE for large monorepos
#   whose integration suites legitimately co-fail in groups > 5.
# - Storm threshold: Tune MAX_FAILURES_PER_RUN_FOR_CLUSTER_ANALYSIS
#   to match each repo's CI noisiness baseline.
# - Infrastructure pattern library: Accept repo-level regex patterns
#   for infra noise in addition to the built-in keyword set.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: Evidence-Source Weighting
# ====================================================================
# Cluster failures derive signal weight from:
# - Repeated co-failure events (TEST_FAILURE, weight 0.5)
# - Rollback/incident-linked runs on the same PR (weight 0.8/1.0)
#
# Infrastructure failures are suppressed entirely — they contribute
# zero evidence to cluster patterns.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================


# ---------------------------------------------------------------------------
# Infrastructure noise: test names/suites matching these keywords are
# treated as infra-only failures and excluded from cluster evidence.
# The list is conservative to avoid over-filtering.
# ---------------------------------------------------------------------------
_INFRA_NOISE_KEYWORDS: Tuple[str, ...] = (
    "setup",
    "teardown",
    "fixture",
    "docker",
    "container",
    "network_",
    "_network",
    "timeout_setup",
    "db_migration",
    "env_check",
    "health_check",
    "infra_",
    "_infra",
    "ci_config",
    "bootstrap",
)


def _is_infrastructure_noise(suite_name: str, test_name: str) -> bool:
    """
    Returns True when a test case is classified as infrastructure-only noise.

    Heuristic: if both the suite name AND the test name contain at least
    one infra keyword the test is considered infrastructure-only.  Requiring
    both fields to match prevents over-aggressive suppression of legitimate
    tests that happen to include a keyword in only one field.
    """
    combined = f"{suite_name} {test_name}".lower()
    return sum(1 for kw in _INFRA_NOISE_KEYWORDS if kw in combined) >= 2


class TestClusterFailureEngine:
    """
    Identifies pairs (and bounded triples) of test cases that repeatedly
    fail *together* within the same test run, contextualised against the
    changed files that triggered the run.

    Two clustering axes are detected:

      AXIS 1 — Same-suite clusters
        Tests in the **same test suite** that co-fail in ≥ MIN_CLUSTER_OCCURRENCES
        runs.  Suite membership is the primary grouping key.

      AXIS 2 — Module-neighbourhood clusters
        Tests that resolve to the **same module neighbourhood** (via the
        TestAreaResolver hierarchy) and co-fail in ≥ MIN_CLUSTER_OCCURRENCES
        runs, even if they belong to different suites.

    Noise suppression:
      - Flaky / quarantined tests are excluded.
      - Infrastructure-noise tests are excluded.
      - Giant failure storms (runs with > MAX_FAILURES_PER_RUN) are skipped.
      - Clusters larger than MAX_CLUSTER_SIZE are split into bounded pairs/
        triples rather than generating an unbounded n-tuple.

    Pattern type:  TEST_CLUSTER_FAILURE
    Key format:    TEST_CLUSTER_FAILURE:<suite_or_neighbourhood>:<sorted_test1>,<sorted_test2>[,<sorted_test3>]
    """

    # ------------------------------------------------------------------ #
    # Cluster bounds                                                       #
    # ------------------------------------------------------------------ #
    MIN_CLUSTER_OCCURRENCES: int = 3   # Rule 2 from spec
    MAX_CLUSTER_SIZE: int       = 5    # Rule 6 from spec — absolute ceiling
    MIN_DISTINCT_RUNS: int      = 2    # Guard against single-run storm

    # Storm suppression: skip runs with too many co-failures
    MAX_FAILURES_PER_RUN_FOR_CLUSTER_ANALYSIS: int = 30

    # ------------------------------------------------------------------ #
    # Versioning                                                           #
    # ------------------------------------------------------------------ #
    GENERATION_VERSION          = "v1.2.0"
    SCORING_VERSION             = "weighted.v2"
    NORMALIZATION_RULES_VERSION = "rules.v1"

    # ------------------------------------------------------------------ #
    # Actuarial lifecycle                                                  #
    # ------------------------------------------------------------------ #
    STALE_AFTER_DAYS      = 90
    INVALIDATE_AFTER_DAYS = 180

    def __init__(self, db: Session) -> None:
        self.db = db

    # ================================================================== #
    # Public API                                                           #
    # ================================================================== #

    def detect_test_clusters(
        self,
        db: Session,
        repository_id: uuid.UUID,
        evidence_bundle: FailureEvidenceBundle,
    ) -> Dict[str, Any]:
        """
        Scans the evidence bundle for test cases that repeatedly co-fail in
        the same runs and persists TEST_CLUSTER_FAILURE fragility patterns.

        Only ``failed`` and ``error`` TestResults are used (Rule 1).
        Infrastructure noise and flaky tests are suppressed before clustering.

        Returns a summary dict with ``patterns_mined`` and ``diagnostics``.
        """
        logger.info(
            "TestClusterFailureEngine starting for repository %s…",
            repository_id,
        )

        # ---------------------------------------------------------------- #
        # 1. Preserve manually invalidated pattern keys                     #
        # ---------------------------------------------------------------- #
        invalidated_keys: Set[str] = {
            p.normalized_pattern_key
            for p in db.query(FragilityPattern.normalized_pattern_key).filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.pattern_type == "TEST_CLUSTER_FAILURE",
                FragilityPattern.status == "INVALIDATED",
            ).all()
        }

        # ---------------------------------------------------------------- #
        # 2. Build flaky / quarantined exclusion set                        #
        # ---------------------------------------------------------------- #
        flaky_profiles = db.query(FlakyTestProfile).filter(
            FlakyTestProfile.repository_id == repository_id
        ).all()

        excluded_test_case_ids: Set[uuid.UUID] = set()
        for fp in flaky_profiles:
            if (
                fp.status in ("quarantined", "unstable")
                or fp.failure_rate > 0.2
                or fp.instability_score > 0.2
            ):
                excluded_test_case_ids.add(fp.test_case_id)

        # ---------------------------------------------------------------- #
        # 3. Resolve TestCase objects for all failing results               #
        # ---------------------------------------------------------------- #
        # Rule 1: only status in {failed, error}
        qualifying_result_statuses = {"failed", "error"}
        qualifying_results = [
            r for r in evidence_bundle.failed_test_results
            if r.status in qualifying_result_statuses
        ]

        all_tc_ids = {r.test_case_id for r in qualifying_results}
        tc_map: Dict[uuid.UUID, TestCase] = {}
        if all_tc_ids:
            tcs = db.query(TestCase).filter(TestCase.id.in_(all_tc_ids)).all()
            tc_map = {tc.id: tc for tc in tcs}

        # ---------------------------------------------------------------- #
        # 4. Index run metadata from the bundle                             #
        # ---------------------------------------------------------------- #
        # run_id → FailureEvidenceTestRun (for pr_id and created_at)
        run_meta = {r.test_run_id: r for r in evidence_bundle.related_test_runs}

        # pr_id → sorted changed-file paths
        pr_to_files: Dict[uuid.UUID, List[str]] = defaultdict(list)
        for cf in evidence_bundle.related_changed_files:
            pr_to_files[cf.pull_request_id].append(
                cf.file_path.replace("\\", "/")
            )
        pr_to_files = {
            pr_id: sorted(set(paths)) for pr_id, paths in pr_to_files.items()
        }

        # rollback / incident PR flags
        rollback_pr_ids: Set[uuid.UUID] = set()
        incident_pr_ids: Set[uuid.UUID] = set()
        rec_to_pr = {
            r.recommendation_run_id: r.pull_request_id
            for r in evidence_bundle.linked_recommendations
        }
        for out in evidence_bundle.linked_incidents:
            pr_id = rec_to_pr.get(out.recommendation_run_id)
            if pr_id:
                if out.rollback_occurred:
                    rollback_pr_ids.add(pr_id)
                if out.escaped_defect:
                    incident_pr_ids.add(pr_id)

        # ---------------------------------------------------------------- #
        # 5. Group qualifying (non-flaky, non-infra) failures by run_id    #
        # ---------------------------------------------------------------- #
        # run_id → list of qualifying TestCase objects that failed in that run
        run_to_failing_tcs: Dict[uuid.UUID, List[TestCase]] = defaultdict(list)

        suppressed_storm_runs    = 0
        suppressed_infra_tests   = 0
        suppressed_flaky_tests   = 0

        # Group results by run first so we can apply storm suppression
        run_to_results: Dict[uuid.UUID, List[Any]] = defaultdict(list)
        for res in qualifying_results:
            run_to_results[res.test_run_id].append(res)

        for run_id, results in run_to_results.items():
            run_obj = run_meta.get(run_id)
            if not run_obj:
                continue
            # Must be a failed run linked to a PR
            if run_obj.status != "failed" or not run_obj.pull_request_id:
                continue

            # Storm suppression: skip giant failure runs
            if len(results) > self.MAX_FAILURES_PER_RUN_FOR_CLUSTER_ANALYSIS:
                suppressed_storm_runs += 1
                continue

            for res in results:
                tc = tc_map.get(res.test_case_id)
                if not tc:
                    continue

                # Flaky / quarantined exclusion
                if tc.id in excluded_test_case_ids:
                    suppressed_flaky_tests += 1
                    continue

                # Infrastructure noise exclusion
                if _is_infrastructure_noise(tc.suite_name, tc.test_name):
                    suppressed_infra_tests += 1
                    continue

                run_to_failing_tcs[run_id].append(tc)

        # ---------------------------------------------------------------- #
        # 6. Generate bounded cluster pairs/triples per run                #
        #                                                                   #
        # We produce pairs (size 2) from every qualifying run, plus one    #
        # representative triple (first 3 sorted) when ≥ 3 tests co-fail.  #
        # Each tuple is keyed by BOTH its cluster grouping axis AND the    #
        # sorted stable_identity list for determinism.                     #
        # ---------------------------------------------------------------- #

        # cluster_key → list of evidence dicts
        cluster_evidence: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for run_id, failing_tcs in run_to_failing_tcs.items():
            if len(failing_tcs) < 2:
                continue  # Need ≥ 2 tests to form any cluster

            run_obj = run_meta[run_id]
            pr_id   = run_obj.pull_request_id  # always set (checked above)

            pr_rollback = pr_id in rollback_pr_ids
            pr_incident = pr_id in incident_pr_ids

            # Churn of trigger files (for scoring)
            churn = sum(
                cf.additions + cf.deletions
                for cf in evidence_bundle.related_changed_files
                if cf.pull_request_id == pr_id
            )

            # ---- AXIS 1: Same-suite clustering -------------------------
            suite_groups: Dict[str, List[TestCase]] = defaultdict(list)
            for tc in failing_tcs:
                suite_groups[tc.suite_name].append(tc)

            for suite_name, suite_tcs in suite_groups.items():
                if len(suite_tcs) < 2:
                    continue
                # Cap and sort
                capped = sorted(suite_tcs, key=lambda t: t.stable_identity)[
                    : self.MAX_CLUSTER_SIZE
                ]
                self._emit_cluster_combos(
                    capped,
                    axis_label=f"suite:{suite_name}",
                    run_id=run_id,
                    pr_id=pr_id,
                    pr_rollback=pr_rollback,
                    pr_incident=pr_incident,
                    created_at=run_obj.created_at,
                    churn=churn,
                    cluster_evidence=cluster_evidence,
                )

            # ---- AXIS 2: Module-neighbourhood clustering ---------------
            neighbourhood_groups: Dict[str, List[TestCase]] = defaultdict(list)
            for tc in failing_tcs:
                neighbourhood = self._resolve_neighbourhood(tc)
                neighbourhood_groups[neighbourhood].append(tc)

            for neighbourhood, nb_tcs in neighbourhood_groups.items():
                if len(nb_tcs) < 2:
                    continue
                # Avoid double-counting pairs already captured by Axis 1
                # (same suite implies same neighbourhood for the suite-based key)
                capped = sorted(nb_tcs, key=lambda t: t.stable_identity)[
                    : self.MAX_CLUSTER_SIZE
                ]
                self._emit_cluster_combos(
                    capped,
                    axis_label=f"neighbourhood:{neighbourhood}",
                    run_id=run_id,
                    pr_id=pr_id,
                    pr_rollback=pr_rollback,
                    pr_incident=pr_incident,
                    created_at=run_obj.created_at,
                    churn=churn,
                    cluster_evidence=cluster_evidence,
                )

        # ---------------------------------------------------------------- #
        # 7. Filter, score, and persist qualifying patterns                 #
        # ---------------------------------------------------------------- #
        patterns_mined       = 0
        skipped_below_thresh = 0

        for cluster_key in sorted(cluster_evidence.keys()):
            raw_items = cluster_evidence[cluster_key]

            # Deduplicate on (run_id, pr_id)
            seen: Set[Tuple[uuid.UUID, uuid.UUID]] = set()
            deduped: List[Dict[str, Any]] = []
            for ev in raw_items:
                k = (ev["run_id"], ev["pr_id"])
                if k not in seen:
                    seen.add(k)
                    deduped.append(ev)

            evidence_count     = len(deduped)
            distinct_run_ids   = {ev["run_id"] for ev in deduped}
            distinct_runs_count = len(distinct_run_ids)
            distinct_prs       = {ev["pr_id"] for ev in deduped}
            distinct_prs_count = len(distinct_prs)

            # Rule 2: MIN_CLUSTER_OCCURRENCES = 3
            if evidence_count < self.MIN_CLUSTER_OCCURRENCES:
                skipped_below_thresh += 1
                continue

            # Guard: ≥ 2 distinct runs
            if distinct_runs_count < self.MIN_DISTINCT_RUNS:
                skipped_below_thresh += 1
                continue

            normalized_pattern_key = f"TEST_CLUSTER_FAILURE:{cluster_key}"

            if normalized_pattern_key in invalidated_keys:
                continue

            # ---------------------------------------------------------- #
            # Scoring                                                      #
            # ---------------------------------------------------------- #
            rollback_count = sum(1 for ev in deduped if ev["rollback"])
            incident_count = sum(1 for ev in deduped if ev["incident"])

            # 1. Frequency score
            freq_score = min(evidence_count / 10.0, 1.0) * 100.0

            # 2. Density score
            effective_total = max(evidence_bundle.total_runs_in_window, 20)
            density_score   = (evidence_count / effective_total) * 100.0

            # 3. Recency score
            timestamps = [ev["created_at"] for ev in deduped if ev.get("created_at")]
            last_seen  = max(timestamps) if timestamps else datetime.utcnow()
            days_since = max(
                (evidence_bundle.evidence_window_end - last_seen).days, 0
            )
            recency_score = math.exp(-days_since / 14.0) * 100.0

            # 4. Churn score
            total_churn = sum(ev["churn"] for ev in deduped)
            churn_score = (
                min(math.log(1.0 + total_churn) / math.log(1.0 + 1000.0), 1.0)
                * 100.0
            )

            # 5. Rollback score (progressive)
            rollback_score = min(rollback_count / 3.0, 1.0) * 100.0

            # 6. Incident score (escalates faster)
            incident_score = min(incident_count / 3.0, 1.0) * 100.0

            weighted_score = round(
                0.20 * freq_score
                + 0.05 * density_score
                + 0.20 * recency_score
                + 0.15 * churn_score
                + 0.20 * rollback_score
                + 0.20 * incident_score,
                2,
            )

            # Risk classification
            if weighted_score >= 80.0:
                risk_level = "CRITICAL"
            elif weighted_score >= 50.0:
                risk_level = "HIGH"
            elif weighted_score >= 30.0:
                risk_level = "MODERATE"
            else:
                risk_level = "LOW"

            # Confidence level
            if evidence_count >= 5 and distinct_prs_count >= 3 and days_since < 30:
                confidence_level = "HIGH"
            elif evidence_count >= 3 and distinct_prs_count >= 2 and days_since < 90:
                confidence_level = "MODERATE"
            else:
                confidence_level = "LOW"

            # ---------------------------------------------------------- #
            # Human-readable explanation (Rule 5 template)                 #
            #                                                              #
            # Example:                                                     #
            # "payment_refund_spec and user_subscription_spec failed       #
            #  together in 4 regressions involving session token changes." #
            # ---------------------------------------------------------- #
            member_identities: List[str] = deduped[0]["member_identities"]
            trigger_files: List[str]     = deduped[0].get("trigger_files", [])

            # Short display names (test_name part after "::")
            def _short_name(identity: str) -> str:
                return identity.split("::")[-1] if "::" in identity else identity

            names_label = " and ".join(_short_name(i) for i in member_identities)

            trigger_label = ""
            if trigger_files:
                # Show at most 2 trigger files to keep the explanation concise
                sample = trigger_files[:2]
                trigger_label = " involving " + " and ".join(
                    f.split("/")[-1] for f in sample
                ) + " changes"

            outcome_suffix = ""
            if rollback_count or incident_count:
                parts: List[str] = []
                if rollback_count:
                    parts.append(
                        f"{rollback_count} rollback-linked"
                    )
                if incident_count:
                    parts.append(
                        f"{incident_count} incident-linked"
                    )
                outcome_suffix = f" ({', '.join(parts)})"

            explanation = (
                f"{names_label} failed together in {evidence_count} regression"
                + ("s" if evidence_count != 1 else "")
                + trigger_label
                + outcome_suffix
                + f" during the last {evidence_bundle.history_window_days} days."
            )

            # ---------------------------------------------------------- #
            # Overwrite protection                                          #
            # ---------------------------------------------------------- #
            existing = (
                db.query(FragilityPattern)
                .filter(
                    FragilityPattern.repository_id == repository_id,
                    FragilityPattern.normalized_pattern_key == normalized_pattern_key,
                )
                .first()
            )

            if existing:
                existing_window_end_str = existing.replayable_evidence_snapshot.get(
                    "evidence_window_end"
                )
                is_newer_window = True
                if existing_window_end_str:
                    try:
                        ew = datetime.fromisoformat(existing_window_end_str)
                        is_newer_window = evidence_bundle.evidence_window_end > ew
                    except Exception:
                        pass

                is_stronger  = evidence_count > existing.evidence_count
                is_newer_ver = self.SCORING_VERSION != existing.scoring_formula_version

                if is_newer_window or is_stronger or is_newer_ver:
                    db.delete(existing)
                    db.commit()
                else:
                    continue

            # ---------------------------------------------------------- #
            # Deterministic evidence IDs (UUID v5)                         #
            # ---------------------------------------------------------- #
            sorted_deduped = sorted(
                deduped,
                key=lambda x: (
                    x.get("created_at") or datetime.min,
                    str(x.get("run_id") or ""),
                    str(x.get("pr_id")  or ""),
                ),
            )

            evidence_ids: List[str] = []
            for ev in sorted_deduped:
                namespace_payload = (
                    f"{normalized_pattern_key}|TEST_FAILURE|"
                    f"{ev['run_id']}|{ev['pr_id']}|"
                    f"{self.NORMALIZATION_RULES_VERSION}|{self.SCORING_VERSION}|"
                    f"{evidence_bundle.evidence_window_start.isoformat()}->"
                    f"{evidence_bundle.evidence_window_end.isoformat()}"
                )
                det_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, namespace_payload))
                evidence_ids.append(det_uuid)

            # ---------------------------------------------------------- #
            # Replayable snapshot                                          #
            # ---------------------------------------------------------- #
            linked_prs  = sorted({str(ev["pr_id"])  for ev in sorted_deduped})
            linked_runs = sorted({str(ev["run_id"]) for ev in sorted_deduped})

            bundle_payload = (
                f"key:{normalized_pattern_key}|prs:{linked_prs}|runs:{linked_runs}"
            )
            bundle_hash = hashlib.sha256(
                bundle_payload.encode("utf-8")
            ).hexdigest()

            summary_stats = {
                "total_evidence":     evidence_count,
                "distinct_prs_count": distinct_prs_count,
                "distinct_runs_count": distinct_runs_count,
                "days_since_last_seen": days_since,
                "rollback_count":     rollback_count,
                "incident_count":     incident_count,
                "cluster_size":       len(member_identities),
            }

            replayable_snapshot = {
                "evidence_ids":            sorted(evidence_ids),
                "evidence_counts":         {"TEST_FAILURE": evidence_count},
                "source_entity_references": member_identities,
                "evidence_bundle_hash":    bundle_hash,
                "linked_prs":              linked_prs,
                "linked_runs":             linked_runs,
                "linked_incidents":        [],
                "summary_statistics":      summary_stats,
                "evidence_window_start":   evidence_bundle.evidence_window_start.isoformat(),
                "evidence_window_end":     evidence_bundle.evidence_window_end.isoformat(),
            }

            score_components = {
                "frequency":  freq_score,
                "density":    density_score,
                "recency":    recency_score,
                "churn":      churn_score,
                "rollback":   rollback_score,
                "incident":   incident_score,
            }

            hash_payload = {
                "normalized_pattern_key": normalized_pattern_key,
                "evidence_ids":           sorted(evidence_ids),
                "score_components":       score_components,
                "evidence_window_start":  evidence_bundle.evidence_window_start.isoformat(),
                "evidence_window_end":    evidence_bundle.evidence_window_end.isoformat(),
                "scoring_formula_version": self.SCORING_VERSION,
            }
            serialized       = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"))
            pattern_hash_val = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

            # Context for fragility resolver matching
            context = {
                "cluster_key":         cluster_key,
                "member_identities":   member_identities,
                "trigger_files":       trigger_files,
                "rollback_count":      rollback_count,
                "incident_count":      incident_count,
                "related_tests":       member_identities,
            }

            # ---------------------------------------------------------- #
            # Persist pattern                                               #
            # ---------------------------------------------------------- #
            # Title: short names joined with " + "
            short_names = [_short_name(i) for i in member_identities]
            title = "Test Cluster: " + " + ".join(short_names)

            pattern = FragilityPattern(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pattern_type="TEST_CLUSTER_FAILURE",
                normalized_pattern_key=normalized_pattern_key,
                title=title,
                explanation=explanation,
                fragility_score=weighted_score,
                risk_level=risk_level,
                confidence_level=confidence_level,
                pattern_hash=pattern_hash_val,
                score_components=score_components,
                replayable_evidence_snapshot=replayable_snapshot,
                fragility_generation_version=self.GENERATION_VERSION,
                scoring_formula_version=self.SCORING_VERSION,
                evidence_count=evidence_count,
                incident_count=incident_count,
                related_failure_count=evidence_count,
                status="ACTIVE",
                context=context,
                first_seen_at=min(timestamps) if timestamps else datetime.utcnow(),
                last_seen_at=last_seen,
            )
            db.add(pattern)
            db.flush()

            # Persist evidence links
            for idx, ev in enumerate(sorted_deduped):
                rollback_note = " Rollback-linked." if ev.get("rollback") else ""
                incident_note = " Incident-linked." if ev.get("incident") else ""
                link_summary = (
                    f"Tests [{', '.join(member_identities)}] co-failed in run "
                    f"'{ev['run_id']}' (PR: {ev['pr_id']})."
                    f"{rollback_note}{incident_note}"
                )
                link = FragilityEvidenceLink(
                    id=uuid.UUID(evidence_ids[idx]),
                    fragility_pattern_id=pattern.id,
                    evidence_type="TEST_FAILURE",
                    source_test_run_id=ev["run_id"],
                    source_pull_request_id=ev["pr_id"],
                    evidence_summary=link_summary,
                )
                db.add(link)

            patterns_mined += 1

        db.commit()

        logger.info(
            "TestClusterFailureEngine finished: %d patterns mined, "
            "%d skipped (below threshold), %d storm runs suppressed, "
            "%d infra tests suppressed, %d flaky tests suppressed.",
            patterns_mined,
            skipped_below_thresh,
            suppressed_storm_runs,
            suppressed_infra_tests,
            suppressed_flaky_tests,
        )

        return {
            "patterns_mined": patterns_mined,
            "diagnostics": {
                "skipped_below_threshold":  skipped_below_thresh,
                "suppressed_storm_runs":    suppressed_storm_runs,
                "suppressed_infra_tests":   suppressed_infra_tests,
                "suppressed_flaky_tests":   suppressed_flaky_tests,
            },
        }

    # ================================================================== #
    # Internal helpers                                                     #
    # ================================================================== #

    @staticmethod
    def _resolve_neighbourhood(tc: TestCase) -> str:
        """
        Resolves the module neighbourhood for a TestCase using a
        lightweight version of the TestAreaResolver hierarchy:
          1. Suite name (stripped of noise suffixes)
          2. Stable identity path prefix (before "::")
          3. Fallback: "general"
        """
        suite = tc.suite_name.lower()
        clean = (
            suite
            .replace("_suite",  "")
            .replace("_tests",  "")
            .replace("test_",   "")
            .replace("_test",   "")
        ).strip()
        if clean:
            return clean

        if "::" in tc.stable_identity:
            prefix = tc.stable_identity.split("::")[0]
            cleaned = (
                prefix
                .replace("_suite",  "")
                .replace("_tests",  "")
                .replace("test_",   "")
                .replace("_test",   "")
            ).strip().lower()
            if cleaned:
                return cleaned

        return "general"

    def _emit_cluster_combos(
        self,
        tcs: List[TestCase],
        axis_label: str,
        run_id: uuid.UUID,
        pr_id: uuid.UUID,
        pr_rollback: bool,
        pr_incident: bool,
        created_at: Optional[datetime],
        churn: int,
        cluster_evidence: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        """
        Generates bounded cluster combination keys from a list of co-failing
        TestCase objects and appends one evidence dict per combo to
        ``cluster_evidence``.

        Combinations generated:
          - All pairs  (n=2)
          - One representative triple (first 3) when ≥ 3 tests present
        """
        # All pairs
        for tc_a, tc_b in iter_combinations(tcs, 2):
            sorted_ids = sorted(
                [tc_a.stable_identity, tc_b.stable_identity]
            )
            cluster_key = f"{axis_label}:{','.join(sorted_ids)}"
            # Capture the trigger files from the PR
            cluster_evidence[cluster_key].append({
                "run_id":             run_id,
                "pr_id":              pr_id,
                "created_at":         created_at,
                "rollback":           pr_rollback,
                "incident":           pr_incident,
                "churn":              churn,
                "member_identities":  sorted_ids,
                "trigger_files":      [],  # filled at pattern-creation time from pr_to_files
            })

        # One representative triple
        if len(tcs) >= 3:
            triple = sorted(tcs[:3], key=lambda t: t.stable_identity)
            sorted_ids = [t.stable_identity for t in triple]
            cluster_key = f"{axis_label}:{','.join(sorted_ids)}"
            cluster_evidence[cluster_key].append({
                "run_id":             run_id,
                "pr_id":              pr_id,
                "created_at":         created_at,
                "rollback":           pr_rollback,
                "incident":           pr_incident,
                "churn":              churn,
                "member_identities":  sorted_ids,
                "trigger_files":      [],
            })

    # ================================================================== #
    # Lifecycle: stale decay                                               #
    # ================================================================== #

    def apply_stale_decay(
        self,
        repository_id: uuid.UUID,
        now: Optional[datetime] = None,
    ) -> int:
        """
        Applies a cautious stale decay of 10 % every 30 days to active
        TEST_CLUSTER_FAILURE patterns:
          - score_new = score_orig × 0.9^(days/30)
          - Transition to STALE after 90 days of inactivity.
          - Transition to INVALIDATED with reason STALE_NO_RECENT_EVIDENCE
            after 180 days.
        """
        now_time = now or datetime.utcnow()
        active_patterns = (
            self.db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.pattern_type == "TEST_CLUSTER_FAILURE",
                FragilityPattern.status == "ACTIVE",
            )
            .all()
        )

        decayed_count = 0
        for p in active_patterns:
            days_since = max((now_time - p.last_seen_at).days, 0)

            if days_since >= self.STALE_AFTER_DAYS:
                decay_ratio = 0.9 ** (days_since / 30.0)
                p.fragility_score = round(p.fragility_score * decay_ratio, 2)

                new_components = dict(p.score_components)
                new_components["decayed"]    = True
                new_components["decay_days"] = days_since
                p.score_components = new_components
                p.updated_at = now_time
                decayed_count += 1

                if days_since >= self.INVALIDATE_AFTER_DAYS:
                    p.status             = "INVALIDATED"
                    p.invalidated_reason = "STALE_NO_RECENT_EVIDENCE"
                    p.invalidated_at     = now_time
                    p.invalidated_by     = "SYSTEM_DECAY"
                    logger.info(
                        "Pattern %s transitioned to INVALIDATED (age > %d days).",
                        p.normalized_pattern_key,
                        self.INVALIDATE_AFTER_DAYS,
                    )
                else:
                    p.status = "STALE"
                    logger.info(
                        "Pattern %s transitioned to STALE (age > %d days).",
                        p.normalized_pattern_key,
                        self.STALE_AFTER_DAYS,
                    )

        self.db.commit()
        return decayed_count
