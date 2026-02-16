"""Approval workflow models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ActionType(str, Enum):
    """Types of actions that require approval."""

    GITHUB_CREATE_ISSUE = "github_create_issue"
    GITHUB_CREATE_PR = "github_create_pr"
    GITHUB_COMMENT = "github_comment"
    GITHUB_UPDATE_ISSUE = "github_update_issue"
    CALENDAR_CREATE_EVENT = "calendar_create_event"
    CALENDAR_UPDATE_EVENT = "calendar_update_event"
    CALENDAR_DELETE_EVENT = "calendar_delete_event"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    API_MUTATION = "api_mutation"
    COMMAND_EXECUTE = "command_execute"
    OTHER = "other"


class ApprovalRequest(BaseModel):
    """Request for approval of an action."""

    id: UUID = Field(default_factory=uuid4, description="Unique request ID")
    action_type: ActionType = Field(..., description="Type of action requesting approval")
    action_description: str = Field(..., description="Human-readable description of the action")
    action_details: Dict[str, Any] = Field(
        default_factory=dict, description="Detailed parameters of the action"
    )
    connector: str = Field(..., description="Connector requesting approval")
    user_id: str = Field(..., description="User ID (e.g., Telegram chat ID)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING, description="Current status of the request"
    )

    class Config:
        """Pydantic config."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class ApprovalResponse(BaseModel):
    """Response to an approval request."""

    request_id: UUID = Field(..., description="ID of the approval request")
    status: ApprovalStatus = Field(..., description="Approval decision")
    responded_at: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )
    user_comment: Optional[str] = Field(None, description="Optional user comment")

    class Config:
        """Pydantic config."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class ApprovalRecord(BaseModel):
    """Complete record of an approval request and response."""

    request: ApprovalRequest
    response: Optional[ApprovalResponse] = None
    completed_at: Optional[datetime] = None

    class Config:
        """Pydantic config."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
