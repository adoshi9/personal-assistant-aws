"""Base connector class."""

from abc import ABC, abstractmethod
from typing import Optional

import structlog

from app.approvals.models import ApprovalRequest
from app.security import get_secrets_manager

logger = structlog.get_logger(__name__)


class BaseConnector(ABC):
    """Base class for all connectors."""

    def __init__(self, user_id: str):
        """Initialize connector.

        Args:
            user_id: User ID (e.g., Telegram chat ID) for approval notifications
        """
        self.user_id = user_id
        self.secrets_manager = get_secrets_manager()
        self.logger = logger.bind(connector=self.__class__.__name__, user_id=user_id)

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connector and load credentials."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if connector is healthy and can communicate with external service."""
        pass

    async def send_approval_notification(self, request: ApprovalRequest) -> None:
        """Send approval notification to user.

        This is a callback used by the approval manager.
        Subclasses can override to customize notification behavior.

        Args:
            request: The approval request
        """
        self.logger.info(
            "Approval required",
            request_id=str(request.id),
            action=request.action_description,
        )
