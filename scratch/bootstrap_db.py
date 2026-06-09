from app.db.session import engine
from sqlalchemy import text

def bootstrap_triggers():
    with engine.connect() as conn:
        print("Registering snapshot immutability triggers...")
        # Create function
        conn.execute(text("""
            CREATE OR REPLACE FUNCTION block_mutation_on_evidence()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'Immutability Violation: Evidence ledger mutation is blocked.';
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        # Drop triggers if they exist
        conn.execute(text("DROP TRIGGER IF EXISTS enforce_snapshot_immutability ON pull_request_snapshots;"))
        conn.execute(text("DROP TRIGGER IF EXISTS enforce_artifact_update_immutability ON raw_artifacts;"))

        # Create trigger on pull_request_snapshots to block all modifications
        conn.execute(text("""
            CREATE TRIGGER enforce_snapshot_immutability
            BEFORE UPDATE OR DELETE ON pull_request_snapshots
            FOR EACH ROW EXECUTE FUNCTION block_mutation_on_evidence();
        """))
        
        # Create trigger on raw_artifacts to block UPDATES only (allowing DELETEs for payload pruning)
        conn.execute(text("""
            CREATE TRIGGER enforce_artifact_update_immutability
            BEFORE UPDATE ON raw_artifacts
            FOR EACH ROW EXECUTE FUNCTION block_mutation_on_evidence();
        """))
        
        conn.commit()
        print("Triggers registered successfully!")

if __name__ == "__main__":
    bootstrap_triggers()
