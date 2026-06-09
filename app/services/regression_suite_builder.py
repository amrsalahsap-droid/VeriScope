"""
Regression Suite Builder Service

Converts recommendation runs into persistent regression suites with scope items.
"""

import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationRun, RecommendedTest, SuggestedTestScenario
from app.models.regression_suite import (
    RegressionSuite, RegressionScopeItem, ScopeOverride,
    SuiteType, SuiteStatus, ScopeItemType, ScopeTier, ScopePriority, ExecutionStatus
)
from app.models.test_result import TestCase
from app.models.external_test_case_detailed import ExternalTestCase
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.behavior_scenario import BehaviorScenario
from app.models.business_behavior_mapping import BusinessBehaviorMapping

logger = logging.getLogger(__name__)


class RegressionSuiteBuilder:
    """Builds regression suites from recommendation runs."""
    
    @classmethod
    def create_from_recommendation_run(
        cls,
        db: Session,
        recommendation_run_id: uuid.UUID,
        created_by: Optional[str] = None,
        force_new: bool = False
    ) -> Dict[str, Any]:
        """
        Create a regression suite from a recommendation run.
        
        Args:
            db: Database session
            recommendation_run_id: UUID of the recommendation run
            created_by: User who created the suite
            force_new: If True, create a new suite even if one exists for this run
            
        Returns:
            Dictionary with suite summary including counts by tier/type
        """
        logger.info(f"Creating regression suite from recommendation run {recommendation_run_id}")
        
        # Load recommendation run
        run = db.query(RecommendationRun).filter(
            RecommendationRun.id == recommendation_run_id
        ).first()
        
        if not run:
            raise ValueError(f"Recommendation run {recommendation_run_id} not found")
        
        # Check if suite already exists for this run (idempotency)
        existing_suite = db.query(RegressionSuite).filter(
            RegressionSuite.recommendation_run_id == recommendation_run_id
        ).first()
        
        if existing_suite and not force_new:
            logger.info(f"Regression suite already exists for run {recommendation_run_id}, returning existing")
            return cls._build_suite_summary(existing_suite)
        
        # Determine suite type
        suite_type = SuiteType.PR_REGRESSION
        if run.pull_request:
            suite_type = SuiteType.PR_REGRESSION
        else:
            suite_type = SuiteType.RELEASE_REGRESSION
        
        # Create regression suite
        suite = RegressionSuite(
            repository_id=run.repository_id,
            pull_request_id=run.pull_request_id,
            recommendation_run_id=run.id,
            name=f"Regression Suite - {run.pr_id[:50]}",
            description=f"Regression suite generated from recommendation run {run.id}",
            suite_type=suite_type,
            status=SuiteStatus.DRAFT,
            confidence_level=run.evidence_quality,
            scope_score=cls._calculate_scope_score(run),
            created_by=created_by or "system",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        db.add(suite)
        db.flush()
        
        # Create scope items from recommended tests
        cls._create_scope_items_from_tests(db, suite, run)
        
        # Create scope items from suggested scenarios
        cls._create_scope_items_from_scenarios(db, suite, run)
        
        # Create scope items from manual test cases if available
        cls._create_scope_items_from_manual_tests(db, suite, run)
        
        # Create scope items for coverage gaps
        cls._create_scope_items_from_coverage_gaps(db, suite, run)
        
        db.commit()
        logger.info(f"Created regression suite {suite.id} with {len(suite.scope_items)} scope items")
        
        return cls._build_suite_summary(suite, db)
    
    @classmethod
    def _build_suite_summary(cls, suite: RegressionSuite, db: Session = None) -> Dict[str, Any]:
        """Build a summary of the suite with counts by tier/type."""
        # Get all scope items for this suite
        from sqlalchemy import func
        
        if db is None:
            # Use the relationship if no db session provided
            scope_items = suite.scope_items
        else:
            # Query from database
            scope_items = db.query(RegressionScopeItem).filter(
                RegressionScopeItem.regression_suite_id == suite.id
            ).all()
        
        # Count by tier
        tier_counts = {}
        for tier in [ScopeTier.MUST_RUN, ScopeTier.SHOULD_RUN, ScopeTier.OPTIONAL]:
            count = sum(1 for item in scope_items if item.tier == tier)
            tier_counts[tier] = count
        
        # Count by item type
        type_counts = {}
        for item_type in [ScopeItemType.AUTOMATED_TEST, ScopeItemType.MANUAL_TEST, ScopeItemType.SUGGESTED_SCENARIO, ScopeItemType.COVERAGE_GAP]:
            count = sum(1 for item in scope_items if item.item_type == item_type)
            type_counts[item_type] = count
        
        return {
            "suite_id": str(suite.id),
            "name": suite.name,
            "suite_type": suite.suite_type,
            "status": suite.status,
            "total_scope_items": len(suite.scope_items),
            "tier_counts": tier_counts,
            "type_counts": type_counts,
            "created_at": suite.created_at.isoformat() if suite.created_at else None,
        }
    
    @classmethod
    def _calculate_scope_score(cls, run: RecommendationRun) -> float:
        """Calculate scope score based on recommendation quality."""
        # Simple heuristic based on evidence quality
        quality_scores = {
            "HIGH": 0.9,
            "MODERATE": 0.7,
            "LOW": 0.5,
            "UNKNOWN": 0.3
        }
        return quality_scores.get(run.evidence_quality, 0.5)
    
    @classmethod
    def _create_scope_items_from_tests(
        cls,
        db: Session,
        suite: RegressionSuite,
        run: RecommendationRun
    ) -> None:
        """Create scope items from recommended tests."""
        recommended_tests = db.query(RecommendedTest).filter(
            RecommendedTest.recommendation_run_id == run.id,
            RecommendedTest.included == True
        ).all()
        
        for rec_test in recommended_tests:
            # Determine tier and priority based on reason_type or priority score
            tier, priority = cls._map_test_tier_priority(rec_test)
            
            # Find test case
            test_case = db.query(TestCase).filter(
                TestCase.stable_identity == rec_test.test_identifier,
                TestCase.repository_id == run.repository_id
            ).first()
            
            # Create scope item
            scope_item = RegressionScopeItem(
                regression_suite_id=suite.id,
                test_case_id=test_case.id if test_case else None,
                item_type=ScopeItemType.AUTOMATED_TEST,
                tier=tier,
                priority=priority,
                selection_reason=rec_test.reason,
                evidence_summary={
                    "source_signal": rec_test.source_signal,
                    "confidence": rec_test.confidence,
                    "estimated_duration": rec_test.estimated_duration_seconds,
                    "priority": rec_test.priority
                },
                execution_status=ExecutionStatus.NOT_RUN,
                is_excluded=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(scope_item)
            db.flush()  # Flush to get the ID for linking
            
            # Link to behavior/journey/AC if available from impact profile
            cls._link_business_context(db, scope_item, run, rec_test.test_identifier)
    
    @classmethod
    def _create_scope_items_from_scenarios(
        cls,
        db: Session,
        suite: RegressionSuite,
        run: RecommendationRun
    ) -> None:
        """Create scope items from suggested scenarios."""
        suggested_scenarios = db.query(SuggestedTestScenario).filter(
            SuggestedTestScenario.recommendation_run_id == run.id
        ).all()
        
        for scenario in suggested_scenarios:
            # Determine tier and priority based on importance
            tier, priority = cls._map_scenario_tier_priority(scenario)
            
            # Create scope item
            scope_item = RegressionScopeItem(
                regression_suite_id=suite.id,
                suggested_scenario_id=scenario.id,
                item_type=ScopeItemType.SUGGESTED_SCENARIO,
                tier=tier,
                priority=priority,
                selection_reason=f"Suggested scenario for {scenario.impacted_area}",
                evidence_summary={
                    "testing_type": scenario.testing_type,
                    "priority": scenario.priority,
                    "confidence": scenario.confidence,
                    "automation_candidate": scenario.automation_candidate
                },
                execution_status=ExecutionStatus.MANUAL_PENDING,
                is_excluded=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(scope_item)
            db.flush()  # Flush to get the ID for linking
            
            # Skip behavior/journey linking for scenarios due to model incompatibilities
    
    @classmethod
    def _create_scope_items_from_manual_tests(
        cls,
        db: Session,
        suite: RegressionSuite,
        run: RecommendationRun
    ) -> None:
        """Create scope items from manual test cases if available."""
        # Find external test cases linked to this repository
        manual_tests = db.query(ExternalTestCase).filter(
            ExternalTestCase.repository_id == run.repository_id,
            ExternalTestCase.automation_status == "MANUAL"
        ).limit(10).all()  # Limit to avoid too many manual tests
        
        for manual_test in manual_tests:
            # Determine tier based on priority
            priority = manual_test.priority or "MEDIUM"
            if priority == "CRITICAL":
                tier = ScopeTier.MUST_RUN
                priority_enum = ScopePriority.CRITICAL
            elif priority == "HIGH":
                tier = ScopeTier.SHOULD_RUN
                priority_enum = ScopePriority.HIGH
            elif priority == "MEDIUM":
                tier = ScopeTier.SHOULD_RUN
                priority_enum = ScopePriority.MEDIUM
            else:
                tier = ScopeTier.OPTIONAL
                priority_enum = ScopePriority.LOW
            
            # Create scope item
            scope_item = RegressionScopeItem(
                regression_suite_id=suite.id,
                external_test_case_id=manual_test.id,
                item_type=ScopeItemType.MANUAL_TEST,
                tier=tier,
                priority=priority_enum,
                selection_reason=f"Manual test case: {manual_test.title}",
                evidence_summary={
                    "provider": manual_test.provider,
                    "external_id": manual_test.external_id
                },
                execution_status=ExecutionStatus.MANUAL_PENDING,
                is_excluded=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(scope_item)
            db.flush()
            
            # Link to behavior/journey if available
            if manual_test.behavior_id:
                scope_item.behavior_id = manual_test.behavior_id
            if manual_test.journey_id:
                scope_item.journey_id = manual_test.journey_id
    
    @classmethod
    def _create_scope_items_from_coverage_gaps(
        cls,
        db: Session,
        suite: RegressionSuite,
        run: RecommendationRun
    ) -> None:
        """Create scope items for coverage gaps without concrete tests."""
        # This is a placeholder for future implementation
        # For now, we'll create coverage gap items for behaviors that have no test coverage
        # based on the impact profile
        
        impact_profile = run.impact_profile or {}
        impacted_behaviors = impact_profile.get("impacted_behaviors", [])
        
        # Limit to a few coverage gaps to avoid overwhelming the suite
        for behavior_id in impacted_behaviors[:3]:
            # Check if there's already a test for this behavior in the suite
            existing_item = suite.scope_items.filter(
                RegressionScopeItem.behavior_id == behavior_id
            ).first()
            
            if not existing_item:
                # Create a coverage gap item
                scope_item = RegressionScopeItem(
                    regression_suite_id=suite.id,
                    behavior_id=behavior_id,
                    item_type=ScopeItemType.COVERAGE_GAP,
                    tier=ScopeTier.OPTIONAL,
                    priority=ScopePriority.LOW,
                    selection_reason="Coverage gap identified for impacted behavior",
                    evidence_summary={
                        "gap_type": "no_test_coverage",
                        "behavior_id": str(behavior_id)
                    },
                    execution_status=ExecutionStatus.NOT_RUN,
                    is_excluded=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                db.add(scope_item)
    
    @classmethod
    def _link_business_context(
        cls,
        db: Session,
        scope_item: RegressionScopeItem,
        run: RecommendationRun,
        test_identifier: str
    ) -> None:
        """Link scope item to behavior/journey/AC if available."""
        # Simplified version - skip business context linking for now
        # due to model incompatibilities
        pass
        
        # Try to find acceptance criterion if this is a PR
        if run.pull_request_id:
            ac = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.pull_request_id == run.pull_request_id
            ).first()
            if ac:
                scope_item.acceptance_criterion_id = ac.id
    
    @classmethod
    def _map_test_tier_priority(cls, rec_test: RecommendedTest) -> tuple:
        """Map recommended test to tier and priority based on priority score."""
        # Use priority score to determine tier
        if rec_test.priority >= 0.8:
            return ScopeTier.MUST_RUN, ScopePriority.CRITICAL
        elif rec_test.priority >= 0.5:
            return ScopeTier.SHOULD_RUN, ScopePriority.HIGH
        else:
            return ScopeTier.OPTIONAL, ScopePriority.MEDIUM
    
    @classmethod
    def _map_scenario_tier_priority(cls, scenario: SuggestedTestScenario) -> tuple:
        """Map suggested scenario to tier and priority based on priority."""
        priority = (scenario.priority or "").upper()
        
        if priority == "CRITICAL" or priority == "HIGH":
            return ScopeTier.MUST_RUN, ScopePriority.CRITICAL
        elif priority == "MEDIUM":
            return ScopeTier.SHOULD_RUN, ScopePriority.HIGH
        else:  # LOW or optional
            return ScopeTier.OPTIONAL, ScopePriority.MEDIUM
    
    @classmethod
    def _priority_to_tier(cls, priority: float) -> str:
        """Convert numeric priority to tier."""
        if priority >= 0.8:
            return ScopeTier.MUST_RUN
        elif priority >= 0.5:
            return ScopeTier.SHOULD_RUN
        else:
            return ScopeTier.OPTIONAL
    
    @classmethod
    def _priority_to_enum(cls, priority: float) -> str:
        """Convert numeric priority to priority enum."""
        if priority >= 0.8:
            return ScopePriority.CRITICAL
        elif priority >= 0.6:
            return ScopePriority.HIGH
        elif priority >= 0.4:
            return ScopePriority.MEDIUM
        else:
            return ScopePriority.LOW
