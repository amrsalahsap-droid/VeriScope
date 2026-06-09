"""Verify recommendation readiness and completeness scoring fixes."""
import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.readiness import RecommendationReadinessAssessment
from app.services.recommendation_readiness_service import RecommendationReadinessService

db = SessionLocal()
try:
    # Find any repository that is selected for analysis
    repo = db.query(Repository).filter(Repository.selected_for_analysis == True).first()
    if not repo:
        repo = db.query(Repository).first()
        
    if not repo:
        print("No repository found in database!")
        sys.exit(1)
        
    print(f"Testing with Repository: {repo.full_name} ({repo.id})")
    
    # Run readiness assessment
    svc = RecommendationReadinessService(db)
    assessment = svc.assess_readiness(repository_id=repo.id)
    
    print(f"Readiness Level: {assessment.readiness_level}")
    print(f"Expected Confidence: {assessment.expected_confidence}")
    print(f"Readiness Score: {assessment.readiness_score}")
    print(f"Intelligence Completeness Score: {assessment.intelligence_completeness_score}")
    
    # Assert intelligence_completeness_score is equal to readiness_score
    # since it shouldn't be multiplied by 100
    expected_score = int(assessment.readiness_score)
    actual_score = assessment.intelligence_completeness_score
    print(f"Expected: {expected_score}, Actual: {actual_score}")
    assert actual_score == expected_score, f"Completeness score mismatch! Expected {expected_score}, got {actual_score}"
    print("SUCCESS: Completeness score is correctly formatted!")

finally:
    db.close()
