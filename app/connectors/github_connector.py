"""GitHub connector for repository operations."""

from typing import Any, Dict, List, Optional

from github import Github, GithubException
import structlog

from app.approvals.decorators import requires_approval
from app.connectors.base import BaseConnector

logger = structlog.get_logger(__name__)


class GitHubConnector(BaseConnector):
    """Connector for GitHub API operations."""

    def __init__(self, user_id: str, token_secret: str = "github/token"):
        """Initialize GitHub connector.

        Args:
            user_id: User ID for approval notifications
            token_secret: AWS Secrets Manager secret name for GitHub token
        """
        super().__init__(user_id)
        self.token_secret = token_secret
        self.client: Optional[Github] = None

    async def initialize(self) -> None:
        """Initialize GitHub client with token from Secrets Manager."""
        try:
            token = await self.secrets_manager.get_secret(self.token_secret)
            self.client = Github(token)
            self.logger.info("GitHub connector initialized")
        except Exception as e:
            self.logger.error("Failed to initialize GitHub connector", error=str(e))
            raise

    async def health_check(self) -> bool:
        """Check if GitHub API is accessible."""
        try:
            if not self.client:
                return False
            user = self.client.get_user()
            user.login  # Trigger API call
            return True
        except Exception as e:
            self.logger.error("GitHub health check failed", error=str(e))
            return False

    async def list_repositories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List user's repositories.

        Args:
            limit: Maximum number of repositories to return

        Returns:
            List of repository information
        """
        if not self.client:
            raise RuntimeError("GitHub client not initialized")

        try:
            user = self.client.get_user()
            repos = user.get_repos()

            result = []
            for i, repo in enumerate(repos):
                if i >= limit:
                    break
                result.append(
                    {
                        "name": repo.name,
                        "full_name": repo.full_name,
                        "description": repo.description,
                        "url": repo.html_url,
                        "stars": repo.stargazers_count,
                        "forks": repo.forks_count,
                        "private": repo.private,
                    }
                )

            self.logger.info("Listed repositories", count=len(result))
            return result
        except GithubException as e:
            self.logger.error("Failed to list repositories", error=str(e))
            raise

    async def search_issues(
        self, query: str, repo: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for issues.

        Args:
            query: Search query
            repo: Optional repository name (format: "owner/repo")
            limit: Maximum number of issues to return

        Returns:
            List of issue information
        """
        if not self.client:
            raise RuntimeError("GitHub client not initialized")

        try:
            # Build search query
            search_query = query
            if repo:
                search_query = f"{query} repo:{repo}"

            issues = self.client.search_issues(search_query)

            result = []
            for i, issue in enumerate(issues):
                if i >= limit:
                    break
                result.append(
                    {
                        "number": issue.number,
                        "title": issue.title,
                        "state": issue.state,
                        "url": issue.html_url,
                        "repository": issue.repository.full_name,
                        "author": issue.user.login if issue.user else None,
                        "created_at": issue.created_at.isoformat(),
                        "comments": issue.comments,
                    }
                )

            self.logger.info("Searched issues", query=query, count=len(result))
            return result
        except GithubException as e:
            self.logger.error("Failed to search issues", error=str(e))
            raise

    @requires_approval(
        action_type="github_create_issue",
        description_template="Create GitHub issue '{title}' in {repo}",
        detail_keys=["repo", "title", "body", "labels"],
    )
    async def create_issue(
        self,
        repo: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new issue (requires approval).

        Args:
            repo: Repository name (format: "owner/repo")
            title: Issue title
            body: Issue body
            labels: Optional list of label names

        Returns:
            Created issue information
        """
        if not self.client:
            raise RuntimeError("GitHub client not initialized")

        try:
            repository = self.client.get_repo(repo)
            issue = repository.create_issue(title=title, body=body, labels=labels or [])

            self.logger.info(
                "Created GitHub issue", repo=repo, issue_number=issue.number, title=title
            )

            return {
                "number": issue.number,
                "title": issue.title,
                "url": issue.html_url,
                "state": issue.state,
                "created_at": issue.created_at.isoformat(),
            }
        except GithubException as e:
            self.logger.error("Failed to create issue", error=str(e))
            raise

    @requires_approval(
        action_type="github_comment",
        description_template="Comment on GitHub issue #{issue_number} in {repo}",
        detail_keys=["repo", "issue_number", "comment"],
    )
    async def comment_on_issue(
        self, repo: str, issue_number: int, comment: str
    ) -> Dict[str, Any]:
        """Add a comment to an issue (requires approval).

        Args:
            repo: Repository name (format: "owner/repo")
            issue_number: Issue number
            comment: Comment text

        Returns:
            Comment information
        """
        if not self.client:
            raise RuntimeError("GitHub client not initialized")

        try:
            repository = self.client.get_repo(repo)
            issue = repository.get_issue(issue_number)
            comment_obj = issue.create_comment(comment)

            self.logger.info(
                "Commented on GitHub issue", repo=repo, issue_number=issue_number
            )

            return {
                "comment_id": comment_obj.id,
                "url": comment_obj.html_url,
                "created_at": comment_obj.created_at.isoformat(),
            }
        except GithubException as e:
            self.logger.error("Failed to comment on issue", error=str(e))
            raise
