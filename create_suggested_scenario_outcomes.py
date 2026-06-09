"""Create the missing suggested_scenario_outcomes table from the model definition."""
from app.db.session import engine
from app.models.recommendation import SuggestedScenarioOutcome

# Create only this table (checkfirst avoids errors if it exists)
SuggestedScenarioOutcome.__table__.create(bind=engine, checkfirst=True)
print("suggested_scenario_outcomes table created (or already existed).")
