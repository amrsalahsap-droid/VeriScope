#!/usr/bin/env python3
"""
Input 2 Hierarchy Inspection Script

This script inspects the current Input 2 implementation to verify:
- Multiple enhancements per PR support
- Multiple ACs per enhancement support  
- Parent-child relationship preservation
- Stable identity rules
- Readiness rules
"""

import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.requirement_package import RequirementPackage
from app.models.requirement_group import RequirementGroup
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.testable_scenario import TestableScenario
from app.models.repository import Repository
from app.models.pull_request import PullRequest


def inspect_input2_hierarchy(db_session, repository_id=None, pull_request_id=None):
    """
    Inspect Input 2 hierarchy implementation and output status.
    
    Args:
        db_session: SQLAlchemy session
        repository_id: Optional specific repository to inspect
        pull_request_id: Optional specific PR to inspect
    """
    print("=" * 80)
    print("INPUT 2 HIERARCHY INSPECTION")
    print("=" * 80)
    
    # 1. Check Model Structure
    print("\n### MODEL STRUCTURE ###")
    print("RequirementPackage model:")
    print(f"  - Fields: {[c.name for c in RequirementPackage.__table__.columns]}")
    print(f"  - Relationships: {[r.key for r in RequirementPackage.__mapper__.relationships]}")
    
    print("\nRequirementGroup model:")
    print(f"  - Fields: {[c.name for c in RequirementGroup.__table__.columns]}")
    print(f"  - Relationships: {[r.key for r in RequirementGroup.__mapper__.relationships]}")
    
    print("\nAcceptanceCriterion model:")
    print(f"  - Fields: {[c.name for c in AcceptanceCriterion.__table__.columns]}")
    print(f"  - Relationships: {[r.key for r in AcceptanceCriterion.__mapper__.relationships]}")
    
    print("\nTestableScenario model:")
    print(f"  - Fields: {[c.name for c in TestableScenario.__table__.columns]}")
    print(f"  - Relationships: {[r.key for r in TestableScenario.__mapper__.relationships]}")
    
    # 2. Check Database State
    print("\n### DATABASE STATE ###")
    
    # Count packages
    pkg_count = db_session.query(RequirementPackage).count()
    print(f"Requirement packages: {pkg_count}")
    
    # Count groups
    group_count = db_session.query(RequirementGroup).count()
    print(f"Requirement groups: {group_count}")
    
    # Count ACs
    ac_count = db_session.query(AcceptanceCriterion).count()
    print(f"Acceptance criteria: {ac_count}")
    
    # Count scenarios
    scenario_count = db_session.query(TestableScenario).count()
    print(f"Testable scenarios: {scenario_count}")
    
    # 3. Check Stable Identity Rules
    print("\n### STABLE IDENTITY RULES ###")
    
    # Check groups without stable keys
    groups_without_keys = db_session.query(RequirementGroup).filter(
        RequirementGroup.stable_group_key.is_(None)
    ).count()
    print(f"Groups without stable_group_key: {groups_without_keys}")
    
    # Check ACs without stable keys
    acs_without_keys = db_session.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.stable_ac_key.is_(None)
    ).count()
    print(f"ACs without stable_ac_key: {acs_without_keys}")
    
    # Check for duplicate AC keys within groups
    duplicate_acs = 0
    groups = db_session.query(RequirementGroup).all()
    for group in groups:
        ac_keys = [ac.stable_ac_key for ac in group.acceptance_criteria if ac.stable_ac_key]
        if len(ac_keys) != len(set(ac_keys)):
            duplicate_acs += len(ac_keys) - len(set(ac_keys))
    print(f"Duplicate AC keys within groups: {duplicate_acs}")
    
    # 4. Check Hierarchy Preservation
    print("\n### HIERARCHY PRESERVATION ###")
    
    # Check ACs without group assignment
    ungrouped_acs = db_session.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.requirement_group_id.is_(None)
    ).count()
    print(f"ACs without group assignment: {ungrouped_acs}")
    
    # Check multiple enhancements per PR
    pr_group_counts = {}
    for group in groups:
        pr_id = str(group.pull_request_id)
        pr_group_counts[pr_id] = pr_group_counts.get(pr_id, 0) + 1
    
    prs_with_multiple_groups = sum(1 for count in pr_group_counts.values() if count > 1)
    print(f"PRs with multiple enhancement groups: {prs_with_multiple_groups}")
    
    # Check multiple ACs per enhancement
    groups_with_multiple_acs = sum(1 for group in groups if len(group.acceptance_criteria) > 1)
    print(f"Groups with multiple ACs: {groups_with_multiple_acs}")
    
    # 5. Specific PR Inspection (if provided)
    if pull_request_id:
        print(f"\n### SPECIFIC PR INSPECTION: {pull_request_id} ###")
        
        pkg = db_session.query(RequirementPackage).filter(
            RequirementPackage.pull_request_id == pull_request_id
        ).first()
        
        if pkg:
            print(f"Requirement package exists: True")
            print(f"  - ID: {pkg.id}")
            print(f"  - Status: {pkg.status}")
            print(f"  - Source type: {pkg.source_type}")
            
            pr_groups = db_session.query(RequirementGroup).filter(
                RequirementGroup.requirement_package_id == pkg.id
            ).all()
            
            print(f"Requirement groups: {len(pr_groups)}")
            for group in pr_groups:
                print(f"  - Group {group.group_number}: {group.title} ({group.group_type})")
                print(f"    Stable key: {group.stable_group_key}")
                print(f"    ACs: {len(group.acceptance_criteria)}")
                
                for ac in group.acceptance_criteria:
                    print(f"      AC-{ac.ac_number}: {ac.title or ac.raw_text[:50]}")
                    print(f"        Stable key: {ac.stable_ac_key}")
                    print(f"        Status: {ac.status}")
                    print(f"        Scenarios: {len(ac.testable_scenarios)}")
        else:
            print(f"Requirement package exists: False")
    
    # 6. Final Assessment
    print("\n### REQUIREMENT HIERARCHY STATUS ###")
    print(f"RequirementPackage: {'EXISTS' if pkg_count > 0 else 'MISSING'}")
    print(f"RequirementGroup/Enhancement: {'EXISTS' if group_count > 0 else 'MISSING'}")
    print(f"AcceptanceCriterion: {'EXISTS' if ac_count > 0 else 'MISSING'}")
    print(f"TestableScenario: {'EXISTS' if scenario_count > 0 else 'MISSING'}")
    print(f"Parent-child mapping: {'PRESERVED' if ungrouped_acs == 0 else 'PARTIAL'}")
    print(f"Multiple enhancements supported: {prs_with_multiple_groups > 0}")
    print(f"Multiple ACs per enhancement supported: {groups_with_multiple_acs > 0}")
    print(f"Flattening risk: {'LOW' if prs_with_multiple_groups > 0 else 'HIGH'}")
    
    required_fixes = []
    if groups_without_keys > 0:
        required_fixes.append(f"{groups_without_keys} groups missing stable keys")
    if acs_without_keys > 0:
        required_fixes.append(f"{acs_without_keys} ACs missing stable keys")
    if duplicate_acs > 0:
        required_fixes.append(f"{duplicate_acs} duplicate AC keys within groups")
    if ungrouped_acs > 0:
        required_fixes.append(f"{ungrouped_acs} ACs without group assignment")
    
    print(f"Required fixes: {required_fixes if required_fixes else 'None - hierarchy is healthy'}")
    
    # 7. Answer Key Questions
    print("\n### KEY QUESTIONS ###")
    print(f"Does the current implementation support multiple enhancements per PR? {prs_with_multiple_groups > 0}")
    print(f"Does it support multiple ACs per enhancement? {groups_with_multiple_acs > 0}")
    print(f"Does it preserve parent-child relationship between enhancement and AC? {ungrouped_acs == 0}")
    print(f"Or does it flatten everything into one list? {ungrouped_acs > 0}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    # Database connection
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/veriscope")
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Parse command line args
        repository_id = sys.argv[1] if len(sys.argv) > 1 else None
        pull_request_id = sys.argv[2] if len(sys.argv) > 2 else None
        
        inspect_input2_hierarchy(session, repository_id, pull_request_id)
    finally:
        session.close()
