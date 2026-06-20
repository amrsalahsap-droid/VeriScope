"""
Tests for Sync Retry Policy Service

Tests retry policy behavior including:
- Backoff schedule
- Jitter (disabled in tests)
- Retry-after handling
- Error classification
- Retryable vs non-retryable errors
"""

import pytest
from datetime import datetime, timedelta
from app.services.sync_retry_policy_service import SyncRetryPolicyService, ErrorType


class TestSyncRetryPolicy:
    """Test sync retry policy service."""
    
    def test_backoff_schedule(self):
        """Test that backoff schedule follows expected intervals."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        # Attempt 0 (first retry) → 1 minute
        next_attempt, _ = policy.calculate_next_retry(0, "TESTRAIL")
        expected = datetime.utcnow() + timedelta(seconds=60)
        assert abs((next_attempt - expected).total_seconds()) < 1
        
        # Attempt 1 → 5 minutes
        next_attempt, _ = policy.calculate_next_retry(1, "TESTRAIL")
        expected = datetime.utcnow() + timedelta(seconds=300)
        assert abs((next_attempt - expected).total_seconds()) < 1
        
        # Attempt 2 → 15 minutes
        next_attempt, _ = policy.calculate_next_retry(2, "TESTRAIL")
        expected = datetime.utcnow() + timedelta(seconds=900)
        assert abs((next_attempt - expected).total_seconds()) < 1
        
        # Attempt 3 → 60 minutes
        next_attempt, _ = policy.calculate_next_retry(3, "TESTRAIL")
        expected = datetime.utcnow() + timedelta(seconds=3600)
        assert abs((next_attempt - expected).total_seconds()) < 1
        
        # Attempt 4+ → 60 minutes (uses last value)
        next_attempt, _ = policy.calculate_next_retry(4, "TESTRAIL")
        expected = datetime.utcnow() + timedelta(seconds=3600)
        assert abs((next_attempt - expected).total_seconds()) < 1
    
    def test_jitter_disabled_in_tests(self):
        """Test that jitter can be disabled for deterministic tests."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        # Multiple calls should return very similar results without jitter
        # (within 1 second tolerance due to datetime.utcnow() timing)
        next_attempt1, _ = policy.calculate_next_retry(0, "TESTRAIL")
        next_attempt2, _ = policy.calculate_next_retry(0, "TESTRAIL")
        
        # Should be within 1 second of each other (no jitter means minimal variance)
        assert abs((next_attempt1 - next_attempt2).total_seconds()) < 1
    
    def test_retry_after_overrides_backoff(self):
        """Test that Retry-After header overrides backoff."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        # Retry-After of 120 seconds should override 1 minute backoff
        next_attempt, _ = policy.calculate_next_retry(0, "TESTRAIL", retry_after_seconds=120)
        expected = datetime.utcnow() + timedelta(seconds=120)
        assert abs((next_attempt - expected).total_seconds()) < 1
    
    def test_classify_rate_limit_error(self):
        """Test that 429 is classified as RATE_LIMITED."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        error_type = policy.classify_error("Too many requests", http_status=429)
        assert error_type == ErrorType.RATE_LIMITED
    
    def test_classify_authentication_errors(self):
        """Test that 401/403 are classified as AUTHENTICATION_FAILED."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        error_type_401 = policy.classify_error("Unauthorized", http_status=401)
        assert error_type_401 == ErrorType.AUTHENTICATION_FAILED
        
        error_type_403 = policy.classify_error("Forbidden", http_status=403)
        assert error_type_403 == ErrorType.AUTHENTICATION_FAILED
    
    def test_classify_configuration_error(self):
        """Test that missing config is classified as CONFIGURATION_ERROR."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        error_type = policy.classify_error("Missing required field", http_status=400)
        assert error_type == ErrorType.CONFIGURATION_ERROR
    
    def test_classify_temporary_provider_failure(self):
        """Test that 5xx errors are classified as TEMPORARY_PROVIDER_FAILURE."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        error_type_500 = policy.classify_error("Internal server error", http_status=500)
        assert error_type_500 == ErrorType.TEMPORARY_PROVIDER_FAILURE
        
        error_type_503 = policy.classify_error("Service unavailable", http_status=503)
        assert error_type_503 == ErrorType.TEMPORARY_PROVIDER_FAILURE
    
    def test_classify_network_failure(self):
        """Test that network errors are classified as NETWORK_FAILURE."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        error_type = policy.classify_error("Connection timeout")
        assert error_type == ErrorType.NETWORK_FAILURE
        
        error_type = policy.classify_error("DNS resolution failed")
        assert error_type == ErrorType.NETWORK_FAILURE
    
    def test_classify_permanent_provider_failure(self):
        """Test that 404 is classified as PERMANENT_PROVIDER_FAILURE."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        error_type = policy.classify_error("Not found", http_status=404)
        assert error_type == ErrorType.PERMANENT_PROVIDER_FAILURE
    
    def test_is_retryable_errors(self):
        """Test that retryable errors are correctly identified."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        retryable_errors = [
            ErrorType.RATE_LIMITED,
            ErrorType.TEMPORARY_PROVIDER_FAILURE,
            ErrorType.NETWORK_FAILURE,
            ErrorType.UNKNOWN_FAILURE,
        ]
        
        for error_type in retryable_errors:
            assert policy.is_retryable(error_type) is True
    
    def test_non_retryable_errors(self):
        """Test that non-retryable errors are correctly identified."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        non_retryable_errors = [
            ErrorType.AUTHENTICATION_FAILED,
            ErrorType.CONFIGURATION_ERROR,
            ErrorType.PERMANENT_PROVIDER_FAILURE,
        ]
        
        for error_type in non_retryable_errors:
            assert policy.is_retryable(error_type) is False
    
    def test_should_dead_letter_after_max_attempts(self):
        """Test that jobs go to DEAD_LETTER after max attempts."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        # At max attempts, should go to DEAD_LETTER
        assert policy.should_dead_letter(5) is True
        assert policy.should_dead_letter(6) is True
    
    def test_should_not_dead_letter_before_max_attempts(self):
        """Test that jobs don't go to DEAD_LETTER before max attempts."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        # Before max attempts, should not go to DEAD_LETTER
        assert policy.should_dead_letter(0) is False
        assert policy.should_dead_letter(1) is False
        assert policy.should_dead_letter(4) is False
    
    def test_custom_max_attempts(self):
        """Test that custom max attempts can be specified."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        # Custom max attempts
        assert policy.should_dead_letter(3, max_attempts=3) is True
        assert policy.should_dead_letter(2, max_attempts=3) is False
    
    def test_error_classification_from_message(self):
        """Test error classification from error message content."""
        policy = SyncRetryPolicyService(enable_jitter=False)
        
        # Rate limit from message
        error_type = policy.classify_error("Rate limit exceeded")
        assert error_type == ErrorType.RATE_LIMITED
        
        # Auth from message
        error_type = policy.classify_error("Access denied")
        assert error_type == ErrorType.AUTHENTICATION_FAILED
        
        # Network from message
        error_type = policy.classify_error("Network unreachable")
        assert error_type == ErrorType.NETWORK_FAILURE
