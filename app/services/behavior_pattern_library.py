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
        
        # Authentication pattern
        if not self.get_pattern("Authentication"):
            self.create_pattern(
                name="Authentication",
                aliases=["auth", "login", "logout", "token", "session", "jwt", "password", "signin", "log-in"],
                journey="Authentication",
                risk_level="CRITICAL",
                description="User authentication and session management",
                default_scenarios=[
                    {"title": "Successful login with valid credentials", "priority": "BLOCKER", "type": "POSITIVE"},
                    {"title": "Login with invalid credentials", "priority": "MUST", "type": "NEGATIVE"},
                    {"title": "Session timeout", "priority": "MUST", "type": "EDGE"},
                    {"title": "JWT token expiration", "priority": "MUST", "type": "EDGE"},
                    {"title": "Password change", "priority": "SHOULD", "type": "POSITIVE"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1
        
        # Password Reset pattern
        if not self.get_pattern("Password Reset"):
            self.create_pattern(
                name="Password Reset",
                aliases=["reset-password", "forgot-password", "password-reset", "recovery", "recover-password"],
                journey="Authentication",
                risk_level="HIGH",
                description="Password recovery and reset functionality",
                default_scenarios=[
                    {"title": "Request password reset with valid email", "priority": "BLOCKER", "type": "POSITIVE"},
                    {"title": "Reset with invalid token", "priority": "MUST", "type": "NEGATIVE"},
                    {"title": "Reset with expired token", "priority": "MUST", "type": "EDGE"},
                    {"title": "Rate limiting on reset requests", "priority": "SHOULD", "type": "SECURITY"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1
        
        # Registration pattern
        if not self.get_pattern("User Registration"):
            self.create_pattern(
                name="User Registration",
                aliases=["signup", "sign-up", "register", "registration", "create-account", "join"],
                journey="Authentication",
                risk_level="HIGH",
                description="New user account creation and onboarding",
                default_scenarios=[
                    {"title": "Successful registration with valid data", "priority": "BLOCKER", "type": "POSITIVE"},
                    {"title": "Registration with duplicate email", "priority": "MUST", "type": "NEGATIVE"},
                    {"title": "Email verification flow", "priority": "MUST", "type": "POSITIVE"},
                    {"title": "Password strength validation", "priority": "SHOULD", "type": "SECURITY"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1
        
        # Billing pattern
        if not self.get_pattern("Billing"):
            self.create_pattern(
                name="Billing",
                aliases=["billing", "subscription", "invoice", "payment", "plan", "pricing", "checkout"],
                journey="Billing",
                risk_level="HIGH",
                description="Billing, subscription, and payment management",
                default_scenarios=[
                    {"title": "Successful payment processing", "priority": "BLOCKER", "type": "POSITIVE"},
                    {"title": "Payment failure handling", "priority": "MUST", "type": "NEGATIVE"},
                    {"title": "Subscription upgrade/downgrade", "priority": "MUST", "type": "POSITIVE"},
                    {"title": "Invoice generation", "priority": "SHOULD", "type": "POSITIVE"},
                    {"title": "Refund processing", "priority": "SHOULD", "type": "POSITIVE"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1
        
        # Notifications pattern
        if not self.get_pattern("Notifications"):
            self.create_pattern(
                name="Notifications",
                aliases=["notification", "email", "sms", "message", "alert", "push"],
                journey="Notifications",
                risk_level="LOW",
                description="User notifications and messaging",
                default_scenarios=[
                    {"title": "Email notification delivery", "priority": "MUST", "type": "POSITIVE"},
                    {"title": "SMS notification delivery", "priority": "SHOULD", "type": "POSITIVE"},
                    {"title": "Push notification delivery", "priority": "SHOULD", "type": "POSITIVE"},
                    {"title": "Notification preferences", "priority": "OPTIONAL", "type": "POSITIVE"},
                ],
            )
            stats["created"] += 1
        else:
            stats["skipped"] += 1
        
        return stats
