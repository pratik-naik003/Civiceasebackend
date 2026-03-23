from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IssueStatusEnum, PriorityLevelEnum


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class IssueCreate(BaseModel):
    description: str = Field(min_length=5, max_length=5000)
    location: Location
    photo_key: str | None = None


class IssueStatusUpdate(BaseModel):
    status: IssueStatusEnum
    note: str | None = None


class IssueResponse(BaseModel):
    id: int
    description: str
    latitude: float
    longitude: float
    status: IssueStatusEnum
    priority_level: PriorityLevelEnum
    priority_score: float
    department_id: int | None = None
    ai_routing_reason: str | None = None
    cluster_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IssueListResponse(BaseModel):
    items: list[IssueResponse]
    total: int
