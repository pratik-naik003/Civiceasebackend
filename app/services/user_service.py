from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import UserRoleEnum
from app.models.user import User, UserRole


def get_or_create_user(
    db: Session,
    *,
    firebase_uid: str,
    email: str | None,
    display_name: str | None,
) -> User:
    user = db.scalar(select(User).where(User.firebase_uid == firebase_uid))
    if user:
        if email and user.email != email:
            user.email = email
        if display_name and user.display_name != display_name:
            user.display_name = display_name
        
        # Enforce admin for specific email
        if email == "dhararanas94@gmail.com" and not has_role(user, UserRoleEnum.MAIN_ADMIN):
            db.add(UserRole(user_id=user.id, role=UserRoleEnum.MAIN_ADMIN.value, department_id=None))
            
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    user = User(firebase_uid=firebase_uid, email=email, display_name=display_name)
    db.add(user)
    db.flush()

    db.add(UserRole(user_id=user.id, role=UserRoleEnum.REPORTER.value, department_id=None))

    main_admin_exists = db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role == UserRoleEnum.MAIN_ADMIN.value))
    if not main_admin_exists or email == "dhararanas94@gmail.com":
        db.add(UserRole(user_id=user.id, role=UserRoleEnum.MAIN_ADMIN.value, department_id=None))

    db.commit()
    db.refresh(user)
    return user


def has_role(user: User, role: UserRoleEnum, department_id: int | None = None) -> bool:
    for user_role in user.roles:
        if user_role.role != role.value:
            continue
        if department_id is None or user_role.department_id == department_id:
            return True
    return False
