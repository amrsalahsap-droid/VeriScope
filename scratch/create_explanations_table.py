import sys
import os

# Add parent directory to path to enable local app imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv(r"c:\Users\amrsa\Downloads\veriscope\.env")

from app.db.session import engine
from app.db.base import Base
import app.models.recommendation  # Ensure models are loaded in metadata

def create_table():
    print("Creating recommendation_explanations table if not exists...")
    Base.metadata.create_all(bind=engine)
    print("Table created successfully!")

if __name__ == "__main__":
    create_table()
