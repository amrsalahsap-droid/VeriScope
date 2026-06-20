"""
GitHub Rate Limit Handling Tests

Tests for GitHub API rate limit handling, retry logic, and failure states.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.github_api_client import (
    GitHubApiClient,
    GitHubRateLimitExceededError,
    GitHubServiceUnavailableError
)


