"""
Test script for Behavior Diagnostics Service and API.

Tests diagnostics generation and display.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_diagnostics_service import BehaviorDiagnosticsService
from app.schemas.behavior_diagnostics import (
    BehaviorDiagnosticsSummary,
    BehaviorDiagnosticsDetail,
    BehaviorDiagnosticsResponse,
)
from dataclasses import dataclass
from typing import Optional
import uuid


# Mock database session for testing
class MockQuery:
    def __init__(self, data=None):
        self.data = data or []
        self.filters = []
    
    def filter(self, *args):
        self.filters.append(args)
        return self
    
    def join(self, model):
        return self
    
    def order_by(self, *args):
        return self
    
    def count(self):
        return len(self.data)
    
    def first(self):
        return self.data[0] if self.data else None
    
    def all(self):
        return self.data


class MockDB:
    def query(self, model):
        # Return mock data based on model type
        if "Repository" in str(model):
            return MockQuery([MockRepository()])
        elif "Behavior" in str(model):
            return MockQuery([
                MockBehavior("Authentication", "HIGH"),
                MockBehavior("Billing", "MODERATE"),
                MockBehavior("Password Reset", "HIGH"),
                MockBehavior("User Registration", "LOW"),
            ])
        elif "BehaviorEvidence" in str(model):
            return MockQuery([
                MockEvidence("ROUTE"),
                MockEvidence("TEST"),
                MockEvidence("MODULE"),
            ])
        elif "RepositorySemanticEntry" in str(model):
            return MockQuery([MockSemanticEntry()])
        return MockQuery()
    
    def commit(self):
        pass


@dataclass
class MockRepository:
    id: str = str(uuid.uuid4())
    name: str = "test-repo"


@dataclass
class MockBehavior:
    id: str = str(uuid.uuid4())
    repository_id: str = str(uuid.uuid4())
    name: str = "Test Behavior"
    confidence: str = "HIGH"
    journey_name: Optional[str] = None
    risk_level: str = "MEDIUM"
    updated_at: str = "2024-01-01T00:00:00"


@dataclass
class MockEvidence:
    id: str = str(uuid.uuid4())
    behavior_id: str = str(uuid.uuid4())
    evidence_type: str = "ROUTE"
    confidence: str = "HIGH"


@dataclass
class MockSemanticEntry:
    id: str = str(uuid.uuid4())
    repository_id: str = str(uuid.uuid4())


def test_diagnostics_service():
    """Test diagnostics service with mock database."""
    print("=" * 60)
    print("BEHAVIOR DIAGNOSTICS SERVICE TEST")
    print("=" * 60)
    
    # Initialize service with mock DB
    db = MockDB()
    service = BehaviorDiagnosticsService(db)
    
    repository_id = str(uuid.uuid4())
    
    print("\nTest 1: Get Diagnostics")
    print("-" * 60)
    try:
        diagnostics = service.get_diagnostics(repository_id)
        print(f"Repository ID: {diagnostics.repository_id}")
        print(f"Total Behaviors: {diagnostics.summary.total_behaviors}")
        print(f"High Confidence: {diagnostics.summary.high_confidence}")
        print(f"Medium Confidence: {diagnostics.summary.medium_confidence}")
        print(f"Low Confidence: {diagnostics.summary.low_confidence}")
        print(f"Discovery Coverage: {diagnostics.summary.discovery_coverage}%")
        print(f"Last Updated: {diagnostics.summary.last_updated}")
        print(f"Evidence Sources: {diagnostics.summary.evidence_sources}")
        print(f"Behaviors Count: {len(diagnostics.behaviors)}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\nTest 2: Summary Components")
    print("-" * 60)
    try:
        summary = service._get_summary(repository_id)
        print(f"Total Behaviors: {summary.total_behaviors}")
        print(f"High Confidence: {summary.high_confidence}")
        print(f"Medium Confidence: {summary.medium_confidence}")
        print(f"Low Confidence: {summary.low_confidence}")
        print(f"Evidence Sources: {summary.evidence_sources}")
        print(f"Discovery Coverage: {summary.discovery_coverage}%")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\nTest 3: Behavior Details")
    print("-" * 60)
    try:
        behaviors = service._get_behavior_details(repository_id)
        print(f"Behavior Details Count: {len(behaviors)}")
        for behavior in behaviors:
            print(f"\n  Behavior: {behavior.behavior_name}")
            print(f"    Confidence: {behavior.confidence}")
            print(f"    Evidence Count: {behavior.evidence_count}")
            print(f"    Discovery Sources: {behavior.discovery_sources}")
            print(f"    Journey: {behavior.journey}")
            print(f"    Risk Level: {behavior.risk_level}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\nTest 4: Evidence Sources")
    print("-" * 60)
    try:
        sources = service._get_evidence_sources(repository_id)
        print(f"Evidence Sources: {sources}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\nTest 5: Coverage Calculation")
    print("-" * 60)
    try:
        coverage = service._calculate_coverage(repository_id)
        print(f"Discovery Coverage: {coverage}%")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\nTest 6: Confidence Breakdown")
    print("-" * 60)
    try:
        behavior = MockBehavior("Test Behavior", "HIGH")
        breakdown = service._get_confidence_breakdown(behavior)
        print(f"Confidence Breakdown: {breakdown}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Test schema validation
    print("\nTest 7: Schema Validation")
    print("-" * 60)
    try:
        summary = BehaviorDiagnosticsSummary(
            total_behaviors=10,
            high_confidence=5,
            medium_confidence=3,
            low_confidence=2,
            evidence_sources={"ROUTE": 5, "TEST": 3, "MODULE": 2},
            discovery_coverage=75.5,
            last_updated="2024-01-01T00:00:00",
        )
        print(f"Summary Schema Valid: {summary.total_behaviors == 10}")
        
        detail = BehaviorDiagnosticsDetail(
            behavior_id=str(uuid.uuid4()),
            behavior_name="Authentication",
            confidence="HIGH",
            evidence_count=5,
            discovery_sources=["ROUTE", "TEST"],
            journey="Authentication",
            risk_level="MEDIUM",
        )
        print(f"Detail Schema Valid: {detail.behavior_name == 'Authentication'}")
        
        response = BehaviorDiagnosticsResponse(
            repository_id=str(uuid.uuid4()),
            summary=summary,
            behaviors=[detail],
        )
        print(f"Response Schema Valid: {len(response.behaviors) == 1}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_diagnostics_service()
