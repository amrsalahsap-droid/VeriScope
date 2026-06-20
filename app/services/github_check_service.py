"""
GitHub Check Service

Service for posting commit status checks and PR comments to GitHub.
"""
import logging
import requests
from typing import Optional, Dict, Any
from app.models.pipeline_run import QualityGateStatus
from app.config import settings

logger = logging.getLogger("veriscope.github_check_service")


class GitHubCheckService:
    """Service for GitHub commit status and PR comment operations."""
    
    # Marker for update-in-place PR comments
    COMMENT_MARKER = "<!-- veriscope-quality-gate -->"
    
    def __init__(self, github_token: Optional[str] = None, ci_fail_on_partial: Optional[bool] = None):
        """
        Initialize GitHub check service.
        
        Args:
            github_token: GitHub personal access token for API authentication
            ci_fail_on_partial: Whether PARTIAL quality gate should fail CI (defaults to config)
        """
        self.github_token = github_token
        self.ci_fail_on_partial = ci_fail_on_partial if ci_fail_on_partial is not None else settings.CI_FAIL_ON_PARTIAL
        self.api_base = "https://api.github.com"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for GitHub API requests."""
        if not self.github_token:
            raise ValueError("GitHub token is required for API calls")
        
        return {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
    
    def create_check_run(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
        name: str = "Veriscope Quality Gate",
        status: str = "in_progress",
        conclusion: Optional[str] = None,
        details_url: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create or update a GitHub check run.
        
        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit SHA
            name: Check run name
            status: Status (queued, in_progress, completed)
            conclusion: Conclusion (success, failure, neutral, cancelled, skipped, timed_out, action_required)
            details_url: URL for more details
            output: Check run output (title, summary, text, annotations)
        
        Returns:
            GitHub API response or None on failure
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/check-runs"
        
        payload = {
            "name": name,
            "head_sha": commit_sha,
            "status": status
        }
        
        if conclusion:
            payload["conclusion"] = conclusion
        
        if details_url:
            payload["details_url"] = details_url
        
        if output:
            payload["output"] = output
        
        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to create GitHub check run: {e}")
            return None
    
    def create_commit_status(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
        state: str,
        description: str,
        context: str = "veriscope/quality-gate",
        target_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create or update a GitHub commit status.
        
        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit SHA
            state: State (pending, success, failure, error)
            description: Description
            context: Context string
            target_url: Target URL for more details
        
        Returns:
            GitHub API response or None on failure
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/statuses/{commit_sha}"
        
        payload = {
            "state": state,
            "description": description,
            "context": context
        }
        
        if target_url:
            payload["target_url"] = target_url
        
        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to create GitHub commit status: {e}")
            return None
    
    def find_existing_comment(
        self,
        owner: str,
        repo: str,
        pull_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Find existing Veriscope PR comment.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: Pull request number
        
        Returns:
            Comment data or None if not found
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/issues/{pull_number}/comments"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            comments = response.json()
            
            for comment in comments:
                if self.COMMENT_MARKER in comment.get("body", ""):
                    return comment
            
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to find existing PR comment: {e}")
            return None
    
    def create_pr_comment(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        body: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new PR comment.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: Pull request number
            body: Comment body (markdown)
        
        Returns:
            GitHub API response or None on failure
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/issues/{pull_number}/comments"
        
        payload = {"body": body}
        
        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to create PR comment: {e}")
            return None
    
    def update_pr_comment(
        self,
        owner: str,
        repo: str,
        comment_id: int,
        body: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing PR comment.
        
        Args:
            owner: Repository owner
            repo: Repository name
            comment_id: Comment ID
            body: New comment body (markdown)
        
        Returns:
            GitHub API response or None on failure
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/issues/comments/{comment_id}"
        
        payload = {"body": body}
        
        try:
            response = requests.patch(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to update PR comment: {e}")
            return None
    
    def post_pr_comment(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        body: str
    ) -> Optional[Dict[str, Any]]:
        """
        Post or update PR comment (update-in-place).
        
        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: Pull request number
            body: Comment body (markdown)
        
        Returns:
            GitHub API response or None on failure
        """
        # Ensure marker is in the body
        if self.COMMENT_MARKER not in body:
            body = f"{self.COMMENT_MARKER}\n\n{body}"
        
        # Try to find existing comment
        existing = self.find_existing_comment(owner, repo, pull_number)
        
        if existing:
            return self.update_pr_comment(owner, repo, existing["id"], body)
        else:
            return self.create_pr_comment(owner, repo, pull_number, body)
    
    def map_quality_gate_to_status(self, quality_gate: QualityGateStatus) -> str:
        """
        Map quality gate status to GitHub commit status.
        
        Status mapping:
        - PASSED → success
        - PARTIAL → neutral or failure depending on ciFailOnPartial config
        - FAILED → failure
        - BLOCKED → failure
        - UNKNOWN → pending
        """
        if quality_gate == QualityGateStatus.PASSED:
            return "success"
        elif quality_gate == QualityGateStatus.PARTIAL:
            # PARTIAL can be configured to fail CI
            if self.ci_fail_on_partial:
                return "failure"
            return "neutral"
        elif quality_gate == QualityGateStatus.FAILED:
            return "failure"
        elif quality_gate == QualityGateStatus.BLOCKED:
            return "failure"
        else:  # UNKNOWN
            return "pending"
    
    @staticmethod
    def generate_pr_comment(
        quality_gate: QualityGateStatus,
        required_count: int,
        regression_scope_summary: Dict[str, int],
        summary_text: str,
        recommendation_url: Optional[str] = None,
        artifact_url: Optional[str] = None
    ) -> str:
        """
        Generate markdown PR comment for quality gate result.
        
        Comment is update-in-place if one already exists (to avoid spam).
        """
        gate_emoji = {
            QualityGateStatus.PASSED: "✅",
            QualityGateStatus.PARTIAL: "⚠️",
            QualityGateStatus.FAILED: "❌",
            QualityGateStatus.BLOCKED: "🚫",
            QualityGateStatus.UNKNOWN: "⏳"
        }.get(quality_gate, "⏳")
        
        gate_label = quality_gate.value.replace("_", " ").title()
        
        comment = f"""{GitHubCheckService.COMMENT_MARKER}
