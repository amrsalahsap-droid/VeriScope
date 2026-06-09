"""
ChangedFileFailureHotspotMiner Service

Detects files/modules often changed before failed runs.
Creates FragilityMemory and FragilityEvidenceEvent records for:
- FILE_FAILURE_HOTSPOT
- RISKY_CHANGE_COMBINATION
- BEHAVIOR_FRAGILITY (if mapped)
- JOURNEY_FRAGILITY (if mapped)
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestRun, TestResult, TestCase
from app.models.recommendation import RecommendationOutcome
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.behavior_scenario import BehaviorScenario
from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent

logger = logging.getLogger(__name__)


class ChangedFileFailureHotspotMiner:
    """Detects files/modules often changed before failed runs."""
    
    DEFAULT_TIME_WINDOW_DAYS = 180
    MIN_EVIDENCE_COUNT = 3
    MIN_DISTINCT_PRS = 2
    TEMPORAL_PROXIMITY_HOURS = 24
    ESCAPED_DEFECT_BONUS = 25.0
    ROLLBACK_BONUS = 20.0
    
    def __init__(self, db: Session):
        self.db = db
    
    def mine_file_hotspots(
        self,
        repository_id: uuid.UUID,
        time_window_days: int = DEFAULT_TIME_WINDOW_DAYS,
    ) -> Dict[str, int]:
        """
        Mine file failure hotspots and create fragility memory records.
        
        Args:
            repository_id: Repository to mine
            time_window_days: Time window for historical data (default 180 days)
            
        Returns:
            Dict with mining results:
            - file_hotspots_detected: count of FILE_FAILURE_HOTSPOT patterns
            - risky_combinations_detected: count of RISKY_CHANGE_COMBINATION patterns
            - behavior_fragility_detected: count of BEHAVIOR_FRAGILITY patterns
            - journey_fragility_detected: count of JOURNEY_FRAGILITY patterns
            - evidence_events_created: count of evidence events created
        """
        logger.info(f"Mining file failure hotspots for repository {repository_id} with {time_window_days} day window")
        
        # Calculate time window
        now = datetime.utcnow()
        window_start = now - timedelta(days=time_window_days)
        
        # Validate repository
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")
        
        results = {
            "file_hotspots_detected": 0,
            "risky_combinations_detected": 0,
            "behavior_fragility_detected": 0,
            "journey_fragility_detected": 0,
            "evidence_events_created": 0,
        }
        
        # 1. Detect file failure hotspots
        file_hotspots = self._detect_file_hotspots(repository_id, window_start, now)
        results["file_hotspots_detected"] = len(file_hotspots)
        
        # 2. Detect risky file combinations
        risky_combinations = self._detect_risky_combinations(repository_id, window_start, now)
        results["risky_combinations_detected"] = len(risky_combinations)
        
        # 3. Create fragility memory records
        for hotspot_data in file_hotspots:
            memory_id, evidence_count = self._create_file_hotspot_memory(
                repository_id, hotspot_data, window_start, now
            )
            results["evidence_events_created"] += evidence_count
            
            # Check for behavior/journey mapping
            behavior_fragility = self._map_file_to_behavior_fragility(
                repository_id, hotspot_data, memory_id, window_start, now
            )
            if behavior_fragility:
                results["behavior_fragility_detected"] += 1
                results["evidence_events_created"] += 1
            
            journey_fragility = self._map_file_to_journey_fragility(
                repository_id, hotspot_data, memory_id, window_start, now
            )
            if journey_fragility:
                results["journey_fragility_detected"] += 1
                results["evidence_events_created"] += 1
        
        for combination_data in risky_combinations:
            memory_id, evidence_count = self._create_risky_combination_memory(
                repository_id, combination_data, window_start, now
            )
            results["evidence_events_created"] += evidence_count
        
        self.db.commit()
        
        logger.info(
            f"File hotspot mining complete: hotspots={results['file_hotspots_detected']}, "
            f"combinations={results['risky_combinations_detected']}, "
            f"behavior_fragility={results['behavior_fragility_detected']}, "
            f"journey_fragility={results['journey_fragility_detected']}, "
            f"evidence_events={results['evidence_events_created']}"
        )
        
        return results
    
    def _detect_file_hotspots(
        self,
        repository_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict]:
        """
        Detect files often changed before failed test runs.
        
        Links failures to PRs by commit/head_sha when possible.
        Uses conservative temporal proximity if no exact linkage.
        """
        # Query failed test runs within window
        failed_runs = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.created_at >= window_start,
            TestRun.created_at <= window_end,
            TestRun.status == "failed",
            TestRun.parser_support_status != "UNSUPPORTED",
        ).all()
        
        # Build file -> failure count mapping
        file_failure_counts = defaultdict(int)
        file_failure_prs = defaultdict(set)
        file_failure_details = defaultdict(list)
        
        for run in failed_runs:
            # Try to find PR by commit/head_sha linkage
            pr = None
            if run.commit_sha:
                pr = self.db.query(PullRequest).filter(
                    PullRequest.repository_id == repository_id,
                    PullRequest.head_commit_sha == run.commit_sha,
                ).first()
            
            # Fallback: use pull_request_id from test run
            if not pr and run.pull_request_id:
                pr = self.db.query(PullRequest).filter(
                    PullRequest.id == run.pull_request_id
                ).first()
            
            # Fallback: use temporal proximity
            if not pr:
                pr = self.db.query(PullRequest).filter(
                    PullRequest.repository_id == repository_id,
                    PullRequest.closed_at >= run.created_at - timedelta(hours=self.TEMPORAL_PROXIMITY_HOURS),
                    PullRequest.closed_at <= run.created_at + timedelta(hours=self.TEMPORAL_PROXIMITY_HOURS),
                ).first()
            
            if not pr:
                continue
            
            # Get changed files for this PR
            changed_files = self.db.query(PullRequestChangedFile).filter(
                PullRequestChangedFile.pull_request_id == pr.id
            ).all()
            
            for cf in changed_files:
                file_path = cf.file_path
                file_failure_counts[file_path] += 1
                file_failure_prs[file_path].add(pr.id)
                file_failure_details[file_path].append({
                    "pr_id": pr.id,
                    "pr_number": pr.number,
                    "commit_sha": pr.head_commit_sha,
                    "test_run_id": run.id,
                    "occurred_at": run.created_at,
                    "has_escaped_defect": self._check_escaped_defect_for_run(run.id),
                    "has_rollback": self._check_rollback_for_run(run.id),
                })
        
        # Filter for significant hotspots
        hotspots = []
        for file_path, count in file_failure_counts.items():
            if count < self.MIN_EVIDENCE_COUNT:
                continue
            
            pr_ids = file_failure_prs[file_path]
            if len(pr_ids) < self.MIN_DISTINCT_PRS:
                continue
            
            # Calculate score
            details = file_failure_details[file_path]
            score = self._calculate_hotspot_score(details, count, len(pr_ids), window_end)
            
            # Get most recent failure
            most_recent = max(details, key=lambda x: x["occurred_at"])
            
            hotspots.append({
                "file_path": file_path,
                "failure_count": count,
                "distinct_pr_count": len(pr_ids),
                "most_recent_at": most_recent["occurred_at"],
                "first_seen_at": min(d["occurred_at"] for d in details),
                "score": score,
                "details": details,
            })
        
        return hotspots
    
    def _detect_risky_combinations(
        self,
        repository_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict]:
        """
        Detect risky file combinations that often lead to failures.
        """
        # Query failed test runs within window
        failed_runs = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.created_at >= window_start,
            TestRun.created_at <= window_end,
            TestRun.status == "failed",
            TestRun.parser_support_status != "UNSUPPORTED",
        ).all()
        
        # Build file combination -> failure count mapping
        combination_counts = defaultdict(int)
        combination_prs = defaultdict(set)
        combination_details = defaultdict(list)
        
        for run in failed_runs:
            # Find PR (same logic as hotspot detection)
            pr = None
            if run.commit_sha:
                pr = self.db.query(PullRequest).filter(
                    PullRequest.repository_id == repository_id,
                    PullRequest.head_commit_sha == run.commit_sha,
                ).first()
            
            if not pr and run.pull_request_id:
                pr = self.db.query(PullRequest).filter(
                    PullRequest.id == run.pull_request_id
                ).first()
            
            if not pr:
                pr = self.db.query(PullRequest).filter(
                    PullRequest.repository_id == repository_id,
                    PullRequest.closed_at >= run.created_at - timedelta(hours=self.TEMPORAL_PROXIMITY_HOURS),
                    PullRequest.closed_at <= run.created_at + timedelta(hours=self.TEMPORAL_PROXIMITY_HOURS),
                ).first()
            
            if not pr:
                continue
            
            # Get changed files
            changed_files = self.db.query(PullRequestChangedFile).filter(
                PullRequestChangedFile.pull_request_id == pr.id
            ).all()
            
            file_paths = [cf.file_path for cf in changed_files]
            
            # Count all combinations (pairs)
            for i in range(len(file_paths)):
                for j in range(i + 1, len(file_paths)):
                    combination = tuple(sorted([file_paths[i], file_paths[j]]))
                    combination_counts[combination] += 1
                    combination_prs[combination].add(pr.id)
                    combination_details[combination].append({
                        "pr_id": pr.id,
                        "pr_number": pr.number,
                        "test_run_id": run.id,
                        "occurred_at": run.created_at,
                    })
        
        # Filter for significant combinations
        risky_combinations = []
        for combination, count in combination_counts.items():
            if count < self.MIN_EVIDENCE_COUNT:
                continue
            
            pr_ids = combination_prs[combination]
            if len(pr_ids) < self.MIN_DISTINCT_PRS:
                continue
            
            # Calculate score
            details = combination_details[combination]
            score = self._calculate_combination_score(count, len(pr_ids), window_end)
            
            risky_combinations.append({
                "file_combination": combination,
                "combination_count": count,
                "distinct_pr_count": len(pr_ids),
                "score": score,
                "details": details,
            })
        
        return risky_combinations
    
    def _calculate_hotspot_score(
        self,
        details: List[Dict],
        failure_count: int,
        distinct_pr_count: int,
        window_end: datetime,
    ) -> float:
        """
        Calculate fragility score for file hotspot.
        
        Factors:
        - Failure frequency
        - PR diversity
        - Recency
        - Escaped defect bonus
        - Rollback bonus
        """
        # Frequency score (0-100)
        frequency_score = min(100.0, (failure_count / 10.0) * 100.0)
        
        # PR diversity score (0-100)
        diversity_score = min(100.0, (distinct_pr_count / 5.0) * 100.0)
        
        # Recency score (0-100)
        most_recent = max(d["occurred_at"] for d in details)
        days_since = (window_end - most_recent).days
        recency_score = max(0.0, 100.0 - (days_since / 180.0) * 100.0)
        
        # Base score
        base_score = (frequency_score * 0.4) + (diversity_score * 0.3) + (recency_score * 0.3)
        
        # Apply bonuses
        has_escaped_defect = any(d.get("has_escaped_defect", False) for d in details)
        has_rollback = any(d.get("has_rollback", False) for d in details)
        
        if has_escaped_defect:
            base_score = min(100.0, base_score + self.ESCAPED_DEFECT_BONUS)
        
        if has_rollback:
            base_score = min(100.0, base_score + self.ROLLBACK_BONUS)
        
        return round(base_score, 2)
    
    def _calculate_combination_score(
        self,
        combination_count: int,
        distinct_pr_count: int,
        window_end: datetime,
    ) -> float:
        """
        Calculate fragility score for risky file combination.
        """
        # Frequency score
        frequency_score = min(100.0, (combination_count / 5.0) * 100.0)
        
        # PR diversity score
        diversity_score = min(100.0, (distinct_pr_count / 3.0) * 100.0)
        
        # Weighted score
        score = (frequency_score * 0.6) + (diversity_score * 0.4)
        
        return round(score, 2)
    
    def _check_escaped_defect_for_run(self, test_run_id: uuid.UUID) -> bool:
        """Check if test run has linked escaped defect."""
        outcome = self.db.query(RecommendationOutcome).join(
            TestRun, RecommendationOutcome.recommendation_run_id == TestRun.recommendation_run_id
        ).filter(
            TestRun.id == test_run_id,
            RecommendationOutcome.escaped_defect == True,
        ).first()
        return outcome is not None
    
    def _check_rollback_for_run(self, test_run_id: uuid.UUID) -> bool:
        """Check if test run has linked rollback."""
        outcome = self.db.query(RecommendationOutcome).join(
            TestRun, RecommendationOutcome.recommendation_run_id == TestRun.recommendation_run_id
        ).filter(
            TestRun.id == test_run_id,
            RecommendationOutcome.rollback_occurred == True,
        ).first()
        return outcome is not None
    
    def _create_file_hotspot_memory(
        self,
        repository_id: uuid.UUID,
        hotspot_data: Dict,
        window_start: datetime,
        window_end: datetime,
    ) -> Tuple[uuid.UUID, int]:
        """
        Create FragilityMemory record for file failure hotspot.
        """
        # Generate deterministic memory key
        memory_key = f"FILE_FAILURE_HOTSPOT:{hotspot_data['file_path']}"
        
        # Determine risk level
        risk_level = self._determine_risk_level(hotspot_data["score"])
        
        # Calculate confidence based on evidence count
        confidence = min(1.0, hotspot_data["failure_count"] / 10.0)
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "FILE",
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = hotspot_data["score"]
            existing.risk_level = risk_level
            existing.confidence = confidence
            existing.last_seen_at = window_end
            existing.status = "ACTIVE"
            memory_id = existing.id
        else:
            # Create new memory
            memory = FragilityMemoryV2(
                repository_id=repository_id,
                memory_key=memory_key,
                memory_type="FILE_FAILURE_HOTSPOT",
                subject_type="FILE",
                subject_id=None,
                subject_name=hotspot_data["file_path"],
                risk_level=risk_level,
                fragility_score=hotspot_data["score"],
                confidence=confidence,
                status="ACTIVE",
                first_seen_at=hotspot_data["first_seen_at"],
                last_seen_at=window_end,
            )
            self.db.add(memory)
            self.db.flush()
            memory_id = memory.id
        
        # Create evidence events for each failure
        evidence_count = 0
        for detail in hotspot_data["details"]:
            self._create_evidence_event(
                memory_id=memory_id,
                repository_id=repository_id,
                evidence_type="TEST_FAILURE",
                source_entity_type="TEST_RUN",
                source_entity_id=detail["test_run_id"],
                pull_request_id=detail["pr_id"],
                test_run_id=detail["test_run_id"],
                changed_files=[hotspot_data["file_path"]],
                evidence_summary=f"File {hotspot_data['file_path']} changed in PR #{detail['pr_number']} before failed test run",
                evidence_weight=1.0 / len(hotspot_data["details"]),
                occurred_at=detail["occurred_at"],
            )
            evidence_count += 1
        
        return memory_id, evidence_count
    
    def _create_risky_combination_memory(
        self,
        repository_id: uuid.UUID,
        combination_data: Dict,
        window_start: datetime,
        window_end: datetime,
    ) -> Tuple[uuid.UUID, int]:
        """
        Create FragilityMemory record for risky file combination.
        """
        # Generate deterministic memory key
        combination_key = ":".join(combination_data["file_combination"])
        memory_key = f"RISKY_CHANGE_COMBINATION:{combination_key}"
        
        # Determine risk level
        risk_level = self._determine_risk_level(combination_data["score"])
        
        # Calculate confidence
        confidence = min(1.0, combination_data["combination_count"] / 5.0)
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "FILE",
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = combination_data["score"]
            existing.risk_level = risk_level
            existing.confidence = confidence
            existing.last_seen_at = window_end
            existing.status = "ACTIVE"
            memory_id = existing.id
        else:
            # Create new memory
            memory = FragilityMemoryV2(
                repository_id=repository_id,
                memory_key=memory_key,
                memory_type="RISKY_CHANGE_COMBINATION",
                subject_type="FILE",
                subject_id=None,
                subject_name=combination_key,
                risk_level=risk_level,
                fragility_score=combination_data["score"],
                confidence=confidence,
                status="ACTIVE",
                first_seen_at=window_start,
                last_seen_at=window_end,
            )
            self.db.add(memory)
            self.db.flush()
            memory_id = memory.id
        
        # Create evidence event
        self._create_evidence_event(
            memory_id=memory_id,
            repository_id=repository_id,
            evidence_type="CO_FAILURE",
            source_entity_type="TEST_RUN",
            source_entity_id=None,
            changed_files=list(combination_data["file_combination"]),
            evidence_summary=f"Risky file combination {combination_key} detected in {combination_data['combination_count']} failed runs",
            evidence_weight=1.0,
            occurred_at=window_end,
        )
        
        return memory_id, 1
    
    def _map_file_to_behavior_fragility(
        self,
        repository_id: uuid.UUID,
        hotspot_data: Dict,
        fragility_memory_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> Optional[uuid.UUID]:
        """
        Map file hotspot to behavior fragility if file is linked to behavior.
        """
        # Check if file is linked to behavior via test coverage
        # This would require test coverage data linking files to behaviors
        # For now, return None as this requires additional data
        return None
    
    def _map_file_to_journey_fragility(
        self,
        repository_id: uuid.UUID,
        hotspot_data: Dict,
        fragility_memory_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> Optional[uuid.UUID]:
        """
        Map file hotspot to journey fragility if file is linked to journey.
        """
        # Check if file is linked to journey via test coverage
        # This would require test coverage data linking files to journeys
        # For now, return None as this requires additional data
        return None
    
    def _create_evidence_event(
        self,
        memory_id: uuid.UUID,
        repository_id: uuid.UUID,
        evidence_type: str,
        source_entity_type: str,
        source_entity_id: Optional[uuid.UUID],
        pull_request_id: Optional[uuid.UUID] = None,
        recommendation_run_id: Optional[uuid.UUID] = None,
        test_run_id: Optional[uuid.UUID] = None,
        test_result_id: Optional[uuid.UUID] = None,
        incident_url: Optional[str] = None,
        rollback_url: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        affected_behaviors: Optional[List[str]] = None,
        affected_journeys: Optional[List[str]] = None,
        evidence_summary: str = "",
        evidence_weight: float = 1.0,
        occurred_at: Optional[datetime] = None,
    ):
        """Create FragilityEvidenceEvent record."""
        event = FragilityEvidenceEvent(
            fragility_memory_id=memory_id,
            repository_id=repository_id,
            evidence_type=evidence_type,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            pull_request_id=pull_request_id,
            recommendation_run_id=recommendation_run_id,
            test_run_id=test_run_id,
            test_result_id=test_result_id,
            incident_url=incident_url,
            rollback_url=rollback_url,
            changed_files=changed_files or [],
            affected_behaviors=affected_behaviors or [],
            affected_journeys=affected_journeys or [],
            evidence_summary=evidence_summary,
            evidence_weight=evidence_weight,
            occurred_at=occurred_at or datetime.utcnow(),
        )
        self.db.add(event)
    
    def _determine_risk_level(self, score: float) -> str:
        """Determine risk level from fragility score."""
        if score >= 75.0:
            return "CRITICAL"
        elif score >= 50.0:
            return "HIGH"
        elif score >= 25.0:
            return "MODERATE"
        else:
            return "LOW"
