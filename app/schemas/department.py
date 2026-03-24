from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class DepartmentPersonCreate(BaseModel):
    name: str
    email: str | None = None


class DepartmentPersonResponse(BaseModel):
    id: int
    department_id: int
    name: str
    email: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepartmentPanelIssueResponse(BaseModel):
    id: int
    title: str | None = None
    description: str
    status: str
    priority_level: str
    assigned_person_id: int | None = None
    assigned_person_name: str | None = None
    photo_urls: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepartmentPanelResponse(BaseModel):
    department: DepartmentResponse
    people: list[DepartmentPersonResponse]
    issues: list[DepartmentPanelIssueResponse]


class AssignIssuePersonRequest(BaseModel):
    person_id: int
