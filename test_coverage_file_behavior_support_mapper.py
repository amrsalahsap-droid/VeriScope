"""
Test script for CoverageFileBehaviorSupportMapper.

Tests mapping code coverage report metrics to behaviors and scenario support.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.coverage_file_behavior_support_mapper import CoverageFileBehaviorSupportMapper
import uuid


def test_coverage_file_behavior_support_mapper():
    """Verify code coverage maps accurately as supportive confidence evidence."""
    print("=" * 60)
    print("COVERAGE FILE BEHAVIOR SUPPORT MAPPER TEST")
    print("=" * 60)
    
    mapper = CoverageFileBehaviorSupportMapper(db=None)
    
    # 1. Setup test values
    b_id = str(uuid.uuid4())
    behavior_evidences = [
        {"behavior_id": b_id, "source_path": "auth/reset-password/api.py"},
    ]
    
    behavior_impact_items = [
        {"behavior_id": b_id, "behavior_name": "Password Reset", "behavior_scenario_id": str(uuid.uuid4())},
    ]
    
    # Test Case 1: Direct File Match (Score/Coverage HIGH)
    print("\nTest 1: Direct File Match (High Coverage)")
    print("-" * 60)
    
    coverage_file_entries = [
        {"file_path": "auth/reset-password/api.py", "line_coverage_ratio": 0.90},
    ]
    
    records1 = mapper.map_coverage_support(
        coverage_file_entries=coverage_file_entries,
        behavior_evidences=behavior_evidences,
        behavior_impact_items=behavior_impact_items,
    )
    
    assert len(records1) == 1
    rec1 = records1[0]
    print(f"  File: {rec1['coverage_file_path']}")
    print(f"  Support Type: {rec1['support_type']} (expected DIRECT_FILE)")
    print(f"  Confidence: {rec1['confidence']} (expected HIGH)")
    print(f"  Reason: {rec1['reason']}")
    assert rec1["support_type"] == "DIRECT_FILE"
    assert rec1["confidence"] == "HIGH"
    
    # Test Case 2: Related Module Match
    print("\n\nTest 2: Related Module Match")
    print("-" * 60)
    
    coverage_file_entries_module = [
        {"file_path": "src/services/password-validator.ts", "line_coverage_ratio": 0.65},
    ]
    
    records2 = mapper.map_coverage_support(
        coverage_file_entries=coverage_file_entries_module,
        behavior_evidences=behavior_evidences,
        behavior_impact_items=behavior_impact_items,
    )
    
    assert len(records2) == 1
    rec2 = records2[0]
    print(f"  File: {rec2['coverage_file_path']}")
    print(f"  Support Type: {rec2['support_type']} (expected RELATED_MODULE)")
    print(f"  Confidence: {rec2['confidence']} (expected MODERATE)")
    print(f"  Reason: {rec2['reason']}")
    assert rec2["support_type"] == "RELATED_MODULE"
    assert rec2["confidence"] == "MODERATE"
    
    # Test Case 3: Unrelated File Match (Must NOT produce mappings)
    print("\n\nTest 3: Unrelated File Match")
    print("-" * 60)
    
    coverage_file_entries_unrelated = [
        {"file_path": "billing/subscription/service.py", "line_coverage_ratio": 0.85},
    ]
    
    records3 = mapper.map_coverage_support(
        coverage_file_entries=coverage_file_entries_unrelated,
        behavior_evidences=behavior_evidences,
        behavior_impact_items=behavior_impact_items,
    )
    
    print(f"  Unrelated file produced {len(records3)} support records.")
    assert len(records3) == 0, "Expected unrelated files to be rejected from matching"
    print("[PASS] Unrelated files successfully filtered")
    
    # Test Case 4: Branch/Commit Mismatch Penalty
    print("\n\nTest 4: Branch/Commit Mismatch Penalty")
    print("-" * 60)
    
    records4 = mapper.map_coverage_support(
        coverage_file_entries=coverage_file, # Reuse direct match
        behavior_evidences=behavior_evidences,
        behavior_impact_items=behavior_impact_items,
        commit_mismatch=True,
    )
    
    assert len(records4) == 1
    rec4 = records4[0]
    print(f"  Support Type: {rec4['support_type']} (expected DIRECT_FILE)")
    print(f"  Confidence: {rec4['confidence']} (expected LOW due to mismatch)")
    print(f"  Reason: {rec4['reason']}")
    assert rec4["support_type"] == "DIRECT_FILE"
    assert rec4["confidence"] == "LOW"
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    # Minor adjustment: define coverage_file list before reuse in Test 4
    coverage_file = [{"file_path": "auth/reset-password/api.py", "line_coverage_ratio": 0.90}]
    test_coverage_file_behavior_support_mapper()
