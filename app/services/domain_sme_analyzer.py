from typing import Dict, Any, List, Optional, Set
import re
from app.models.project_context_index import ProjectContextIndex

# Define the standard clusters
STANDARD_CLUSTERS = {
    "signup": ["signup", "sign-up", "register", "registration", "onboarding"],
    "login": ["login", "signin", "sign-in", "auth", "session", "token", "jwt"],
    "password reset": ["reset-password", "reset_password", "forgot-password", "forgot_password", "password/reset", "password-reset", "recovery", "recover"],
    "checkout": ["checkout", "payment", "stripe", "checkout-form", "pay"],
    "subscription": ["subscription", "subscribe", "plan", "invoice", "billing"],
    "notifications": ["notification", "notify", "email", "mail", "sms", "alert"],
    "profile/account": ["profile", "account", "user-profile", "avatar", "settings/profile"],
    "admin/settings": ["admin", "settings", "control-panel", "configuration", "system-settings"]
}

# Construct canonical maps
CANONICAL_CLUSTER_MAP = {}
for cluster_key, keywords in STANDARD_CLUSTERS.items():
    for kw in keywords:
        CANONICAL_CLUSTER_MAP[kw.lower()] = cluster_key
        # Cleaned version without non-alphanumeric characters
        clean_kw = re.sub(r'[^a-z0-9]', '', kw.lower())
        CANONICAL_CLUSTER_MAP[clean_kw] = cluster_key

