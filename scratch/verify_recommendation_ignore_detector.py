import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.recommendation_ignore_detector import RecommendationIgnoreDetector

def test_empty_recommendation():
    print("--- Testing Empty Recommendation (N=0) ---")
    res = RecommendationIgnoreDetector.detect([], ["test_a", "test_b"])
    assert res["is_presented"] is False
    assert res["total_recommended"] == 0
    assert res["overlap_ratio"] == 0.0
    assert res["status"] == "NOT_APPLICABLE"
    assert res["is_tiny"] is False
    print("[PASSED] Empty recommendation mapped successfully.\n")

def test_large_suites():
    print("--- Testing Large Suites (N >= 5) ---")
    rec = ["t1", "t2", "t3", "t4", "t5"]
    
    # 1. 100% overlap
    res1 = RecommendationIgnoreDetector.detect(rec, rec)
    assert res1["status"] == "FULLY_FOLLOWED"
    assert res1["overlap_ratio"] == 1.0
    assert res1["adjusted_overlap_ratio"] == 1.0
    assert res1["is_tiny"] is False
    
    # 2. 80% overlap
    res2 = RecommendationIgnoreDetector.detect(rec, ["t1", "t2", "t3", "t4"])
    assert res2["status"] == "PARTIALLY_FOLLOWED"
    assert res2["overlap_ratio"] == 0.8
    assert res2["adjusted_overlap_ratio"] == 0.8
    
    # 3. 40% overlap
    res3 = RecommendationIgnoreDetector.detect(rec, ["t1", "t2"])
    assert res3["status"] == "PARTIALLY_FOLLOWED"
    assert res3["overlap_ratio"] == 0.4
    assert res3["adjusted_overlap_ratio"] == 0.4
    
    # 4. 20% overlap
    res4 = RecommendationIgnoreDetector.detect(rec, ["t1"])
    assert res4["status"] == "IGNORED"
    assert res4["overlap_ratio"] == 0.2
    assert res4["adjusted_overlap_ratio"] == 0.2
    
    # 5. 0% overlap
    res5 = RecommendationIgnoreDetector.detect(rec, [])
    assert res5["status"] == "IGNORED"
    assert res5["overlap_ratio"] == 0.0
    assert res5["adjusted_overlap_ratio"] == 0.0
    
    print("[PASSED] Large suites mapped successfully.\n")

def test_tiny_suites():
    print("--- Testing Tiny Suites (N < 5) - Conservative Prevention ---")
    
    # 1. N=3, X=1 (Raw 33.33% but statistically adjusted above 40%)
    res1 = RecommendationIgnoreDetector.detect(["t1", "t2", "t3"], ["t1"])
    assert res1["is_tiny"] is True
    assert res1["overlap_ratio"] == 0.333333
    # Check that it gets adjusted above 40% (upper Wilson bound)
    assert res1["adjusted_overlap_ratio"] >= 0.40
    # Assert it was saved from being classified as IGNORED!
    assert res1["status"] == "PARTIALLY_FOLLOWED"
    print("  [OK] N=3, X=1 avoided False Positive Ignored status!")
    
    # 2. N=3, X=0 (Zero overlap must be IGNORED)
    res2 = RecommendationIgnoreDetector.detect(["t1", "t2", "t3"], ["other"])
    assert res2["overlap_ratio"] == 0.0
    assert res2["adjusted_overlap_ratio"] == 0.0
    assert res2["status"] == "IGNORED"
    
    # 3. N=1, X=0 (Zero overlap must be IGNORED)
    res3 = RecommendationIgnoreDetector.detect(["t1"], [])
    assert res3["status"] == "IGNORED"
    
    # 4. N=1, X=1 (100% overlap)
    res4 = RecommendationIgnoreDetector.detect(["t1"], ["t1"])
    assert res4["status"] == "FULLY_FOLLOWED"
    
    # 5. N=4, X=1 (Raw 25% but adjusted above 40%)
    res5 = RecommendationIgnoreDetector.detect(["t1", "t2", "t3", "t4"], ["t1"])
    assert res5["overlap_ratio"] == 0.25
    assert res5["adjusted_overlap_ratio"] >= 0.40
    assert res5["status"] == "PARTIALLY_FOLLOWED"
    
    print("[PASSED] Tiny suites conservative handling mapped successfully.\n")

def main():
    print("======================================================================")
    print("STARTING RECOMMENDATION IGNORE DETECTOR SERVICE VERIFICATION")
    print("======================================================================\n")

    test_empty_recommendation()
    test_large_suites()
    test_tiny_suites()

    print("ALL RECOMMENDATION IGNORE DETECTOR VERIFICATION CHECKS PASSED SUCCESSFULLY!\n")

if __name__ == "__main__":
    main()
