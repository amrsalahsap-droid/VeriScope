import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.services.github_app import GitHubAppService

db = SessionLocal()
try:
    repo = db.query(Repository).filter(Repository.id == "5d10f067-820c-4fcc-9150-501a4fd2b893").first()
    if not repo:
        print("Repository 5d10f067-820c-4fcc-9150-501a4fd2b893 not found!")
        sys.exit(1)
        
    print(f"Syncing architecture for repository: {repo.full_name}")
    service = GitHubAppService(db)
    service.sync_repository_architecture(repo.id, repo.installation_id)
    print("SUCCESS: Architecture graph built successfully without attribute errors!")
finally:
    db.close()
