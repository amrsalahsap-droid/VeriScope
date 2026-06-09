from typing import List, Set
import re
from pathlib import Path


class Tokenizer:
    """Deterministic tokenizer for semantic indexing."""
    
    # Common stopwords to filter out
    STOPWORDS: Set[str] = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "as", "is", "was", "are", "were", "be", "been", "being", "have", "has",
        "had", "do", "does", "did", "will", "would", "should", "could", "may", "might", "must",
        "can", "this", "that", "these", "those", "it", "its", "they", "them", "their", "there",
        "here", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "just", "also", "now", "then", "once", "if", "else", "while",
    }
    
    # Technical stopwords specific to code
    TECH_STOPWORDS: Set[str] = {
        "src", "lib", "app", "api", "v1", "v2", "index", "main", "default", "base", "core",
        "common", "shared", "util", "utils", "helper", "helpers", "service", "services",
        "controller", "controllers", "model", "models", "view", "views", "component",
        "components", "module", "modules", "package", "packages", "config", "configs",
        "const", "var", "let", "func", "function", "class", "interface", "type", "enum",
        "import", "export", "from", "require", "return", "async", "await", "try", "catch",
        "finally", "throw", "new", "this", "super", "extends", "implements", "public",
        "private", "protected", "static", "readonly", "abstract", "override", "get", "set",
    }
    
    @classmethod
    def tokenize_path(cls, path: str) -> List[str]:
        """Tokenize a file path deterministically."""
        # Convert to lowercase
        path_lower = path.lower()
        
        # Remove file extensions
        path_lower = re.sub(r'\.[a-z0-9]+$', '', path_lower)
        
        # Split by common separators
        tokens = re.split(r'[/\\\-_.]', path_lower)
        
        # Filter out empty strings and stopwords
        tokens = [t for t in tokens if t and t not in cls.STOPWORDS and t not in cls.TECH_STOPWORDS]
        
        # Remove very short tokens (less than 2 chars)
        tokens = [t for t in tokens if len(t) >= 2]
        
        return tokens
    
    @classmethod
    def tokenize_content(cls, content: str) -> List[str]:
        """Tokenize content text deterministically."""
        # Convert to lowercase
        content_lower = content.lower()
        
        # Split by non-alphanumeric characters
        tokens = re.split(r'[^a-z0-9]+', content_lower)
        
        # Filter out empty strings and stopwords
        tokens = [t for t in tokens if t and t not in cls.STOPWORDS and t not in cls.TECH_STOPWORDS]
        
        # Remove very short tokens
        tokens = [t for t in tokens if len(t) >= 2]
        
        return tokens
    
    @classmethod
    def normalize_token(cls, token: str) -> str:
        """Normalize a single token."""
        # Convert to lowercase
        token = token.lower()
        
        # Remove special characters
        token = re.sub(r'[^a-z0-9]', '', token)
        
        return token
    
    @classmethod
    def deduplicate_tokens(cls, tokens: List[str]) -> List[str]:
        """Deduplicate tokens while preserving order."""
        seen = set()
        result = []
        for token in tokens:
            if token not in seen:
                seen.add(token)
                result.append(token)
        return result
    
    @classmethod
    def tokenize(cls, text: str, content: str = None) -> List[str]:
        """Tokenize text with optional content, return normalized unique tokens."""
        # Tokenize path/identifier
        tokens = cls.tokenize_path(text)
        
        # If content provided, tokenize and merge
        if content:
            content_tokens = cls.tokenize_content(content)
            tokens.extend(content_tokens)
        
        # Normalize all tokens
        tokens = [cls.normalize_token(t) for t in tokens]
        
        # Deduplicate
        tokens = cls.deduplicate_tokens(tokens)
        
        return tokens