## Veriscope Quality Gate: {gate_label} {gate_emoji}

{summary_text}

### Regression Scope
- **Required:** {regression_scope_summary.get('required', 0)}
- **Recommended:** {regression_scope_summary.get('recommended', 0)}
- **Optional:** {regression_scope_summary.get('optional', 0)}
- **Safe to Skip:** {regression_scope_summary.get('safe_to_skip', 0)}
- **Total Executable:** {regression_scope_summary.get('total_executable', 0)}

"""
        
        if required_count > 0:
            comment += f"### Required Before Release\n{required_count} critical requirements still require review or execution.\n"
        
        if recommendation_url:
            comment += f"\n[View Full Recommendation]({recommendation_url})\n"
        
        if artifact_url:
            comment += f"\n[Download Evidence Artifact]({artifact_url})\n"
        
        comment += "\n---\n*Commented by Veriscope CI/CD Integration*"
        
        return comment
    
    @staticmethod
    def should_update_comment(existing_comment: Optional[str], new_comment: str) -> bool:
        """
        Determine if PR comment should be updated.
        
        Update if:
        - No existing comment
        - Quality gate status changed
        - Required count changed significantly
        """
        if not existing_comment:
            return True
        
        # Simple check: if the quality gate header changed
        # Extract quality gate from both comments
        def extract_gate(comment: str) -> str:
            for line in comment.split('\n'):
                if 'Quality Gate:' in line:
                    return line
            return ""
        
        existing_gate = extract_gate(existing_comment)
        new_gate = extract_gate(new_comment)
        
        return existing_gate != new_gate
    
    @staticmethod
    def redact_secrets(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact secret values from payload before posting to GitHub.
        
        Redacts keys like: password, api_key, token, secret, etc.
        """
        secret_keys = {
            'password', 'api_key', 'apiKey', 'token', 'client_secret', 'clientSecret',
            'access_token', 'accessToken', 'refresh_token', 'refreshToken',
            'authorization', 'Authorization', 'secret', 'private_key', 'privateKey'
        }
        
        def redact_dict(d: Dict[str, Any]) -> Dict[str, Any]:
            redacted = {}
            for key, value in d.items():
                if key in secret_keys:
                    redacted[key] = "***REDACTED***"
                elif isinstance(value, dict):
                    redacted[key] = redact_dict(value)
                elif isinstance(value, list):
                    redacted[key] = [redact_dict(item) if isinstance(item, dict) else item for item in value]
                else:
                    redacted[key] = value
            return redacted
        
        return redact_dict(payload)
