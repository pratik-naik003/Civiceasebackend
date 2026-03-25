from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_firebase_token
from app.db.session import get_db
from app.models.enums import UserRoleEnum
from app.models.user import User
from app.services.user_service import get_or_create_user, has_role


DbSession = Annotated[Session, Depends(get_db)]


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth header")
    return token


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    token = _extract_bearer_token(authorization)
    decoded = verify_firebase_token(token)

    firebase_uid = decoded.get("uid")
    if not firebase_uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return get_or_create_user(
        db,
        firebase_uid=firebase_uid,
        email=decoded.get("email"),
        display_name=decoded.get("name"),
    )


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_main_admin(user: CurrentUser) -> User:
    if not has_role(user, UserRoleEnum.MAIN_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Main admin role required")
    return user


def require_reporter(user: CurrentUser) -> User:
    if not has_role(user, UserRoleEnum.REPORTER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reporter role required")
    return user


def require_department_employee(user: CurrentUser) -> User:
    if not has_role(user, UserRoleEnum.DEPARTMENT_EMPLOYEE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department employee role required")
    return user


def require_department_admin(department_id: int, user: User) -> None:
    if has_role(user, UserRoleEnum.MAIN_ADMIN):
        return
    if not has_role(user, UserRoleEnum.DEPARTMENT_ADMIN, department_id=department_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department admin role required")
