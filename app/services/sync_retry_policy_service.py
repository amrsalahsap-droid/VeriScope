"""
Sync Retry Policy Service

Determines retry behavior for sync events with:
- Exponential backoff with jitter
- Error classification
- Retry-after handling
- Max attempts enforcement
"""

import random
from datetime import datetime, timedelta
from typing import Optional, Tuple
from enum import Enum


class ErrorType(Enum):
    """Classification of sync errors."""
    RATE_LIMITED = "RATE_LIMITED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    TEMPORARY_PROVIDER_FAILURE = "TEMPORARY_PROVIDER_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    PERMANENT_PROVIDER_FAILURE = "PERMANENT_PROVIDER_FAILURE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


class SyncRetryPolicyService:
    """Service for calculating retry policy for sync events."""
    
    # Default backoff schedule in seconds
    BACKOFF_SCHEDULE = [
        60,      # attempt 1 → 1 minute
        300,     # attempt 2 → 5 minutes
        900,     # attempt 3 → 15 minutes
        3600,    # attempt 4 → 60 minutes
    ]
    
    MAX_ATTEMPTS = 5  # After 5 attempts, go to DEAD_LETTER
    
    # Jitter percentage (±10%)
    JITTER_PERCENTAGE = 0.10
    
    def __init__(self, enable_jitter: bool = True):
        """
        Initialize retry policy service.
        
        Args:
            enable_jitter: Whether to add jitter to backoff calculations.
                          Set to False for tests to get deterministic results.
        """
        self.enable_jitter = enable_jitter
    
    def calculate_next_retry(
        self,
        attempt_count: int,
        provider: str,
        error_type: Optional[ErrorType] = None,
        retry_after_seconds: Optional[int] = None
    ) -> Tuple[datetime, Optional[ErrorType]]:
        """
        Calculate the next retry time for a sync event.
        
        Args:
            attempt_count: Current attempt count (0-indexed)
            provider: Provider name (TESTRAIL, XRAY, ZEPHYR)
            error_type: Classified error type if known
            retry_after_seconds: Retry-After header value from provider response
            
        Returns:
            Tuple of (next_attempt_at, error_type)
        """
        # If retry_after is provided and valid, use it
        if retry_after_seconds is not None and retry_after_seconds > 0:
            base_delay = retry_after_seconds
        else:
            # Use backoff schedule
            if attempt_count >= len(self.BACKOFF_SCHEDULE):
                # Exceeded schedule, use last value
                base_delay = self.BACKOFF_SCHEDULE[-1]
            else:
                base_delay = self.BACKOFF_SCHEDULE[attempt_count]
        
        # Add jitter if enabled
        if self.enable_jitter:
            jitter_amount = base_delay * self.JITTER_PERCENTAGE
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay_seconds = base_delay + jitter
        else:
            delay_seconds = base_delay
        
        next_attempt_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        return next_attempt_at, error_type
    
    def should_dead_letter(self, attempt_count: int, max_attempts: Optional[int] = None) -> bool:
        """
        Determine if a sync event should go to DEAD_LETTER.
        
        Args:
            attempt_count: Current attempt count
            max_attempts: Override max attempts (uses default if None)
            
        Returns:
            True if should go to DEAD_LETTER
        """
        effective_max = max_attempts or self.MAX_ATTEMPTS
        return attempt_count >= effective_max
    
    def classify_error(
        self,
        error: str,
        http_status: Optional[int] = None,
        error_context: Optional[dict] = None
    ) -> ErrorType:
        """
        Classify an error to determine retry behavior.
        
        Args:
            error: Error message
            http_status: HTTP status code if available
            error_context: Additional error context
            
        Returns:
            Classified error type
        """
        error_lower = error.lower() if error else ""
        
        # Check HTTP status codes first
        if http_status:
            if http_status == 429:
                return ErrorType.RATE_LIMITED
            elif http_status in (401, 403):
                return ErrorType.AUTHENTICATION_FAILED
            elif http_status == 404:
                return ErrorType.PERMANENT_PROVIDER_FAILURE
            elif http_status >= 500:
                return ErrorType.TEMPORARY_PROVIDER_FAILURE
            elif http_status == 400:
                # Check if it's a configuration error
                if any(keyword in error_lower for keyword in [
                    "missing", "required", "invalid", "configuration", "config"
                ]):
                    return ErrorType.CONFIGURATION_ERROR
        
        # Check error message content
        if "rate limit" in error_lower or "too many requests" in error_lower:
            return ErrorType.RATE_LIMITED
        elif any(keyword in error_lower for keyword in [
            "unauthorized", "authentication", "forbidden", "access denied"
        ]):
            return ErrorType.AUTHENTICATION_FAILED
        elif any(keyword in error_lower for keyword in [
            "not found", "does not exist", "404"
        ]):
            return ErrorType.PERMANENT_PROVIDER_FAILURE
        elif any(keyword in error_lower for keyword in [
            "timeout", "connection", "network", "dns", "unreachable"
        ]):
            return ErrorType.NETWORK_FAILURE
        elif any(keyword in error_lower for keyword in [
            "missing", "required", "invalid", "configuration", "config"
        ]):
            return ErrorType.CONFIGURATION_ERROR
        elif any(keyword in error_lower for keyword in [
            "internal server error", "service unavailable", "502", "503", "504"
        ]):
            return ErrorType.TEMPORARY_PROVIDER_FAILURE
        
        return ErrorType.UNKNOWN_FAILURE
    
    def is_retryable(self, error_type: ErrorType) -> bool:
        """
        Determine if an error type is retryable.
        
        Args:
            error_type: Classified error type
            
        Returns:
            True if error is retryable
        """
        retryable_types = {
            ErrorType.RATE_LIMITED,
            ErrorType.TEMPORARY_PROVIDER_FAILURE,
            ErrorType.NETWORK_FAILURE,
            ErrorType.UNKNOWN_FAILURE,
        }
        return error_type in retryable_types
