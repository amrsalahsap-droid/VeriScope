"""
MissingCoverageFragilityMiner Service

Promotes repeated missing coverage gaps into fragility memory.
Creates FragilityMemory and FragilityEvidenceEvent records for:
- MISSING_COVERAGE_PATTERN
- BEHAVIOR_FRAGILITY
- SCENARIO_FRAGILITY
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.repository import Repository
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    SuggestedScenario,
    SuggestedScenarioOutcome,
    RecommendedTest,
    RecommendationOverrideRecord,
)
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.behavior_scenario import BehaviorScenario
from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent

logger = logging.getLogger(__name__)


class MissingCoverageFragilityMiner:
    """Promotes repeated missing coverage gaps into fragility memory."""
    
    DEFAULT_TIME_WINDOW_DAYS = 90
    MIN_MISSING_COUNT = 3
    MIN_DISTINCT_PRS = 2
    
    # Risk scores
    MISSING_ALONE_BASE_SCORE = 40.0
    MISSING_PLUS_ESCAPED_DEFECT_SCORE = 75.0
    MISSING_PLUS_MANUAL_ADDITION_SCORE = 60.0
    
    def __init__(self, db: Session):
        self.db = db
    
    def mine_missing_coverage_patterns(
        self,
        repository_id: uuid.UUID,
        time_window_days: int = DEFAULT_TIME_WINDOW_DAYS,
    ) -> Dict[str, int]:
        """
        Mine missing coverage patterns and create fragility memory records.
        
        Args:
            repository_id: Repository to mine
            time_window_days: Time window for historical data (default 90 days)
            
        Returns:
            Dict with mining results:
            - missing_coverage_patterns_detected: count of MISSING_COVERAGE_PATTERN patterns
            - behavior_fragility_detected: count of BEHAVIOR_FRAGILITY patterns
            - scenario_fragility_detected: count of SCENARIO_FRAGILITY patterns
            - evidence_events_created: count of evidence events created
        """
        logger.info(f"Mining missing coverage patterns for repository {repository_id} with {time_window_days} day window")
        
        # Calculate time window
        now = datetime.utcnow()
        window_start = now - timedelta(days=time_window_days)
        
        # Validate repository
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")
        
        results = {
            "missing_coverage_patterns_detected": 0,
            "behavior_fragility_detected": 0,
            "scenario_fragility_detected": 0,
            "evidence_events_created": 0,
        }
        
        # 1. Detect repeated missing scenarios
        missing_scenarios = self._detect_repeated_missing_scenarios(repository_id, window_start, now)
        
        # 2. Detect missing scenarios tied to escaped defects
        escaped_defect_scenarios = self._detect_escaped_defect_missing_scenarios(repository_id, window_start, now)
        
        # 3. Detect repeated manual additions
        manual_addition_scenarios = self._detect_repeated_manual_additions(repository_id, window_start, now)
        
        # Combine and deduplicate
        all_missing_data = {}
        
        for scenario_data in missing_scenarios:
            key = scenario_data["scenario_key"]
            if key not in all_missing_data:
                all_missing_data[key] = scenario_data
            else:
                # Merge data
                all_missing_data[key]["missing_count"] += scenario_data["missing_count"]
                all_missing_data[key]["pr_ids"].update(scenario_data["pr_ids"])
        
        for scenario_data in escaped_defect_scenarios:
            key = scenario_data["scenario_key"]
            if key not in all_missing_data:
                all_missing_data[key] = scenario_data
            else:
                # Mark as having escaped defect
                all_missing_data[key]["has_escaped_defect"] = True
                all_missing_data[key]["missing_count"] += scenario_data["missing_count"]
        
        for scenario_data in manual_addition_scenarios:
            key = scenario_data["scenario_key"]
            if key not in all_missing_data:
                all_missing_data[key] = scenario_data
            else:
                # Mark as having manual additions
                all_missing_data[key]["has_manual_addition"] = True
                all_missing_data[key]["manual_addition_count"] += scenario_data["manual_addition_count"]
        
        # Create fragility memory records
        for scenario_key, data in all_missing_data.items():
            # Determine risk level based on rules
            if data.get("has_escaped_defect"):
                score = self.MISSING_PLUS_ESCAPED_DEFECT_SCORE
                risk_level = "HIGH"
            elif data.get("has_manual_addition"):
                score = self.MISSING_PLUS_MANUAL_ADDITION_SCORE
                risk_level = "MODERATE"
            else:
                score = self.MISSING_ALONE_BASE_SCORE
                risk_level = "LOW"
            
            # Update score based on missing count
            score = min(100.0, score + (data["missing_count"] - self.MIN_MISSING_COUNT) * 5.0)
            
            # Create MISSING_COVERAGE_PATTERN
            memory_id, evidence_count = self._create_missing_coverage_memory(
                repository_id, scenario_key, data, score, risk_level, window_start, now
            )
            results["missing_coverage_patterns_detected"] += 1
            results["evidence_events_created"] += evidence_count
            
            # Create behavior fragility
            behavior_memory_id = self._create_behavior_fragility_from_missing(
                repository_id, scenario_key, data, score, risk_level, window_start, now
            )
            if behavior_memory_id:
                results["behavior_fragility_detected"] += 1
                results["evidence_events_created"] += 1
            
            # Create scenario fragility
            scenario_memory_id = self._create_scenario_fragility(
                repository_id, scenario_key, data, score, risk_level, window_start, now
            )
            if scenario_memory_id:
                results["scenario_fragility_detected"] += 1
                results["evidence_events_created"] += 1
        
        self.db.commit()
        
        logger.info(
            f"Missing coverage mining complete: "
            f"missing_coverage={results['missing_coverage_patterns_detected']}, "
            f"behavior_fragility={results['behavior_fragility_detected']}, "
            f"scenario_fragility={results['scenario_fragility_detected']}, "
            f"evidence_events={results['evidence_events_created']}"
        )
        
        return results
    
    def _detect_repeated_missing_scenarios(
        self,
        repository_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict]:
        """
        Detect scenarios repeatedly missing across PRs.
        """
        # Query suggested scenario outcomes within window
        scenario_outcomes = self.db.query(SuggestedScenarioOutcome).join(
            SuggestedScenario, SuggestedScenarioOutcome.suggested_scenario_id == SuggestedScenario.id
        ).join(
            RecommendationOutcome, SuggestedScenarioOutcome.outcome_id == RecommendationOutcome.id
        ).filter(
            RecommendationOutcome.repository_id == repository_id,
            RecommendationOutcome.created_at >= window_start,
            RecommendationOutcome.created_at <= window_end,
            SuggestedScenarioOutcome.actually_executed == False,
        ).all()
        
        # Group by scenario key
        scenario_missing_counts = defaultdict(int)
        scenario_pr_ids = defaultdict(set)
        scenario_details = defaultdict(list)
        
        for outcome in scenario_outcomes:
            scenario_key = outcome.suggested_scenario.scenario_key
            pr_id = outcome.outcome.pull_request_id
            
            scenario_missing_counts[scenario_key] += 1
            if pr_id:
                scenario_pr_ids[scenario_key].add(pr_id)
            
            scenario_details[scenario_key].append({
                "outcome_id": outcome.id,
                "pr_id": pr_id,
                "occurred_at": outcome.outcome.created_at,
            })
        
        # Filter for significant missing patterns
        missing_scenarios = []
        for scenario_key, count in scenario_missing_counts.items():
            if count < self.MIN_MISSING_COUNT:
                continue
            
            pr_ids = scenario_pr_ids[scenario_key]
            if len(pr_ids) < self.MIN_DISTINCT_PRS:
                continue
            
            missing_scenarios.append({
                "scenario_key": scenario_key,
                "missing_count": count,
                "pr_ids": pr_ids,
                "has_escaped_defect": False,
                "has_manual_addition": False,
                "manual_addition_count": 0,
                "details": scenario_details[scenario_key],
            })
        
        return missing_scenarios
    
    def _detect_escaped_defect_missing_scenarios(
        self,
        repository_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict]:
        """
        Detect missing scenarios later tied to escaped defects.
        """
        # Query outcomes with escaped defects
        escaped_outcomes = self.db.query(RecommendationOutcome).filter(
            RecommendationOutcome.repository_id == repository_id,
            RecommendationOutcome.escaped_defect == True,
            RecommendationOutcome.created_at >= window_start,
            RecommendationOutcome.created_at <= window_end,
        ).all()
        
        escaped_scenarios = []
        
        for outcome in escaped_outcomes:
            # Get scenario outcomes for this outcome
            scenario_outcomes = self.db.query(SuggestedScenarioOutcome).join(
                SuggestedScenario, SuggestedScenarioOutcome.suggested_scenario_id == SuggestedScenario.id
            ).filter(
                SuggestedScenarioOutcome.outcome_id == outcome.id,
                SuggestedScenarioOutcome.actually_executed == False,
            ).all()
            
            for so in scenario_outcomes:
                scenario_key = so.suggested_scenario.scenario_key
                
                escaped_scenarios.append({
                    "scenario_key": scenario_key,
                    "missing_count": 1,
                    "pr_ids": {outcome.pull_request_id} if outcome.pull_request_id else set(),
                    "has_escaped_defect": True,
                    "has_manual_addition": False,
                    "manual_addition_count": 0,
                    "details": [{
                        "outcome_id": outcome.id,
                        "pr_id": outcome.pull_request_id,
                        "occurred_at": outcome.created_at,
                    }],
                })
        
        return escaped_scenarios
    
    def _detect_repeated_manual_additions(
        self,
        repository_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict]:
        """
        Detect repeated manual additions for same missing behavior.
        """
        # Query override records within window
        override_records = self.db.query(RecommendationOverrideRecord).join(
            RecommendationOutcome, RecommendationOverrideRecord.outcome_id == RecommendationOutcome.id
        ).filter(
            RecommendationOutcome.repository_id == repository_id,
            RecommendationOutcome.created_at >= window_start,
            RecommendationOutcome.created_at <= window_end,
            RecommendationOverrideRecord.override_type == "MANUAL_ADDITION",
        ).all()
        
        # Group by test identifier (as proxy for scenario)
        test_addition_counts = defaultdict(int)
        test_pr_ids = defaultdict(set)
        test_details = defaultdict(list)
        
        for override in override_records:
            test_identifier = override.test_identifier
            pr_id = override.outcome.pull_request_id
            
            test_addition_counts[test_identifier] += 1
            if pr_id:
                test_pr_ids[test_identifier].add(pr_id)
            
            test_details[test_identifier].append({
                "override_id": override.id,
                "pr_id": pr_id,
                "occurred_at": override.outcome.created_at,
            })
        
        # Map test identifiers to scenarios
        manual_addition_scenarios = []
        for test_identifier, count in test_addition_counts.items():
            if count < self.MIN_MISSING_COUNT:
                continue
            
            pr_ids = test_pr_ids[test_identifier]
            if len(pr_ids) < self.MIN_DISTINCT_PRS:
                continue
            
            # Find scenarios linked to this test
            behavior_scenarios = self.db.query(BehaviorScenario).filter(
                BehaviorScenario.test_identifier == test_identifier
            ).all()
            
            for bs in behavior_scenarios:
                scenario_key = bs.scenario_key
                
                manual_addition_scenarios.append({
                    "scenario_key": scenario_key,
                    "missing_count": 0,  # Not directly missing, but manually added
                    "pr_ids": pr_ids,
                    "has_escaped_defect": False,
                    "has_manual_addition": True,
                    "manual_addition_count": count,
                    "details": test_details[test_identifier],
                })
        
        return manual_addition_scenarios
    
    def _create_missing_coverage_memory(
        self,
        repository_id: uuid.UUID,
        scenario_key: str,
        data: Dict,
        score: float,
        risk_level: str,
        window_start: datetime,
        window_end: datetime,
    ) -> Tuple[uuid.UUID, int]:
        """
        Create FragilityMemory record for missing coverage pattern.
        """
        # Generate deterministic memory key
        memory_key = f"MISSING_COVERAGE_PATTERN:{scenario_key}"
        
        # Calculate confidence
        confidence = min(1.0, data["missing_count"] / 5.0)
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "SCENARIO",
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = max(existing.fragility_score, score)
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
                memory_type="MISSING_COVERAGE_PATTERN",
                subject_type="SCENARIO",
                subject_id=None,
                subject_name=scenario_key,
                risk_level=risk_level,
                fragility_score=score,
                confidence=confidence,
                status="ACTIVE",
                first_seen_at=window_start,
                last_seen_at=window_end,
            )
            self.db.add(memory)
            self.db.flush()
            memory_id = memory.id
        
        # Create evidence events
        evidence_count = 0
        for detail in data["details"]:
            self._create_evidence_event(
                memory_id=memory_id,
                repository_id=repository_id,
                evidence_type="MISSING_COVERAGE",
                source_entity_type="OUTCOME",
                source_entity_id=detail.get("outcome_id") or detail.get("override_id"),
                pull_request_id=detail["pr_id"],
                evidence_summary=f"Scenario {scenario_key} was missing coverage in PR #{detail['pr_id'] if detail['pr_id'] else 'unknown'}",
                evidence_weight=1.0 / len(data["details"]),
                occurred_at=detail["occurred_at"],
            )
            evidence_count += 1
        
        return memory_id, evidence_count
    
    def _create_behavior_fragility_from_missing(
        self,
        repository_id: uuid.UUID,
        scenario_key: str,
        data: Dict,
        score: float,
        risk_level: str,
        window_start: datetime,
        window_end: datetime,
    ) -> Optional[uuid.UUID]:
        """
        Create BEHAVIOR_FRAGILITY from missing coverage.
        """
        # Find behavior linked to this scenario
        behavior_scenarios = self.db.query(BehaviorScenario).filter(
            BehaviorScenario.scenario_key == scenario_key
        ).all()
        
        if not behavior_scenarios:
            return None
        
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
                existing.fragility_score = max(existing.fragility_score, score)
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
                    risk_level=risk_level,
                    fragility_score=score,
                    confidence=0.6,
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
                evidence_type="MISSING_COVERAGE",
                source_entity_type="OUTCOME",
                source_entity_id=None,
                affected_behaviors=[behavior.name],
                evidence_summary=f"Behavior {behavior.name} has repeated missing coverage (scenario {scenario_key})",
                evidence_weight=1.0,
                occurred_at=window_end,
            )
        
        return memory_id
    
    def _create_scenario_fragility(
        self,
        repository_id: uuid.UUID,
        scenario_key: str,
        data: Dict,
        score: float,
        risk_level: str,
        window_start: datetime,
        window_end: datetime,
    ) -> Optional[uuid.UUID]:
        """
        Create SCENARIO_FRAGILITY for missing coverage.
        """
        # Generate deterministic memory key
        memory_key = f"SCENARIO_FRAGILITY:{scenario_key}"
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "SCENARIO",
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = max(existing.fragility_score, score)
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
                memory_type="MISSING_COVERAGE_PATTERN",
                subject_type="SCENARIO",
                subject_id=None,
                subject_name=scenario_key,
                risk_level=risk_level,
                fragility_score=score,
                confidence=0.6,
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
            evidence_type="MISSING_COVERAGE",
            source_entity_type="OUTCOME",
            source_entity_id=None,
            evidence_summary=f"Scenario {scenario_key} has repeated missing coverage",
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
        """Determine risk level from score."""
        if score >= 75.0:
            return "CRITICAL"
        elif score >= 50.0:
            return "HIGH"
        elif score >= 25.0:
            return "MODERATE"
        else:
            return "LOW"
