"""Create the missing pattern_memories_v2 table from the model definition."""
from app.db.session import engine
from app.models.pattern_memory_v2 import PatternMemoryV2

# Create only this table (checkfirst avoids errors if it exists)
PatternMemoryV2.__table__.create(bind=engine, checkfirst=True)
print("pattern_memories_v2 table created (or already existed).")
