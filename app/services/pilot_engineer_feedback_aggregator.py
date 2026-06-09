import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationEngineerFeedback
)

logger = logging.getLogger("veriscope.pilot_engineer_feedback_aggregator")

class PilotEngineerFeedbackAggregator:
    """
    PilotEngineerFeedbackAggregator
    ===============================
    Aggregates developer recommendation feedback across the pilot window.
    Strictly preserves raw, append-only lineage without sentiment manipulation
    while safely filtering out abusive or noisy feedback to collect representative,
    anonymized developer quotes.
    """

    @classmethod
    def _is_safe_quote(cls, text: str) -> bool:
        """
        Screen quotes for length, generic placeholders, excessive capitalized shouting,
        and abusive or vulgar language.
        """
        if not text:
            return False
            
        cleaned = text.strip()
        if len(cleaned) < 5:
            return False
            
        # Screen generic placeholders
        text_lower = cleaned.lower()
        if text_lower in ("none", "n/a", "test", "null", "asdf", "qwer", "testing"):
            return False
            
        # Screen excessive shouting (shouting length > 10 chars is ruled out as noisy)
        if cleaned.isupper() and len(cleaned) > 10:
            return False
            
        # Screen abusive/noisy/vulgar keywords
        ABUSIVE_KEYWORDS = {
            "fuck", "shit", "bitch", "asshole", "crap", "damn", "garbage", "trash",
            "idiot", "stupid", "dumb", "hate", "useless", "wtf", "sucks", "suck",
            "pathetic", "horrible", "terrible", "crap", "fool", "bastard"
        }
        
        # Replace punctuation to check precise word matches
        normalized_text = text_lower.replace("!", "").replace("?", "").replace(".", "").replace(",", "")
        words = normalized_text.split()
        
        for word in words:
            if word in ABUSIVE_KEYWORDS:
                return False
                
        return True

    @classmethod
    def aggregate_feedback(
        cls,
        db: Session,
        repository_ids: List[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Aggregate developer recommendation feedback deterministically and safely.
        """
        # Return empty metrics package if no repositories enrolled
        if not repository_ids:
            return {
                "reporting_window_start": start_date.isoformat(),
                "reporting_window_end": end_date.isoformat(),
                "total_feedback_count": 0,
                "useful_feedback_count": 0,
                "missing_tests_feedback_count": 0,
                "unclear_reasoning_feedback_count": 0,
                "too_many_tests_feedback_count": 0,
                "not_useful_feedback_count": 0,
                "representative_quotes": [],
                "excluded_noise_count": 0
            }

        # 1. Fetch all runs within time window and repository scope
        runs = db.query(RecommendationRun).filter(
            RecommendationRun.repository_id.in_(repository_ids),
            RecommendationRun.created_at >= start_date,
            RecommendationRun.created_at <= end_date
        ).all()
        run_ids = [run.id for run in runs]

        # 2. Fetch all outcomes for these runs
        outcomes = []
        if run_ids:
            outcomes = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id.in_(run_ids)
            ).all()
        outcome_ids = [outcome.id for outcome in outcomes]

        # 3. Fetch all engineer feedback records linked to these outcomes
        feedbacks = []
        if outcome_ids:
            feedbacks = db.query(RecommendationEngineerFeedback).filter(
                RecommendationEngineerFeedback.recommendation_outcome_id.in_(outcome_ids)
            ).order_by(RecommendationEngineerFeedback.created_at.asc()).all()

        # Initialize counts
        total_feedback_count = len(feedbacks)
        useful_feedback_count = 0
        missing_tests_feedback_count = 0
        unclear_reasoning_feedback_count = 0
        too_many_tests_feedback_count = 0
        not_useful_feedback_count = 0

        # Collect safe representative anonymized quotes
        representative_quotes = []
        excluded_noise_count = 0
        seen_quotes = set()

        for fb in feedbacks:
            fb_type = fb.feedback_type.upper()
            
            # Increment raw type counts without modification
            if fb_type == "USEFUL":
                useful_feedback_count += 1
            elif fb_type == "MISSING_TESTS":
                missing_tests_feedback_count += 1
            elif fb_type == "UNCLEAR_REASONING":
                unclear_reasoning_feedback_count += 1
            elif fb_type == "TOO_MANY_TESTS":
                too_many_tests_feedback_count += 1
            elif fb_type == "NOT_USEFUL":
                not_useful_feedback_count += 1

            # Process quote safety and anonymization
            text = fb.feedback_text
            if text:
                if cls._is_safe_quote(text):
                    cleaned = text.strip()
                    if cleaned not in seen_quotes:
                        if len(representative_quotes) < 3:
                            representative_quotes.append(cleaned)
                            seen_quotes.add(cleaned)
                else:
                    excluded_noise_count += 1

        return {
            "reporting_window_start": start_date.isoformat(),
            "reporting_window_end": end_date.isoformat(),
            "total_feedback_count": total_feedback_count,
            "useful_feedback_count": useful_feedback_count,
            "missing_tests_feedback_count": missing_tests_feedback_count,
            "unclear_reasoning_feedback_count": unclear_reasoning_feedback_count,
            "too_many_tests_feedback_count": too_many_tests_feedback_count,
            "not_useful_feedback_count": not_useful_feedback_count,
            "representative_quotes": representative_quotes,
            "excluded_noise_count": excluded_noise_count
        }
