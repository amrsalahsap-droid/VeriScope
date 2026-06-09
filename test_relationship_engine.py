"""
Test script for BehaviorRelationshipEngine.

Tests behavior relationship discovery with examples.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_relationship_engine import BehaviorRelationshipEngine
from dataclasses import dataclass


# Mock evidence class for testing
@dataclass
class MockEvidence:
    source_type: str
    source_identifier: str
    confidence: str
    metadata: dict = None


def test_relationship_engine():
    """Test relationship engine with examples."""
    print("=" * 60)
    print("BEHAVIOR RELATIONSHIP ENGINE TEST")
    print("=" * 60)
    
    # Initialize relationship engine
    engine = BehaviorRelationshipEngine(db=None)
    
    # Test behaviors
    behavior_names = [
        "Password Reset",
        "Authentication",
        "User Registration",
        "User Management",
        "Subscription Renewal",
        "Billing",
        "Password Change",
        "Social Login",
    ]
    
    # Create mock evidences
    evidences = {
        "Password Reset": [
            MockEvidence("ROUTE", "Password Reset", "HIGH", {"route": "/api/auth/reset-password"}),
            MockEvidence("MODULE", "Password Reset", "HIGH", {"module": "services/auth/"}),
        ],
        "Authentication": [
            MockEvidence("ROUTE", "Authentication", "HIGH", {"route": "/api/auth/login"}),
            MockEvidence("MODULE", "Authentication", "HIGH", {"module": "services/auth/"}),
        ],
        "User Registration": [
            MockEvidence("ROUTE", "User Registration", "HIGH", {"route": "/api/auth/register"}),
            MockEvidence("MODULE", "User Registration", "HIGH", {"module": "services/auth/"}),
        ],
        "User Management": [
            MockEvidence("ROUTE", "User Management", "HIGH", {"route": "/api/users/"}),
            MockEvidence("MODULE", "User Management", "HIGH", {"module": "services/users/"}),
        ],
        "Subscription Renewal": [
            MockEvidence("ROUTE", "Subscription Renewal", "HIGH", {"route": "/api/billing/renew"}),
            MockEvidence("MODULE", "Subscription Renewal", "HIGH", {"module": "services/billing/"}),
        ],
        "Billing": [
            MockEvidence("ROUTE", "Billing", "HIGH", {"route": "/api/billing/"}),
            MockEvidence("MODULE", "Billing", "HIGH", {"module": "services/billing/"}),
        ],
    }
    
    print("\nDiscovering relationships...")
    print("-" * 60)
    relationships = engine.discover_relationships(behavior_names, evidences)
    
    print(f"Total relationships discovered: {len(relationships)}")
    
    # Display relationships
    print("\nDiscovered Relationships:")
    print("-" * 60)
    for rel in relationships:
        print(f"\n{rel.child_behavior} --[{rel.relationship_type}]--> {rel.parent_behavior}")
        print(f"  Confidence: {rel.confidence}")
        print(f"  Evidence:")
        for evidence in rel.evidence:
            print(f"    - {evidence}")
    
    # Build behavior graph
    print("\n\nBuilding Behavior Graph:")
    print("-" * 60)
    graph = engine.build_behavior_graph(relationships)
    
    print("\nDEPENDS_ON relationships:")
    for child, parents in graph["depends_on"].items():
        print(f"  {child} depends on: {', '.join(parents)}")
    
    print("\nPART_OF relationships:")
    for child, parents in graph["part_of"].items():
        print(f"  {child} is part of: {', '.join(parents)}")
    
    print("\nEXTENDS relationships:")
    for child, parents in graph["extends"].items():
        print(f"  {child} extends: {', '.join(parents)}")
    
    # Test relationships by behavior
    print("\n\nRelationships by Behavior:")
    print("-" * 60)
    
    for behavior in ["Password Reset", "Authentication", "User Registration"]:
        rels = engine.get_relationships_by_behavior(relationships, behavior)
        print(f"\n{behavior}:")
        print(f"  As parent: {len(rels['as_parent'])} relationship(s)")
        for rel in rels['as_parent']:
            print(f"    - {rel.child_behavior} depends on {behavior}")
        print(f"  As child: {len(rels['as_child'])} relationship(s)")
        for rel in rels['as_child']:
            print(f"    - {behavior} depends on {rel.parent_behavior}")
    
    # Test relationships by type
    print("\n\nRelationships by Type:")
    print("-" * 60)
    
    for rel_type in ["DEPENDS_ON", "PART_OF", "EXTENDS"]:
        type_rels = engine.get_relationships_by_type(relationships, rel_type)
        print(f"\n{rel_type}: {len(type_rels)} relationship(s)")
        for rel in type_rels:
            print(f"  {rel.child_behavior} -> {rel.parent_behavior}")
    
    # Verify specific examples
    print("\n\nVerifying Specific Examples:")
    print("-" * 60)
    
    # Password Reset depends on Authentication
    password_reset_rels = engine.get_relationships_by_behavior(relationships, "Password Reset")
    depends_on_auth = any(
        rel.parent_behavior == "Authentication" and rel.relationship_type == "DEPENDS_ON"
        for rel in password_reset_rels['as_child']
    )
    print(f"Password Reset depends on Authentication: {depends_on_auth}")
    
    # User Registration depends on User Management
    user_reg_rels = engine.get_relationships_by_behavior(relationships, "User Registration")
    depends_on_user_mgmt = any(
        rel.parent_behavior == "User Management" and rel.relationship_type == "DEPENDS_ON"
        for rel in user_reg_rels['as_child']
    )
    print(f"User Registration depends on User Management: {depends_on_user_mgmt}")
    
    # Subscription Renewal depends on Billing
    sub_renewal_rels = engine.get_relationships_by_behavior(relationships, "Subscription Renewal")
    depends_on_billing = any(
        rel.parent_behavior == "Billing" and rel.relationship_type == "DEPENDS_ON"
        for rel in sub_renewal_rels['as_child']
    )
    print(f"Subscription Renewal depends on Billing: {depends_on_billing}")
    
    # Test serialization
    print("\n\nTest: Relationship Serialization")
    print("-" * 60)
    if relationships:
        rel_dict = relationships[0].to_dict()
        print(f"Serialized relationship keys: {list(rel_dict.keys())}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_relationship_engine()
