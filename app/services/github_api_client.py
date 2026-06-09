import jwt
import time
import httpx
import logging
import json
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from redis import Redis
from app.config import settings

logger = logging.getLogger("veriscope.github_client")

# Specialized Custom Exceptions
class GitHubClientError(Exception):
    """Base exception for all GitHub Client issues."""
    pass

class GitHubAuthPermissionError(GitHubClientError):
    """401/403: Authentication or Permission issues (stable)."""
    pass

class GitHubNotFoundError(GitHubClientError):
    """404: Resource missing or access removed (stable)."""
    pass

class GitHubConflictError(GitHubClientError):
    """409: Conflict (stable)."""
    pass

class GitHubValidationError(GitHubClientError):
    """422: Validation issue (stable)."""
    pass

class GitHubRateLimitExceededError(GitHubClientError):
    """429 or secondary rate limit: Exhausted (transient)."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after

class GitHubServiceUnavailableError(GitHubClientError):
    """5xx: Transient GitHub internal issues (transient)."""
    pass

class GitHubApiClient:
    def __init__(self):
        self.app_id = settings.GITHUB_APP_ID
        self.private_key = settings.github_private_key  # reads from file path or direct value
        self.base_url = "https://api.github.com"
        
        # Redis Connection
        try:
            self.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            self.redis.ping()
            self.redis_available = True
        except Exception as e:
            logger.warning(f"Redis is unavailable for token caching, falling back: {e}")
            self.redis_available = False

    def generate_app_jwt(self) -> str:
        """Generate RS256 JWT valid for 10 minutes to authenticate as GitHub App."""
        if not self.app_id or not self.private_key:
            raise GitHubAuthPermissionError("GitHub GITHUB_APP_ID or GITHUB_PRIVATE_KEY configuration is missing.")
        
        now = int(time.time())
        payload = {
            "iat": now - 60,            # 1 minute leeway in the past
            "exp": now + 540,           # 9 minutes in the future (10 max)
            "iss": str(self.app_id)
        }
        
        try:
            # Strip potential leading/trailing whitespaces from PEM
            pem_key = self.private_key.strip()
            return jwt.encode(payload, pem_key, algorithm="RS256")
        except Exception as e:
            logger.error(f"Failed to encode JWT with private key: {e}")
            raise GitHubAuthPermissionError(f"Error signing JWT with configured private key: {e}")

    def get_installation_token(self, installation_id: int) -> str:
        """Retrieve installation access token, caching in Redis with 5-minute expiry buffer."""
        cache_key = f"github_installation_token:{installation_id}"
        
        # 1. Try fetching from Redis Cache
        if self.redis_available:
            try:
                cached_data = self.redis.get(cache_key)
                if cached_data:
                    info = json.loads(cached_data)
                    token = info.get("token")
                    expires_at_str = info.get("expires_at")
                    
                    if token and expires_at_str:
                        # Expecting ISO UTC format: e.g., 2026-05-22T06:01:51Z
                        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        
                        # Apply 5-minute safety buffer
                        buffer_seconds = 300
                        if (expires_at - now).total_seconds() > buffer_seconds:
                            return token
                        else:
                            logger.info(f"Cached installation token for {installation_id} expires soon, refreshing.")
            except Exception as e:
                logger.warning(f"Error reading token from Redis cache: {e}")

        # 2. Cache missed or expiring; request new token from GitHub
        logger.info(f"Requesting new installation access token for ID: {installation_id}")
        app_jwt = self.generate_app_jwt()
        
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        url = f"{self.base_url}/app/installations/{installation_id}/access_tokens"
        
        # Direct HTTP post
        response = self.request("POST", url, headers=headers)
        token_data = response.json()
        
        token = token_data.get("token")
        expires_at_str = token_data.get("expires_at")
        
        if not token or not expires_at_str:
            raise GitHubAuthPermissionError("GitHub access token request returned invalid payload structure.")
        
        # 3. Store in Redis
        if self.redis_available:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                ttl_seconds = int((expires_at - now).total_seconds()) - 60 # Set TTL slightly below actual expiry
                
                if ttl_seconds > 0:
                    info = {"token": token, "expires_at": expires_at_str}
                    self.redis.setex(cache_key, ttl_seconds, json.dumps(info))
            except Exception as e:
                logger.warning(f"Failed to cache installation token in Redis: {e}")
                
        return token

    def get_installation_details(self, installation_id: int) -> Dict[str, Any]:
        """Fetch basic installation details to verify metadata."""
        app_jwt = self.generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        url = f"{self.base_url}/app/installations/{installation_id}"
        response = self.request("GET", url, headers=headers)
        return response.json()

    def request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> httpx.Response:
        """Call GitHub APIs with full rate limit handling and error classification.

        The `timeout` parameter accepts a caller-supplied value so that the
        PR comment delivery layer can enforce its own hard 10-second budget.
        The default is 10 s; the previous hard-coded value of 30 s was too
        permissive for a latency-sensitive comment delivery pipeline.
        """
        # Ensure default User-Agent
        req_headers = headers.copy()
        if "User-Agent" not in req_headers:
            req_headers["User-Agent"] = "Veriscope-Trust-System"
            
        with httpx.Client() as client:
            try:
                response = client.request(
                    method=method,
                    url=url,
                    headers=req_headers,
                    params=params,
                    json=body,
                    timeout=timeout,
                )
            except Exception as e:
                logger.error(f"GitHub API HTTP request failed: {e}")
                raise GitHubServiceUnavailableError(f"Network transport failure contacting GitHub: {e}")

            self._process_rate_limit_headers(response.headers)
            
            # Handle standard error classification
            status_code = response.status_code
            if 200 <= status_code < 300:
                return response
            
            # Handle rate limits
            if status_code == 429:
                retry_after = response.headers.get("Retry-After")
                retry_after_secs = int(retry_after) if retry_after and retry_after.isdigit() else None
                msg = f"GitHub secondary rate limit triggered. Retry-After: {retry_after}"
                logger.warning(msg)
                raise GitHubRateLimitExceededError(msg, retry_after=retry_after_secs)
                
            if status_code in (401, 403):
                # Check if it was actually a rate limit issue
                if response.headers.get("X-RateLimit-Remaining") == "0":
                    msg = "GitHub primary rate limit exhausted (returned 403)."
                    logger.warning(msg)
                    reset_time = response.headers.get("X-RateLimit-Reset")
                    retry_after_secs = None
                    if reset_time and reset_time.isdigit():
                        retry_after_secs = max(1, int(reset_time) - int(time.time()))
                    raise GitHubRateLimitExceededError(msg, retry_after=retry_after_secs)
                raise GitHubAuthPermissionError(f"GitHub authorization or permission denied: {response.text}")
                
            if status_code == 404:
                raise GitHubNotFoundError(f"GitHub resource not found: {url}")
                
            if status_code == 409:
                raise GitHubConflictError(f"GitHub conflict encountered: {response.text}")
                
            if status_code == 422:
                raise GitHubValidationError(f"GitHub unprocessable entity validation error: {response.text}")
                
            if status_code >= 500:
                raise GitHubServiceUnavailableError(f"GitHub service unavailable (5xx): status {status_code}, response: {response.text}")
                
            raise GitHubClientError(f"GitHub client request failed with status {status_code}: {response.text}")

    def _process_rate_limit_headers(self, headers: httpx.Headers):
        """Monitor rate limit headers to prevent hitting absolute limits."""
        limit = headers.get("X-RateLimit-Limit")
        remaining = headers.get("X-RateLimit-Remaining")
        reset_time_str = headers.get("X-RateLimit-Reset")
        retry_after = headers.get("Retry-After")
        
        if remaining is not None:
            rem = int(remaining)
            if rem < 50:
                logger.warning(f"GitHub API remaining rate limit is low: {rem}/{limit}. Reset time: {reset_time_str}")
            
            if rem == 0 and reset_time_str:
                reset_epoch = int(reset_time_str)
                sleep_duration = max(0, reset_epoch - int(time.time())) + 2 # Add buffer
                logger.error(f"GitHub Rate Limit Exhausted! Raising exception with {sleep_duration}s retry delay.")
                raise GitHubRateLimitExceededError(
                    f"GitHub Rate Limit Exhausted! Reset in {sleep_duration} seconds.",
                    retry_after=sleep_duration
                )

    def parse_link_header(self, link_header: str) -> Dict[str, str]:
        """Parse RFC 5988 Link header containing pagination targets."""
        links = {}
        pattern = r'<([^>]+)>;\s*rel="([^"]+)"'
        matches = re.findall(pattern, link_header)
        for url, rel in matches:
            links[rel] = url
        return links

    def list_installation_repositories(self, installation_id: int) -> Tuple[List[Dict[str, Any]], bool, int, int, Optional[str]]:
        """Paginate and fetch all accessible repositories for the installation."""
        token = self.get_installation_token(installation_id)
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        url = f"{self.base_url}/installation/repositories"
        params = {"per_page": 100}
        
        all_repositories: List[Dict[str, Any]] = []
        pagination_completed = False
        pages_received = 0
        pages_expected = 1
        last_page_url = None
        
        next_url = url
        while next_url:
            logger.info(f"Fetching repository page: {next_url}")
            # Page fetch with custom headers & params (params are ignored if URL already contains query details)
            response = self.request("GET", next_url, headers=headers, params=params if next_url == url else None)
            data = response.json()
            
            repos = data.get("repositories", [])
            total_count = data.get("total_count", len(repos))
            pages_expected = (total_count // 100) + (1 if total_count % 100 > 0 else 0)
            
            all_repositories.extend(repos)
            pages_received += 1
            last_page_url = next_url
            
            logger.info(f"Page fetched. repositories_in_page={len(repos)}, cumulative_repository_count={len(all_repositories)}")
            
            # Parse link headers
            link_header = response.headers.get("link")
            if link_header:
                links = self.parse_link_header(link_header)
                next_url = links.get("next")
            else:
                next_url = None
                
        pagination_completed = True
        return all_repositories, pagination_completed, pages_expected, pages_received, last_page_url

    def get_repository(self, installation_id: int, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch a single repository's metadata from GitHub.
        
        Args:
            installation_id: The GitHub App installation ID
            owner: Repository owner (user or organization)
            repo: Repository name
            
        Returns:
            Repository data from GitHub API
            
        Raises:
            GitHubNotFoundError: If repository not found
            GitHubAuthPermissionError: If no access to repository
        """
        token = self.get_installation_token(installation_id)
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        url = f"{self.base_url}/repos/{owner}/{repo}"
        
        logger.info(f"Fetching repository: {owner}/{repo}")
        response = self.request("GET", url, headers=headers)
        return response.json()

    def get_pull_request_commits(self, installation_id: int, owner: str, repo: str, pull_number: int) -> Tuple[List[Dict[str, Any]], bool, int, int, Optional[str]]:
        """Paginate and fetch all commits for the specified Pull Request."""
        token = self.get_installation_token(installation_id)
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_number}/commits"
        params = {"per_page": 100}
        
        all_commits: List[Dict[str, Any]] = []
        pagination_completed = False
        pages_received = 0
        pages_expected = 1
        last_page_url = None
        
        next_url = url
        while next_url:
            logger.info(f"Fetching PR commits page: {next_url}")
            response = self.request("GET", next_url, headers=headers, params=params if next_url == url else None)
            commits = response.json()
            
            if not isinstance(commits, list):
                logger.error(f"GitHub commits API returned non-list payload: {commits}")
                break
                
            all_commits.extend(commits)
            pages_received += 1
            last_page_url = next_url
            
            link_header = response.headers.get("link")
            if link_header:
                links = self.parse_link_header(link_header)
                next_url = links.get("next")
                # Estimate total pages using pagination link headers if present
                if "last" in links:
                    last_url = links["last"]
                    try:
                        match = re.search(r"[?&]page=(\d+)", last_url)
                        if match:
                            pages_expected = int(match.group(1))
                    except Exception:
                        pass
            else:
                next_url = None
                pages_expected = pages_received
                
        pagination_completed = True
        return all_commits, pagination_completed, pages_expected, pages_received, last_page_url

    def get_pull_request_files(self, installation_id: int, owner: str, repo: str, pull_number: int) -> Tuple[List[Dict[str, Any]], bool, int, int, Optional[str]]:
        """Paginate and fetch all changed files for the specified Pull Request."""
        token = self.get_installation_token(installation_id)
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_number}/files"
        params = {"per_page": 100}
        
        all_files: List[Dict[str, Any]] = []
        pagination_completed = False
        pages_received = 0
        pages_expected = 1
        last_page_url = None
        
        next_url = url
        while next_url:
            logger.info(f"Fetching PR files page: {next_url}")
            response = self.request("GET", next_url, headers=headers, params=params if next_url == url else None)
            files = response.json()
            
            if not isinstance(files, list):
                logger.error(f"GitHub files API returned non-list payload: {files}")
                break
                
            all_files.extend(files)
            pages_received += 1
            last_page_url = next_url
            
            link_header = response.headers.get("link")
            if link_header:
                links = self.parse_link_header(link_header)
                next_url = links.get("next")
                if "last" in links:
                    last_url = links["last"]
                    try:
                        match = re.search(r"[?&]page=(\d+)", last_url)
                        if match:
                            pages_expected = int(match.group(1))
                    except Exception:
                        pass
            else:
                next_url = None
                pages_expected = pages_received
                
        pagination_completed = True
        return all_files, pagination_completed, pages_expected, pages_received, last_page_url

    def list_pr_comments(self, installation_id: int, owner: str, repo: str, pull_number: int) -> List[Dict[str, Any]]:
        """List all issue comments on a pull request, traversing all pagination pages."""
        token = self.get_installation_token(installation_id)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pull_number}/comments"
        params = {"per_page": 100}
        all_comments = []
        next_url = url
        
        while next_url:
            logger.info(f"Fetching PR comments page: {next_url}")
            response = self.request("GET", next_url, headers=headers, params=params if next_url == url else None)
            comments = response.json()
            
            if not isinstance(comments, list):
                logger.error(f"GitHub comments API returned non-list payload: {comments}")
                break
                
            all_comments.extend(comments)
            
            link_header = response.headers.get("link")
            if link_header:
                links = self.parse_link_header(link_header)
                next_url = links.get("next")
            else:
                next_url = None
                
        return all_comments

    def create_pr_comment(self, installation_id: int, owner: str, repo: str, pull_number: int, body_text: str) -> Dict[str, Any]:
        """Create a new issue comment on a pull request."""
        token = self.get_installation_token(installation_id)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pull_number}/comments"
        body = {"body": body_text}
        
        response = self.request("POST", url, headers=headers, body=body)
        return response.json()

    def update_pr_comment(self, installation_id: int, owner: str, repo: str, comment_id: int, body_text: str) -> Dict[str, Any]:
        """Update an existing issue comment on a pull request."""
        token = self.get_installation_token(installation_id)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/comments/{comment_id}"
        body = {"body": body_text}
        
        response = self.request("PATCH", url, headers=headers, body=body)
        return response.json()

    def delete_pr_comment(self, installation_id: int, owner: str, repo: str, comment_id: int) -> bool:
        """Delete an existing issue comment on a pull request."""
        token = self.get_installation_token(installation_id)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/comments/{comment_id}"
        
        self.request("DELETE", url, headers=headers)
        return True

    def get_pull_request(self, installation_id: int, owner: str, repo: str, pull_number: int) -> Dict[str, Any]:
        """Fetch pull request metadata from GitHub."""
        token = self.get_installation_token(installation_id)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_number}"
        response = self.request("GET", url, headers=headers)
        return response.json()

    def list_pull_requests(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """List pull requests for a repository, paginating through all results."""
        token = self.get_installation_token(installation_id)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        all_prs: List[Dict[str, Any]] = []
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params: Dict[str, Any] = {"state": state, "per_page": per_page, "page": 1}

        while url:
            response = self.request("GET", url, headers=headers, params=params)
            page_data = response.json()
            if not isinstance(page_data, list):
                break
            all_prs.extend(page_data)
            link_header = response.headers.get("Link", "")
            links = self.parse_link_header(link_header)
            next_url = links.get("next")
            if next_url:
                url = next_url
                params = {}
            else:
                break

        return all_prs

    def get_repository_tree(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        tree_sha: str = "main",
        recursive: bool = True
    ) -> List[Dict[str, Any]]:
        """Fetch the full file tree of a repository from GitHub.
        
        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            tree_sha: Branch name or commit SHA (default: "main")
            recursive: Whether to fetch recursively (default: True)
            
        Returns:
            List of file/directory entries in the tree
        """
        token = self.get_installation_token(installation_id)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        url = f"{self.base_url}/repos/{owner}/{repo}/git/trees/{tree_sha}"
        params = {"recursive": "1" if recursive else "0"}
        
        logger.info(f"Fetching repository tree: {owner}/{repo} at {tree_sha} (recursive={recursive})")
        response = self.request("GET", url, headers=headers, params=params)
        data = response.json()
        
        return data.get("tree", [])
