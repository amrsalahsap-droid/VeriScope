"""Deduplication Service - Filters recommendations overlapping with existing tests."""

import string
import logging
import re
from typing import List, Set, Any

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "with", "for", "of", "to", "in", "on", "at", 
    "by", "from", "and", "or", "but", "not", "this", "that", "these", "those", "password", 
    "test", "should", "verify", "reject", "rejection", "accept", "acceptance", "validation", 
    "validate", "fails", "passes", "incorrect", "correct", "invalid", "valid"
}

def _normalize_and_tokenize(text: str) -> Set[str]:
    """Lowercase, strip punctuation, tokenize, and filter out stop words."""
    if not text:
        return set()
    # Replace punctuation with spaces
    translator = str.maketrans(string.punctuation, ' ' * len(string.punctuation))
    text_clean = text.translate(translator).lower()
    # Tokenize
    words = text_clean.split()
    # Filter out stop words and short words
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}

def deduplicate_recommendations(recommendations: List[Any], existing_tests: Set[str]) -> List[Any]:
    """Filters recommendations overlapping with existing passed tests using Jaccard similarity."""
    if not recommendations:
        return []
    if not existing_tests:
        return recommendations

    filtered = []
    
    # Process existing test tokens
    test_tokens_list = []
    for test in existing_tests:
        test_str = str(test)
        # Split snake_case and camelCase
        test_words = test_str.replace('_', ' ').replace('-', ' ')
        test_words = re.sub(r'([a-z])([A-Z])', r'\1 \2', test_words)
        test_tokens_list.append((test_str, _normalize_and_tokenize(test_words)))

    for rec in recommendations:
        ds = getattr(rec, "detailed_scenario", None)
        text_to_analyze = ""
        if ds:
            text_to_analyze += f" {getattr(ds, 'test_input', '')} {getattr(ds, 'expected_result', '')}"
        
        text_to_analyze += f" {getattr(rec, 'title', '')} {getattr(rec, 'suggested_test_scenario', '')}"
        
        rec_tokens = _normalize_and_tokenize(text_to_analyze)
        if not rec_tokens:
            filtered.append(rec)
            continue
            
        is_duplicate = False
        matching_test = None
        best_similarity = 0.0
        
        for test_name, test_tokens in test_tokens_list:
            if not test_tokens:
                continue
            intersection = rec_tokens.intersection(test_tokens)
            union = rec_tokens.union(test_tokens)
            similarity = len(intersection) / len(union) if union else 0.0
            
            if similarity > best_similarity:
                best_similarity = similarity
                matching_test = test_name
                
            if similarity > 0.70:
                is_duplicate = True
                break
                
        if is_duplicate:
            logger.info(f"[Deduplication] Dropped recommendation '{rec.title}' as duplicate of existing test '{matching_test}' (similarity: {best_similarity:.2%})")
        else:
            filtered.append(rec)
            
    return filtered