class DomainSMEAnalyzer:
    """
    DomainSMEAnalyzer learns project-specific vocabulary dynamically.
    Learns deterministic token clusters, maintains repository-specific vocabulary,
    and facilitates token matching for recommendations.
    """

    @classmethod
    def get_canonical_cluster(cls, term: str) -> Optional[str]:
        if not term:
            return None
        term_lower = term.lower().strip()
        
        # 1. Substring matching of standard keywords (highest priority)
        # Sort keywords by length descending so that longer/more specific keywords match first
        all_keywords = []
        for cluster_key, keywords in STANDARD_CLUSTERS.items():
            for kw in keywords:
                all_keywords.append((kw.lower(), cluster_key))
        
        all_keywords.sort(key=lambda x: len(x[0]), reverse=True)
        
        for kw, cluster_key in all_keywords:
            clean_kw = re.sub(r'[^a-z0-9]', '', kw)
            clean_term = re.sub(r'[^a-z0-9]', '', term_lower)
            if kw in term_lower or (len(clean_kw) > 3 and clean_kw in clean_term):
                return cluster_key
                
        # 2. Split into tokens and look up individual tokens or map them
        cleaned = re.sub(r'\.(py|js|ts|tsx|html|css|json|yaml|yml)$', '', term_lower)
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', cleaned)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1).lower()
        tokens = [t for t in re.split(r'[^a-zA-Z0-9]', s2) if len(t) > 1]
        
        votes = {}
        for t in tokens:
            if t in CANONICAL_CLUSTER_MAP:
                cluster = CANONICAL_CLUSTER_MAP[t]
                votes[cluster] = votes.get(cluster, 0) + 1
            else:
                for kw, cluster_key in all_keywords:
                    if t == kw or (len(t) > 3 and t in kw) or (len(kw) > 3 and kw in t):
                        votes[cluster_key] = votes.get(cluster_key, 0) + 1
                        
        if votes:
            return max(votes, key=votes.get)
            
        return None

    @classmethod
    def match_terms(cls, term_a: str, term_b: str) -> bool:
        """
        Determines if two terms reside in the same feature/synonym cluster.
        """
        if not term_a or not term_b:
            return False
            
        cluster_a = cls.get_canonical_cluster(term_a)
        cluster_b = cls.get_canonical_cluster(term_b)
        
        if cluster_a and cluster_b:
            return cluster_a == cluster_b
            
        # Fallback to token overlap
        tokens_a = {t for t in re.split(r'[^a-zA-Z0-9]', term_a.lower()) if len(t) > 2}
        tokens_b = {t for t in re.split(r'[^a-zA-Z0-9]', term_b.lower()) if len(t) > 2}
        
        generic = {"test", "tests", "spec", "specs", "service", "services", "class", "helper", "helpers", "utils", "util"}
        tokens_a -= generic
        tokens_b -= generic
        
        if tokens_a and tokens_b:
            return len(tokens_a.intersection(tokens_b)) > 0
            
        return False

    @classmethod
    def analyze(
        cls,
        context_index: Optional[ProjectContextIndex],
        changed_files: List[str],
        pr_title: str,
        test_cases: List[Any] = None
    ) -> Dict[str, Any]:
        """
        Collects vocabulary from context index, changed files, PR title, and test cases.
        Learns synonyms and builds a deterministic DomainVocabulary structure.
        """
        domain_terms_set: Set[str] = set()
        feature_aliases: Dict[str, str] = {}
        test_term_map: Dict[str, List[str]] = {}

        # Initialize test_term_map lists for all standard clusters to ensure they exist
        for key in STANDARD_CLUSTERS:
            test_term_map[key] = []

        # 1. Process files (changed files & files in context index)
        all_files = set(changed_files or [])
        if context_index:
            # Gather files from context index
            if context_index.user_journeys:
                for journey in context_index.user_journeys:
                    all_files.update(journey.get("source_files", []))
            if context_index.domains:
                for domain in context_index.domains:
                    all_files.update(domain.get("source_files", []))
            if context_index.routes:
                # Add route names as well to domain terms
                for r in context_index.routes:
                    if isinstance(r, dict):
                        route_name = r.get("path") or r.get("name")
                    else:
                        route_name = str(r)
                    if route_name:
                        domain_terms_set.add(route_name)
                        cluster = cls.get_canonical_cluster(route_name)
                        if cluster:
                            domain_terms_set.add(cluster)

        # Process each file to extract folder name and file name
        for file_path in sorted(list(all_files)):
            # Extract domain terms from folders/filenames
            parts = re.split(r'[^a-zA-Z0-9]', file_path)
            for p in parts:
                if len(p) > 2 and p.lower() not in {"src", "app", "tests", "test"}:
                    domain_terms_set.add(p.lower())

            cluster = cls.get_canonical_cluster(file_path)
            if cluster:
                feature_aliases[file_path] = cluster
                domain_terms_set.add(cluster)

        # 2. Process PR title
        if pr_title:
            title_parts = re.split(r'[^a-zA-Z0-9]', pr_title)
            for tp in title_parts:
                if len(tp) > 2:
                    domain_terms_set.add(tp.lower())
            title_cluster = cls.get_canonical_cluster(pr_title)
            if title_cluster:
                domain_terms_set.add(title_cluster)

        # 3. Process test cases to populate test_term_map
        test_cases_list = test_cases or []
        for tc in test_cases_list:
            # We can have SQLAlchemy objects or dictionaries
            test_name = None
            suite_name = None
            stable_id = None
            
            if isinstance(tc, dict):
                test_name = tc.get("test_name")
                suite_name = tc.get("suite_name")
                stable_id = tc.get("stable_identity")
            else:
                test_name = getattr(tc, "test_name", None)
                suite_name = getattr(tc, "suite_name", None)
                stable_id = getattr(tc, "stable_identity", None)
            
            if not stable_id:
                # Fallback to test_name
                stable_id = test_name or "unknown_test"

            # Add test components to domain terms
            if test_name:
                parts = re.split(r'[^a-zA-Z0-9]', test_name)
                for p in parts:
                    if len(p) > 2 and p.lower() not in {"test"}:
                        domain_terms_set.add(p.lower())
            if suite_name:
                parts = re.split(r'[^a-zA-Z0-9]', suite_name)
                for p in parts:
                    if len(p) > 2 and p.lower() not in {"tests", "test"}:
                        domain_terms_set.add(p.lower())

            # Identify the cluster for the test case
            tc_cluster = cls.get_canonical_cluster(stable_id)
            if not tc_cluster and test_name:
                tc_cluster = cls.get_canonical_cluster(test_name)
            
            if tc_cluster:
                if tc_cluster not in test_term_map:
                    test_term_map[tc_cluster] = []
                if stable_id not in test_term_map[tc_cluster]:
                    test_term_map[tc_cluster].append(stable_id)

        # Add synonyms list based on standard clusters but filtered/sorted
        synonyms = []
        for cluster_key, terms in STANDARD_CLUSTERS.items():
            synonyms.append({
                "cluster": cluster_key,
                "terms": sorted(terms)
            })

        # Ensure all test_term_map lists are sorted for determinism
        for k in test_term_map:
            test_term_map[k] = sorted(test_term_map[k])

        # Return structured DomainVocabulary
        return {
            "domain_terms": sorted(list(domain_terms_set)),
            "synonyms": sorted(synonyms, key=lambda x: x["cluster"]),
            "feature_aliases": dict(sorted(feature_aliases.items())),
            "test_term_map": dict(sorted(test_term_map.items()))
        }
