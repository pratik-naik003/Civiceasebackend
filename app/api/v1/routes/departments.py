from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession, get_current_user, require_main_admin
from app.models.department import Department
from app.models.enums import UserRoleEnum
from app.models.user import User, UserRole
from app.schemas.department import AssignDepartmentAdminRequest, DepartmentCreate, DepartmentResponse, DepartmentUpdate

router = APIRouter()


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, db: DbSession, _: User = Depends(require_main_admin)):
    existing = db.scalar(select(Department).where(Department.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Department with this name already exists")

    department = Department(name=payload.name, description=payload.description)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@router.get("/departments", response_model=list[DepartmentResponse])
def list_departments(db: DbSession, user: User = Depends(get_current_user)):
    stmt = select(Department)
    if not any(role.role == UserRoleEnum.MAIN_ADMIN.value for role in user.roles):
        stmt = stmt.where(Department.is_active.is_(True))
    return db.scalars(stmt.order_by(Department.name.asc())).all()


@router.patch("/departments/{department_id}", response_model=DepartmentResponse)
def update_department(department_id: int, payload: DepartmentUpdate, db: DbSession, _: User = Depends(require_main_admin)):
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    if payload.name is not None:
        department.name = payload.name
    if payload.description is not None:
        department.description = payload.description
    if payload.is_active is not None:
        department.is_active = payload.is_active

    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@router.post("/departments/{department_id}/admins", status_code=status.HTTP_201_CREATED)
def assign_department_admin(
    department_id: int,
    payload: AssignDepartmentAdminRequest,
    db: DbSession,
    _: User = Depends(require_main_admin),
):
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role == UserRoleEnum.DEPARTMENT_ADMIN.value,
            UserRole.department_id == department_id,
        )
    )
    if existing:
        return {"message": "Already assigned"}

    db.add(UserRole(user_id=user.id, role=UserRoleEnum.DEPARTMENT_ADMIN.value, department_id=department_id))
    db.commit()
    return {"message": "Department admin assigned"}


@router.get("/departments/{department_id}/admins")
def list_department_admins(department_id: int, db: DbSession, _: User = Depends(require_main_admin)):
    roles = db.scalars(
        select(UserRole).where(
            UserRole.department_id == department_id,
            UserRole.role == UserRoleEnum.DEPARTMENT_ADMIN.value,
        )
    ).all()

    user_ids = [r.user_id for r in roles]
    if not user_ids:
        return []

    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    return [{"id": u.id, "email": u.email, "display_name": u.display_name} for u in users]
