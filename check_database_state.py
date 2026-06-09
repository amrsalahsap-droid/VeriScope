"""
Quick database state check for behavior discovery verification.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.journey_behavior import JourneyBehavior
from app.models.behavior_evidence import BehaviorEvidence
from app.models.repository import Repository

db_gen = get_db()
db = next(db_gen)

try:
    # Get all repositories
    repos = db.query(Repository).all()
    print(f"Total repositories: {len(repos)}")
    
    for repo in repos:
        print(f"\n=== Repository: {repo.full_name} ({repo.id}) ===")
        
        # Count behaviors
        total_behaviors = db.query(Behavior).filter(
            Behavior.repository_id == repo.id,
            Behavior.is_deleted == False
        ).count()
        
        auto_discovered = db.query(Behavior).filter(
            Behavior.repository_id == repo.id,
            Behavior.is_deleted == False,
            Behavior.discovery_source == "AUTO_DISCOVERED"
        ).count()
        
        manual = db.query(Behavior).filter(
            Behavior.repository_id == repo.id,
            Behavior.is_deleted == False,
            Behavior.discovery_source != "AUTO_DISCOVERED"
        ).count()
        
        print(f"Total behaviors: {total_behaviors}")
        print(f"Auto-discovered: {auto_discovered}")
        print(f"Manual: {manual}")
        
        # Count journeys
        total_journeys = db.query(Journey).filter(
            Journey.repository_id == repo.id,
            Journey.is_deleted == False
        ).count()
        
        print(f"Total journeys: {total_journeys}")
        
        # Count journey-behavior mappings
        journey_ids = db.query(Journey.id).filter(
            Journey.repository_id == repo.id,
            Journey.is_deleted == False
        ).all()
        
        mappings = db.query(JourneyBehavior).filter(
            JourneyBehavior.journey_id.in_([j[0] for j in journey_ids])
        ).count()
        
        print(f"Journey-behavior mappings: {mappings}")
        
        # Count behavior evidences
        behavior_ids = db.query(Behavior.id).filter(
            Behavior.repository_id == repo.id,
            Behavior.is_deleted == False
        ).all()
        
        evidences = db.query(BehaviorEvidence).filter(
            BehaviorEvidence.behavior_id.in_([b[0] for b in behavior_ids])
        ).count()
        
        print(f"Behavior evidences: {evidences}")
        
        # Show sample behaviors
        if total_behaviors > 0:
            sample_behaviors = db.query(Behavior).filter(
                Behavior.repository_id == repo.id,
                Behavior.is_deleted == False
            ).limit(5).all()
            print("\nSample behaviors:")
            for b in sample_behaviors:
                print(f"  - {b.name} (source: {b.discovery_source}, confidence: {b.confidence})")

finally:
    db.close()
