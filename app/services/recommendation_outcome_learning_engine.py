"""
RecommendationOutcomeLearningEngine Service

Converts recommendation outcomes into future recommendation signals.

This service processes outcomes and applies learning rules to update:
- PatternMemory: File pattern to test associations
- TestCoverageLink: Test to file coverage relationships
- ScenarioIntent: Scenario meaning and priority

Learning Rules:
1. Kept + passed/failed recommended test: strengthen related behavior/test mapping
2. Removed recommended test: weaken low-confidence signal
3. Manually added test: create/strengthen PatternMemory and TestCoverageLink
4. Suggested scenario accepted/important: strengthen scenario intent
5. Suggested scenario dismissed: reduce priority for similar low-confidence suggestions
6. Escaped defect: strengthen missed behaviors/scenarios and increase future risk
7. Rollback: mark related behavior/journey as fragile

Rules:
- Append-only learning events
- No destructive updates to historical recommendation results
- Learning must be explainable
"""

import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationTestOutcome,
    SuggestedScenarioOutcome,
    RecommendationOverride,
    RecommendedTest,
    ScenarioIntent,
)
from app.models.pattern_memory_v2 import (
    PatternMemoryV2,
    SIGNAL_TYPE_MANUAL_ADDITION,
    SIGNAL_TYPE_MANUAL_REMOVAL,
    SIGNAL_TYPE_ACCEPTED_SCENARIO,
    SIGNAL_TYPE_DISMISSED_SCENARIO,
    SIGNAL_TYPE_ESCAPED_DEFECT,
    SIGNAL_TYPE_ROLLBACK,
    SIGNAL_TYPE_EXECUTION_RESULT,
)
from app.models.test_coverage_link import TestCoverageLink
from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent
from app.models.behavior_scenario import BehaviorScenario
from app.services.pattern_memory_v2_upsert import PatternMemoryV2Upsert

logger = logging.getLogger(__name__)


