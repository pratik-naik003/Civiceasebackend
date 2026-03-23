from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResourceCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    link_url: str = Field(min_length=5, max_length=4000)
    thumbnail_url: str | None = Field(default=None, max_length=4000)
    department_id: int | None = None


class ResourceResponse(BaseModel):
    id: int
    title: str
    link_url: str
    thumbnail_url: str | None
    department_id: int | None
    department_name: str | None
    published_by: str
    created_by_role: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
