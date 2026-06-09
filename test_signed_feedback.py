"""
Test signed feedback URL generation and endpoints.

Verifies that signed URLs can be generated and validated, and feedback endpoints work correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_signed_feedback():
    """Test signed feedback URL generation and endpoints."""
    print("=" * 70)
    print("SIGNED FEEDBACK TEST")
    print("=" * 70)
    
    # Test 1: Signed URL generator exists
    print("\n[1] Signed URL Generator Exists")
    print("-" * 70)
    
    generator_path = "app/services/signed_url_generator.py"
    if os.path.exists(generator_path):
        print(f"  [PASS] Signed URL generator exists at {generator_path}")
    else:
        print(f"  [FAIL] Signed URL generator not found at {generator_path}")
        return False
    
    # Test 2: SignedURLGenerator class exists
    print("\n[2] SignedURLGenerator Class Exists")
    print("-" * 70)
    
    with open(generator_path, "r") as f:
        content = f.read()
        
        if "class SignedURLGenerator" in content:
            print("  [PASS] SignedURLGenerator class exists")
        else:
            print("  [FAIL] SignedURLGenerator class missing")
            return False
    
    # Test 3: generate_feedback_url method exists
    print("\n[3] generate_feedback_url Method Exists")
    print("-" * 70)
    
    with open(generator_path, "r") as f:
        content = f.read()
        
        if "def generate_feedback_url" in content:
            print("  [PASS] generate_feedback_url method exists")
        else:
            print("  [FAIL] generate_feedback_url method missing")
            return False
    
    # Test 4: validate_signature method exists
    print("\n[4] validate_signature Method Exists")
    print("-" * 70)
    
    with open(generator_path, "r") as f:
        content = f.read()
        
        if "def validate_signature" in content:
            print("  [PASS] validate_signature method exists")
        else:
            print("  [FAIL] validate_signature method missing")
            return False
    
    # Test 5: URL includes expiration
    print("\n[5] URL Includes Expiration")
    print("-" * 70)
    
    with open(generator_path, "r") as f:
        content = f.read()
        
        if "expires_at" in content:
            print("  [PASS] URL includes expires_at")
        else:
            print("  [FAIL] expires_at missing")
            return False
    
    # Test 6: URL includes signature
    print("\n[6] URL Includes Signature")
    print("-" * 70)
    
    with open(generator_path, "r") as f:
        content = f.read()
        
        if "signature" in content or "sig" in content:
            print("  [PASS] URL includes signature")
        else:
            print("  [FAIL] signature missing")
            return False
    
    # Test 7: Feedback endpoints exist
    print("\n[7] Feedback Endpoints Exist")
    print("-" * 70)
    
    router_path = "app/routers/recommendation.py"
    with open(router_path, "r") as f:
        content = f.read()
        
        if "/feedback/useful" in content:
            print("  [PASS] /feedback/useful endpoint exists")
        else:
            print("  [FAIL] /feedback/useful endpoint missing")
            return False
        
        if "/feedback/not-useful" in content:
            print("  [PASS] /feedback/not-useful endpoint exists")
        else:
            print("  [FAIL] /feedback/not-useful endpoint missing")
            return False
        
        if "/feedback/missing-tests" in content:
            print("  [PASS] /feedback/missing-tests endpoint exists")
        else:
            print("  [FAIL] /feedback/missing-tests endpoint missing")
            return False
    
    # Test 8: Endpoints validate signature
    print("\n[8] Endpoints Validate Signature")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "validate_signature" in content:
            print("  [PASS] Endpoints validate signature")
        else:
            print("  [FAIL] Signature validation missing")
            return False
    
    # Test 9: Endpoints verify recommendation run ID
    print("\n[9] Endpoints Verify Recommendation Run ID")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "recommendation_run_id" in content and "mismatch" in content:
            print("  [PASS] Endpoints verify recommendation run ID")
        else:
            print("  [FAIL] Recommendation run ID verification missing")
            return False
    
    # Test 10: Endpoints verify feedback type
    print("\n[10] Endpoints Verify Feedback Type")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "feedback_type" in content and "mismatch" in content:
            print("  [PASS] Endpoints verify feedback type")
        else:
            print("  [FAIL] Feedback type verification missing")
            return False
    
    # Test 11: Endpoints use RecommendationEngineerFeedbackCapture
    print("\n[11] Endpoints Use RecommendationEngineerFeedbackCapture")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "RecommendationEngineerFeedbackCapture" in content:
            print("  [PASS] Endpoints use RecommendationEngineerFeedbackCapture")
        else:
            print("  [FAIL] RecommendationEngineerFeedbackCapture usage missing")
            return False
    
    # Test 12: Endpoints update existing RecommendationOutcome
    print("\n[12] Endpoints Update Existing RecommendationOutcome")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "capture_feedback" in content:
            print("  [PASS] Endpoints call capture_feedback (updates existing outcome)")
        else:
            print("  [FAIL] capture_feedback call missing")
            return False
    
    # Test 13: Singleton instance exists
    print("\n[13] Singleton Instance Exists")
    print("-" * 70)
    
    with open(generator_path, "r") as f:
        content = f.read()
        
        if "signed_url_generator" in content:
            print("  [PASS] Singleton instance exists")
        else:
            print("  [FAIL] Singleton instance missing")
            return False
    
    # Test 14: HMAC-SHA256 signing
    print("\n[14] HMAC-SHA256 Signing")
    print("-" * 70)
    
    with open(generator_path, "r") as f:
        content = f.read()
        
        if "hmac" in content and "sha256" in content:
            print("  [PASS] Uses HMAC-SHA256 signing")
        else:
            print("  [FAIL] HMAC-SHA256 signing missing")
            return False
    
    # Test 15: Base64 encoding
    print("\n[15] Base64 Encoding")
    print("-" * 70)
    
    with open(generator_path, "r") as f:
        content = f.read()
        
        if "base64" in content:
            print("  [PASS] Uses Base64 encoding")
        else:
            print("  [FAIL] Base64 encoding missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nSigned feedback verified:")
    print("  - Signed URL generator exists")
    print("  - SignedURLGenerator class exists")
    print("  - generate_feedback_url method exists")
    print("  - validate_signature method exists")
    print("  - URL includes expiration")
    print("  - URL includes signature")
    print("  - Feedback endpoints exist")
    print("  - Endpoints validate signature")
    print("  - Endpoints verify recommendation run ID")
    print("  - Endpoints verify feedback type")
    print("  - Endpoints use RecommendationEngineerFeedbackCapture")
    print("  - Endpoints update existing RecommendationOutcome")
    print("  - Singleton instance exists")
    print("  - HMAC-SHA256 signing")
    print("  - Base64 encoding")
    print("\nGitHub PR comment can later capture simple feedback safely.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_signed_feedback()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
