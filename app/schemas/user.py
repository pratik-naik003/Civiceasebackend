from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import UserRoleEnum


class UserResponse(BaseModel):
    id: int
    firebase_uid: str
    email: str | None = None
    display_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRoleResponse(BaseModel):
    id: int
    role: UserRoleEnum
    department_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class UserMeResponse(BaseModel):
    id: int
    firebase_uid: str
    email: str | None = None
    display_name: str | None = None
    created_at: datetime
    roles: list[UserRoleResponse]

    model_config = ConfigDict(from_attributes=True)
