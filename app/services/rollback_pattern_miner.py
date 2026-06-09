"""
RollbackPatternMiner Service

Learns from rollbacks.
Creates FragilityMemory and FragilityEvidenceEvent records for:
- ROLLBACK_PATTERN
- BEHAVIOR_FRAGILITY
- JOURNEY_FRAGILITY
- RISKY_CHANGE_COMBINATION
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Set, Optional
from collections import defaultdict
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


class RollbackPatternMiner:
    """Learns from rollbacks."""
    
    ROLLBACK_WEIGHT = 1.0  # High-weight evidence
    ROLLBACK_SCORE_BONUS = 20.0
    REPEATED_ROLLBACK_BONUS = 15.0
    LOW_CONFIDENCE_CAP = 0.5
    
    def __init__(self, db: Session):
        self.db = db
    
    def mine_rollback_patterns(
        self,
        repository_id: uuid.UUID,
    ) -> Dict[str, int]:
        """
        Mine rollback patterns and create fragility memory records.
        
        Args:
            repository_id: Repository to mine
            
        Returns:
            Dict with mining results:
            - rollback_patterns_detected: count of ROLLBACK_PATTERN patterns
            - behavior_fragility_detected: count of BEHAVIOR_FRAGILITY patterns
            - journey_fragility_detected: count of JOURNEY_FRAGILITY patterns
            - risky_combinations_detected: count of RISKY_CHANGE_COMBINATION patterns
            - evidence_events_created: count of evidence events created
        """
        logger.info(f"Mining rollback patterns for repository {repository_id}")
        
        # Validate repository
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")
        
        results = {
            "rollback_patterns_detected": 0,
            "behavior_fragility_detected": 0,
            "journey_fragility_detected": 0,
            "risky_combinations_detected": 0,
            "evidence_events_created": 0,
        }
        
        # Query outcomes with rollbacks
        rollback_outcomes = self.db.query(RecommendationOutcome).filter(
            RecommendationOutcome.repository_id == repository_id,
            RecommendationOutcome.rollback_occurred == True,
        ).all()
        
        logger.info(f"Found {len(rollback_outcomes)} rollback outcomes")
        
        # Track rollback counts per behavior/journey for escalation
        behavior_rollback_counts = defaultdict(int)
        journey_rollback_counts = defaultdict(int)
        
        for outcome in rollback_outcomes:
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
            
            # Analyze rollback context
            analysis = self._analyze_rollback(
                outcome, rec_run, pr, changed_files, recommended_tests,
                test_outcomes, suggested_scenarios, scenario_outcomes
            )
            
            # Track rollback counts
            for behavior_id in analysis["affected_behaviors"]:
                behavior_rollback_counts[behavior_id] += 1
            for journey_id in analysis["affected_journeys"]:
                journey_rollback_counts[journey_id] += 1
            
            # Create ROLLBACK_PATTERN
            memory_id, evidence_count = self._create_rollback_memory(
                repository_id, outcome, rec_run, pr, analysis
            )
            results["rollback_patterns_detected"] += 1
            results["evidence_events_created"] += evidence_count
            
            # Create behavior fragility
            if analysis["affected_behaviors"]:
                behavior_memory_id = self._create_behavior_fragility(
                    repository_id, outcome, rec_run, pr, analysis, behavior_rollback_counts
                )
                if behavior_memory_id:
                    results["behavior_fragility_detected"] += 1
                    results["evidence_events_created"] += 1
            
            # Create journey fragility
            if analysis["affected_journeys"]:
                journey_memory_id = self._create_journey_fragility(
                    repository_id, outcome, rec_run, pr, analysis, journey_rollback_counts
                )
                if journey_memory_id:
                    results["journey_fragility_detected"] += 1
                    results["evidence_events_created"] += 1
            
            # Create risky combination if multiple files changed
            if len(changed_files) >= 2:
                combination_memory_id = self._create_risky_combination_memory(
                    repository_id, outcome, rec_run, pr, analysis
                )
                if combination_memory_id:
                    results["risky_combinations_detected"] += 1
                    results["evidence_events_created"] += 1
        
        self.db.commit()
        
        logger.info(
            f"Rollback pattern mining complete: "
            f"rollback_patterns={results['rollback_patterns_detected']}, "
            f"behavior_fragility={results['behavior_fragility_detected']}, "
            f"journey_fragility={results['journey_fragility_detected']}, "
            f"risky_combinations={results['risky_combinations_detected']}, "
            f"evidence_events={results['evidence_events_created']}"
        )
        
        return results
    
    def _analyze_rollback(
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
        Analyze rollback context.
        
        Returns:
            Dict with analysis results:
            - affected_behaviors: list of behavior IDs
            - affected_journeys: list of journey IDs
            - missing_scenarios: list of scenario keys that were suggested but not executed
            - confidence: confidence level of linkage
        """
        analysis = {
            "affected_behaviors": [],
            "affected_journeys": [],
            "missing_scenarios": [],
            "confidence": 1.0,
        }
        
        # Determine confidence based on linkage quality
        if not pr:
            analysis["confidence"] = 0.3  # Low confidence without PR linkage
        elif not outcome.rollback_url:
            analysis["confidence"] = 0.5  # Medium confidence without rollback URL
        else:
            analysis["confidence"] = 1.0  # High confidence with full linkage
        
        # Find scenarios that were suggested but not executed
        executed_scenario_ids = {so.suggested_scenario_id for so in scenario_outcomes if so.actually_executed}
        for ss in suggested_scenarios:
            if ss.id not in executed_scenario_ids:
                analysis["missing_scenarios"].append(ss.scenario_key)
        
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
        
        # Also map behaviors/journeys via changed files if available
        # This would require test coverage data linking files to behaviors
        # For now, we only use scenario-based mapping
        
        return analysis
    
    def _create_rollback_memory(
        self,
        repository_id: uuid.UUID,
        outcome: RecommendationOutcome,
        rec_run: RecommendationRun,
        pr: Optional[PullRequest],
        analysis: Dict,
    ) -> Tuple[uuid.UUID, int]:
        """
        Create FragilityMemory record for rollback pattern.
        """
        # Generate deterministic memory key
        memory_key = f"ROLLBACK_PATTERN:{outcome.recommendation_run_id}"
        
        # Determine risk level (rollbacks are always HIGH or CRITICAL)
        risk_level = "CRITICAL" if analysis["confidence"] >= 0.7 else "HIGH"
        
        # Calculate confidence (cap at LOW_CONFIDENCE_CAP for low-confidence linkage)
        confidence = min(analysis["confidence"], self.LOW_CONFIDENCE_CAP) if analysis["confidence"] < 0.7 else analysis["confidence"]
        
        # Calculate score (rollbacks get high score)
        score = 80.0 if analysis["confidence"] >= 0.7 else 60.0
        
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
                memory_type="ROLLBACK_PATTERN",
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
            evidence_type="ROLLBACK",
            source_entity_type="OUTCOME",
            source_entity_id=outcome.id,
            pull_request_id=outcome.pull_request_id,
            recommendation_run_id=outcome.recommendation_run_id,
            rollback_url=outcome.rollback_url,
            changed_files=analysis.get("changed_files", []),
            affected_behaviors=[str(bid) for bid in analysis.get("affected_behaviors", [])],
            affected_journeys=[str(jid) for jid in analysis.get("affected_journeys", [])],
            evidence_summary=f"Rollback occurred after recommendation run {rec_run.id}. "
                           f"Missing scenarios: {len(analysis.get('missing_scenarios', []))}",
            evidence_weight=self.ROLLBACK_WEIGHT * confidence,
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
        behavior_rollback_counts: Dict[uuid.UUID, int],
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
            
            # Calculate score with escalation for repeated rollbacks
            rollback_count = behavior_rollback_counts.get(behavior_id, 1)
            base_score = 75.0 if analysis["confidence"] >= 0.7 else 55.0
            escalation_bonus = min(20.0, (rollback_count - 1) * self.REPEATED_ROLLBACK_BONUS)
            score = min(100.0, base_score + escalation_bonus)
            
            # Cap confidence for low-confidence linkage
            confidence = min(analysis["confidence"], self.LOW_CONFIDENCE_CAP) if analysis["confidence"] < 0.7 else analysis["confidence"]
            
            if existing:
                # Update existing memory
                existing.fragility_score = max(existing.fragility_score, score)
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
                    memory_type="BEHAVIOR_FRAGILITY",
                    subject_type="BEHAVIOR",
                    subject_id=behavior.id,
                    subject_name=behavior.name,
                    risk_level=self._determine_risk_level(score),
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
                evidence_type="ROLLBACK",
                source_entity_type="OUTCOME",
                source_entity_id=outcome.id,
                pull_request_id=outcome.pull_request_id,
                recommendation_run_id=outcome.recommendation_run_id,
                rollback_url=outcome.rollback_url,
                affected_behaviors=[behavior.name],
                evidence_summary=f"Rollback occurred after changes to behavior {behavior.name} in PR #{pr.number if pr else 'unknown'}. "
                               f"This is rollback #{rollback_count} for this behavior.",
                evidence_weight=self.ROLLBACK_WEIGHT * confidence,
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
        journey_rollback_counts: Dict[uuid.UUID, int],
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
            
            # Calculate score with escalation for repeated rollbacks
            rollback_count = journey_rollback_counts.get(journey_id, 1)
            base_score = 75.0 if analysis["confidence"] >= 0.7 else 55.0
            escalation_bonus = min(20.0, (rollback_count - 1) * self.REPEATED_ROLLBACK_BONUS)
            score = min(100.0, base_score + escalation_bonus)
            
            # Cap confidence for low-confidence linkage
            confidence = min(analysis["confidence"], self.LOW_CONFIDENCE_CAP) if analysis["confidence"] < 0.7 else analysis["confidence"]
            
            if existing:
                # Update existing memory
                existing.fragility_score = max(existing.fragility_score, score)
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
                    memory_type="JOURNEY_FRAGILITY",
                    subject_type="JOURNEY",
                    subject_id=journey.id,
                    subject_name=journey.name,
                    risk_level=self._determine_risk_level(score),
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
                evidence_type="ROLLBACK",
                source_entity_type="OUTCOME",
                source_entity_id=outcome.id,
                pull_request_id=outcome.pull_request_id,
                recommendation_run_id=outcome.recommendation_run_id,
                rollback_url=outcome.rollback_url,
                affected_journeys=[journey.name],
                evidence_summary=f"Rollback occurred after changes to journey {journey.name} in PR #{pr.number if pr else 'unknown'}. "
                               f"This is rollback #{rollback_count} for this journey.",
                evidence_weight=self.ROLLBACK_WEIGHT * confidence,
                occurred_at=outcome.created_at,
            )
        
        return memory_id
    
    def _create_risky_combination_memory(
        self,
        repository_id: uuid.UUID,
        outcome: RecommendationOutcome,
        rec_run: RecommendationRun,
        pr: Optional[PullRequest],
        analysis: Dict,
    ) -> Optional[uuid.UUID]:
        """
        Create RISKY_CHANGE_COMBINATION for multiple changed files.
        """
        if not analysis.get("changed_files") or len(analysis["changed_files"]) < 2:
            return None
        
        # Generate deterministic memory key
        changed_files = sorted(analysis["changed_files"])
        combination_key = ":".join(changed_files[:5])  # Limit to first 5 files
        memory_key = f"RISKY_CHANGE_COMBINATION:{combination_key}"
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "FILE",
        ).first()
        
        # Calculate score
        base_score = 65.0 if analysis["confidence"] >= 0.7 else 45.0
        score = min(100.0, base_score + self.ROLLBACK_SCORE_BONUS)
        
        # Cap confidence for low-confidence linkage
        confidence = min(analysis["confidence"], self.LOW_CONFIDENCE_CAP) if analysis["confidence"] < 0.7 else analysis["confidence"]
        
        if existing:
            # Update existing memory
            existing.fragility_score = max(existing.fragility_score, score)
            existing.risk_level = self._determine_risk_level(existing.fragility_score)
            existing.confidence = min(1.0, existing.confidence + 0.1)
            existing.last_seen_at = datetime.utcnow()
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
                risk_level=self._determine_risk_level(score),
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
            evidence_type="ROLLBACK",
            source_entity_type="OUTCOME",
            source_entity_id=outcome.id,
            pull_request_id=outcome.pull_request_id,
            recommendation_run_id=outcome.recommendation_run_id,
            rollback_url=outcome.rollback_url,
            changed_files=changed_files,
            evidence_summary=f"Risky file combination {combination_key} led to rollback in PR #{pr.number if pr else 'unknown'}",
            evidence_weight=self.ROLLBACK_WEIGHT * confidence,
            occurred_at=outcome.created_at,
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
