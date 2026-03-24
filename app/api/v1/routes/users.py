from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserMeResponse, UserRoleResponse

router = APIRouter(prefix="/users")


@router.get("/me", response_model=UserMeResponse)
def me(user: User = Depends(get_current_user)):
    return UserMeResponse(
        id=user.id,
        firebase_uid=user.firebase_uid,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
        roles=[UserRoleResponse.model_validate(role, from_attributes=True) for role in user.roles],
    )
