from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.recommendation import RecommendationRun, RecommendationExplanation, RecommendationOutcome

class EvidenceGapDetector:
    @classmethod
    def detect_gaps(cls, db: Session, run: RecommendationRun, explanations: List[Any]) -> List[Dict[str, str]]:
        gaps = []
        
        # 1. No direct coverage mapping
        has_coverage_match = False
        for exp in explanations:
            sig_list = getattr(exp, "signals", []) or []
            if "coverage match" in [s.lower() for s in sig_list]:
                has_coverage_match = True
                break
                
        if not has_coverage_match:
            domains = set()
            for exp in explanations:
                dom_list = getattr(exp, "domains", []) or []
                for d in dom_list:
                    if d.lower() != "general":
                        domains.add(d.title())
            area_str = " and ".join(sorted(list(domains))) if domains else "password reset"
            gaps.append({
                "severity": "HIGH",
                "message": f"No direct coverage mapping exists for {area_str} workflow.",
                "impact": "Veriscope must rely on module-level path heuristics, reducing selection precision."
            })
            
        # 2. Stale coverage
        is_coverage_stale = False
        if not run.coverage_report_id:
            is_coverage_stale = True
        elif run.evidence_quality in ("LOW", "UNKNOWN"):
            is_coverage_stale = True
            
        if is_coverage_stale:
            gaps.append({
                "severity": "WARNING",
                "message": "Coverage report is stale or mapped from a fallback branch/commit.",
                "impact": "Code lines modified in this PR might have shifted, causing direct line-level mappings to be misaligned."
            })
            
        # 3. Missing test history
        if not run.test_history_window_start or run.flakiness_profile_hash in (None, "empty_flakiness_state"):
            gaps.append({
                "severity": "WARNING",
                "message": "Test history and flakiness data are missing or incomplete.",
                "impact": "Flaky tests cannot be quarantined automatically, and historical failure signals cannot be prioritized."
            })
            
        # 4. Low graph confidence
        if run.dependency_state_hash in (None, "empty_dependency_state", "empty_v3"):
            gaps.append({
                "severity": "WARNING",
                "message": "Static dependency graph tracking is inactive or has low confidence.",
                "impact": "Veriscope cannot trace indirect architectural import relationships across code boundaries."
            })
            
        # 5. No outcome data
        outcome_count = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.repository_id == run.repository_id,
            RecommendationOutcome.recommendation_run_id != run.id
        ).count()
        if outcome_count == 0:
            gaps.append({
                "severity": "INFO",
                "message": "No historical recommendation outcome data exists for this repository.",
                "impact": "Adaptive feedback learning is inactive, preventing the engine from calibrating recommendations based on developer behavior."
            })
            
        # 6. Weak token matching
        has_token_match = False
        for exp in explanations:
            sig_list = getattr(exp, "signals", []) or []
            if "token match" in [s.lower() for s in sig_list]:
                has_token_match = True
                break
                
        if not has_token_match:
            gaps.append({
                "severity": "WARNING",
                "message": "Weak semantic token correlation between changed files and test suites.",
                "impact": "Convention-based fallback matching must be used, which may result in broader test recommendations."
            })
            
        # 7. Pattern Memory check
        try:
            from app.models.pattern_memory import PatternMemory
            pm_count = db.query(PatternMemory).filter(
                PatternMemory.repository_id == run.repository_id
            ).count()
            if pm_count == 0:
                gaps.append({
                    "severity": "WARNING",
                    "message": "No learning memory available yet.",
                    "impact": "Recommendations cannot benefit from incremental outcome learning or engineer overrides."
                })
        except Exception as exc:
            import logging
            logging.getLogger("veriscope.recommendation").warning(
                f"PatternMemory table missing or unavailable during gap detection: {exc}"
            )
            gaps.append({
                "severity": "WARNING",
                "message": "No learning memory available yet.",
                "impact": "Recommendations cannot benefit from incremental outcome learning or engineer overrides."
            })
            
        return gaps
