import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import settings
from app.db.session import get_db
from app.models.user import User, Workspace, WorkspaceMember

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Decodes the NextAuth JWT token and resolves the authenticated user in the database.
    If the user doesn't exist, they are auto-registered.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.STATE_SECRET_KEY,
            algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError as e:
        print(f"[AUTH ERROR] Token expired: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
    except jwt.InvalidTokenError as e:
        print(f"[AUTH ERROR] Invalid token: {e}")
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            print(f"[AUTH ERROR] Unverified payload: {unverified}")
        except Exception as ue:
            print(f"[AUTH ERROR] Failed to decode unverified: {ue}")
        print(f"[AUTH ERROR] Token: {token}")
        print(f"[AUTH ERROR] Expected Secret: {settings.STATE_SECRET_KEY}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token."
        )

    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing required user claims (email)."
        )

    # 1. Resolve or create User
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Create user
        user = User(
            email=email,
            name=payload.get("name"),
            avatar_url=payload.get("avatar_url") or payload.get("image"),
            auth_provider="github",
            provider_user_id=payload.get("sub") or payload.get("id")
        )
        db.add(user)
        db.flush() # Populate user.id

    # 2. Check or assign Workspace (Workspace Isolation)
    # Check if the user has an active workspace membership
    member = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).first()
    if not member:
        # If the user is the first user of this workspace context
        # Check if the token claims a specific workspace
        workspace_id = payload.get("workspace_id")
        workspace = None
        if workspace_id:
            workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        
        if not workspace:
            # First user creates a fresh workspace as OWNER
            base_slug = email.split("@")[0].lower().replace(".", "-") + "-workspace"
            slug = base_slug
            # Ensure slug is unique
            import uuid as _uuid
            counter = 1
            while db.query(Workspace).filter(Workspace.slug == slug).first():
                slug = f"{base_slug}-{str(_uuid.uuid4())[:6]}"
                counter += 1
                if counter > 5:
                    break
            workspace = Workspace(
                name=f"{user.name or email.split('@')[0]}'s Workspace",
                slug=slug,
                created_by_user_id=user.id
            )
            db.add(workspace)
            db.flush()

        # Link user to workspace as OWNER
        member = WorkspaceMember(
            user_id=user.id,
            workspace_id=workspace.id,
            role="OWNER" # "OWNER", "ADMIN", "MEMBER"
        )
        db.add(member)
        db.commit()
    else:
        # Update user attributes if changed
        user.name = payload.get("name") or user.name
        user.avatar_url = payload.get("avatar_url") or payload.get("image") or user.avatar_url
        user.provider_user_id = payload.get("sub") or payload.get("id") or user.provider_user_id
        db.commit()

    return user


def get_current_workspace(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Workspace:
    """
    Resolves the active Workspace of the authenticated user.
    """
    member = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any active workspace."
        )
    
    workspace = db.query(Workspace).filter(Workspace.id == member.workspace_id).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found."
        )
    return workspace


def get_current_workspace_id(
    workspace: Workspace = Depends(get_current_workspace)
) -> str:
    """
    Resolves the active workspace ID.
    """
    return str(workspace.id)


class require_workspace_member:
    """
    Role-based authentication guard dependency for workspaces.
    Usage: Depends(require_workspace_member(role="ADMIN"))
    """
    def __init__(self, role: str = None):
        self.role = role

    def __call__(
        self,
        user: User = Depends(get_current_user),
        workspace: Workspace = Depends(get_current_workspace),
        db: Session = Depends(get_db)
    ) -> WorkspaceMember:
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.workspace_id == workspace.id
        ).first()

        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You are not a member of this workspace."
            )

        if self.role:
            # Map roles hierarchy: OWNER > ADMIN > MEMBER
            role_values = {"OWNER": 3, "ADMIN": 2, "MEMBER": 1}
            user_role_val = role_values.get(member.role, 0)
            required_role_val = role_values.get(self.role, 0)

            if user_role_val < required_role_val:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Requires {self.role} role or higher."
                )

        return member


