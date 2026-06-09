import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.schemas.recommendation import SkippedSummary

class SkippedReasoningService:
    @staticmethod
    def build_skipped_summary(
        db: Session,
        repository_id: uuid.UUID,
        recommended_test_ids: List[str],
        all_test_ids: List[str],
        evidence_quality: str = "HIGH",
        max_examples: int = 3
    ) -> SkippedSummary:
        """
        Build bounded skipped area reasoning, compactly summarizing skipped areas with cautious language under weak evidence.
        """
        rec_set = set(recommended_test_ids)
        skipped_identities = sorted(list(set(all_test_ids) - rec_set))
        skipped_count = len(skipped_identities)

        if skipped_count == 0:
            skipped_reason_summary = "No tests were skipped."
            top_skipped_examples = []
        else:
            top_skipped_examples = skipped_identities[:max_examples]
            
            # Determine explanation language based on evidence quality
            if evidence_quality == "HIGH":
                skipped_reason_summary = (
                    f"Skipped {skipped_count} stable tests that have no direct or transitive intersection "
                    f"with the changes. Safe to skip under high trust evidence quality."
                )
            elif evidence_quality == "MODERATE":
                skipped_reason_summary = (
                    f"Skipped {skipped_count} tests: Not selected by current evidence. "
                    f"No direct or dependency mapping found. Operating under moderate trust evidence quality."
                )
            else:  # LOW or UNKNOWN quality
                skipped_reason_summary = (
                    f"Skipped {skipped_count} tests: Not selected by current evidence. "
                    f"No direct or dependency mapping found. Caution: Skipped under low or unknown trust evidence quality."
                )

        return SkippedSummary(
            skipped_count=skipped_count,
            skipped_reason_summary=skipped_reason_summary,
            top_skipped_examples=top_skipped_examples
        )
