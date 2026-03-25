from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IssueStatusEnum, PriorityLevelEnum


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class IssueCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=5, max_length=5000)
    location: Location | None = None
    photo_key: str | None = None


class IssueImageUploadRequest(BaseModel):
    file_name: str


class IssueImageUploadResponse(BaseModel):
    photo_key: str
    signed_upload_url: str | None = None


class IssueStatusUpdate(BaseModel):
    status: IssueStatusEnum
    note: str | None = None


class EmployeeIssueCompleteRequest(BaseModel):
    photo_key: str = Field(min_length=3)
    note: str | None = Field(default=None, max_length=2000)


class IssueResponse(BaseModel):
    id: int
    title: str | None = None
    description: str
    latitude: float | None = None
    longitude: float | None = None
    status: IssueStatusEnum
    priority_level: PriorityLevelEnum
    priority_score: float
    department_id: int | None = None
    department_name: str | None = None
    assigned_person_id: int | None = None
    assigned_person_name: str | None = None
    ai_routing_reason: str | None = None
    cluster_id: int | None = None
    photo_keys: list[str] = Field(default_factory=list)
    photo_urls: list[str] = Field(default_factory=list)
    resolution_photo_key: str | None = None
    resolution_photo_url: str | None = None
    resolution_note: str | None = None
    resolved_by_user_id: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IssueListResponse(BaseModel):
    items: list[IssueResponse]
    total: int
