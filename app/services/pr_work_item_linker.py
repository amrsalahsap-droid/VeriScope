"""
PR Work Item Linker Service

Detects and links pull requests to external work items (Jira, Azure DevOps, etc.)
based on detected keys in PR title, body, branch name, commit messages, or manual linking.
"""

import re
import uuid
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session

from app.models.pull_request import PullRequest, PullRequestCommit
from app.models.external_work_item import ExternalWorkItem
from app.models.pull_request_work_item_link import PullRequestWorkItemLink


class PRWorkItemLinker:
    """
    Detects and links PRs to external work items.
    
    Detects work item keys from:
    - PR title
    - PR description/body
    - Branch name
    - Commit messages
    - URLs in PR body
    
    Supports:
    - Jira: ABC-123 format
    - Azure DevOps: #12345, AB#12345 format
    - URLs: Extracts keys from work item URLs
    """
    
    # Jira key pattern: uppercase letters, hyphen, numbers (e.g., ABC-123)
    JIRA_KEY_PATTERN = r'\b([A-Z]+-\d+)\b'
    
    # Azure DevOps patterns: #12345 or AB#12345
    AZURE_NUMERIC_PATTERN = r'#(\d{4,})\b'
    AZURE_PREFIX_PATTERN = r'\b([A-Z]+)#(\d+)\b'
    
    # URL patterns for extracting keys
    JIRA_URL_PATTERN = r'atlassian\.net/browse/([A-Z]+-\d+)'
    AZURE_URL_PATTERN = r'dev\.azure\.com/[^/]+/[^/]+/_workitems/edit/(\d+)'
    
    # Branch name pattern: feature/ABC-123-description
    BRANCH_KEY_PATTERN = r'([A-Z]+-\d+)[/-]'
    
    # Confidence scores for different sources
    CONFIDENCE_SCORES = {
        "PR_TITLE": 0.9,
        "BRANCH_NAME": 0.85,
        "PR_BODY": 0.7,
        "COMMIT_MESSAGE": 0.6,
        "MANUAL": 1.0,
    }
    
    def __init__(self, db: Session):
        """Initialize the linker with database session."""
        self.db = db
    
    def link_pr_to_work_items(
        self,
        pull_request: PullRequest,
        commits: Optional[List[PullRequestCommit]] = None
    ) -> List[PullRequestWorkItemLink]:
        """
        Detect and link work items for a pull request.
        
        Args:
            pull_request: The PullRequest to link
            commits: Optional list of commits for commit message detection
            
        Returns:
            List of created PullRequestWorkItemLink objects
        """
        detected_keys = self._detect_all_keys(pull_request, commits)
        
        if not detected_keys:
            return []
        
        # Match detected keys to ExternalWorkItem records
        workspace_id = pull_request.repository.workspace_id
        external_work_items = self._find_external_work_items(workspace_id, detected_keys.keys())
        
        # Create links
        links = []
        for key, sources in detected_keys.items():
            # Use the highest confidence source
            best_source = max(sources, key=lambda x: self.CONFIDENCE_SCORES.get(x, 0.5))
            confidence = self.CONFIDENCE_SCORES.get(best_source, 0.5)
            
            # Check if we have a matching ExternalWorkItem
            external_work_item = external_work_items.get(key)
            
            # Check for duplicate link
            existing = self.db.query(PullRequestWorkItemLink).filter(
                PullRequestWorkItemLink.pull_request_id == pull_request.id,
                PullRequestWorkItemLink.external_work_item_id == external_work_item.id if external_work_item else None,
                PullRequestWorkItemLink.unresolved_key == key if not external_work_item else None
            ).first()
            
            if existing:
                continue
            
            # Create link
            link = PullRequestWorkItemLink(
                id=uuid.uuid4(),
                pull_request_id=pull_request.id,
                external_work_item_id=external_work_item.id if external_work_item else None,
                unresolved_key=key if not external_work_item else None,
                link_source=best_source,
                confidence=confidence
            )
            self.db.add(link)
            links.append(link)
        
        self.db.commit()
        return links
    
    def _detect_all_keys(
        self,
        pull_request: PullRequest,
        commits: Optional[List[PullRequestCommit]] = None
    ) -> Dict[str, Set[str]]:
        """
        Detect work item keys from all sources.
        
        Returns:
            Dictionary mapping key to set of sources where it was found
        """
        detected = {}
        
        # Detect from PR title
        title_keys = self._detect_keys_from_text(pull_request.title)
        for key in title_keys:
            if key not in detected:
                detected[key] = set()
            detected[key].add("PR_TITLE")
        
        # Detect from PR body (if available - would need to fetch from GitHub)
        # For now, we'll skip body detection as it's not in the model
        
        # Detect from branch name
        branch_keys = self._detect_keys_from_branch(pull_request.source_branch)
        for key in branch_keys:
            if key not in detected:
                detected[key] = set()
            detected[key].add("BRANCH_NAME")
        
        # Detect from commit messages
        if commits:
            for commit in commits:
                commit_keys = self._detect_keys_from_text(commit.message)
                for key in commit_keys:
                    if key not in detected:
                        detected[key] = set()
                    detected[key].add("COMMIT_MESSAGE")
        
        return detected
    
    def _detect_keys_from_text(self, text: str) -> Set[str]:
        """Detect work item keys from text."""
        keys = set()
        
        # Jira keys
        jira_keys = re.findall(self.JIRA_KEY_PATTERN, text)
        keys.update(jira_keys)
        
        # Azure numeric keys (#12345)
        azure_numeric = re.findall(self.AZURE_NUMERIC_PATTERN, text)
        for num in azure_numeric:
            keys.add(f"#{num}")
        
        # Azure prefix keys (AB#12345)
        azure_prefix = re.findall(self.AZURE_PREFIX_PATTERN, text)
        for prefix, num in azure_prefix:
            keys.add(f"{prefix}#{num}")
        
        # Jira URLs
        jira_urls = re.findall(self.JIRA_URL_PATTERN, text)
        keys.update(jira_urls)
        
        # Azure URLs
        azure_urls = re.findall(self.AZURE_URL_PATTERN, text)
        for num in azure_urls:
            keys.add(f"#{num}")
        
        return keys
    
    def _detect_keys_from_branch(self, branch_name: str) -> Set[str]:
        """Detect work item keys from branch name."""
        keys = set()
        
        # Pattern: feature/ABC-123-description
        branch_keys = re.findall(self.BRANCH_KEY_PATTERN, branch_name)
        keys.update(branch_keys)
        
        # Also try general text detection on branch name
        keys.update(self._detect_keys_from_text(branch_name))
        
        return keys
    
    def _find_external_work_items(
        self,
        workspace_id: uuid.UUID,
        keys: Set[str]
    ) -> Dict[str, ExternalWorkItem]:
        """
        Find ExternalWorkItem records for detected keys.
        
        Returns:
            Dictionary mapping key to ExternalWorkItem
        """
        if not keys:
            return {}
        
        # Query for work items matching any of the detected keys
        work_items = self.db.query(ExternalWorkItem).filter(
            ExternalWorkItem.workspace_id == workspace_id,
            ExternalWorkItem.external_key.in_(keys)
        ).all()
        
        return {wi.external_key: wi for wi in work_items}
    
    def resolve_unresolved_links(
        self,
        workspace_id: uuid.UUID
    ) -> int:
        """
        Resolve unresolved links by matching to newly imported work items.
        
        Args:
            workspace_id: Workspace to resolve links for
            
        Returns:
            Number of links resolved
        """
        # Find all unresolved links
        unresolved_links = self.db.query(PullRequestWorkItemLink).filter(
            PullRequestWorkItemLink.external_work_item_id.is_(None),
            PullRequestWorkItemLink.unresolved_key.isnot_(None)
        ).all()
        
        resolved_count = 0
        
        for link in unresolved_links:
            # Try to find matching ExternalWorkItem
            work_item = self.db.query(ExternalWorkItem).filter(
                ExternalWorkItem.workspace_id == workspace_id,
                ExternalWorkItem.external_key == link.unresolved_key
            ).first()
            
            if work_item:
                link.external_work_item_id = work_item.id
                link.unresolved_key = None
                resolved_count += 1
        
        self.db.commit()
        return resolved_count
