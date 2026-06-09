"""Reproduce the recommendation generation to capture the real first error."""
import traceback
from sqlalchemy import event
from app.db.session import SessionLocal, engine
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate

REPO_ID = "357af7ba-56b6-4cc6-a6af-642519287491"
PR_ID = "a45662eb-66e2-415b-93ce-ce1188ac7897"

_first_error = {"captured": False}

@event.listens_for(engine, "handle_error")
def _on_error(ctx):
    if _first_error["captured"]:
        return
    err = str(ctx.original_exception)
    # Skip the cascading aborted-transaction errors; capture the real first one
    if "current transaction is aborted" in err:
        return
    _first_error["captured"] = True
    print("=" * 70)
    print("FIRST REAL DB ERROR:")
    print(err)
    print("-" * 70)
    print("STATEMENT:")
    print(str(ctx.statement)[:1500])
    print("=" * 70)

db = SessionLocal()
svc = RecommendationService(db)
try:
    run = svc.create_recommendation_run(
        RecommendationRunCreate(
            repository_id=REPO_ID,
            pr_id=PR_ID,
            changed_files=[],
            triggered_by="MANUAL_DRY_RUN"
        )
    )
    print("SUCCESS:", run.id if hasattr(run, 'id') else run)
except Exception as e:
    print("=" * 60)
    print("FULL TRACEBACK:")
    traceback.print_exc()
finally:
    db.close()
