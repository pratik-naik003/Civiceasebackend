from typing import Any
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.issue import Location


class ToolEventResponse(BaseModel):
    tool: str
    status: str
    message: str
    args: dict[str, Any] = Field(default_factory=dict)


class ComplaintDraftResponse(BaseModel):
    title: str | None = None
    description: str | None = None
    location: Location | None = None
    photo_keys: list[str] = Field(default_factory=list)
    ready_to_submit: bool = False
    submitted_issue_id: int | None = None


class ChatbotMessageRequest(BaseModel):
    session_id: str
    message: str = ""
    photo_keys: list[str] = Field(default_factory=list)
    location: Location | None = None


class ChatbotMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    photo_keys: list[str] = Field(default_factory=list)
    photo_urls: list[str] = Field(default_factory=list)
    location: Location | None = None
    tool_events: list[ToolEventResponse] = Field(default_factory=list)
    created_issue_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatbotSessionResponse(BaseModel):
    session_id: str
    title: str | None = None
    draft: ComplaintDraftResponse
    messages: list[ChatbotMessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ChatbotTurnResponse(BaseModel):
    session_id: str
    user_message: ChatbotMessageResponse
    assistant_message: ChatbotMessageResponse
    draft: ComplaintDraftResponse
    created_issue_id: int | None = None
