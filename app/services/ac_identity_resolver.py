import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

def normalize_ac_text(text: str) -> str:
    """Normalize AC text by removing prefixes, lowercasing, and stripping punctuation."""
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # Trim
    text = text.strip()
    # Remove leading numbering/prefixes like "7.", "AC-07", "07 -", "1 -", "AC 07 -", "1. ", "AC 01 - "
    text = re.sub(r'^(?:ac[- ]*\d+|\d+)[-.\s]*', '', text)
    # Remove repeated spaces
    text = re.sub(r'\s+', ' ', text)
    # Remove punctuation noise, keeping letters and digits
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Again remove repeated spaces and trim
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def normalize_test_name(name: str) -> str:
    """Normalize JUnit test case names by handling camelCase/snake_case and lowercasing."""
    if not name:
        return ""
    # Handle camelCase
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', name)
    # Lowercase and replace non-alphanumeric with spaces
    name = name.lower()
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    # Remove repeated spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def build_ac_canonical_key(ac) -> str:
    """Build a stable deterministic key for an acceptance criterion."""
    text = getattr(ac, "text", None) or getattr(ac, "title", None)
    if not text and isinstance(ac, dict):
        text = ac.get("text") or ac.get("title") or ""
    if not text:
        text = ""
    
    label = getattr(ac, "label", None) or getattr(ac, "readable_id", None)
    if not label and isinstance(ac, dict):
        label = ac.get("label") or ac.get("readable_id") or ""
    if not label:
        label = ""
        
    norm_label = ""
    if label:
        match = re.search(r'(\d+)', str(label))
        if match:
            norm_label = f"ac_{int(match.group(1)):02d}"
            
    norm_text = normalize_ac_text(text)
    slug = re.sub(r'\s+', '_', norm_text).strip('_')
    
    if norm_label:
        return f"{norm_label}_{slug}"
    return slug

@dataclass
class ResolvedACIdentity:
    database_ac_id: Optional[str]
    source_ac_number: Optional[int]
    normalized_title: str
    canonical_key: str
    confidence: float
    matched_by: str

def extract_ac_number(val) -> Optional[int]:
    """Safely extract integer AC number from various representation types."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    val_str = str(val).strip()
    match = re.search(r'(?:ac[- ]*)?(\d+)', val_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def get_attr(obj, attr_names, default=None):
    """Fallback helper to get attribute or dictionary value from object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        for name in attr_names:
            if obj.get(name) is not None:
                return obj[name]
        return default
    for name in attr_names:
        if hasattr(obj, name) and getattr(obj, name) is not None:
            return getattr(obj, name)
    return default

def get_semantic_overlap_score(str1: str, str2: str) -> float:
    """Calculate ratio of overlapping important tokens between two strings."""
    words1 = set(str1.split())
    words2 = set(str2.split())
    
    stopwords = {
        'is', 'at', 'least', 'a', 'the', 'an', 'and', 'or', 'in', 'on', 'of', 'for', 
        'with', 'to', 'be', 'should', 'must', 'if', 'when', 'than', 'are', 'was', 
        'were', 'been', 'has', 'have', 'had', 'do', 'does', 'did', 'by', 'from', 
        'about', 'as', 'but'
    }
    
    important1 = {w for w in words1 if w not in stopwords and len(w) > 2}
    important2 = {w for w in words2 if w not in stopwords and len(w) > 2}
    
    if not important1 or not important2:
        return 0.0
        
    intersection = important1.intersection(important2)
    return len(intersection) / min(len(important1), len(important2))

