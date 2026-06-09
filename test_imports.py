import sys
sys.path.insert(0, 'C:\\Users\\amrsa\\Downloads\\veriscope')

# Test imports
try:
    from app.models.user import User, Workspace, WorkspaceMember
    print("[OK] user models")
    
    from app.models.github_installation import GitHubInstallation
    print("[OK] github_installation model")
    
    from app.models.repository import Repository
    print("[OK] repository model")
    
    from app.models.repository_sync_job import RepositorySyncJob
    print("[OK] repository_sync_job model")
    
    from app.models.pilot import PilotWorkspaceProfile
    print("[OK] pilot model")
    
    from app.routers.github import router as github_router
    print("[OK] github router")
    
    from app.services.github_app import GitHubAppService
    print("[OK] github_app service")
    
    from app.dependencies.auth import require_workspace_member
    print("[OK] auth dependencies")
    
    print("\nSUCCESS: All imports successful! Backend code is valid.")
    
except Exception as e:
    print(f"\nERROR: Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
