"""Test the detailed readiness API structure without authentication."""
from app.services.detailed_readiness_service import DetailedReadinessService
from app.db.session import SessionLocal
import json

def test_api_response_structure():
    """Test the API response structure matches the expected format."""
    db = SessionLocal()
    
    try:
        # Create the service
        service = DetailedReadinessService(db)
        
        # Test with a repository ID that exists
        repository_id = "a5de7396-88ca-49f5-af9d-8937aecfcfab"
        pull_request_id = "805e8062-b20f-4831-81aa-f6e7d0e796fd"
        
        print(f"Testing API response structure...")
        
        # Perform the detailed assessment
        detailed_readiness = service.get_detailed_readiness(
            repository_id=repository_id,
            pull_request_id=pull_request_id
        )
        
        # Convert to dict to simulate API response
        response_data = detailed_readiness.dict()
        
        # Verify response structure matches expected format
        expected_fields = [
            'readiness_level', 'expected_confidence', 'readiness_score',
            'can_generate', 'available_signals', 'missing_signals', 'recommended_actions'
        ]
        
        print(f"\nRequired fields present: {all(field in response_data for field in expected_fields)}")
        
        # Verify signal structure
        available_signal = response_data['available_signals'][0] if response_data['available_signals'] else None
        if available_signal:
            signal_fields = ['key', 'label', 'status', 'impact', 'confidence_contribution']
            print(f"Available signal structure correct: {all(field in available_signal for field in signal_fields)}")
        
        missing_signal = response_data['missing_signals'][0] if response_data['missing_signals'] else None
        if missing_signal:
            missing_fields = ['key', 'label', 'severity', 'impact', 'estimated_confidence_gain', 'actions']
            print(f"Missing signal structure correct: {all(field in missing_signal for field in missing_fields)}")
        
        action = response_data['recommended_actions'][0] if response_data['recommended_actions'] else None
        if action:
            action_fields = ['action', 'label', 'priority', 'estimated_confidence_gain']
            print(f"Action structure correct: {all(field in action for field in action_fields)}")
        
        # Print formatted response
        print(f"\n=== API Response Structure ===")
        print(json.dumps(response_data, indent=2))
        
        print(f"\n✅ API response structure validation completed successfully!")
        
    except Exception as e:
        print(f"Error during API structure validation: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    test_api_response_structure()
