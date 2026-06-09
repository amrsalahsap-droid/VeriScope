"""
EscapedDefectMiner Service

Learns from defects that escaped after recommendation/execution.
Creates FragilityMemory and FragilityEvidenceEvent records for:
- ESCAPED_DEFECT_PATTERN
- BEHAVIOR_FRAGILITY
- JOURNEY_FRAGILITY
- MISSING_COVERAGE_PATTERN
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Set, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendedTest,
    SuggestedScenario,
    RecommendationTestOutcome,
    SuggestedScenarioOutcome,
)
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.behavior_scenario import BehaviorScenario
from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent

logger = logging.getLogger(__name__)


class EscapedDefectMiner:
    """Learns from defects that escaped after recommendation/execution."""
    
    ESCAPED_DEFECT_WEIGHT = 1.0  # High-weight evidence
    MISSING_COVERAGE_WEIGHT = 0.8
    SCENARIO_INTENT_STRENGTHENING = 0.5
    
    def __init__(self, db: Session):
        self.db = db
    
    def mine_escaped_defects(
        self,
        repository_id: uuid.UUID,
    ) -> Dict[str, int]:
        """
        Mine escaped defects and create fragility memory records.
        
        Args:
            repository_id: Repository to mine
            
        Returns:
            Dict with mining results:
            - escaped_defect_patterns_detected: count of ESCAPED_DEFECT_PATTERN patterns
            - behavior_fragility_detected: count of BEHAVIOR_FRAGILITY patterns
            - journey_fragility_detected: count of JOURNEY_FRAGILITY patterns
            - missing_coverage_patterns_detected: count of MISSING_COVERAGE_PATTERN patterns
            - scenario_intents_strengthened: count of scenario intents strengthened
            - evidence_events_created: count of evidence events created
        """
        logger.info(f"Mining escaped defects for repository {repository_id}")
        
        # Validate repository
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")
        
        results = {
            "escaped_defect_patterns_detected": 0,
            "behavior_fragility_detected": 0,
            "journey_fragility_detected": 0,
            "missing_coverage_patterns_detected": 0,
            "scenario_intents_strengthened": 0,
            "evidence_events_created": 0,
        }
        
        # Query outcomes with escaped defects
        escaped_outcomes = self.db.query(RecommendationOutcome).filter(
            RecommendationOutcome.repository_id == repository_id,
            RecommendationOutcome.escaped_defect == True,
        ).all()
        
        logger.info(f"Found {len(escaped_outcomes)} escaped defect outcomes")
        
        for outcome in escaped_outcomes:
            # Get recommendation run
            rec_run = self.db.query(RecommendationRun).filter(
                RecommendationRun.id == outcome.recommendation_run_id
            ).first()
            
            if not rec_run:
                logger.warning(f"Recommendation run {outcome.recommendation_run_id} not found for outcome {outcome.id}")
                continue
            
            # Get PR
            pr = self.db.query(PullRequest).filter(
                PullRequest.id == outcome.pull_request_id
            ).first() if outcome.pull_request_id else None
            
            # Get changed files
            changed_files = []
            if pr:
                changed_files_objs = self.db.query(PullRequestChangedFile).filter(
                    PullRequestChangedFile.pull_request_id == pr.id
                ).all()
                changed_files = [cf.file_path for cf in changed_files_objs]
            
            # Get recommended tests
            recommended_tests = self.db.query(RecommendedTest).filter(
                RecommendedTest.recommendation_run_id == rec_run.id
            ).all()
            
            # Get test outcomes
            test_outcomes = self.db.query(RecommendationTestOutcome).filter(
                RecommendationTestOutcome.outcome_id == outcome.id
            ).all()
            
            # Get suggested scenarios
            suggested_scenarios = self.db.query(SuggestedScenario).filter(
                SuggestedScenario.recommendation_run_id == rec_run.id
            ).all()
            
            # Get scenario outcomes
            scenario_outcomes = self.db.query(SuggestedScenarioOutcome).filter(
                SuggestedScenarioOutcome.outcome_id == outcome.id
            ).all()
            
            # Analyze what was missed
            analysis = self._analyze_escaped_defect(
                outcome, rec_run, pr, changed_files, recommended_tests,
                test_outcomes, suggested_scenarios, scenario_outcomes
            )
            
            # Create ESCAPED_DEFECT_PATTERN
            memory_id, evidence_count = self._create_escaped_defect_memory(
                repository_id, outcome, rec_run, pr, analysis
            )
            results["escaped_defect_patterns_detected"] += 1
            results["evidence_events_created"] += evidence_count
            
            # Create behavior fragility
            if analysis["affected_behaviors"]:
                behavior_memory_id = self._create_behavior_fragility(
                    repository_id, outcome, rec_run, pr, analysis
                )
                if behavior_memory_id:
                    results["behavior_fragility_detected"] += 1
                    results["evidence_events_created"] += 1
            
            # Create journey fragility
            if analysis["affected_journeys"]:
                journey_memory_id = self._create_journey_fragility(
                    repository_id, outcome, rec_run, pr, analysis
                )
                if journey_memory_id:
                    results["journey_fragility_detected"] += 1
                    results["evidence_events_created"] += 1
            
            # Create missing coverage pattern
            if analysis["missing_scenarios"]:
                missing_memory_id = self._create_missing_coverage_memory(
                    repository_id, outcome, rec_run, pr, analysis
                )
                if missing_memory_id:
                    results["missing_coverage_patterns_detected"] += 1
                    results["evidence_events_created"] += 1
            
            # Strengthen scenario intents
            for scenario_intent in analysis["scenario_intents_to_strengthen"]:
                strengthened = self._strengthen_scenario_intent(
                    repository_id, scenario_intent, outcome, rec_run, pr
                )
                if strengthened:
                    results["scenario_intents_strengthened"] += 1
                    results["evidence_events_created"] += 1
        
        self.db.commit()
        
        logger.info(
            f"Escaped defect mining complete: "
            f"escaped_defects={results['escaped_defect_patterns_detected']}, "
            f"behavior_fragility={results['behavior_fragility_detected']}, "
            f"journey_fragility={results['journey_fragility_detected']}, "
            f"missing_coverage={results['missing_coverage_patterns_detected']}, "
            f"scenario_intents={results['scenario_intents_strengthened']}, "
            f"evidence_events={results['evidence_events_created']}"
        )
        
        return results
    
    def _analyze_escaped_defect(
        self,
        outcome: RecommendationOutcome,
        rec_run: RecommendationRun,
        pr: Optional[PullRequest],
        changed_files: List[str],
        recommended_tests: List[RecommendedTest],
        test_outcomes: List[RecommendationTestOutcome],
        suggested_scenarios: List[SuggestedScenario],
        scenario_outcomes: List[SuggestedScenarioOutcome],
    ) -> Dict:
        """
        Analyze what was missed in the escaped defect.
        
        Returns:
            Dict with analysis results:
            - affected_behaviors: list of behavior IDs
            - affected_journeys: list of journey IDs
            - missing_scenarios: list of scenario keys that were suggested but not executed
            - scenario_intents_to_strengthen: list of scenario keys to strengthen
            - missed_tests: list of test identifiers that were recommended but not executed
        """
        analysis = {
            "affected_behaviors": [],
            "affected_journeys": [],
            "missing_scenarios": [],
            "scenario_intents_to_strengthen": [],
            "missed_tests": [],
        }
        
        # Find tests that were recommended but not executed
        executed_test_ids = {to.recommended_test_id for to in test_outcomes if to.actually_executed}
        for rt in recommended_tests:
            if rt.id not in executed_test_ids:
                analysis["missed_tests"].append(rt.test_identifier)
        
        # Find scenarios that were suggested but not executed
        executed_scenario_ids = {so.suggested_scenario_id for so in scenario_outcomes if so.actually_executed}
        for ss in suggested_scenarios:
            if ss.id not in executed_scenario_ids:
                analysis["missing_scenarios"].append(ss.scenario_key)
                # Check if scenario was accepted (should strengthen intent)
                scenario_outcome = next((so for so in scenario_outcomes if so.suggested_scenario_id == ss.id), None)
                if scenario_outcome and scenario_outcome.outcome_status in ["ACCEPTED", "MARKED_IMPORTANT"]:
                    analysis["scenario_intents_to_strengthen"].append(ss.scenario_key)
        
        # Map to behaviors via scenarios
        for scenario_key in analysis["missing_scenarios"]:
            behavior_scenarios = self.db.query(BehaviorScenario).filter(
                BehaviorScenario.scenario_key == scenario_key
            ).all()
            for bs in behavior_scenarios:
                if bs.behavior_id not in analysis["affected_behaviors"]:
                    analysis["affected_behaviors"].append(bs.behavior_id)
        
        # Map to journeys via behaviors
        for behavior_id in analysis["affected_behaviors"]:
            behavior = self.db.query(Behavior).filter(Behavior.id == behavior_id).first()
            if behavior and behavior.journey_id and behavior.journey_id not in analysis["affected_journeys"]:
                analysis["affected_journeys"].append(behavior.journey_id)
        
        return analysis
    
    def _create_escaped_defect_memory(
        self,
        repository_id: uuid.UUID,
        outcome: RecommendationOutcome,
        rec_run: RecommendationRun,
        pr: Optional[PullRequest],
        analysis: Dict,
    ) -> Tuple[uuid.UUID, int]:
        """
        Create FragilityMemory record for escaped defect pattern.
        """
        # Generate deterministic memory key
        memory_key = f"ESCAPED_DEFECT_PATTERN:{outcome.recommendation_run_id}"
        
        # Determine risk level (escaped defects are always HIGH or CRITICAL)
        risk_level = "CRITICAL" if outcome.production_incident_url else "HIGH"
        
        # Calculate confidence (escaped defects are high confidence)
        confidence = 1.0
        
        # Calculate score (escaped defects get high score)
        score = 85.0 if outcome.production_incident_url else 70.0
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "PR_PATTERN",
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = max(existing.fragility_score, score)
            existing.risk_level = risk_level
            existing.confidence = confidence
            existing.last_seen_at = datetime.utcnow()
            existing.status = "ACTIVE"
            memory_id = existing.id
        else:
            # Create new memory
            memory = FragilityMemoryV2(
                repository_id=repository_id,
                memory_key=memory_key,
                memory_type="ESCAPED_DEFECT_PATTERN",
                subject_type="PR_PATTERN",
                subject_id=outcome.recommendation_run_id,
                subject_name=f"PR #{pr.number if pr else 'unknown'} - {rec_run.id}",
                risk_level=risk_level,
                fragility_score=score,
                confidence=confidence,
                status="ACTIVE",
                first_seen_at=outcome.created_at,
                last_seen_at=datetime.utcnow(),
            )
            self.db.add(memory)
            self.db.flush()
            memory_id = memory.id
        
        # Create evidence event
        self._create_evidence_event(
            memory_id=memory_id,
            repository_id=repository_id,
            evidence_type="ESCAPED_DEFECT",
            source_entity_type="OUTCOME",
            source_entity_id=outcome.id,
            pull_request_id=outcome.pull_request_id,
            recommendation_run_id=outcome.recommendation_run_id,
            incident_url=outcome.production_incident_url,
            changed_files=analysis.get("changed_files", []),
            affected_behaviors=[str(bid) for bid in analysis.get("affected_behaviors", [])],
            affected_journeys=[str(jid) for jid in analysis.get("affected_journeys", [])],
            evidence_summary=f"Escaped defect detected in recommendation run {rec_run.id}. "
                           f"Missed tests: {len(analysis.get('missed_tests', []))}, "
                           f"Missing scenarios: {len(analysis.get('missing_scenarios', []))}",
            evidence_weight=self.ESCAPED_DEFECT_WEIGHT,
            occurred_at=outcome.created_at,
        )
        
        return memory_id, 1
    
    def _create_behavior_fragility(
        self,
        repository_id: uuid.UUID,
        outcome: RecommendationOutcome,
        rec_run: RecommendationRun,
        pr: Optional[PullRequest],
        analysis: Dict,
    ) -> Optional[uuid.UUID]:
        """
        Create BEHAVIOR_FRAGILITY for affected behaviors.
        """
        if not analysis["affected_behaviors"]:
            return None
        
        memory_id = None
        for behavior_id in analysis["affected_behaviors"]:
            behavior = self.db.query(Behavior).filter(Behavior.id == behavior_id).first()
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
                existing.fragility_score = min(100.0, existing.fragility_score + 15.0)
                existing.risk_level = self._determine_risk_level(existing.fragility_score)
                existing.confidence = min(1.0, existing.confidence + 0.2)
                existing.last_seen_at = datetime.utcnow()
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
                    risk_level="HIGH",
                    fragility_score=70.0,
                    confidence=0.8,
                    status="ACTIVE",
                    first_seen_at=outcome.created_at,
                    last_seen_at=datetime.utcnow(),
                )
                self.db.add(memory)
                self.db.flush()
                memory_id = memory.id
            
            # Create evidence event
            self._create_evidence_event(
                memory_id=memory_id,
                repository_id=repository_id,
                evidence_type="ESCAPED_DEFECT",
                source_entity_type="OUTCOME",
                source_entity_id=outcome.id,
                pull_request_id=outcome.pull_request_id,
                recommendation_run_id=outcome.recommendation_run_id,
                incident_url=outcome.production_incident_url,
                affected_behaviors=[behavior.name],
                evidence_summary=f"Previous escaped defect related to behavior {behavior.name} in PR #{pr.number if pr else 'unknown'}",
                evidence_weight=self.ESCAPED_DEFECT_WEIGHT,
                occurred_at=outcome.created_at,
            )
        
        return memory_id
    
    def _create_journey_fragility(
        self,
        repository_id: uuid.UUID,
        outcome: RecommendationOutcome,
        rec_run: RecommendationRun,
        pr: Optional[PullRequest],
        analysis: Dict,
    ) -> Optional[uuid.UUID]:
        """
        Create JOURNEY_FRAGILITY for affected journeys.
        """
        if not analysis["affected_journeys"]:
            return None
        
        memory_id = None
        for journey_id in analysis["affected_journeys"]:
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
                existing.fragility_score = min(100.0, existing.fragility_score + 15.0)
                existing.risk_level = self._determine_risk_level(existing.fragility_score)
                existing.confidence = min(1.0, existing.confidence + 0.2)
                existing.last_seen_at = datetime.utcnow()
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
                    risk_level="HIGH",
                    fragility_score=70.0,
                    confidence=0.8,
                    status="ACTIVE",
                    first_seen_at=outcome.created_at,
                    last_seen_at=datetime.utcnow(),
                )
                self.db.add(memory)
                self.db.flush()
                memory_id = memory.id
            
            # Create evidence event
            self._create_evidence_event(
                memory_id=memory_id,
                repository_id=repository_id,
                evidence_type="ESCAPED_DEFECT",
                source_entity_type="OUTCOME",
                source_entity_id=outcome.id,
                pull_request_id=outcome.pull_request_id,
                recommendation_run_id=outcome.recommendation_run_id,
                incident_url=outcome.production_incident_url,
                affected_journeys=[journey.name],
                evidence_summary=f"Previous escaped defect related to journey {journey.name} in PR #{pr.number if pr else 'unknown'}",
                evidence_weight=self.ESCAPED_DEFECT_WEIGHT,
                occurred_at=outcome.created_at,
            )
        
        return memory_id
    
    def _create_missing_coverage_memory(
        self,
        repository_id: uuid.UUID,
        outcome: RecommendationOutcome,
        rec_run: RecommendationRun,
        pr: Optional[PullRequest],
        analysis: Dict,
    ) -> Optional[uuid.UUID]:
        """
        Create MISSING_COVERAGE_PATTERN for missing scenarios.
        """
        if not analysis["missing_scenarios"]:
            return None
        
        # Generate deterministic memory key (aggregate all missing scenarios)
        scenario_keys = sorted(analysis["missing_scenarios"])
        memory_key = f"MISSING_COVERAGE_PATTERN:{':'.join(scenario_keys)}"
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "SCENARIO",
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = min(100.0, existing.fragility_score + 10.0)
            existing.risk_level = self._determine_risk_level(existing.fragility_score)
            existing.confidence = min(1.0, existing.confidence + 0.15)
            existing.last_seen_at = datetime.utcnow()
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
                subject_name=":".join(scenario_keys[:3]),  # Truncate for display
                risk_level="MODERATE",
                fragility_score=50.0,
                confidence=0.6,
                status="ACTIVE",
                first_seen_at=outcome.created_at,
                last_seen_at=datetime.utcnow(),
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
            source_entity_id=outcome.id,
            pull_request_id=outcome.pull_request_id,
            recommendation_run_id=outcome.recommendation_run_id,
            evidence_summary=f"Missing coverage: scenarios {scenario_keys} were suggested but not executed before escaped defect",
            evidence_weight=self.MISSING_COVERAGE_WEIGHT,
            occurred_at=outcome.created_at,
        )
        
        return memory_id
    
    def _strengthen_scenario_intent(
        self,
        repository_id: uuid.UUID,
        scenario_key: str,
        outcome: RecommendationOutcome,
        rec_run: RecommendationRun,
        pr: Optional[PullRequest],
    ) -> bool:
        """
        Strengthen scenario intent for scenarios that were accepted but still led to escaped defect.
        This creates a learning gap - the scenario was important but coverage was insufficient.
        """
        # This would update PatternMemoryV2 or ScenarioIntent
        # For now, create an evidence event documenting the learning gap
        # The actual strengthening logic would be in the PatternMemoryV2Upsert service
        
        # Create a temporary fragility memory to track the learning gap
        memory_key = f"SCENARIO_LEARNING_GAP:{scenario_key}"
        
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "SCENARIO",
        ).first()
        
        if existing:
            existing.fragility_score = min(100.0, existing.fragility_score + 10.0)
            existing.last_seen_at = datetime.utcnow()
            memory_id = existing.id
        else:
            memory = FragilityMemoryV2(
                repository_id=repository_id,
                memory_key=memory_key,
                memory_type="MISSING_COVERAGE_PATTERN",
                subject_type="SCENARIO",
                subject_id=None,
                subject_name=scenario_key,
                risk_level="MODERATE",
                fragility_score=60.0,
                confidence=0.7,
                status="ACTIVE",
                first_seen_at=outcome.created_at,
                last_seen_at=datetime.utcnow(),
            )
            self.db.add(memory)
            self.db.flush()
            memory_id = memory.id
        
        # Create evidence event
        self._create_evidence_event(
            memory_id=memory_id,
            repository_id=repository_id,
            evidence_type="OUTCOME_FEEDBACK",
            source_entity_type="OUTCOME",
            source_entity_id=outcome.id,
            pull_request_id=outcome.pull_request_id,
            recommendation_run_id=outcome.recommendation_run_id,
            evidence_summary=f"Scenario {scenario_key} was accepted but coverage was insufficient (escaped defect occurred)",
            evidence_weight=self.SCENARIO_INTENT_STRENGTHENING,
            occurred_at=outcome.created_at,
        )
        
        return True
    
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
