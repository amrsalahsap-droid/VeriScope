"""
Verification script for Behavior Discovery v2.

Tests the complete behavior discovery pipeline with intelligence analyzers,
evidence aggregation, confidence calculation, and relationship discovery.
"""

import sys
import os
import tempfile
import shutil
from datetime import datetime
from typing import List, Dict, Any

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.db.session import SessionLocal
from app.services.route_intelligence_analyzer import RouteIntelligenceAnalyzer
from app.services.test_intelligence_analyzer import TestIntelligenceAnalyzer
from app.services.module_intelligence_analyzer import ModuleIntelligenceAnalyzer
from app.services.documentation_intelligence_analyzer import DocumentationIntelligenceAnalyzer
from app.services.behavior_evidence_aggregator import BehaviorEvidenceAggregator
from app.services.behavior_confidence_engine import BehaviorConfidenceEngine
from app.services.behavior_relationship_engine import BehaviorRelationshipEngine
from app.services.behavior_catalog_builder import BehaviorCatalogBuilder


class BehaviorDiscoveryV2Verifier:
    """Verifier for behavior discovery v2."""
    
    def __init__(self):
        self.db = SessionLocal()
        self.test_results = []
        self.repository = None
        self.temp_dir = None
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log a test result."""
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "message": message,
        })
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
        if message:
            print(f"     {message}")
    
    def setup_repository(self) -> None:
        """Create a test repository with artifacts (in-memory only)."""
        print("\n=== Setting up test repository ===")
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp(prefix="veriscope_test_")
        print(f"Created temp directory: {self.temp_dir}")
        
        # Create directory structure
        directories = [
            "auth",
            "reset-password",
            "signup",
            "subscriptions",
            "notifications",
            "services/auth",
            "services/billing",
            "services/notifications",
            "tests",
        ]
        
        for directory in directories:
            dir_path = os.path.join(self.temp_dir, directory)
            os.makedirs(dir_path, exist_ok=True)
            print(f"Created directory: {directory}")
        
        # Create route files
        routes = {
            "auth/api.py": """
from fastapi import APIRouter

router = APIRouter()

@router.post("/login")
async def login():
    return {"message": "Login successful"}

@router.post("/logout")
async def logout():
    return {"message": "Logout successful"}
""",
            "reset-password/api.py": """
from fastapi import APIRouter

router = APIRouter()

@router.post("/reset-password")
async def reset_password():
    return {"message": "Password reset email sent"}
""",
            "signup/api.py": """
from fastapi import APIRouter

router = APIRouter()

@router.post("/register")
async def register():
    return {"message": "Registration successful"}
""",
            "subscriptions/api.py": """
from fastapi import APIRouter

router = APIRouter()

@router.post("/subscription")
async def create_subscription():
    return {"message": "Subscription created"}

@router.get("/subscription")
async def get_subscription():
    return {"message": "Subscription details"}
""",
            "notifications/api.py": """
from fastapi import APIRouter

router = APIRouter()

@router.post("/notification")
async def send_notification():
    return {"message": "Notification sent"}
""",
        }
        
        for file_path, content in routes.items():
            full_path = os.path.join(self.temp_dir, file_path)
            with open(full_path, 'w') as f:
                f.write(content)
            print(f"Created route file: {file_path}")
        
        # Create test files
        test_content = """
import pytest

def should_reject_expired_token():
    assert True

def should_allow_valid_token():
    assert True

def should_create_subscription():
    assert True

def test_password_reset_flow():
    assert True

def test_user_registration():
    assert True

def test_send_notification():
    assert True
"""
        
        test_path = os.path.join(self.temp_dir, "tests/test_auth.py")
        with open(test_path, 'w') as f:
            f.write(test_content)
        print(f"Created test file: tests/test_auth.py")
        
        # Create README
        readme_content = """
# Test Application

Users can register, login, reset passwords, and manage subscriptions.

## Features

