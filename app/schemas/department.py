from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DepartmentCreate(BaseModel):
    name: str
    description: str


class DepartmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    id: int
    name: str
    description: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignDepartmentAdminRequest(BaseModel):
    user_id: int
