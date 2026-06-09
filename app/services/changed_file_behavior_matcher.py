from typing import List, Dict, Any, Optional, Set
import re
import os

from app.models.behavior import Behavior
from app.models.behavior_evidence import BehaviorEvidence
from app.models.journey_behavior import JourneyBehavior
from app.models.journey import Journey


class ChangedFileBehaviorMatcher:
    """Matches pull request changed files to business behaviors using a multi-stage matcher."""

    # Generic/non-informative tokens to ignore
    GENERIC_TOKENS = {
        "app", "src", "page", "index", "route", "api", "test", "spec", "service", 
        "controller", "module", "utils", "util", "helpers", "helper", "component", 
        "components", "form", "view", "views", "lib", "libs", "main", "core"
    }

    # Behavior alias / synonym mappings
    ALIAS_SYNONYMS = {
        "auth": ["authentication", "login", "signin", "session"],
        "login": ["authentication", "signin", "auth"],
        "logout": ["authentication", "signout", "auth"],
        "password reset": ["password-reset", "reset-password", "forgot-password", "password-recovery", "recovery"],
        "user registration": ["signup", "sign-up", "register", "registration", "onboarding"],
        "subscription management": ["billing", "subscription", "plan", "invoice"],
        "checkout": ["payment", "stripe", "checkout", "pay", "cart"],
        "notifications": ["email", "notify", "push", "sms", "alert"],
        "reporting": ["analytics", "dashboard", "report", "statistics"],
        "administration": ["admin", "manage", "control-panel"],
    }

    def __init__(self, db: Optional[Any] = None):
        """Initialize matcher with optional database session."""
        self.db = db

    def normalize_path(self, file_path: str) -> str:
        """Normalize file path to use forward slashes and lowercased format."""
        path = file_path.replace("\\", "/")
        return path.lower()

    def tokenize_string(self, text: str) -> List[str]:
        """Split camelCase, kebab-case, snake_case and non-alphanumeric chars into clean lowercased tokens."""
        # Convert camelCase to space separated
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', text)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1)
        # Split by non-alphanumeric characters and lowercase
        tokens = re.split(r'[^a-zA-Z0-9]', s2.lower())
        # Filter empty and generic tokens
        return [t for t in tokens if t and len(t) > 1]

    def match_changed_files(
        self,
        changed_files: List[str],
        behaviors: List[Behavior],
        evidences: List[BehaviorEvidence],
        journey_behaviors: List[JourneyBehavior] = [],
        journeys: List[Journey] = [],
        semantic_index: Optional[Dict[str, Any]] = None,
        domain_vocab: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run multi-stage behavior matching for pull request changed files."""
        matches = []

        # Construct lookup maps
        evidence_by_behavior = {}
        for ev in evidences:
            b_id_str = str(ev.behavior_id)
            if b_id_str not in evidence_by_behavior:
                evidence_by_behavior[b_id_str] = []
            evidence_by_behavior[b_id_str].append(ev)

        behavior_to_journeys = self._build_behavior_to_journeys_map(journey_behaviors, journeys)

        # Process each changed file
        for file_path in changed_files:
            norm_path = self.normalize_path(file_path)
            path_tokens = set(self.tokenize_string(norm_path)) - self.GENERIC_TOKENS

            # Process each behavior
            for behavior in behaviors:
                b_id_str = str(behavior.id)
                b_name_lower = behavior.name.lower()
                b_slug_lower = behavior.slug.lower()
                b_evidences = evidence_by_behavior.get(b_id_str, [])

                # Match stages in order of specificity and strength:
                
                # Stage 1: Direct evidence path match (Score 1.0)
                matched_ev = self._find_direct_evidence_match(norm_path, b_evidences)
                if matched_ev:
                    matches.append({
                        "file_path": file_path,
                        "behavior_id": b_id_str,
                        "behavior_name": behavior.name,
                        "signal_type": "DIRECT_EVIDENCE",
                        "score": 1.0,
                        "confidence": "HIGH",
                        "reason": f"Direct match on cataloged evidence path: {matched_ev.source_path}",
                    })
                    continue

                # Stage 2: Path suffix match (Score 0.9)
                if self._is_path_suffix_match(norm_path, b_slug_lower, b_evidences):
                    matches.append({
                        "file_path": file_path,
                        "behavior_id": b_id_str,
                        "behavior_name": behavior.name,
                        "signal_type": "PATH_SUFFIX",
                        "score": 0.9,
                        "confidence": "HIGH",
                        "reason": f"Path suffix matches behavior signature / slug '{behavior.slug}'",
                    })
                    continue

                # Stage 3: Route/Page/Module structure match (Score 0.8)
                if self._is_route_page_module_match(norm_path, b_name_lower, b_slug_lower):
                    matches.append({
                        "file_path": file_path,
                        "behavior_id": b_id_str,
                        "behavior_name": behavior.name,
                        "signal_type": "ROUTE_PAGE_MODULE",
                        "score": 0.8,
                        "confidence": "HIGH",
                        "reason": f"File path contains standard structure patterns matching behavior '{behavior.name}'",
                    })
                    continue

                # Stage 4: Token match (Score 0.7)
                matched_tokens = self._find_meaningful_token_matches(path_tokens, behavior)
                if matched_tokens:
                    matches.append({
                        "file_path": file_path,
                        "behavior_id": b_id_str,
                        "behavior_name": behavior.name,
                        "signal_type": "TOKEN_MATCH",
                        "score": 0.7,
                        "confidence": "MODERATE",
                        "reason": f"Path tokens match behavior descriptor tokens: {', '.join(matched_tokens)}",
                    })
                    continue

                # Stage 5: Behavior alias / synonym match (Score 0.6)
                matched_synonyms = self._find_synonym_matches(path_tokens, b_name_lower)
                if matched_synonyms:
                    matches.append({
                        "file_path": file_path,
                        "behavior_id": b_id_str,
                        "behavior_name": behavior.name,
                        "signal_type": "ALIAS_SYNONYM",
                        "score": 0.6,
                        "confidence": "MODERATE",
                        "reason": f"Path contains known synonyms associated with behavior '{behavior.name}': {', '.join(matched_synonyms)}",
                    })
                    continue

                # Stage 6: Journey expansion match (Score 0.5)
                mapped_journeys = behavior_to_journeys.get(b_id_str, [])
                journey_match = self._find_journey_expansion_match(path_tokens, mapped_journeys)
                if journey_match:
                    matches.append({
                        "file_path": file_path,
                        "behavior_id": b_id_str,
                        "behavior_name": behavior.name,
                        "signal_type": "JOURNEY_EXPANSION",
                        "score": 0.5,
                        "confidence": "LOW",
                        "reason": f"Path references mapped parent journey '{journey_match.name}'",
                    })
                    continue

        return matches

    def _find_direct_evidence_match(self, norm_path: str, evidences: List[BehaviorEvidence]) -> Optional[BehaviorEvidence]:
        """Check if path matches evidence sources directly."""
        for ev in evidences:
            if ev.source_path:
                norm_ev_path = self.normalize_path(ev.source_path)
                if norm_ev_path in norm_path:
                    return ev
        return None

    def _is_path_suffix_match(self, norm_path: str, slug: str, evidences: List[BehaviorEvidence]) -> bool:
        """Check if path suffix matches behavior slugs or evidence suffixes."""
        clean_slug = slug.replace("-", "/")
        if norm_path.endswith(clean_slug) or norm_path.endswith(slug):
            return True
        for ev in evidences:
            if ev.source_path:
                norm_ev = self.normalize_path(ev.source_path)
                if norm_path.endswith(norm_ev):
                    return True
        return False

    def _is_route_page_module_match(self, norm_path: str, b_name: str, b_slug: str) -> bool:
        """Matches structural indicators (route patterns, pages structures, modules structure)."""
        b_name_clean = b_name.replace(" ", "")
        b_slug_clean = b_slug.replace("-", "")

        # Route pattern: api/auth, api/reset-password
        if "api/" in norm_path or "routes/" in norm_path or "route." in norm_path:
            if b_slug in norm_path or b_slug_clean in norm_path or b_name_clean in norm_path:
                return True

        # Page pattern: pages/signup, app/login
        if "pages/" in norm_path or "app/" in norm_path:
            if b_slug in norm_path or b_slug_clean in norm_path or b_name_clean in norm_path:
                return True

        # Module pattern: modules/users/signup.ts
        if "modules/" in norm_path:
            if b_slug in norm_path or b_slug_clean in norm_path or b_name_clean in norm_path:
                return True

        return False

    def _find_meaningful_token_matches(self, path_tokens: Set[str], behavior: Behavior) -> List[str]:
        """Find meaningful tokens matched against behavior descriptors (excluding generics)."""
        b_tokens = set(self.tokenize_string(behavior.name) + self.tokenize_string(behavior.slug)) - self.GENERIC_TOKENS
        matched = list(path_tokens.intersection(b_tokens))
        return matched

    def _find_synonym_matches(self, path_tokens: Set[str], b_name: str) -> List[str]:
        """Find matching terms from domain alias synonyms."""
        matched = []
        for alias, synonyms in self.ALIAS_SYNONYMS.items():
            if alias in b_name:
                for syn in synonyms:
                    if syn in path_tokens:
                        matched.append(syn)
        return matched

    def _find_journey_expansion_match(self, path_tokens: Set[str], journeys: List[Journey]) -> Optional[Journey]:
        """Find if path tokens match parent user journeys."""
        for journey in journeys:
            j_tokens = set(self.tokenize_string(journey.name)) - self.GENERIC_TOKENS
            if path_tokens.intersection(j_tokens):
                return journey
        return None

    def _build_behavior_to_journeys_map(
        self,
        journey_behaviors: List[JourneyBehavior],
        journeys: List[Journey],
    ) -> Dict[str, List[Journey]]:
        """Map behaviors to associated Journeys."""
        b_map = {}
        journey_dict = {str(j.id): j for j in journeys}

        for jb in journey_behaviors:
            b_id = str(jb.behavior_id)
            j_id = str(jb.journey_id)
            if b_id not in b_map:
                b_map[b_id] = []
            if j_id in journey_dict:
                b_map[b_id].append(journey_dict[j_id])

        return b_map
