"""
Test script for BehaviorDiscoveryRefreshPipeline.

Tests pipeline execution with various triggers.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_discovery_refresh_pipeline import (
    BehaviorDiscoveryRefreshPipeline,
    PipelineTrigger,
    PipelineResult,
)
from dataclasses import dataclass
from typing import Optional
import uuid


# Mock Repository class for testing
@dataclass
class MockRepository:
    id: str
    name: str
    workspace_path: Optional[str] = None


def test_pipeline():
    """Test pipeline with various triggers."""
    print("=" * 60)
    print("BEHAVIOR DISCOVERY REFRESH PIPELINE TEST")
    print("=" * 60)
    
    # Create mock repository
    repository = MockRepository(
        id=str(uuid.uuid4()),
        name="test-repo",
        workspace_path="/tmp/test-repo",
    )
    
    # Mock database session (would be real in production)
    class MockDB:
        def commit(self):
            pass
    
    db = MockDB()
    
    # Initialize pipeline
    pipeline = BehaviorDiscoveryRefreshPipeline(db)
    
    # Test 1: Repository Sync trigger
    print("\nTest 1: Repository Sync Trigger")
    print("-" * 60)
    try:
        result = pipeline.trigger_on_repository_sync(repository)
        print(f"Success: {result.success}")
        print(f"Trigger: {result.trigger.value}")
        print(f"Steps Completed: {len(result.steps_completed)}")
        for step in result.steps_completed:
            print(f"  - {step}")
        if result.steps_failed:
            print(f"Steps Failed: {len(result.steps_failed)}")
            for step in result.steps_failed:
                print(f"  - {step}")
        print(f"Behaviors Discovered: {result.behaviors_discovered}")
        print(f"Behaviors Updated: {result.behaviors_updated}")
        print(f"Execution Time: {result.execution_time_seconds:.2f}s")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Test 2: New PR trigger
    print("\n\nTest 2: New PR Trigger")
    print("-" * 60)
    try:
        result = pipeline.trigger_on_new_pr(repository)
        print(f"Success: {result.success}")
        print(f"Trigger: {result.trigger.value}")
        print(f"Steps Completed: {len(result.steps_completed)}")
        for step in result.steps_completed:
            print(f"  - {step}")
        if result.steps_failed:
            print(f"Steps Failed: {len(result.steps_failed)}")
            for step in result.steps_failed:
                print(f"  - {step}")
        print(f"Behaviors Discovered: {result.behaviors_discovered}")
        print(f"Behaviors Updated: {result.behaviors_updated}")
        print(f"Execution Time: {result.execution_time_seconds:.2f}s")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Test 3: Manual Refresh trigger
    print("\n\nTest 3: Manual Refresh Trigger (Incremental)")
    print("-" * 60)
    try:
        result = pipeline.trigger_manual_refresh(repository, force_full_rebuild=False)
        print(f"Success: {result.success}")
        print(f"Trigger: {result.trigger.value}")
        print(f"Steps Completed: {len(result.steps_completed)}")
        for step in result.steps_completed:
            print(f"  - {step}")
        if result.steps_failed:
            print(f"Steps Failed: {len(result.steps_failed)}")
            for step in result.steps_failed:
                print(f"  - {step}")
        print(f"Behaviors Discovered: {result.behaviors_discovered}")
        print(f"Behaviors Updated: {result.behaviors_updated}")
        print(f"Execution Time: {result.execution_time_seconds:.2f}s")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Test 4: Manual Refresh trigger (Full Rebuild)
    print("\n\nTest 4: Manual Refresh Trigger (Full Rebuild)")
    print("-" * 60)
    try:
        result = pipeline.trigger_manual_refresh(repository, force_full_rebuild=True)
        print(f"Success: {result.success}")
        print(f"Trigger: {result.trigger.value}")
        print(f"Steps Completed: {len(result.steps_completed)}")
        for step in result.steps_completed:
            print(f"  - {step}")
        if result.steps_failed:
            print(f"Steps Failed: {len(result.steps_failed)}")
            for step in result.steps_failed:
                print(f"  - {step}")
        print(f"Behaviors Discovered: {result.behaviors_discovered}")
        print(f"Behaviors Updated: {result.behaviors_updated}")
        print(f"Execution Time: {result.execution_time_seconds:.2f}s")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Test 5: New Documentation trigger
    print("\n\nTest 5: New Documentation Trigger")
    print("-" * 60)
    try:
        result = pipeline.trigger_on_new_documentation(repository)
        print(f"Success: {result.success}")
        print(f"Trigger: {result.trigger.value}")
        print(f"Steps Completed: {len(result.steps_completed)}")
        for step in result.steps_completed:
            print(f"  - {step}")
        if result.steps_failed:
            print(f"Steps Failed: {len(result.steps_failed)}")
            for step in result.steps_failed:
                print(f"  - {step}")
        print(f"Behaviors Discovered: {result.behaviors_discovered}")
        print(f"Behaviors Updated: {result.behaviors_updated}")
        print(f"Execution Time: {result.execution_time_seconds:.2f}s")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Test 6: New Tests trigger
    print("\n\nTest 6: New Tests Trigger")
    print("-" * 60)
    try:
        result = pipeline.trigger_on_new_tests(repository)
        print(f"Success: {result.success}")
        print(f"Trigger: {result.trigger.value}")
        print(f"Steps Completed: {len(result.steps_completed)}")
        for step in result.steps_completed:
            print(f"  - {step}")
        if result.steps_failed:
            print(f"Steps Failed: {len(result.steps_failed)}")
            for step in result.steps_failed:
                print(f"  - {step}")
        print(f"Behaviors Discovered: {result.behaviors_discovered}")
        print(f"Behaviors Updated: {result.behaviors_updated}")
        print(f"Execution Time: {result.execution_time_seconds:.2f}s")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Test result serialization
    print("\n\nTest: Result Serialization")
    print("-" * 60)
    try:
        result = pipeline.trigger_on_repository_sync(repository)
        result_dict = result.to_dict()
        print(f"Serialized result keys: {list(result_dict.keys())}")
        print(f"Trigger value: {result_dict['trigger']}")
        print(f"Repository ID: {result_dict['repository_id']}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Test pipeline flow verification
    print("\n\nPipeline Flow Verification:")
    print("-" * 60)
    print("Expected Flow:")
    print("1. Semantic Index Refresh")
    print("2. Pattern Matching (Evidence Collection)")
    print("3. Evidence Aggregation")
    print("4. Confidence Calculation")
    print("5. Relationship Discovery")
    print("6. Behavior Merge")
    print("7. Catalog Update")
    
    print("\nActual Flow (from last execution):")
    if result.steps_completed:
        for i, step in enumerate(result.steps_completed, 1):
            print(f"{i}. {step}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_pipeline()
