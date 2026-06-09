"""
Run behavior discovery on a real repository to verify it works end-to-end.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.repository import Repository
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.journey_behavior import JourneyBehavior
from app.models.behavior_evidence import BehaviorEvidence
from app.models.architecture_node import ArchitectureNode
from app.services.behavior_discovery_refresh_pipeline import BehaviorDiscoveryRefreshPipeline
from app.services.journey_discovery_engine import JourneyDiscoveryEngine

db_gen = get_db()
db = next(db_gen)

try:
    # Get real repositories (exclude test repo)
    repos = db.query(Repository).filter(
        Repository.full_name != "test/behavior-discovery-verification"
    ).all()
    
    print(f"Found {len(repos)} real repositories")
    
    for repo in repos:
        print(f"\n{'='*60}")
        print(f"Repository: {repo.full_name}")
        print(f"ID: {repo.id}")
        print(f"Default Branch: {repo.default_branch}")
        print(f"{'='*60}")
        
        # Check architecture nodes count (proxy for file count)
        node_count = db.query(ArchitectureNode).filter(
            ArchitectureNode.repository_id == repo.id
        ).count()
        print(f"Architecture Nodes: {node_count}")
        
        # Clear existing data for this repository
        print("\nCleaning up existing data...")
        db.query(JourneyBehavior).filter(
            JourneyBehavior.journey_id.in_(
                db.query(Journey.id).filter(Journey.repository_id == repo.id)
            )
        ).delete(synchronize_session=False)
        
        db.query(Journey).filter(Journey.repository_id == repo.id).delete(synchronize_session=False)
        
        behavior_ids = db.query(Behavior.id).filter(Behavior.repository_id == repo.id).all()
        db.query(BehaviorEvidence).filter(
            BehaviorEvidence.behavior_id.in_([b[0] for b in behavior_ids])
        ).delete(synchronize_session=False)
        
        db.query(Behavior).filter(Behavior.repository_id == repo.id).delete(synchronize_session=False)
        
        db.commit()
        print("Cleanup complete")
        
        # Run behavior discovery
        print("\n" + "="*60)
        print("Running Behavior Discovery Pipeline")
        print("="*60)
        
        pipeline = BehaviorDiscoveryRefreshPipeline(db)
        result = pipeline.trigger_on_repository_sync(repo)
        
        print(f"\nPipeline Success: {result.success}")
        print(f"Behaviors Discovered: {result.behaviors_discovered}")
        print(f"Behaviors Updated: {result.behaviors_updated}")
        print(f"Execution Time: {result.execution_time_seconds:.2f}s")
        print(f"Steps Completed: {len(result.steps_completed)}")
        
        if result.error_message:
            print(f"Error: {result.error_message}")
        
        print("\nSteps:")
        for step in result.steps_completed:
            print(f"  - {step}")
        
        if result.steps_failed:
            print("\nFailed Steps:")
            for step in result.steps_failed:
                print(f"  - {step}")
        
        # Check behaviors in DB
        behaviors = db.query(Behavior).filter(
            Behavior.repository_id == repo.id,
            Behavior.is_deleted == False
        ).all()
        
        auto_discovered = db.query(Behavior).filter(
            Behavior.repository_id == repo.id,
            Behavior.is_deleted == False,
            Behavior.discovery_source == "AUTO_DISCOVERED"
        ).count()
        
        print(f"\n{'='*60}")
        print("Behavior Persistence Results")
        print(f"{'='*60}")
        print(f"Total Behaviors in DB: {len(behaviors)}")
        print(f"Auto-Discovered: {auto_discovered}")
        
        if behaviors:
            print(f"\nTop 10 Behaviors:")
            for b in behaviors[:10]:
                print(f"  - {b.name}")
                print(f"    Confidence: {b.confidence}")
                print(f"    Source: {b.discovery_source}")
                print(f"    Risk: {b.risk_level}")
                print(f"    Journey: {b.journey_name or 'None'}")
        
        # Check evidences
        behavior_ids = [b.id for b in behaviors]
        evidences = db.query(BehaviorEvidence).filter(
            BehaviorEvidence.behavior_id.in_(behavior_ids)
        ).all()
        
        print(f"\nBehavior Evidences: {len(evidences)}")
        
        # Run journey discovery
        if behaviors:
            print(f"\n{'='*60}")
            print("Running Journey Discovery")
            print(f"{'='*60}")
            
            journey_engine = JourneyDiscoveryEngine(db)
            candidates = journey_engine.discover_journeys(behaviors, str(repo.id))
            
            stats = journey_engine.get_discovery_stats(candidates)
            
            print(f"Journey Candidates: {stats['total_candidates']}")
            print(f"Average Score: {stats['average_score']:.2f}")
            print(f"By Confidence: {stats['by_confidence']}")
            print(f"By Risk: {stats['by_risk']}")
            
            # Persist journeys
            journeys_created = 0
            journeys_updated = 0
            journey_behavior_mappings_created = 0
            
            for candidate in candidates:
                existing_journey = db.query(Journey).filter(
                    Journey.repository_id == repo.id,
                    Journey.name == candidate.name,
                    Journey.is_deleted == False
                ).first()
                
                if existing_journey:
                    existing_journey.description = candidate.description
                    existing_journey.risk_level = candidate.risk_level
                    journeys_updated += 1
                    journey = existing_journey
                else:
                    from datetime import datetime
                    import uuid
                    journey = Journey(
                        id=uuid.uuid4(),
                        repository_id=repo.id,
                        name=candidate.name,
                        slug=candidate.name.lower().replace(" ", "-"),
                        description=candidate.description,
                        risk_level=candidate.risk_level,
                        is_deleted=False,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(journey)
                    journeys_created += 1
            
            db.commit()
            
            # Create mappings
            for candidate in candidates:
                journey = db.query(Journey).filter(
                    Journey.repository_id == repo.id,
                    Journey.name == candidate.name,
                    Journey.is_deleted == False
                ).first()
                
                if not journey:
                    continue
                
                for behavior_name in candidate.behaviors:
                    behavior = db.query(Behavior).filter(
                        Behavior.repository_id == repo.id,
                        Behavior.name == behavior_name,
                        Behavior.is_deleted == False
                    ).first()
                    
                    if not behavior:
                        continue
                    
                    existing_mapping = db.query(JourneyBehavior).filter(
                        JourneyBehavior.journey_id == journey.id,
                        JourneyBehavior.behavior_id == behavior.id
                    ).first()
                    
                    if not existing_mapping:
                        import uuid
                        mapping = JourneyBehavior(
                            id=uuid.uuid4(),
                            journey_id=journey.id,
                            behavior_id=behavior.id,
                            relationship_type="PART_OF",
                            confidence="HIGH"
                        )
                        db.add(mapping)
                        journey_behavior_mappings_created += 1
            
            db.commit()
            
            print(f"\nJourneys Created: {journeys_created}")
            print(f"Journeys Updated: {journeys_updated}")
            print(f"Journey-Behavior Mappings Created: {journey_behavior_mappings_created}")
            
            # Check journeys in DB
            journeys = db.query(Journey).filter(
                Journey.repository_id == repo.id,
                Journey.is_deleted == False
            ).all()
            
            print(f"\nTotal Journeys in DB: {len(journeys)}")
            
            if journeys:
                print(f"\nJourneys:")
                for j in journeys:
                    print(f"  - {j.name}")
                    print(f"    Risk: {j.risk_level}")
                    print(f"    Description: {j.description[:100] if j.description else 'None'}...")
            
            # Check mappings
            journey_ids = [j.id for j in journeys]
            mappings = db.query(JourneyBehavior).filter(
                JourneyBehavior.journey_id.in_(journey_ids)
            ).all()
            
            print(f"\nJourney-Behavior Mappings: {len(mappings)}")
        else:
            print("\nNo behaviors discovered, skipping journey discovery")
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Repository: {repo.full_name}")
        print(f"Architecture Nodes: {node_count}")
        print(f"Behaviors Discovered: {len(behaviors)}")
        print(f"Auto-Discovered: {auto_discovered}")
        print(f"Behavior Evidences: {len(evidences)}")
        print(f"Journeys Discovered: {len(journeys) if behaviors else 0}")
        print(f"Journey-Behavior Mappings: {len(mappings) if behaviors else 0}")
        
        if len(behaviors) > 0:
            print(f"\n[SUCCESS] Behavior Discovery is working on real repository!")
        else:
            print(f"\n[INFO] No behaviors discovered - repository may have no matching patterns")
        
        print(f"\n{'='*60}\n")

finally:
    db.close()
