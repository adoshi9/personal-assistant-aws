"""Approval workflow manager."""

import asyncio
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Callable, Dict, Optional
from uuid import UUID

import structlog

from app.config import get_settings
from app.approvals.models import (
    ApprovalRecord,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalStatus,
)

logger = structlog.get_logger(__name__)


class ApprovalManager:
    """Manage approval workflow for state-changing actions."""

    def __init__(self):
        """Initialize ApprovalManager."""
        self.settings = get_settings()
        self._pending_requests: Dict[UUID, ApprovalRecord] = {}
        self._approval_callbacks: Dict[UUID, asyncio.Future] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    def start_cleanup_task(self) -> None:
        """Start background task to clean up expired approvals."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_approvals())
            logger.info("Started approval cleanup task")

    async def _cleanup_expired_approvals(self) -> None:
        """Background task to clean up expired approval requests."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                now = datetime.utcnow()
                expired_ids = []

                for request_id, record in self._pending_requests.items():
                    if (
                        record.request.status == ApprovalStatus.PENDING
                        and record.request.expires_at < now
                    ):
                        expired_ids.append(request_id)

                for request_id in expired_ids:
                    logger.info("Expiring approval request", request_id=str(request_id))
                    await self._complete_request(
                        request_id,
                        ApprovalResponse(
                            request_id=request_id,
                            status=ApprovalStatus.EXPIRED,
                        ),
                    )

            except asyncio.CancelledError:
                logger.info("Approval cleanup task cancelled")
                break
            except Exception as e:
                logger.error("Error in approval cleanup task", error=str(e))

    async def request_approval(
        self,
        action_type: str,
        action_description: str,
        action_details: Dict,
        connector: str,
        user_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> ApprovalRequest:
        """Create a new approval request.

        Args:
            action_type: Type of action requesting approval
            action_description: Human-readable description
            action_details: Detailed parameters
            connector: Name of the connector requesting approval
            user_id: User ID (e.g., Telegram chat ID)
            timeout_seconds: Optional timeout override

        Returns:
            ApprovalRequest object
        """
        timeout = timeout_seconds or self.settings.approval_timeout_seconds
        expires_at = datetime.utcnow() + timedelta(seconds=timeout)

        request = ApprovalRequest(
            action_type=action_type,
            action_description=action_description,
            action_details=action_details,
            connector=connector,
            user_id=user_id,
            expires_at=expires_at,
        )

        record = ApprovalRecord(request=request)
        self._pending_requests[request.id] = record

        # Create a future that will be resolved when approval is received
        future = asyncio.get_event_loop().create_future()
        self._approval_callbacks[request.id] = future

        logger.info(
            "Created approval request",
            request_id=str(request.id),
            action_type=action_type,
            connector=connector,
            user_id=user_id,
            expires_at=expires_at.isoformat(),
        )

        return request

    async def wait_for_approval(
        self, request_id: UUID, notify_callback: Optional[Callable] = None
    ) -> ApprovalResponse:
        """Wait for approval response.

        Args:
            request_id: ID of the approval request
            notify_callback: Optional callback to notify user (e.g., send Telegram message)

        Returns:
            ApprovalResponse when decision is made

        Raises:
            ValueError: If request not found
            TimeoutError: If request expires before approval
        """
        if request_id not in self._pending_requests:
            raise ValueError(f"Approval request not found: {request_id}")

        record = self._pending_requests[request_id]

        # Send notification to user if callback provided
        if notify_callback:
            try:
                await notify_callback(record.request)
            except Exception as e:
                logger.error(
                    "Failed to send approval notification",
                    request_id=str(request_id),
                    error=str(e),
                )

        # Wait for approval or timeout
        future = self._approval_callbacks[request_id]
        try:
            response = await future
            logger.info(
                "Approval request completed",
                request_id=str(request_id),
                status=response.status,
            )
            return response
        except asyncio.CancelledError:
            logger.info("Approval request cancelled", request_id=str(request_id))
            raise
        except Exception as e:
            logger.error("Error waiting for approval", request_id=str(request_id), error=str(e))
            raise

    async def respond_to_request(
        self, request_id: UUID, status: ApprovalStatus, user_comment: Optional[str] = None
    ) -> ApprovalResponse:
        """Respond to an approval request.

        Args:
            request_id: ID of the approval request
            status: Approval decision (APPROVED or DENIED)
            user_comment: Optional user comment

        Returns:
            ApprovalResponse object

        Raises:
            ValueError: If request not found or already completed
        """
        if request_id not in self._pending_requests:
            raise ValueError(f"Approval request not found: {request_id}")

        record = self._pending_requests[request_id]

        if record.request.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"Approval request already completed with status: {record.request.status}"
            )

        response = ApprovalResponse(
            request_id=request_id,
            status=status,
            user_comment=user_comment,
        )

        await self._complete_request(request_id, response)
        return response

    async def _complete_request(self, request_id: UUID, response: ApprovalResponse) -> None:
        """Complete an approval request.

        Args:
            request_id: ID of the approval request
            response: Approval response
        """
        if request_id not in self._pending_requests:
            return

        record = self._pending_requests[request_id]
        record.request.status = response.status
        record.response = response
        record.completed_at = datetime.utcnow()

        # Resolve the future
        if request_id in self._approval_callbacks:
            future = self._approval_callbacks[request_id]
            if not future.done():
                future.set_result(response)

        logger.info(
            "Completed approval request",
            request_id=str(request_id),
            status=response.status,
        )

    async def cancel_request(self, request_id: UUID) -> None:
        """Cancel a pending approval request.

        Args:
            request_id: ID of the approval request

        Raises:
            ValueError: If request not found
        """
        if request_id not in self._pending_requests:
            raise ValueError(f"Approval request not found: {request_id}")

        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.CANCELLED,
        )

        await self._complete_request(request_id, response)

    def get_request(self, request_id: UUID) -> Optional[ApprovalRecord]:
        """Get an approval request by ID.

        Args:
            request_id: ID of the approval request

        Returns:
            ApprovalRecord if found, None otherwise
        """
        return self._pending_requests.get(request_id)

    def get_pending_requests(self, user_id: Optional[str] = None) -> list[ApprovalRecord]:
        """Get all pending approval requests.

        Args:
            user_id: Optional filter by user ID

        Returns:
            List of pending ApprovalRecords
        """
        pending = [
            record
            for record in self._pending_requests.values()
            if record.request.status == ApprovalStatus.PENDING
        ]

        if user_id:
            pending = [r for r in pending if r.request.user_id == user_id]

        return sorted(pending, key=lambda r: r.request.created_at)

    async def shutdown(self) -> None:
        """Shutdown the approval manager and cancel all pending requests."""
        logger.info("Shutting down approval manager")

        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel all pending requests
        pending_ids = list(self._pending_requests.keys())
        for request_id in pending_ids:
            try:
                await self.cancel_request(request_id)
            except Exception as e:
                logger.error(
                    "Error cancelling request during shutdown",
                    request_id=str(request_id),
                    error=str(e),
                )


@lru_cache
def get_approval_manager() -> ApprovalManager:
    """Get cached ApprovalManager instance."""
    return ApprovalManager()