class RecommendationOutcomeLearningEngine:
    """
    Converts recommendation outcomes into future recommendation signals.
    
    This engine applies learning rules to update PatternMemory, TestCoverageLink,
    and ScenarioIntent based on captured outcomes.
    """

    def __init__(self, db: Session):
        self.db = db
        self.pattern_memory_upsert = PatternMemoryV2Upsert(db)

    def process_outcome(self, recommendation_run_id: str) -> Dict:
        """
        Process a recommendation outcome and apply learning rules.
        
        Args:
            recommendation_run_id: UUID of the recommendation run
            
        Returns:
            Dict with learning results:
            - learning_events_applied: count of learning events applied
            - pattern_memories_updated: count of PatternMemory updates
            - test_coverage_links_updated: count of TestCoverageLink updates
            - scenario_intents_updated: count of ScenarioIntent updates
        """
        try:
            logger.info(f"Processing outcome for recommendation run: {recommendation_run_id}")
            
            # Load outcome data
            outcome = self.db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                logger.warning(f"No outcome found for recommendation run {recommendation_run_id}")
                return {"learning_events_applied": 0}
            
            # Load recommendation run
            rec_run = self.db.query(RecommendationRun).filter(
                RecommendationRun.id == recommendation_run_id
            ).first()
            
            if not rec_run:
                logger.warning(f"Recommendation run {recommendation_run_id} not found")
                return {"learning_events_applied": 0}
            
            # Load related data
            test_outcomes = self.db.query(RecommendationTestOutcome).filter(
                RecommendationTestOutcome.recommendation_run_id == recommendation_run_id
            ).all()
            
            scenario_outcomes = self.db.query(SuggestedScenarioOutcome).filter(
                SuggestedScenarioOutcome.recommendation_run_id == recommendation_run_id
            ).all()
            
            overrides = self.db.query(RecommendationOverride).filter(
                RecommendationOverride.recommendation_run_id == recommendation_run_id
            ).all()
            
            recommended_tests = self.db.query(RecommendedTest).filter(
                RecommendedTest.recommendation_run_id == recommendation_run_id
            ).all()
            
            # Build lookup maps
            test_map = {rt.id: rt for rt in recommended_tests}
            
            # Apply learning rules
            pattern_memories_updated = 0
            test_coverage_links_updated = 0
            scenario_intents_updated = 0
            
            # Rule 1: Kept + passed/failed recommended test strengthens mapping
            for test_outcome in test_outcomes:
                if test_outcome.engineer_decision == "KEPT":
                    recommended_test = test_map.get(test_outcome.recommended_test_id)
                    if recommended_test:
                        if test_outcome.execution_status in ["PASSED", "FAILED"]:
                            pattern_memories_updated += self._strengthen_test_mapping(
                                rec_run, recommended_test, test_outcome
                            )
                            test_coverage_links_updated += self._strengthen_coverage_link(
                                rec_run, recommended_test, test_outcome
                            )
                            # Create failure evidence for failed tests
                            if test_outcome.execution_status == "FAILED":
                                self._create_failure_evidence(rec_run, test_outcome)
            
            # Rule 2: Removed recommended test weakens low-confidence signal
            for test_outcome in test_outcomes:
                if test_outcome.engineer_decision == "REMOVED":
                    recommended_test = test_map.get(test_outcome.recommended_test_id)
                    if recommended_test:
                        if recommended_test.confidence == "LOW":
                            pattern_memories_updated += self._weaken_pattern_memory(
                                rec_run, recommended_test
                            )
                        # Flag weak memory for removed tests
                        self._flag_weak_memory(rec_run, test_outcome)
        
        # Rule 3: Manually added test creates/strengthens relationships
        for override in overrides:
            if override.override_type == "TEST_ADDED":
                pattern_memories_updated += self._create_or_strengthen_pattern_memory(
                    rec_run, override
                )
                test_coverage_links_updated += self._create_or_strengthen_coverage_link(
                    rec_run, override
                )
        
        # Rule 4: Suggested scenario accepted/important strengthens intent
        for scenario_outcome in scenario_outcomes:
            if scenario_outcome.engineer_decision in ["ACCEPTED", "MARKED_IMPORTANT"]:
                scenario_intents_updated += self._strengthen_scenario_intent(
                    rec_run, scenario_outcome
                )
                # Create missing coverage evidence for important scenarios
                if scenario_outcome.engineer_decision == "MARKED_IMPORTANT":
                    self._create_missing_coverage_evidence(rec_run, scenario_outcome)
        
        # Rule 5: Suggested scenario dismissed reduces priority
        for scenario_outcome in scenario_outcomes:
            if scenario_outcome.engineer_decision == "DISMISSED":
                scenario_intents_updated += self._reduce_scenario_priority(
                    rec_run, scenario_outcome
                )
        
        # Rule 6: Escaped defect strengthens missed behaviors
        if outcome.escaped_defect:
            pattern_memories_updated += self._strengthen_missed_behaviors(
                rec_run, outcome
            )
            test_coverage_links_updated += self._strengthen_defect_gaps(
                rec_run, outcome
            )
            # Create fragility evidence for escaped defect
            self._create_escaped_defect_evidence(rec_run, outcome)
        
        # Rule 7: Rollback marks fragile
        if outcome.rollback_occurred:
            pattern_memories_updated += self._mark_fragile_patterns(
                rec_run, outcome
            )
            # Create fragility evidence for rollback
            self._create_rollback_evidence(rec_run, outcome)
        
        self.db.commit()
        
        learning_events_applied = (
            pattern_memories_updated + test_coverage_links_updated + scenario_intents_updated
        )
        
        logger.info(
            f"Learning complete: events={learning_events_applied}, "
            f"pattern_memories={pattern_memories_updated}, "
            f"coverage_links={test_coverage_links_updated}, "
            f"scenario_intents={scenario_intents_updated}"
        )
        
        return {
            "learning_events_applied": learning_events_applied,
            "pattern_memories_updated": pattern_memories_updated,
            "test_coverage_links_updated": test_coverage_links_updated,
            "scenario_intents_updated": scenario_intents_updated,
        }
        except Exception as exc:
            # Log error without exposing SQL details
            logger.error(
                f"Outcome learning failed for recommendation run {recommendation_run_id}: {str(exc)}"
            )
            # Rollback to prevent partial state
            try:
                self.db.rollback()
            except Exception:
                pass
            # Return empty result to not break recommendation generation
            return {
                "learning_events_applied": 0,
                "pattern_memories_updated": 0,
                "test_coverage_links_updated": 0,
                "scenario_intents_updated": 0,
                "error": "Learning processing failed"
            }

    def _strengthen_test_mapping(
        self,
        rec_run: RecommendationRun,
        recommended_test: RecommendedTest,
        test_outcome: RecommendationTestOutcome,
    ) -> int:
        """
        Strengthen PatternMemoryV2 for kept tests that were executed.
        """
        pattern_key = f"test_{recommended_test.test_identifier}"
        
        self.pattern_memory_upsert.upsert_signal(
            repository_id=rec_run.repository_id,
            workspace_id=rec_run.workspace_id,
            pattern_key=pattern_key,
            signal_type=SIGNAL_TYPE_EXECUTION_RESULT,
            strength=0.5,
            confidence=0.5,
            test_identifier=recommended_test.test_identifier,
            increment_usage=True,
            increment_success=(test_outcome.execution_status == "PASSED"),
            increment_failure=(test_outcome.execution_status == "FAILED"),
        )
        
        return 1

    def _strengthen_coverage_link(
        self,
        rec_run: RecommendationRun,
        recommended_test: RecommendedTest,
        test_outcome: RecommendationTestOutcome,
    ) -> int:
        """
        Strengthen TestCoverageLink for kept tests.
        """
        # Get changed files from recommendation run
        changed_files = rec_run.evidence.get("changed_files", [])
        
        updated = 0
        for file_path in changed_files:
            # Find or create TestCoverageLink
            link = self.db.query(TestCoverageLink).filter(
                and_(
                    TestCoverageLink.repository_id == rec_run.repository_id,
                    TestCoverageLink.test_identifier == recommended_test.test_identifier,
                    TestCoverageLink.file_path == file_path,
                )
            ).first()
            
            if link:
                # Append-only: increment counters
                link.run_count += 1
                if test_outcome.execution_status == "PASSED":
                    link.success_count += 1
                elif test_outcome.execution_status == "FAILED":
                    link.failure_count += 1
                link.last_seen_at = datetime.utcnow()
                # Strengthen link_strength
                if link.link_strength is None:
                    link.link_strength = 0.5
                link.link_strength = min(1.0, link.link_strength + 0.05)
            else:
                # Create new TestCoverageLink
                link = TestCoverageLink(
                    workspace_id=rec_run.workspace_id,
                    repository_id=rec_run.repository_id,
                    test_identifier=recommended_test.test_identifier,
                    file_path=file_path,
                    link_strength=0.5,
                    confidence=0.5,
                    source="RECOMMENDATION_OUTCOME",
                    run_count=1,
                    success_count=1 if test_outcome.execution_status == "PASSED" else 0,
                    failure_count=1 if test_outcome.execution_status == "FAILED" else 0,
                    override_count=0,
                    defect_count=0,
                    first_seen_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                )
                self.db.add(link)
            
            updated += 1
        
        return updated

    def _weaken_pattern_memory(
        self,
        rec_run: RecommendationRun,
        recommended_test: RecommendedTest,
    ) -> int:
        """
        Weaken PatternMemoryV2 for removed low-confidence tests.
        """
        pattern_key = f"test_{recommended_test.test_identifier}"
        
        self.pattern_memory_upsert.weaken_signal(
            repository_id=rec_run.repository_id,
            pattern_key=pattern_key,
            signal_type=SIGNAL_TYPE_MANUAL_REMOVAL,
            test_identifier=recommended_test.test_identifier,
            strength_decrement=0.2,
            confidence_decrement=0.1,
        )
        
        return 1

    def _create_or_strengthen_pattern_memory(
        self,
        rec_run: RecommendationRun,
        override: RecommendationOverride,
    ) -> int:
        """
        Create or strengthen PatternMemoryV2 for manually added tests.
        """
        pattern_key = f"manual_{override.test_identifier}"
        
        self.pattern_memory_upsert.upsert_signal(
            repository_id=rec_run.repository_id,
            workspace_id=rec_run.workspace_id,
            pattern_key=pattern_key,
            signal_type=SIGNAL_TYPE_MANUAL_ADDITION,
            strength=0.7,
            confidence=0.7,
            test_identifier=override.test_identifier,
            increment_usage=True,
        )
        
        return 1

    def _create_or_strengthen_coverage_link(
        self,
        rec_run: RecommendationRun,
        override: RecommendationOverride,
    ) -> int:
        """
        Create or strengthen TestCoverageLink for manually added tests.
        """
        changed_files = rec_run.evidence.get("changed_files", [])
        
        updated = 0
        for file_path in changed_files:
            link = self.db.query(TestCoverageLink).filter(
                and_(
                    TestCoverageLink.repository_id == rec_run.repository_id,
                    TestCoverageLink.test_identifier == override.test_identifier,
                    TestCoverageLink.file_path == file_path,
                )
            ).first()
            
            if link:
                # Increment override_count for manual additions
                link.override_count += 1
                link.last_seen_at = datetime.utcnow()
                # Strengthen link for manual additions
                if link.link_strength is None:
                    link.link_strength = 0.5
                link.link_strength = min(1.0, link.link_strength + 0.1)
            else:
                # Create new TestCoverageLink for manual addition
                link = TestCoverageLink(
                    workspace_id=rec_run.workspace_id,
                    repository_id=rec_run.repository_id,
                    test_identifier=override.test_identifier,
                    file_path=file_path,
                    link_strength=0.7,
                    confidence=0.7,
                    source="MANUAL_OVERRIDE",
                    run_count=0,
                    success_count=0,
                    failure_count=0,
                    override_count=1,
                    defect_count=0,
                    first_seen_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                )
                self.db.add(link)
            
            updated += 1
        
        return updated

    def _strengthen_scenario_intent(
        self,
        rec_run: RecommendationRun,
        scenario_outcome: SuggestedScenarioOutcome,
    ) -> int:
        """
        Strengthen PatternMemoryV2 for accepted/important scenarios.
        """
        pattern_key = f"scenario_{scenario_outcome.scenario_intent_key}"
        
        self.pattern_memory_upsert.upsert_signal(
            repository_id=rec_run.repository_id,
            workspace_id=rec_run.workspace_id,
            pattern_key=pattern_key,
            signal_type=SIGNAL_TYPE_ACCEPTED_SCENARIO,
            strength=0.7,
            confidence=0.7,
            scenario_intent_key=scenario_outcome.scenario_intent_key,
            increment_usage=True,
        )
        
        return 1

    def _reduce_scenario_priority(
        self,
        rec_run: RecommendationRun,
        scenario_outcome: SuggestedScenarioOutcome,
    ) -> int:
        """
        Reduce priority for dismissed low-confidence scenarios.
        """
        pattern_key = f"scenario_{scenario_outcome.scenario_intent_key}"
        
        self.pattern_memory_upsert.weaken_signal(
            repository_id=rec_run.repository_id,
            pattern_key=pattern_key,
            signal_type=SIGNAL_TYPE_DISMISSED_SCENARIO,
            scenario_intent_key=scenario_outcome.scenario_intent_key,
            strength_decrement=0.2,
            confidence_decrement=0.1,
        )
        
        return 1

    def _strengthen_missed_behaviors(
        self,
        rec_run: RecommendationRun,
        outcome: RecommendationOutcome,
    ) -> int:
        """
        Strengthen missed behaviors when defect escaped.
        """
        # Find tests that were NOT executed but should have been
        test_outcomes = self.db.query(RecommendationTestOutcome).filter(
            and_(
                RecommendationTestOutcome.recommendation_run_id == rec_run.id,
                RecommendationTestOutcome.execution_status == "NOT_RUN",
            )
        ).all()
        
        updated = 0
        for test_outcome in test_outcomes:
            pattern_key = f"missed_{test_outcome.test_identifier}"
            
            self.pattern_memory_upsert.upsert_signal(
                repository_id=rec_run.repository_id,
                workspace_id=rec_run.workspace_id,
                pattern_key=pattern_key,
                signal_type=SIGNAL_TYPE_ESCAPED_DEFECT,
                strength=0.7,
                confidence=0.7,
                test_identifier=test_outcome.test_identifier,
                increment_usage=True,
                increment_defect=True,
            )
            updated += 1
        
        return updated

    def _strengthen_defect_gaps(
        self,
        rec_run: RecommendationRun,
        outcome: RecommendationOutcome,
    ) -> int:
        """
        Strengthen defect gaps in TestCoverageLink when defect escaped.
        """
        changed_files = rec_run.evidence.get("changed_files", [])
        
        # Find tests that were NOT executed
        test_outcomes = self.db.query(RecommendationTestOutcome).filter(
            and_(
                RecommendationTestOutcome.recommendation_run_id == rec_run.id,
                RecommendationTestOutcome.execution_status == "NOT_RUN",
            )
        ).all()
        
        test_identifiers = {to.test_identifier for to in test_outcomes}
        
        updated = 0
        for file_path in changed_files:
            for test_identifier in test_identifiers:
                link = self.db.query(TestCoverageLink).filter(
                    and_(
                        TestCoverageLink.repository_id == rec_run.repository_id,
                        TestCoverageLink.test_identifier == test_identifier,
                        TestCoverageLink.file_path == file_path,
                    )
                ).first()
                
                if link:
                    # Increment defect_count for gap
                    link.defect_count += 1
                    # Strengthen link to ensure future recommendation
                    if link.link_strength is None:
                        link.link_strength = 0.5
                    link.link_strength = min(1.0, link.link_strength + 0.2)
                    updated += 1
        
        return updated

    def _mark_fragile_patterns(
        self,
        rec_run: RecommendationRun,
        outcome: RecommendationOutcome,
    ) -> int:
        """
        Mark patterns as fragile when rollback occurred.
        """
        # Find tests that were executed and failed
        test_outcomes = self.db.query(RecommendationTestOutcome).filter(
            and_(
                RecommendationTestOutcome.recommendation_run_id == rec_run.id,
                RecommendationTestOutcome.execution_status == "FAILED",
            )
        ).all()
        
        updated = 0
        for test_outcome in test_outcomes:
            pattern_key = f"fragile_{test_outcome.test_identifier}"
            
            self.pattern_memory_upsert.upsert_signal(
                repository_id=rec_run.repository_id,
                workspace_id=rec_run.workspace_id,
                pattern_key=pattern_key,
                signal_type=SIGNAL_TYPE_ROLLBACK,
                strength=0.3,
                confidence=0.3,
                test_identifier=test_outcome.test_identifier,
                increment_usage=True,
                increment_rollback=True,
            )
            updated += 1
        
        return updated

    def _create_escaped_defect_evidence(
        self,
        rec_run: RecommendationRun,
        outcome: RecommendationOutcome,
    ) -> None:
        """
        Create FragilityEvidenceEvent for escaped defect.
        Idempotent - checks for existing evidence before creating.
        """
        # Check if evidence already exists for this outcome
        existing = self.db.query(FragilityEvidenceEvent).filter(
            and_(
                FragilityEvidenceEvent.source_entity_type == "RECOMMENDATION_OUTCOME",
                FragilityEvidenceEvent.source_entity_id == str(outcome.id),
                FragilityEvidenceEvent.evidence_type == "ESCAPED_DEFECT",
            )
        ).first()
        
        if existing:
            logger.debug(f"Escaped defect evidence already exists for outcome {outcome.id}")
            return
        
        # Find behavior/journey context from recommendation run
        impacted_behaviors = []
        impacted_journeys = []
        
        if rec_run.impact_profile:
            for b in rec_run.impact_profile.get("impacted_behaviors", []):
                impacted_behaviors.append(b.get("behavior_id"))
            for j in rec_run.impact_profile.get("impacted_journeys", []):
                impacted_journeys.append(j.get("journey_id"))
        
        # Create evidence for each impacted behavior
        for behavior_id in impacted_behaviors:
            if not behavior_id:
                continue
            
            # Find or create behavior fragility memory
            memory_key = f"behavior_{behavior_id}_escaped_defect"
            memory = self.db.query(FragilityMemoryV2).filter(
                and_(
                    FragilityMemoryV2.repository_id == rec_run.repository_id,
                    FragilityMemoryV2.memory_key == memory_key,
                )
            ).first()
            
            if not memory:
                memory = FragilityMemoryV2(
                    repository_id=rec_run.repository_id,
                    workspace_id=rec_run.workspace_id,
                    memory_key=memory_key,
                    memory_type="ESCAPED_DEFECT_PATTERN",
                    subject_type="BEHAVIOR",
                    subject_id=behavior_id,
                    subject_name=f"Behavior {behavior_id}",
                    risk_level="HIGH",
                    fragility_score=70.0,
                    confidence=0.7,
                    status="ACTIVE",
                    first_seen_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                    last_updated_at=datetime.utcnow(),
                )
                self.db.add(memory)
                self.db.flush()
            
            # Create evidence event
            evidence = FragilityEvidenceEvent(
                fragility_memory_id=memory.id,
                evidence_type="ESCAPED_DEFECT",
                source_entity_type="RECOMMENDATION_OUTCOME",
                source_entity_id=str(outcome.id),
                occurred_at=datetime.utcnow(),
                context_data={
                    "recommendation_run_id": str(rec_run.id),
                    "changed_files": rec_run.evidence.get("changed_files", []),
                    "impacted_behaviors": impacted_behaviors,
                    "impacted_journeys": impacted_journeys,
                },
            )
            self.db.add(evidence)
        
        logger.info(f"Created escaped defect evidence for outcome {outcome.id}")

    def _create_rollback_evidence(
        self,
        rec_run: RecommendationRun,
        outcome: RecommendationOutcome,
    ) -> None:
        """
        Create FragilityEvidenceEvent for rollback.
        Idempotent - checks for existing evidence before creating.
        """
        # Check if evidence already exists for this outcome
        existing = self.db.query(FragilityEvidenceEvent).filter(
            and_(
                FragilityEvidenceEvent.source_entity_type == "RECOMMENDATION_OUTCOME",
                FragilityEvidenceEvent.source_entity_id == str(outcome.id),
                FragilityEvidenceEvent.evidence_type == "ROLLBACK",
            )
        ).first()
        
        if existing:
            logger.debug(f"Rollback evidence already exists for outcome {outcome.id}")
            return
        
        # Find failed tests
        test_outcomes = self.db.query(RecommendationTestOutcome).filter(
            and_(
                RecommendationTestOutcome.recommendation_run_id == rec_run.id,
                RecommendationTestOutcome.execution_status == "FAILED",
            )
        ).all()
        
        # Create evidence for each failed test
        for test_outcome in test_outcomes:
            memory_key = f"test_{test_outcome.test_identifier}_rollback"
            memory = self.db.query(FragilityMemoryV2).filter(
                and_(
                    FragilityMemoryV2.repository_id == rec_run.repository_id,
                    FragilityMemoryV2.memory_key == memory_key,
                )
            ).first()
            
            if not memory:
                memory = FragilityMemoryV2(
                    repository_id=rec_run.repository_id,
                    workspace_id=rec_run.workspace_id,
                    memory_key=memory_key,
                    memory_type="ROLLBACK_PATTERN",
                    subject_type="TEST",
                    subject_id=test_outcome.test_identifier,
                    subject_name=test_outcome.test_identifier,
                    risk_level="HIGH",
                    fragility_score=75.0,
                    confidence=0.7,
                    status="ACTIVE",
                    first_seen_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                    last_updated_at=datetime.utcnow(),
                )
                self.db.add(memory)
                self.db.flush()
            
            # Create evidence event
            evidence = FragilityEvidenceEvent(
                fragility_memory_id=memory.id,
                evidence_type="ROLLBACK",
                source_entity_type="RECOMMENDATION_OUTCOME",
                source_entity_id=str(outcome.id),
                occurred_at=datetime.utcnow(),
                context_data={
                    "recommendation_run_id": str(rec_run.id),
                    "test_identifier": test_outcome.test_identifier,
                    "changed_files": rec_run.evidence.get("changed_files", []),
                },
            )
            self.db.add(evidence)
        
        logger.info(f"Created rollback evidence for outcome {outcome.id}")

    def _create_missing_coverage_evidence(
        self,
        rec_run: RecommendationRun,
        scenario_outcome: SuggestedScenarioOutcome,
    ) -> None:
        """
        Create FragilityEvidenceEvent for manually added important scenario.
        Called when scenario is marked as IMPORTANT.
        """
        # Check if evidence already exists
        existing = self.db.query(FragilityEvidenceEvent).filter(
            and_(
                FragilityEvidenceEvent.source_entity_type == "SCENARIO_OUTCOME",
                FragilityEvidenceEvent.source_entity_id == str(scenario_outcome.id),
                FragilityEvidenceEvent.evidence_type == "MISSING_COVERAGE",
            )
        ).first()
        
        if existing:
            return
        
        # Find behavior from scenario
        scenario = self.db.query(BehaviorScenario).filter(
            BehaviorScenario.scenario_intent_key == scenario_outcome.scenario_intent_key
        ).first()
        
        if not scenario:
            logger.warning(f"Scenario not found for key {scenario_outcome.scenario_intent_key}")
            return
        
        # Create or update missing coverage memory
        memory_key = f"scenario_{scenario.scenario_intent_key}_missing_coverage"
        memory = self.db.query(FragilityMemoryV2).filter(
            and_(
                FragilityMemoryV2.repository_id == rec_run.repository_id,
                FragilityMemoryV2.memory_key == memory_key,
            )
        ).first()
        
        if not memory:
            memory = FragilityMemoryV2(
                repository_id=rec_run.repository_id,
                workspace_id=rec_run.workspace_id,
                memory_key=memory_key,
                memory_type="MISSING_COVERAGE_PATTERN",
                subject_type="SCENARIO",
                subject_id=str(scenario.id),
                subject_name=scenario.scenario_intent_key,
                risk_level="MODERATE",
                fragility_score=50.0,
                confidence=0.6,
                status="ACTIVE",
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow(),
            )
            self.db.add(memory)
            self.db.flush()
        
        # Create evidence event
        evidence = FragilityEvidenceEvent(
            fragility_memory_id=memory.id,
            evidence_type="MISSING_COVERAGE",
            source_entity_type="SCENARIO_OUTCOME",
            source_entity_id=str(scenario_outcome.id),
            occurred_at=datetime.utcnow(),
            context_data={
                "recommendation_run_id": str(rec_run.id),
                "scenario_intent_key": scenario.scenario_intent_key,
                "behavior_id": str(scenario.behavior_id),
                "reason": "Manually added as important scenario",
            },
        )
        self.db.add(evidence)
        
        logger.info(f"Created missing coverage evidence for scenario {scenario.scenario_intent_key}")

    def _create_failure_evidence(
        self,
        rec_run: RecommendationRun,
        test_outcome: RecommendationTestOutcome,
    ) -> None:
        """
        Create FragilityEvidenceEvent for failed recommended test.
        """
        if test_outcome.execution_status != "FAILED":
            return
        
        # Check if evidence already exists
        existing = self.db.query(FragilityEvidenceEvent).filter(
            and_(
                FragilityEvidenceEvent.source_entity_type == "TEST_OUTCOME",
                FragilityEvidenceEvent.source_entity_id == str(test_outcome.id),
                FragilityEvidenceEvent.evidence_type == "TEST_FAILURE",
            )
        ).first()
        
        if existing:
            return
        
        # Create or update test failure memory
        memory_key = f"test_{test_outcome.test_identifier}_failure"
        memory = self.db.query(FragilityMemoryV2).filter(
            and_(
                FragilityMemoryV2.repository_id == rec_run.repository_id,
                FragilityMemoryV2.memory_key == memory_key,
            )
        ).first()
        
        if not memory:
            memory = FragilityMemoryV2(
                repository_id=rec_run.repository_id,
                workspace_id=rec_run.workspace_id,
                memory_key=memory_key,
                memory_type="REPEATED_TEST_FAILURE",
                subject_type="TEST",
                subject_id=test_outcome.test_identifier,
                subject_name=test_outcome.test_identifier,
                risk_level="MODERATE",
                fragility_score=55.0,
                confidence=0.6,
                status="ACTIVE",
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow(),
            )
            self.db.add(memory)
            self.db.flush()
        
        # Create evidence event
        evidence = FragilityEvidenceEvent(
            fragility_memory_id=memory.id,
            evidence_type="TEST_FAILURE",
            source_entity_type="TEST_OUTCOME",
            source_entity_id=str(test_outcome.id),
            occurred_at=datetime.utcnow(),
            context_data={
                "recommendation_run_id": str(rec_run.id),
                "test_identifier": test_outcome.test_identifier,
                "engineer_decision": test_outcome.engineer_decision,
            },
        )
        self.db.add(evidence)
        
        logger.info(f"Created failure evidence for test {test_outcome.test_identifier}")

    def _flag_weak_memory(
        self,
        rec_run: RecommendationRun,
        test_outcome: RecommendationTestOutcome,
    ) -> None:
        """
        Flag or reduce weak memory when irrelevant test is removed.
        """
        if test_outcome.engineer_decision != "REMOVED":
            return
        
        # Find related fragility memory
        memory_key = f"test_{test_outcome.test_identifier}_failure"
        memory = self.db.query(FragilityMemoryV2).filter(
            and_(
                FragilityMemoryV2.repository_id == rec_run.repository_id,
                FragilityMemoryV2.memory_key == memory_key,
            )
        ).first()
        
        if memory:
            # Reduce confidence and score
            memory.confidence = max(0.1, memory.confidence - 0.2)
            memory.fragility_score = max(10.0, memory.fragility_score - 15.0)
            memory.last_updated_at = datetime.utcnow()
            
            # If score is very low, mark as stale
            if memory.fragility_score < 20.0:
                memory.status = "STALE"
                memory.decay_applied = True
                memory.decay_factor = 0.5
            
            logger.info(f"Flagged weak memory for test {test_outcome.test_identifier}")
