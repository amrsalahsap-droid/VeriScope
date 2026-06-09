import re
import hashlib
from typing import Optional

class CommentDeduplicationEngine:
    @staticmethod
    def normalize_body(body_text: str) -> str:
        """Normalize the comment body:
        - Normalize line endings (replace \r\n with \n)
        - Stable timestamp handling (replace datetimes with a static placeholder)
        - Trim trailing spaces from each line
        """
        if not body_text:
            return ""
        
        # 1. Normalize line endings
        body = body_text.replace("\r\n", "\n")

        # 2. Stable timestamp handling: locate dynamic datetime strings and replace them
        # Matches formats like:
        # "2026-05-23 21:43:36"
        # "2026-05-23T21:43:36Z"
        # "2026-05-23T21:43:36+03:00"
        datetime_regex = re.compile(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:Z|(?:\+|-)\d{2}:\d{2})?"
        )
        body = datetime_regex.sub("STABLE_TIMESTAMP", body)

        # 3. Trim trailing spaces on each line
        lines = [line.rstrip() for line in body.split("\n")]
        
        # 4. Join and strip leading/trailing whitespace
        return "\n".join(lines).strip()

    @classmethod
    def compute_body_hash(cls, body_text: str) -> str:
        """Compute the deterministic SHA-256 hash of the normalized comment body."""
        normalized = cls.normalize_body(body_text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def should_update_comment(cls, existing_body: Optional[str], new_body: str) -> bool:
        """Compare the normalized body hashes of the existing and new comments.
        Returns True if different, False if identical (deduplicated).
        """
        if not existing_body:
            return True
        
        existing_hash = cls.compute_body_hash(existing_body)
        new_hash = cls.compute_body_hash(new_body)
        
        return existing_hash != new_hash