- User registration and authentication
- Password reset functionality
- Subscription management
- Email notifications
"""
        
        readme_path = os.path.join(self.temp_dir, "README.md")
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        print(f"Created README.md")
    
    def run_discovery(self) -> None:
        """Run the behavior discovery pipeline."""
        print("\n=== Running behavior discovery ===")
        
        # Initialize analyzers
        route_analyzer = RouteIntelligenceAnalyzer(self.db)
        test_analyzer = TestIntelligenceAnalyzer(self.db)
        module_analyzer = ModuleIntelligenceAnalyzer(self.db)
        doc_analyzer = DocumentationIntelligenceAnalyzer(self.db)
        
        # Collect route evidence
        routes = [
            "/login",
            "/logout",
            "/reset-password",
            "/register",
            "/subscription",
            "/notification",
        ]
        route_evidences = route_analyzer.analyze_routes(routes)
        print(f"Route evidences: {len(route_evidences)}")
        
        # Collect test evidence
        tests = [
            "should_reject_expired_token",
            "should_allow_valid_token",
            "should_create_subscription",
            "test_password_reset_flow",
            "test_user_registration",
            "test_send_notification",
        ]
        test_evidences = test_analyzer.analyze_tests(tests)
        print(f"Test evidences: {len(test_evidences)}")
        
        # Collect module evidence
        modules = [
            "auth/",
            "reset-password/",
            "signup/",
            "subscriptions/",
            "notifications/",
            "services/auth/",
            "services/billing/",
            "services/notifications/",
        ]
        module_evidences = module_analyzer.analyze_modules(modules)
        print(f"Module evidences: {len(module_evidences)}")
        
        # Collect documentation evidence
        readme_path = os.path.join(self.temp_dir, "README.md")
        with open(readme_path, 'r') as f:
            readme_content = f.read()
        doc_evidences = doc_analyzer.analyze_document("README.md", readme_content, "README")
        print(f"Documentation evidences: {len(doc_evidences)}")
        
        # Aggregate evidence
        aggregator = BehaviorEvidenceAggregator(self.db)
        candidates = aggregator.aggregate_evidence(
            route_evidences=route_evidences,
            test_evidences=test_evidences,
            module_evidences=module_evidences,
            documentation_evidences=doc_evidences,
        )
        print(f"Aggregated candidates: {len(candidates)}")
        
        # Calculate confidence
        confidence_engine = BehaviorConfidenceEngine(self.db)
        for candidate in candidates:
            breakdown = confidence_engine.calculate_confidence(
                candidate.evidences,
                repository_total_files=20,
                repository_behavior_files=len(candidate.evidences),
            )
            candidate.confidence_breakdown = breakdown
        print(f"Confidence calculated for {len(candidates)} candidates")
        
        # Discover relationships
        relationship_engine = BehaviorRelationshipEngine(self.db)
        behavior_names = [c.name for c in candidates]
        relationships = relationship_engine.discover_relationships(behavior_names)
        print(f"Relationships discovered: {len(relationships)}")
        
        # Store for verification
        self.candidates = candidates
        self.relationships = relationships
        self.route_evidences = route_evidences
        self.test_evidences = test_evidences
        self.module_evidences = module_evidences
        self.doc_evidences = doc_evidences
    
    def verify_requirements(self) -> None:
        """Verify all 12 requirements."""
        print("\n=== Verifying requirements ===")
        
        behavior_names = [c.name for c in self.candidates]
        
        # 1. Authentication discovered
        auth_discovered = "Authentication" in behavior_names
        self.log_test(
            "1. Authentication discovered",
            auth_discovered,
            f"Found behaviors: {behavior_names}"
        )
        
        # 2. Password Reset discovered
        password_reset_discovered = "Password Reset" in behavior_names
        self.log_test(
            "2. Password Reset discovered",
            password_reset_discovered,
            f"Found behaviors: {behavior_names}"
        )
        
        # 3. Registration discovered
        registration_discovered = "User Registration" in behavior_names
        self.log_test(
            "3. Registration discovered",
            registration_discovered,
            f"Found behaviors: {behavior_names}"
        )
        
        # 4. Subscription Management discovered
        subscription_discovered = "Billing" in behavior_names
        self.log_test(
            "4. Subscription Management discovered",
            subscription_discovered,
            f"Found behaviors: {behavior_names}"
        )
        
        # 5. Notifications discovered
        notifications_discovered = "Notifications" in behavior_names
        self.log_test(
            "5. Notifications discovered",
            notifications_discovered,
            f"Found behaviors: {behavior_names}"
        )
        
        # 6. Evidence generated from routes
        route_evidence_generated = len(self.route_evidences) > 0
        self.log_test(
            "6. Evidence generated from routes",
            route_evidence_generated,
            f"Route evidences: {len(self.route_evidences)}"
        )
        
        # 7. Evidence generated from tests
        test_evidence_generated = len(self.test_evidences) > 0
        self.log_test(
            "7. Evidence generated from tests",
            test_evidence_generated,
            f"Test evidences: {len(self.test_evidences)}"
        )
        
        # 8. Evidence generated from modules
        module_evidence_generated = len(self.module_evidences) > 0
        self.log_test(
            "8. Evidence generated from modules",
            module_evidence_generated,
            f"Module evidences: {len(self.module_evidences)}"
        )
        
        # 9. Evidence generated from documentation
        doc_evidence_generated = len(self.doc_evidences) > 0
        self.log_test(
            "9. Evidence generated from documentation",
            doc_evidence_generated,
            f"Documentation evidences: {len(self.doc_evidences)}"
        )
        
        # 10. Confidence calculated
        confidence_calculated = all(
            hasattr(c, 'confidence_breakdown') and c.confidence_breakdown is not None
            for c in self.candidates
        )
        self.log_test(
            "10. Confidence calculated",
            confidence_calculated,
            f"Candidates with confidence: {sum(1 for c in self.candidates if hasattr(c, 'confidence_breakdown'))}/{len(self.candidates)}"
        )
        
        # 11. Duplicate behaviors merged
        # Check that behaviors with same name are merged
        behavior_counts = {}
        for c in self.candidates:
            if c.name not in behavior_counts:
                behavior_counts[c.name] = 0
            behavior_counts[c.name] += 1
        
        duplicates_merged = all(count == 1 for count in behavior_counts.values())
        self.log_test(
            "11. Duplicate behaviors merged",
            duplicates_merged,
            f"Behavior counts: {behavior_counts}"
        )
        
        # 12. Relationships created
        relationships_created = len(self.relationships) > 0
        self.log_test(
            "12. Relationships created",
            relationships_created,
            f"Relationships: {len(self.relationships)}"
        )
    
    def print_summary(self) -> None:
        """Print verification summary."""
        print("\n=== Verification Summary ===")
        
        passed = sum(1 for r in self.test_results if r["passed"])
        total = len(self.test_results)
        
        print(f"\nTests Passed: {passed}/{total}")
        
        if passed == total:
            print("\n[SUCCESS] All verification tests passed!")
            print("Behavior discovery produces a stable, explainable behavior catalog.")
        else:
            print("\n[FAILURE] Some verification tests failed.")
            print("Behavior discovery needs improvement.")
        
        print("\nDetailed Results:")
        for result in self.test_results:
            status = "[PASS]" if result["passed"] else "[FAIL]"
            print(f"{status} {result['test']}")
            if result["message"]:
                print(f"     {result['message']}")
    
    def cleanup(self) -> None:
        """Clean up test resources."""
        print("\n=== Cleaning up ===")
        
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"Deleted temp directory: {self.temp_dir}")
        
        self.db.close()
    
    def run(self) -> bool:
        """Run the complete verification."""
        try:
            self.setup_repository()
            self.run_discovery()
            self.verify_requirements()
            self.print_summary()
            
            passed = sum(1 for r in self.test_results if r["passed"])
            total = len(self.test_results)
            
            return passed == total
        finally:
            self.cleanup()


def main():
    """Main entry point."""
    print("=" * 60)
    print("BEHAVIOR DISCOVERY V2 VERIFICATION")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    verifier = BehaviorDiscoveryV2Verifier()
    success = verifier.run()
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
