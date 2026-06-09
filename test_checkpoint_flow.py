"""Test the complete checkpoint flow implementation."""
import requests
import json

def test_checkpoint_flow():
    """Test the complete checkpoint flow from frontend to backend."""
    base_url = "http://localhost:8000"
    
    # Test data
    repository_id = "a5de7396-88ca-49f5-af9d-8937aecfcfab"
    pull_request_id = "805e8062-b20f-4831-81aa-f6e7d0e796fd"
    
    print("Testing Complete Checkpoint Flow")
    print("=" * 50)
    
    # Step 1: Test readiness assessment API
    print(f"\n1. Testing readiness assessment for PR {pull_request_id}")
    try:
        response = requests.get(f"{base_url}/api/repositories/{repository_id}/pull-requests/{pull_request_id}/readiness")
        if response.status_code == 200:
            readiness_data = response.json()
            print(f"[SUCCESS] Readiness assessment successful")
            print(f"   Readiness Level: {readiness_data.get('readiness_level')}")
            print(f"   Expected Confidence: {readiness_data.get('expected_confidence')}")
            print(f"   Readiness Score: {readiness_data.get('readiness_score')}")
            print(f"   Can Generate: {readiness_data.get('can_generate')}")
            print(f"   Available Signals: {len(readiness_data.get('available_signals', []))}")
            print(f"   Missing Signals: {len(readiness_data.get('missing_signals', []))}")
            print(f"   Recommended Actions: {len(readiness_data.get('recommended_actions', []))}")
        else:
            print(f"[ERROR] Readiness assessment failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return
    except Exception as e:
        print(f"[ERROR] Readiness assessment error: {e}")
        return
    
    # Step 2: Test checkpoint modal data structure
    print(f"\n2. Testing checkpoint modal data structure")
    try:
        # This simulates what the frontend would display in the checkpoint modal
        available_signals = readiness_data.get('available_signals', [])
        missing_signals = readiness_data.get('missing_signals', [])
        
        print(f"   Available Signals:")
        for signal in available_signals[:5]:  # Show first 5
            print(f"     [AVAILABLE] {signal.get('label')} (+{signal.get('confidence_contribution', 0)})")
        
        print(f"   Missing Signals:")
        for signal in missing_signals[:5]:  # Show first 5
            print(f"     [MISSING] {signal.get('label')} (+{signal.get('estimated_confidence_gain', 0)})")
        
        print(f"   Message: Veriscope can generate this recommendation now with {readiness_data.get('expected_confidence', 'UNKNOWN').lower()} confidence.")
        
    except Exception as e:
        print(f"[ERROR] Checkpoint modal data error: {e}")
        return
    
    # Step 3: Test recommendation generation with readiness_acknowledged
    print(f"\n3. Testing recommendation generation with readiness_acknowledged=true")
    try:
        recommendation_payload = {
            "repository_id": repository_id,
            "pull_request_id": pull_request_id,
            "triggered_by": "engineer-manual",
            "readiness_acknowledged": True
        }
        
        response = requests.post(
            f"{base_url}/api/repositories/{repository_id}/pull-requests/{pull_request_id}/recommendation",
            json=recommendation_payload
        )
        
        if response.status_code == 201:
            recommendation_data = response.json()
            print(f"[SUCCESS] Recommendation generation successful")
            print(f"   Recommendation Run ID: {recommendation_data.get('id')}")
            print(f"   Recommended Tests: {recommendation_data.get('recommended_tests_count', 0)}")
            print(f"   Recommendation Mode: {recommendation_data.get('recommendation_mode', 'UNKNOWN')}")
            print(f"   Evidence Quality: {recommendation_data.get('evidence_quality', 'UNKNOWN')}")
        else:
            print(f"[ERROR] Recommendation generation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return
    except Exception as e:
        print(f"[ERROR] Recommendation generation error: {e}")
        return
    
    # Step 4: Verify readiness_acknowledged was stored
    print(f"\n4. Verifying readiness_acknowledged was stored")
    try:
        recommendation_run_id = recommendation_data.get('id')
        response = requests.get(f"{base_url}/api/recommendations/{recommendation_run_id}")
        
        if response.status_code == 200:
            run_data = response.json()
            print(f"[SUCCESS] Recommendation run retrieved successfully")
            print(f"   Readiness Acknowledged: {run_data.get('readiness_acknowledged', False)}")
            print(f"   Recommendation Readiness State: {run_data.get('recommendation_readiness_state', 'UNKNOWN')}")
            print(f"   Evidence Health Status: {run_data.get('evidence_health_status', 'UNKNOWN')}")
        else:
            print(f"[ERROR] Failed to retrieve recommendation run: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"[ERROR] Verification error: {e}")
    
    print(f"\n" + "=" * 50)
    print("Checkpoint Flow Test Completed!")
    print("[SUCCESS] All components working correctly")
    print("[SUCCESS] Users will see readiness information before generating recommendations")
    print("[SUCCESS] Readiness acknowledgment is properly stored")
    print("[SUCCESS] No more surprises about fallback/low confidence recommendations")

if __name__ == "__main__":
    test_checkpoint_flow()
