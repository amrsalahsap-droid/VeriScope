from typing import List, Optional, Dict
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.behavior_pattern import BehaviorPattern


class BehaviorPatternLibrary:
    """Service to manage reusable business capability patterns."""
    
    def __init__(self, db: Session):
        """Initialize the pattern library with database session."""
        self.db = db
        self._pattern_cache: Optional[Dict[str, BehaviorPattern]] = None
    
    def load_patterns(self, force_reload: bool = False) -> Dict[str, BehaviorPattern]:
        """Load all active patterns into cache."""
        if self._pattern_cache is not None and not force_reload:
            return self._pattern_cache
        
        patterns = self.db.query(BehaviorPattern).filter(
            BehaviorPattern.is_active == 1
        ).all()
        
        self._pattern_cache = {p.name: p for p in patterns}
        return self._pattern_cache
    
    def get_pattern(self, name: str) -> Optional[BehaviorPattern]:
        """Get a pattern by name."""
        patterns = self.load_patterns()
        return patterns.get(name)
    
    def get_all_patterns(self) -> List[BehaviorPattern]:
        """Get all active patterns."""
        patterns = self.load_patterns()
        return list(patterns.values())
    
    def get_patterns_by_journey(self, journey: str) -> List[BehaviorPattern]:
        """Get all patterns for a specific journey."""
        patterns = self.load_patterns()
        return [p for p in patterns.values() if p.journey == journey]
    
    def get_patterns_by_risk_level(self, risk_level: str) -> List[BehaviorPattern]:
        """Get all patterns with a specific risk level."""
        patterns = self.load_patterns()
        return [p for p in patterns.values() if p.risk_level == risk_level]
    
    def match_pattern(self, text: str) -> Optional[BehaviorPattern]:
        """Match text against pattern aliases."""
        text_lower = text.lower()
        patterns = self.load_patterns()
        
        for pattern in patterns.values():
            for alias in pattern.aliases:
                if alias.lower() in text_lower:
                    return pattern
        
        return None
    
    def create_pattern(
        self,
        name: str,
        aliases: List[str],
        journey: str,
        risk_level: str,
        description: Optional[str] = None,
        default_scenarios: Optional[List[Dict]] = None,
    ) -> BehaviorPattern:
        """Create a new behavior pattern."""
        # Check if pattern already exists
        existing = self.db.query(BehaviorPattern).filter(
            BehaviorPattern.name == name,
            BehaviorPattern.is_active == 1,
        ).first()
        
        if existing:
            raise ValueError(f"Pattern '{name}' already exists")
        
        pattern = BehaviorPattern(
            id=uuid.uuid4(),
            name=name,
            version=1,
            aliases=aliases,
            description=description,
            journey=journey,
            risk_level=risk_level,
            default_scenarios=default_scenarios,
            is_active=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        self.db.add(pattern)
        self.db.commit()
        
        # Invalidate cache
        self._pattern_cache = None
        
        return pattern
    
    def update_pattern(
        self,
        name: str,
        aliases: Optional[List[str]] = None,
        journey: Optional[str] = None,
        risk_level: Optional[str] = None,
        description: Optional[str] = None,
        default_scenarios: Optional[List[Dict]] = None,
    ) -> Optional[BehaviorPattern]:
        """Update an existing pattern (creates new version)."""
        pattern = self.db.query(BehaviorPattern).filter(
            BehaviorPattern.name == name,
            BehaviorPattern.is_active == 1,
        ).first()
        
        if not pattern:
            return None
        
        # Deactivate old version
        pattern.is_active = 0
        pattern.updated_at = datetime.utcnow()
        
        # Create new version
        new_version = pattern.version + 1
        new_pattern = BehaviorPattern(
            id=uuid.uuid4(),
            name=name,
            version=new_version,
            aliases=aliases or pattern.aliases,
            description=description or pattern.description,
            journey=journey or pattern.journey,
            risk_level=risk_level or pattern.risk_level,
            default_scenarios=default_scenarios or pattern.default_scenarios,
            is_active=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        self.db.add(new_pattern)
        self.db.commit()
        
        # Invalidate cache
        self._pattern_cache = None
        
        return new_pattern
    
    def deactivate_pattern(self, name: str) -> bool:
        """Deactivate a pattern."""
        pattern = self.db.query(BehaviorPattern).filter(
            BehaviorPattern.name == name,
            BehaviorPattern.is_active == 1,
        ).first()
        
        if not pattern:
            return False
        
        pattern.is_active = 0
        pattern.updated_at = datetime.utcnow()
        self.db.commit()
        
        # Invalidate cache
        self._pattern_cache = None
        
        return True
    
    def seed_initial_patterns(self) -> Dict[str, int]:
        """Seed initial behavior patterns."""
        stats = {
            "created": 0,
            "skipped": 0,
        }
        
        # Deactivate old generic patterns if they exist
        from app.models.behavior_pattern import BehaviorPattern
        for old_name in ["Authentication", "Password Reset", "User Registration", "Billing", "Notifications", "User Management"]:
            old_p = self.db.query(BehaviorPattern).filter(
                BehaviorPattern.name == old_name,
                BehaviorPattern.is_active == 1
            ).first()
            if old_p:
                old_p.is_active = 0
        self.db.commit()

        # 1. Sign-up password validation
        if not self.get_pattern("Sign-up password validation"):
            self.create_pattern(
                name="Sign-up password validation",
                aliases=["sign-up-password-validation", "signup-password-validation", "sign-up-password", "signup-password"],
                journey="Authentication",
                risk_level="HIGH",
                description="Validating password strength and rules during user sign-up",
                default_scenarios=[
                    {"title": "Validate sign-up password complexity rules", "priority": "MUST", "type": "SECURITY"},
                    {"title": "Successful sign-up with strong password", "priority": "BLOCKER", "type": "POSITIVE"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1

        # 2. Reset-password behavior
        if not self.get_pattern("Reset-password behavior"):
            self.create_pattern(
                name="Reset-password behavior",
                aliases=["reset-password-behavior", "reset-password", "forgot-password", "recover-password", "reset_password"],
                journey="Authentication",
                risk_level="HIGH",
                description="User password reset and token recovery flows",
                default_scenarios=[
                    {"title": "Validate password reset expired token rejection", "priority": "MUST", "type": "NEGATIVE"},
                    {"title": "Request password reset with valid email", "priority": "BLOCKER", "type": "POSITIVE"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1

        # 3. Update-password behavior
        if not self.get_pattern("Update-password behavior"):
            self.create_pattern(
                name="Update-password behavior",
                aliases=["update-password-behavior", "update-password", "change-password", "update_password"],
                journey="Authentication",
                risk_level="HIGH",
                description="Updating user password when logged in",
                default_scenarios=[
                    {"title": "Update password with correct current password", "priority": "MUST", "type": "POSITIVE"},
                    {"title": "Update password with weak new password", "priority": "MUST", "type": "NEGATIVE"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1

        # 4. Login after password change
        if not self.get_pattern("Login after password change"):
            self.create_pattern(
                name="Login after password change",
                aliases=["login-after-password-change", "login-after-change", "login-post-change"],
                journey="Authentication",
                risk_level="HIGH",
                description="Validating user login using newly changed or reset password",
                default_scenarios=[
                    {"title": "Successful login after password change", "priority": "MUST", "type": "POSITIVE"},
                    {"title": "Failed login using old password", "priority": "MUST", "type": "NEGATIVE"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1

        # 5. Shared password policy validation
        if not self.get_pattern("Shared password policy validation"):
            self.create_pattern(
                name="Shared password policy validation",
                aliases=["shared-password-policy-validation", "shared-password-policy", "password-policy", "password-validation-rules", "shared_password_policy"],
                journey="Authentication",
                risk_level="HIGH",
                description="Applying unified system-wide password strength policy checks",
                default_scenarios=[
                    {"title": "Validate minimum length constraint", "priority": "MUST", "type": "SECURITY"},
                    {"title": "Validate character class constraints", "priority": "MUST", "type": "SECURITY"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1

        # 6. UI/API validation consistency
        if not self.get_pattern("UI/API validation consistency"):
            self.create_pattern(
                name="UI/API validation consistency",
                aliases=["ui-api-validation-consistency", "ui-api-consistency", "validation-consistency"],
                journey="Authentication",
                risk_level="MEDIUM",
                description="Ensuring client UI and backend API validate passwords identically",
                default_scenarios=[
                    {"title": "UI validation matches API schema validation", "priority": "MUST", "type": "EDGE"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1

        # 7. Account security validation
        if not self.get_pattern("Account security validation"):
            self.create_pattern(
                name="Account security validation",
                aliases=["account-security-validation", "account-security", "security-validation"],
                journey="Authentication",
                risk_level="HIGH",
                description="Validating account lockout and security controls on authentication endpoints",
                default_scenarios=[
                    {"title": "Account lock after maximum consecutive login failures", "priority": "MUST", "type": "SECURITY"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1
        
        return stats
