from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import DbSession, get_current_user, require_department_admin, require_main_admin
from app.models.department import Department
from app.models.department_person import DepartmentPerson
from app.models.issue import Issue, IssueAssignment
from app.models.enums import UserRoleEnum
from app.models.resource import Resource
from app.models.user import User, UserRole
from app.schemas.department import (
    AssignDepartmentAdminRequest,
    AssignIssuePersonRequest,
    DepartmentCreate,
    DepartmentPanelIssueResponse,
    DepartmentPanelResponse,
    DepartmentPersonCreate,
    DepartmentPersonResponse,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.services.issue_service import IssueService

router = APIRouter()


def _to_panel_issue_response(service: IssueService, issue: Issue) -> DepartmentPanelIssueResponse:
    return DepartmentPanelIssueResponse(
        id=issue.id,
        title=issue.title,
        description=issue.description,
        status=issue.status,
        priority_level=issue.priority_level,
        assigned_person_id=issue.assigned_person_id,
        assigned_person_name=issue.assigned_person_name,
        photo_urls=service.get_issue_photo_urls(issue.id),
        created_at=issue.created_at,
    )


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


@router.get("/departments/{department_id}/panel", response_model=DepartmentPanelResponse)
def get_department_panel(department_id: int, db: DbSession, user: User = Depends(get_current_user)):
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    require_department_admin(department_id, user)
    issue_service = IssueService(db)

    people = db.scalars(
        select(DepartmentPerson).where(DepartmentPerson.department_id == department_id).order_by(DepartmentPerson.name.asc())
    ).all()
    issues = db.scalars(
        select(Issue).where(Issue.department_id == department_id).order_by(Issue.priority_score.desc(), Issue.created_at.desc())
    ).all()

    return DepartmentPanelResponse(
        department=DepartmentResponse.model_validate(department, from_attributes=True),
        people=[DepartmentPersonResponse.model_validate(person, from_attributes=True) for person in people],
        issues=[_to_panel_issue_response(issue_service, issue) for issue in issues],
    )


@router.post("/departments/{department_id}/people", response_model=DepartmentPersonResponse, status_code=status.HTTP_201_CREATED)
def add_department_person(
    department_id: int,
    payload: DepartmentPersonCreate,
    db: DbSession,
    user: User = Depends(get_current_user),
):
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    require_department_admin(department_id, user)

    person = DepartmentPerson(department_id=department_id, name=payload.name.strip(), email=payload.email)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.delete("/departments/{department_id}/people/{person_id}", status_code=status.HTTP_200_OK)
def delete_department_person(
    department_id: int,
    person_id: int,
    db: DbSession,
    user: User = Depends(get_current_user),
):
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    require_department_admin(department_id, user)

    person = db.get(DepartmentPerson, person_id)
    if not person or person.department_id != department_id:
        raise HTTPException(status_code=404, detail="Person not found in this department")

    affected_issues = db.scalars(select(Issue).where(Issue.assigned_person_id == person_id)).all()
    for issue in affected_issues:
        issue.assigned_person_id = None
        db.add(issue)

    db.delete(person)
    db.commit()
    return {"message": "Person deleted"}


@router.post("/departments/{department_id}/issues/{issue_id}/assignee", response_model=DepartmentPanelIssueResponse)
def assign_issue_person(
    department_id: int,
    issue_id: int,
    payload: AssignIssuePersonRequest,
    db: DbSession,
    user: User = Depends(get_current_user),
):
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    require_department_admin(department_id, user)

    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.department_id != department_id:
        raise HTTPException(status_code=400, detail="Issue does not belong to this department")

    person = db.get(DepartmentPerson, payload.person_id)
    if not person or person.department_id != department_id:
        raise HTTPException(status_code=404, detail="Person not found in this department")

    issue.assigned_person_id = person.id
    issue.assigned_person_name = person.name
    db.add(issue)
    db.add(
        IssueAssignment(
            issue_id=issue.id,
            department_id=department_id,
            assigned_by="department_admin",
            confidence=None,
            reason=f"Assigned to {person.name}",
        )
    )
    db.commit()
    db.refresh(issue)
    return _to_panel_issue_response(IssueService(db), issue)


@router.delete("/departments/{department_id}", status_code=status.HTTP_200_OK)
def delete_department(department_id: int, db: DbSession, _: User = Depends(require_main_admin)):
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    issue_count = db.scalar(select(func.count(Issue.id)).where(Issue.department_id == department_id)) or 0
    assignment_count = db.scalar(
        select(func.count(IssueAssignment.id)).where(IssueAssignment.department_id == department_id)
    ) or 0
    resource_count = db.scalar(select(func.count(Resource.id)).where(Resource.department_id == department_id)) or 0
    admin_role_count = db.scalar(
        select(func.count(UserRole.id)).where(
            UserRole.department_id == department_id,
            UserRole.role == UserRoleEnum.DEPARTMENT_ADMIN.value,
        )
    ) or 0

    if issue_count or assignment_count or resource_count or admin_role_count:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete department with linked records "
                f"(issues={issue_count}, assignments={assignment_count}, "
                f"resources={resource_count}, admin_roles={admin_role_count})."
            ),
        )

    db.delete(department)
    db.commit()
    return {"message": "Department deleted"}


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
