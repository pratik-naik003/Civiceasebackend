from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department_person import DepartmentPerson
from app.models.enums import UserRoleEnum
from app.models.user import User, UserRole


def _employee_department_ids_for_email(db: Session, email: str | None) -> set[int]:
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return set()

    department_ids = db.scalars(
        select(DepartmentPerson.department_id).where(func.lower(DepartmentPerson.email) == normalized_email)
    ).all()
    return {department_id for department_id in department_ids if department_id is not None}


def _sync_employee_roles(db: Session, user: User, email: str | None) -> None:
    target_department_ids = _employee_department_ids_for_email(db, email)
    current_roles = [role for role in user.roles if role.role == UserRoleEnum.DEPARTMENT_EMPLOYEE.value]
    current_department_ids = {role.department_id for role in current_roles if role.department_id is not None}

    for department_id in sorted(target_department_ids - current_department_ids):
        db.add(UserRole(user_id=user.id, role=UserRoleEnum.DEPARTMENT_EMPLOYEE.value, department_id=department_id))

    for role in current_roles:
        if role.department_id not in target_department_ids:
            db.delete(role)


def get_or_create_user(
    db: Session,
    *,
    firebase_uid: str,
    email: str | None,
    display_name: str | None,
) -> User:
    user = db.scalar(select(User).where(User.firebase_uid == firebase_uid))
    if user:
        if email is not None:
            user.email = email
        if display_name is not None:
            user.display_name = display_name

        if email == "dhararanas94@gmail.com" and not has_role(user, UserRoleEnum.MAIN_ADMIN):
            db.add(UserRole(user_id=user.id, role=UserRoleEnum.MAIN_ADMIN.value, department_id=None))

        _sync_employee_roles(db, user, email)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expire(user, ['roles'])
        return user

    user = User(firebase_uid=firebase_uid, email=email, display_name=display_name)
    db.add(user)
    db.flush()

    db.add(UserRole(user_id=user.id, role=UserRoleEnum.REPORTER.value, department_id=None))

    main_admin_exists = db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role == UserRoleEnum.MAIN_ADMIN.value))
    if not main_admin_exists or email == "dhararanas94@gmail.com":
        db.add(UserRole(user_id=user.id, role=UserRoleEnum.MAIN_ADMIN.value, department_id=None))

    _sync_employee_roles(db, user, email)
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