def resolve_ac_identity(ac, candidates) -> ResolvedACIdentity:
    """Resolve a target AC node/object to database candidates using priority rules."""
    ac_id = get_attr(ac, ['database_ac_id', 'databaseAcId', 'id', 'requirement_id', 'requirementId'])
    ac_title = get_attr(ac, ['text', 'title', 'fullText', 'full_text']) or ""
    ac_num = extract_ac_number(get_attr(ac, ['source_number', 'source_ac_number', 'sourceAcNumber']))
    if ac_num is None:
        ac_num = extract_ac_number(get_attr(ac, ['label', 'readable_id', 'readableId']))
    ac_canonical = get_attr(ac, ['canonical_key', 'canonical_ac_key', 'canonicalKey'])
    
    norm_ac_title = normalize_ac_text(ac_title)
    if not ac_canonical and norm_ac_title:
        ac_canonical = build_ac_canonical_key(ac)

    # Priority 1: Exact database AC ID match
    if ac_id:
        for cand in candidates:
            cand_id = get_attr(cand, ['database_ac_id', 'databaseAcId', 'id', 'requirement_id', 'requirementId'])
            if cand_id and str(cand_id) == str(ac_id):
                return ResolvedACIdentity(
                    database_ac_id=str(cand_id),
                    source_ac_number=extract_ac_number(get_attr(cand, ['source_number', 'source_ac_number', 'sourceAcNumber'])),
                    normalized_title=normalize_ac_text(get_attr(cand, ['text', 'title', 'fullText', 'full_text']) or ""),
                    canonical_key=build_ac_canonical_key(cand),
                    confidence=1.0,
                    matched_by="database_ac_id"
                )

    # Priority 2: Exact AC number match
    if ac_num is not None:
        for cand in candidates:
            cand_num = extract_ac_number(get_attr(cand, ['source_number', 'source_ac_number', 'sourceAcNumber']))
            if cand_num is None:
                cand_num = extract_ac_number(get_attr(cand, ['label', 'readable_id', 'readableId']))
            if cand_num is not None and cand_num == ac_num:
                cand_id = get_attr(cand, ['database_ac_id', 'databaseAcId', 'id', 'requirement_id', 'requirementId'])
                return ResolvedACIdentity(
                    database_ac_id=str(cand_id) if cand_id else None,
                    source_ac_number=cand_num,
                    normalized_title=normalize_ac_text(get_attr(cand, ['text', 'title', 'fullText', 'full_text']) or ""),
                    canonical_key=build_ac_canonical_key(cand),
                    confidence=0.9,
                    matched_by="source_ac_number"
                )

    # Priority 3: Normalized title exact match
    if norm_ac_title:
        for cand in candidates:
            cand_title = get_attr(cand, ['text', 'title', 'fullText', 'full_text']) or ""
            norm_cand_title = normalize_ac_text(cand_title)
            if norm_cand_title and norm_cand_title == norm_ac_title:
                cand_id = get_attr(cand, ['database_ac_id', 'databaseAcId', 'id', 'requirement_id', 'requirementId'])
                return ResolvedACIdentity(
                    database_ac_id=str(cand_id) if cand_id else None,
                    source_ac_number=extract_ac_number(get_attr(cand, ['source_number', 'source_ac_number', 'sourceAcNumber'])),
                    normalized_title=norm_cand_title,
                    canonical_key=build_ac_canonical_key(cand),
                    confidence=0.85,
                    matched_by="normalized_title_exact"
                )

    # Priority 4: Semantic token overlap match
    best_cand = None
    best_score = 0.0
    if norm_ac_title:
        for cand in candidates:
            cand_title = get_attr(cand, ['text', 'title', 'fullText', 'full_text']) or ""
            norm_cand_title = normalize_ac_text(cand_title)
            score = get_semantic_overlap_score(norm_ac_title, norm_cand_title)
            if score > best_score:
                best_score = score
                best_cand = cand
                
    if best_score >= 0.5 and best_cand is not None:
        cand_id = get_attr(best_cand, ['database_ac_id', 'databaseAcId', 'id', 'requirement_id', 'requirementId'])
        return ResolvedACIdentity(
            database_ac_id=str(cand_id) if cand_id else None,
            source_ac_number=extract_ac_number(get_attr(best_cand, ['source_number', 'source_ac_number', 'sourceAcNumber'])),
            normalized_title=normalize_ac_text(get_attr(best_cand, ['text', 'title', 'fullText', 'full_text']) or ""),
            canonical_key=build_ac_canonical_key(best_cand),
            confidence=0.7 + (best_score * 0.15),
            matched_by=f"semantic_token_overlap_score_{best_score:.2f}"
        )

    # Priority 5: Linked test name normalization match
    ac_tests = get_attr(ac, ['linked_existing_tests', 'matched_test_ids', 'verifying_tests']) or []
    if ac_tests:
        for test_item in ac_tests:
            test_name = test_item if isinstance(test_item, str) else get_attr(test_item, ['title', 'name']) or ""
            norm_test = normalize_test_name(test_name)
            if norm_test:
                for cand in candidates:
                    cand_title = get_attr(cand, ['text', 'title', 'fullText', 'full_text']) or ""
                    norm_cand_title = normalize_ac_text(cand_title)
                    if norm_cand_title == norm_test or get_semantic_overlap_score(norm_test, norm_cand_title) >= 0.6:
                        cand_id = get_attr(cand, ['database_ac_id', 'databaseAcId', 'id', 'requirement_id', 'requirementId'])
                        return ResolvedACIdentity(
                            database_ac_id=str(cand_id) if cand_id else None,
                            source_ac_number=extract_ac_number(get_attr(cand, ['source_number', 'source_ac_number', 'sourceAcNumber'])),
                            normalized_title=norm_cand_title,
                            canonical_key=build_ac_canonical_key(cand),
                            confidence=0.65,
                            matched_by="linked_test_name_normalization"
                        )

    # Fallback to self representation
    return ResolvedACIdentity(
        database_ac_id=str(ac_id) if ac_id else None,
        source_ac_number=ac_num,
        normalized_title=norm_ac_title,
        canonical_key=ac_canonical or "",
        confidence=0.5 if ac_id else 0.1,
        matched_by="self"
    )
