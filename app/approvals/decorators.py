"""Decorators for approval workflow."""

import functools
from typing import Any, Callable

import structlog

from app.approvals.manager import get_approval_manager
from app.approvals.models import ApprovalStatus

logger = structlog.get_logger(__name__)


def requires_approval(
    action_type: str,
    description_template: str = "{func_name}",
    detail_keys: list[str] | None = None,
):
    """Decorator to require approval for a function.

    Args:
        action_type: Type of action (e.g., "github_create_issue")
        description_template: Template for action description (can use function name and args)
        detail_keys: List of argument keys to include in action_details

    Example:
        @requires_approval(
            action_type="github_create_issue",
            description_template="Create GitHub issue: {title}",
            detail_keys=["title", "body", "labels"]
        )
        async def create_issue(self, title: str, body: str, labels: list[str]):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get connector instance (first arg for methods)
            connector = args[0] if args else None
            connector_name = (
                connector.__class__.__name__ if connector else func.__module__.split(".")[-1]
            )

            # Build action details
            action_details = {}
            if detail_keys:
                # Get bound arguments
                sig = func.__signature__ if hasattr(func, "__signature__") else None
                if sig:
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    for key in detail_keys:
                        if key in bound_args.arguments:
                            value = bound_args.arguments[key]
                            # Convert to JSON-serializable types
                            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                                action_details[key] = value
                            else:
                                action_details[key] = str(value)

            # Format description
            description = description_template.format(
                func_name=func.__name__, **kwargs, **action_details
            )

            # Get user ID (connector should have this)
            user_id = getattr(connector, "user_id", "unknown") if connector else "unknown"

            # Request approval
            approval_manager = get_approval_manager()
            request = await approval_manager.request_approval(
                action_type=action_type,
                action_description=description,
                action_details=action_details,
                connector=connector_name,
                user_id=user_id,
            )

            logger.info(
                "Requesting approval for action",
                request_id=str(request.id),
                action_type=action_type,
                description=description,
            )

            # Get notification callback from connector if available
            notify_callback = getattr(connector, "send_approval_notification", None)

            # Wait for approval
            response = await approval_manager.wait_for_approval(
                request.id, notify_callback=notify_callback
            )

            if response.status == ApprovalStatus.APPROVED:
                logger.info(
                    "Action approved, executing",
                    request_id=str(request.id),
                    action_type=action_type,
                )
                return await func(*args, **kwargs)
            elif response.status == ApprovalStatus.DENIED:
                logger.warning(
                    "Action denied by user",
                    request_id=str(request.id),
                    action_type=action_type,
                )
                raise PermissionError(f"Action denied by user: {description}")
            elif response.status == ApprovalStatus.EXPIRED:
                logger.warning(
                    "Action approval expired",
                    request_id=str(request.id),
                    action_type=action_type,
                )
                raise TimeoutError(f"Approval request expired: {description}")
            else:
                logger.error(
                    "Unexpected approval status",
                    request_id=str(request.id),
                    status=response.status,
                )
                raise RuntimeError(f"Unexpected approval status: {response.status}")

        return wrapper

    return decorator
