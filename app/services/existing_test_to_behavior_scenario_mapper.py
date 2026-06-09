from typing import List, Dict, Any, Optional, Set
import re

from app.models.behavior import Behavior
from app.models.behavior_scenario import BehaviorScenario
from app.models.test_result import TestCase
from app.models.test_coverage_link import TestCoverageLink


class ExistingTestToBehaviorScenarioMapper:
    """Maps ingested JUnit tests to database behavior scenarios to reduce false 'missing coverage'."""

    # Common generic terms to filter from matching
    GENERIC_TERMS = {
        "should", "can", "allows", "accepts", "test", "tests", "verify", "validates", 
        "assert", "asserts", "it", "when", "then", "given", "spec", "specs", "run", 
        "runs", "class", "method"
    }

    # Keyword synonyms to normalize mapping
    SYNONYM_MAP = {
        "signup": ["register", "onboarding", "sign-up", "create-account"],
        "register": ["signup", "onboarding", "sign-up", "create-account"],
        "login": ["signin", "sign-in", "auth", "session"],
        "signin": ["login", "sign-in", "auth", "session"],
        "password reset": ["reset-password", "forgot-password", "password-recovery", "recovery", "auth"],
        "reset password": ["password-reset", "forgot-password", "password-recovery", "recovery", "auth"],
        "checkout": ["payment", "stripe", "checkout", "pay", "cart"],
        "payment": ["checkout", "stripe", "pay", "charge"],
    }

    def __init__(self, db: Optional[Any] = None):
        """Initialize mapper with optional database session."""
        self.db = db

    def tokenize(self, text: str) -> List[str]:
        """Tokenize snake_case, camelCase, kebab-case and split into clean lowercased words."""
        # Convert camelCase to space separated
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', text)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1)
        # Split and lowercase
        tokens = re.split(r'[^a-zA-Z0-9]', s2.lower())
        return [t for t in tokens if t and len(t) > 1]

    def map_tests_to_scenarios(
        self,
        test_cases: List[TestCase],
        behaviors: List[Behavior],
        scenarios: List[BehaviorScenario],
        test_coverage_links: Optional[List[TestCoverageLink]] = None,
        domain_vocab: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Map ingested test cases to scenarios in the database."""
        mappings = []
        coverage_links = test_coverage_links or []

        # Create fast lookup tables
        behavior_dict = {str(b.id): b for b in behaviors}
        behavior_scenarios_map = {}
        for s in scenarios:
            b_id_str = str(s.behavior_id)
            if b_id_str not in behavior_scenarios_map:
                behavior_scenarios_map[b_id_str] = []
            behavior_scenarios_map[b_id_str].append(s)

        # Build coverage file to behavior mapping
        file_to_behavior_map = {}
        if self.db:
            # Load behavior evidence sources from DB if available
            from app.models.behavior_evidence import BehaviorEvidence
            evidences = self.db.query(BehaviorEvidence).all()
            for ev in evidences:
                if ev.source_path:
                    file_to_behavior_map[ev.source_path.lower()] = str(ev.behavior_id)

        # Process each test case against each scenario
        for tc in test_cases:
            tc_identity_lower = tc.stable_identity.lower()
            tc_tokens = set(self.tokenize(tc_identity_lower)) - self.GENERIC_TERMS

            for behavior in behaviors:
                b_id_str = str(behavior.id)
                b_name_lower = behavior.name.lower()
                b_tokens = set(self.tokenize(b_name_lower)) - self.GENERIC_TERMS

                b_scenarios = behavior_scenarios_map.get(b_id_str, [])
                for scenario in b_scenarios:
                    s_title_lower = scenario.title.lower()
                    s_tokens = set(self.tokenize(s_title_lower)) - self.GENERIC_TERMS

                    # Match stages:
                    
                    # Stage 1: Explicit test name term matching
                    matched_terms = list(tc_tokens.intersection(s_tokens))
                    
                    # Resolve synonym overlap (e.g., test has 'signup', scenario has 'register')
                    synonym_matched = []
                    for t in tc_tokens:
                        for syn_key, syns in self.SYNONYM_MAP.items():
                            if syn_key in s_title_lower and t in syns:
                                synonym_matched.append(t)
                                matched_terms.append(t)

                    matched_terms = list(set(matched_terms))

                    # 1. Determine Confidence & Source Signals
                    confidence = "LOW"
                    source_signal = "TEST_NAME_MAPPING"
                    reason_parts = []

                    # High confidence: strong scenario term match + domain match
                    has_domain_overlap = len(tc_tokens.intersection(b_tokens)) > 0 or any(k in tc_identity_lower for k in b_tokens)
                    if not has_domain_overlap:
                        # Check synonyms
                        for syn_key, syns in self.SYNONYM_MAP.items():
                            if syn_key in b_name_lower and any(syn in tc_tokens for syn in syns):
                                has_domain_overlap = True
                                break

                    scenario_term_overlap_count = len([t for t in matched_terms if t in s_tokens])

                    # Verify against coverage graphs if available
                    has_coverage_trace = False
                    related_links = [l for l in coverage_links if l.test_identifier == tc.stable_identity]
                    if related_links:
                        for link in related_links:
                            link_file_lower = link.file_path.lower()
                            # Check if the covered file belongs to this behavior's evidence
                            if link_file_lower in file_to_behavior_map and file_to_behavior_map[link_file_lower] == b_id_str:
                                has_coverage_trace = True
                                break

                    # Stage 2: Coverage graph trace matching
                    if has_coverage_trace:
                        source_signal = "COVERAGE_GRAPH"
                        reason_parts.append(f"Ingested test coverage graph traces directly to behavior source files")

                    if scenario_term_overlap_count >= 3 and has_domain_overlap:
                        confidence = "HIGH"
                        reason_parts.append(f"Strong semantic token overlap ({scenario_term_overlap_count} terms) matching behavior context")
                    elif scenario_term_overlap_count >= 2 and has_domain_overlap:
                        confidence = "MEDIUM"
                        reason_parts.append("Moderate term overlap matching both behavior domain and scenario descriptor")
                    elif scenario_term_overlap_count >= 1:
                        confidence = "LOW"
                        reason_parts.append("Broad token overlap with scenario descriptor; matching confidence low")

                    if len(reason_parts) > 0:
                        reason = " / ".join(reason_parts)
                        
                        # Save mapping
                        mappings.append({
                            "test_identifier": tc.stable_identity,
                            "behavior_id": b_id_str,
                            "behavior_scenario_id": str(scenario.id),
                            "confidence": confidence,
                            "matched_terms": matched_terms,
                            "reason": reason,
                            "source_signal": source_signal,
                        })

        return mappings
