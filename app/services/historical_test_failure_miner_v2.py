"""
HistoricalTestFailureMinerV2 Service

Detects repeated and meaningful test failures for fragility memory.
Creates FragilityMemory and FragilityEvidenceEvent records for:
- REPEATED_TEST_FAILURE
- CO_FAILURE_PATTERN
- BEHAVIOR_FRAGILITY (if mapped to behavior)
- JOURNEY_FRAGILITY (if mapped to journey)
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.repository import Repository
from app.models.test_result import TestRun, TestResult, TestCase
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.behavior_scenario import BehaviorScenario
from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent

logger = logging.getLogger(__name__)


class HistoricalTestFailureMinerV2:
    """Detects repeated and meaningful test failures for fragility memory."""
    
    DEFAULT_TIME_WINDOW_DAYS = 90
    MIN_FAILURE_COUNT = 3
    MIN_DISTINCT_PRS = 2
    RECENCY_WEIGHT = 0.3
    REPETITION_WEIGHT = 0.7
    
    def __init__(self, db: Session):
        self.db = db
    
    def mine_test_failures(
        self,
        repository_id: uuid.UUID,
        time_window_days: int = DEFAULT_TIME_WINDOW_DAYS,
    ) -> Dict[str, int]:
        """
        Mine test failures and create fragility memory records.
        
        Args:
            repository_id: Repository to mine
            time_window_days: Time window for historical data (default 90 days)
            
        Returns:
            Dict with mining results:
            - repeated_failures_detected: count of REPEATED_TEST_FAILURE patterns
            - co_failure_patterns_detected: count of CO_FAILURE_PATTERN patterns
            - behavior_fragility_detected: count of BEHAVIOR_FRAGILITY patterns
            - journey_fragility_detected: count of JOURNEY_FRAGILITY patterns
            - evidence_events_created: count of evidence events created
        """
        logger.info(f"Mining test failures for repository {repository_id} with {time_window_days} day window")
        
        # Calculate time window
        now = datetime.utcnow()
        window_start = now - timedelta(days=time_window_days)
        
        # Validate repository
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")
        
        results = {
            "repeated_failures_detected": 0,
            "co_failure_patterns_detected": 0,
            "behavior_fragility_detected": 0,
            "journey_fragility_detected": 0,
            "evidence_events_created": 0,
        }
        
        # 1. Detect repeated test failures
        repeated_failures = self._detect_repeated_failures(repository_id, window_start, now)
        results["repeated_failures_detected"] = len(repeated_failures)
        
        # 2. Detect co-failure patterns
        co_failures = self._detect_co_failures(repository_id, window_start, now)
        results["co_failure_patterns_detected"] = len(co_failures)
        
        # 3. Create fragility memory records
        for failure_data in repeated_failures:
            memory_id, evidence_count = self._create_repeated_failure_memory(
                repository_id, failure_data, window_start, now
            )
            results["evidence_events_created"] += evidence_count
            
            # Check for behavior/journey mapping
            behavior_fragility = self._map_to_behavior_fragility(
                repository_id, failure_data, memory_id, window_start, now
            )
            if behavior_fragility:
                results["behavior_fragility_detected"] += 1
                results["evidence_events_created"] += 1
            
            journey_fragility = self._map_to_journey_fragility(
                repository_id, failure_data, memory_id, window_start, now
            )
            if journey_fragility:
                results["journey_fragility_detected"] += 1
                results["evidence_events_created"] += 1
        
        for co_failure_data in co_failures:
            memory_id, evidence_count = self._create_co_failure_memory(
                repository_id, co_failure_data, window_start, now
            )
            results["evidence_events_created"] += evidence_count
        
        self.db.commit()
        
        logger.info(
            f"Test failure mining complete: repeated={results['repeated_failures_detected']}, "
            f"co_failures={results['co_failure_patterns_detected']}, "
            f"behavior_fragility={results['behavior_fragility_detected']}, "
            f"journey_fragility={results['journey_fragility_detected']}, "
            f"evidence_events={results['evidence_events_created']}"
        )
        
        return results
    
    def _detect_repeated_failures(
        self,
        repository_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict]:
        """
        Detect tests failing repeatedly within time window.
        
        Excludes:
        - Unsupported parser runs
        - Quarantined tests (unless specifically tracking quarantine)
        """
        # Query failed test results within window
        failed_results = self.db.query(
            TestResult,
            TestCase,
            TestRun,
        ).join(
            TestCase, TestResult.test_case_id == TestCase.id
        ).join(
            TestRun, TestResult.test_run_id == TestRun.id
        ).filter(
            TestRun.repository_id == repository_id,
            TestRun.created_at >= window_start,
            TestRun.created_at <= window_end,
            TestResult.status == "failed",
            TestRun.parser_support_status != "UNSUPPORTED",
        ).all()
        
        # Group by test stable_identity
        test_failures = defaultdict(list)
        for result, test_case, test_run in failed_results:
            test_failures[test_case.stable_identity].append({
                "result": result,
                "test_case": test_case,
                "test_run": test_run,
                "occurred_at": test_run.created_at,
            })
        
        # Filter for repeated failures
        repeated_failures = []
        for test_identity, failures in test_failures.items():
            if len(failures) < self.MIN_FAILURE_COUNT:
                continue
            
            # Check for distinct PRs
            pr_ids = {f["test_run"].pull_request_id for f in failures if f["test_run"].pull_request_id}
            if len(pr_ids) < self.MIN_DISTINCT_PRS:
                continue
            
            # Calculate score
            score = self._calculate_repeated_failure_score(failures, window_end)
            
            # Get most recent failure
            most_recent = max(failures, key=lambda x: x["occurred_at"])
            
            repeated_failures.append({
                "test_identity": test_identity,
                "test_case_id": most_recent["test_case"].id,
                "test_name": most_recent["test_case"].test_name,
                "suite_name": most_recent["test_case"].suite_name,
                "failure_count": len(failures),
                "distinct_pr_count": len(pr_ids),
                "most_recent_at": most_recent["occurred_at"],
                "first_seen_at": min(f["occurred_at"] for f in failures),
                "score": score,
                "failures": failures,
            })
        
        return repeated_failures
    
    def _detect_co_failures(
        self,
        repository_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict]:
        """
        Detect tests failing together (co-failure patterns).
        """
        # Query failed test runs within window
        failed_runs = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.created_at >= window_start,
            TestRun.created_at <= window_end,
            TestRun.status == "failed",
            TestRun.parser_support_status != "UNSUPPORTED",
        ).all()
        
        # Group failures by test run
        run_failures = defaultdict(list)
        for run in failed_runs:
            failed_results = self.db.query(TestResult, TestCase).join(
                TestCase, TestResult.test_case_id == TestCase.id
            ).filter(
                TestResult.test_run_id == run.id,
                TestResult.status == "failed",
            ).all()
            for result, test_case in failed_results:
                run_failures[run.id].append(test_case.stable_identity)
        
        # Find co-failure patterns
        co_failure_counts = defaultdict(int)
        co_failure_prs = defaultdict(set)
        
        for run_id, test_identities in run_failures.items():
            if len(test_identities) < 2:
                continue
            
            # Get PR for this run
            run = self.db.query(TestRun).filter(TestRun.id == run_id).first()
            pr_id = run.pull_request_id if run else None
            
            # Count all pairs
            for i in range(len(test_identities)):
                for j in range(i + 1, len(test_identities)):
                    pair = tuple(sorted([test_identities[i], test_identities[j]]))
                    co_failure_counts[pair] += 1
                    if pr_id:
                        co_failure_prs[pair].add(pr_id)
        
        # Filter for significant co-failures
        co_failures = []
        for pair, count in co_failure_counts.items():
            if count < self.MIN_FAILURE_COUNT:
                continue
            
            pr_ids = co_failure_prs[pair]
            if len(pr_ids) < self.MIN_DISTINCT_PRS:
                continue
            
            # Calculate score
            score = self._calculate_co_failure_score(count, len(pr_ids), window_end)
            
            co_failures.append({
                "test_pair": pair,
                "co_failure_count": count,
                "distinct_pr_count": len(pr_ids),
                "score": score,
            })
        
        return co_failures
    
    def _calculate_repeated_failure_score(
        self,
        failures: List[Dict],
        window_end: datetime,
    ) -> float:
        """
        Calculate fragility score for repeated failures.
        
        Factors:
        - Repetition (more failures = higher score)
        - Recency (more recent = higher score)
        """
        failure_count = len(failures)
        
        # Repetition score (0-100)
        repetition_score = min(100.0, (failure_count / 10.0) * 100.0)
        
        # Recency score (0-100)
        most_recent = max(f["occurred_at"] for f in failures)
        days_since = (window_end - most_recent).days
        recency_score = max(0.0, 100.0 - (days_since / 90.0) * 100.0)
        
        # Weighted score
        score = (repetition_score * self.REPETITION_WEIGHT) + (recency_score * self.RECENCY_WEIGHT)
        
        return round(score, 2)
    
    def _calculate_co_failure_score(
        self,
        co_failure_count: int,
        distinct_pr_count: int,
        window_end: datetime,
    ) -> float:
        """
        Calculate fragility score for co-failure patterns.
        """
        # Co-failure frequency score
        frequency_score = min(100.0, (co_failure_count / 5.0) * 100.0)
        
        # PR diversity score
        diversity_score = min(100.0, (distinct_pr_count / 3.0) * 100.0)
        
        # Weighted score
        score = (frequency_score * 0.6) + (diversity_score * 0.4)
        
        return round(score, 2)
    
    def _create_repeated_failure_memory(
        self,
        repository_id: uuid.UUID,
        failure_data: Dict,
        window_start: datetime,
        window_end: datetime,
    ) -> Tuple[uuid.UUID, int]:
        """
        Create FragilityMemory record for repeated test failure.
        """
        # Generate deterministic memory key
        memory_key = f"REPEATED_TEST_FAILURE:{failure_data['test_identity']}"
        
        # Determine risk level
        risk_level = self._determine_risk_level(failure_data["score"])
        
        # Calculate confidence based on evidence count
        confidence = min(1.0, failure_data["failure_count"] / 10.0)
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "TEST",
            FragilityMemoryV2.subject_id == failure_data["test_case_id"],
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = failure_data["score"]
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
                memory_type="REPEATED_TEST_FAILURE",
                subject_type="TEST",
                subject_id=failure_data["test_case_id"],
                subject_name=failure_data["test_identity"],
                risk_level=risk_level,
                fragility_score=failure_data["score"],
                confidence=confidence,
                status="ACTIVE",
                first_seen_at=failure_data["first_seen_at"],
                last_seen_at=window_end,
            )
            self.db.add(memory)
            self.db.flush()
            memory_id = memory.id
        
        # Create evidence events for each failure
        evidence_count = 0
        for failure in failure_data["failures"]:
            self._create_evidence_event(
                memory_id=memory_id,
                repository_id=repository_id,
                evidence_type="REPEATED_FAILURE",
                source_entity_type="TEST_RESULT",
                source_entity_id=failure["result"].id,
                pull_request_id=failure["test_run"].pull_request_id,
                test_run_id=failure["test_run"].id,
                test_result_id=failure["result"].id,
                evidence_summary=f"Test {failure_data['test_identity']} failed in run {failure['test_run'].id}",
                evidence_weight=1.0 / len(failure_data["failures"]),
                occurred_at=failure["occurred_at"],
            )
            evidence_count += 1
        
        return memory_id, evidence_count
    
    def _create_co_failure_memory(
        self,
        repository_id: uuid.UUID,
        co_failure_data: Dict,
        window_start: datetime,
        window_end: datetime,
    ) -> Tuple[uuid.UUID, int]:
        """
        Create FragilityMemory record for co-failure pattern.
        """
        # Generate deterministic memory key
        pair_key = ":".join(co_failure_data["test_pair"])
        memory_key = f"CO_FAILURE_PATTERN:{pair_key}"
        
        # Determine risk level
        risk_level = self._determine_risk_level(co_failure_data["score"])
        
        # Calculate confidence
        confidence = min(1.0, co_failure_data["co_failure_count"] / 5.0)
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "TEST",
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = co_failure_data["score"]
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
                memory_type="CO_FAILURE_PATTERN",
                subject_type="TEST",
                subject_id=None,
                subject_name=pair_key,
                risk_level=risk_level,
                fragility_score=co_failure_data["score"],
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
            evidence_summary=f"Co-failure pattern detected: {pair_key} failed together {co_failure_data['co_failure_count']} times",
            evidence_weight=1.0,
            occurred_at=window_end,
        )
        
        return memory_id, 1
    
    def _map_to_behavior_fragility(
        self,
        repository_id: uuid.UUID,
        failure_data: Dict,
        fragility_memory_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> Optional[uuid.UUID]:
        """
        Map test failure to behavior fragility if test is linked to behavior.
        """
        # Check if test is linked to behavior
        behavior_scenarios = self.db.query(BehaviorScenario).filter(
            BehaviorScenario.test_identifier == failure_data["test_identity"]
        ).all()
        
        if not behavior_scenarios:
            return None
        
        # Create behavior fragility for each linked behavior
        memory_id = None
        for bs in behavior_scenarios:
            behavior = self.db.query(Behavior).filter(Behavior.id == bs.behavior_id).first()
            if not behavior:
                continue
            
            # Generate deterministic memory key
            memory_key = f"BEHAVIOR_FRAGILITY:{behavior.id}"
            
            # Check for existing memory
            existing = self.db.query(FragilityMemoryV2).filter(
                FragilityMemoryV2.repository_id == repository_id,
                FragilityMemoryV2.memory_key == memory_key,
                FragilityMemoryV2.subject_type == "BEHAVIOR",
                FragilityMemoryV2.subject_id == behavior.id,
            ).first()
            
            if existing:
                # Update existing memory
                existing.fragility_score = max(existing.fragility_score, failure_data["score"])
                existing.risk_level = self._determine_risk_level(existing.fragility_score)
                existing.confidence = min(1.0, existing.confidence + 0.1)
                existing.last_seen_at = window_end
                existing.status = "ACTIVE"
                memory_id = existing.id
            else:
                # Create new memory
                memory = FragilityMemoryV2(
                    repository_id=repository_id,
                    memory_key=memory_key,
                    memory_type="BEHAVIOR_FRAGILITY",
                    subject_type="BEHAVIOR",
                    subject_id=behavior.id,
                    subject_name=behavior.name,
                    risk_level=self._determine_risk_level(failure_data["score"]),
                    fragility_score=failure_data["score"],
                    confidence=0.5,
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
                evidence_type="TEST_FAILURE",
                source_entity_type="TEST_RESULT",
                source_entity_id=None,
                evidence_summary=f"Test {failure_data['test_identity']} linked to behavior {behavior.name} failed repeatedly",
                evidence_weight=1.0,
                occurred_at=window_end,
            )
        
        return memory_id
    
    def _map_to_journey_fragility(
        self,
        repository_id: uuid.UUID,
        failure_data: Dict,
        fragility_memory_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> Optional[uuid.UUID]:
        """
        Map test failure to journey fragility if test is linked to journey.
        """
        # Check if test is linked to journey via behavior scenarios
        behavior_scenarios = self.db.query(BehaviorScenario).filter(
            BehaviorScenario.test_identifier == failure_data["test_identity"]
        ).all()
        
        if not behavior_scenarios:
            return None
        
        # Get journeys from behaviors
        journey_ids = set()
        for bs in behavior_scenarios:
            behavior = self.db.query(Behavior).filter(Behavior.id == bs.behavior_id).first()
            if behavior and behavior.journey_id:
                journey_ids.add(behavior.journey_id)
        
        if not journey_ids:
            return None
        
        # Create journey fragility for each linked journey
        memory_id = None
        for journey_id in journey_ids:
            journey = self.db.query(Journey).filter(Journey.id == journey_id).first()
            if not journey:
                continue
            
            # Generate deterministic memory key
            memory_key = f"JOURNEY_FRAGILITY:{journey.id}"
            
            # Check for existing memory
            existing = self.db.query(FragilityMemoryV2).filter(
                FragilityMemoryV2.repository_id == repository_id,
                FragilityMemoryV2.memory_key == memory_key,
                FragilityMemoryV2.subject_type == "JOURNEY",
                FragilityMemoryV2.subject_id == journey.id,
            ).first()
            
            if existing:
                # Update existing memory
                existing.fragility_score = max(existing.fragility_score, failure_data["score"])
                existing.risk_level = self._determine_risk_level(existing.fragility_score)
                existing.confidence = min(1.0, existing.confidence + 0.1)
                existing.last_seen_at = window_end
                existing.status = "ACTIVE"
                memory_id = existing.id
            else:
                # Create new memory
                memory = FragilityMemoryV2(
                    repository_id=repository_id,
                    memory_key=memory_key,
                    memory_type="JOURNEY_FRAGILITY",
                    subject_type="JOURNEY",
                    subject_id=journey.id,
                    subject_name=journey.name,
                    risk_level=self._determine_risk_level(failure_data["score"]),
                    fragility_score=failure_data["score"],
                    confidence=0.5,
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
                evidence_type="TEST_FAILURE",
                source_entity_type="TEST_RESULT",
                source_entity_id=None,
                evidence_summary=f"Test {failure_data['test_identity']} linked to journey {journey.name} failed repeatedly",
                evidence_weight=1.0,
                occurred_at=window_end,
            )
        
        return memory_id
    
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
