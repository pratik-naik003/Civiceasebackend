from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import DbSession, require_department_employee
from app.models.department_person import DepartmentPerson
from app.models.enums import IssueStatusEnum, UserRoleEnum
from app.models.issue import Issue, IssueStatusHistory
from app.models.user import User
from app.schemas.issue import (
    EmployeeIssueCompleteRequest,
    IssueImageUploadRequest,
    IssueImageUploadResponse,
    IssueListResponse,
    IssueResponse,
)
from app.services.issue_service import IssueService

router = APIRouter(prefix="/employee")


def _to_issue_response(service: IssueService, issue: Issue) -> IssueResponse:
    return IssueResponse(
        id=issue.id,
        title=issue.title,
        description=issue.description,
        latitude=issue.latitude,
        longitude=issue.longitude,
        status=issue.status,
        priority_level=issue.priority_level,
        priority_score=issue.priority_score,
        department_id=issue.department_id,
        department_name=service.get_department_name(issue.department_id),
        assigned_person_id=issue.assigned_person_id,
        assigned_person_name=issue.assigned_person_name,
        ai_routing_reason=issue.ai_routing_reason,
        cluster_id=issue.cluster_id,
        photo_keys=service.get_issue_photo_keys(issue.id),
        photo_urls=service.get_issue_photo_urls(issue.id),
        resolution_photo_key=issue.resolution_photo_key,
        resolution_photo_url=service.get_photo_url(issue.resolution_photo_key),
        resolution_note=issue.resolution_note,
        resolved_by_user_id=issue.resolved_by_user_id,
        resolved_at=issue.resolved_at,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def _employee_people(db: DbSession, user: User) -> list[DepartmentPerson]:
    normalized_email = (user.email or "").strip().lower()
    if not normalized_email:
        return []

    department_ids = [
        role.department_id
        for role in user.roles
        if role.role == UserRoleEnum.DEPARTMENT_EMPLOYEE.value and role.department_id is not None
    ]
    if not department_ids:
        return []

    stmt = select(DepartmentPerson).where(
        DepartmentPerson.department_id.in_(department_ids),
        func.lower(DepartmentPerson.email) == normalized_email,
    )
    return db.scalars(stmt).all()


def _employee_person_ids(db: DbSession, user: User) -> set[int]:
    return {person.id for person in _employee_people(db, user)}


def _get_employee_issue_or_404(db: DbSession, user: User, issue_id: int) -> Issue:
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    person_ids = _employee_person_ids(db, user)
    if issue.assigned_person_id not in person_ids:
        raise HTTPException(status_code=404, detail="Assigned issue not found")
    return issue


@router.get("/issues", response_model=IssueListResponse)
def list_employee_issues(db: DbSession, user: User = Depends(require_department_employee)):
    service = IssueService(db)
    person_ids = _employee_person_ids(db, user)
    if not person_ids:
        return IssueListResponse(items=[], total=0)

    items = db.scalars(
        select(Issue)
        .where(Issue.assigned_person_id.in_(person_ids))
        .order_by(Issue.status.asc(), Issue.created_at.desc())
    ).all()
    return IssueListResponse(items=[_to_issue_response(service, issue) for issue in items], total=len(items))


@router.get("/issues/{issue_id}", response_model=IssueResponse)
def get_employee_issue(issue_id: int, db: DbSession, user: User = Depends(require_department_employee)):
    issue = _get_employee_issue_or_404(db, user, issue_id)
    return _to_issue_response(IssueService(db), issue)


@router.post("/issues/{issue_id}/start", response_model=IssueResponse)
def start_employee_issue(issue_id: int, db: DbSession, user: User = Depends(require_department_employee)):
    service = IssueService(db)
    issue = _get_employee_issue_or_404(db, user, issue_id)
    if issue.status == IssueStatusEnum.RESOLVED.value:
        raise HTTPException(status_code=400, detail="Resolved issues cannot be restarted")

    if issue.status != IssueStatusEnum.IN_PROGRESS.value:
        issue.status = IssueStatusEnum.IN_PROGRESS.value
        db.add(issue)
        db.add(
            IssueStatusHistory(
                issue_id=issue.id,
                status=IssueStatusEnum.IN_PROGRESS.value,
                updated_by_user_id=user.id,
                note="Work started by assigned employee",
            )
        )
        db.commit()
        db.refresh(issue)

    return _to_issue_response(service, issue)


@router.post("/issues/{issue_id}/proof-upload-url", response_model=IssueImageUploadResponse)
def create_employee_proof_upload_url(
    issue_id: int,
    payload: IssueImageUploadRequest,
    db: DbSession,
    user: User = Depends(require_department_employee),
):
    _get_employee_issue_or_404(db, user, issue_id)
    service = IssueService(db)
    photo_key, signed_url = service.signed_issue_resolution_upload_url(payload.file_name)
    return IssueImageUploadResponse(photo_key=photo_key, signed_upload_url=signed_url)


@router.post("/issues/{issue_id}/complete", response_model=IssueResponse, status_code=status.HTTP_200_OK)
def complete_employee_issue(
    issue_id: int,
    payload: EmployeeIssueCompleteRequest,
    db: DbSession,
    user: User = Depends(require_department_employee),
):
    service = IssueService(db)
    issue = _get_employee_issue_or_404(db, user, issue_id)
    if issue.status == IssueStatusEnum.RESOLVED.value:
        raise HTTPException(status_code=400, detail="Issue is already resolved")
    if issue.status == IssueStatusEnum.PENDING_REVIEW.value:
        raise HTTPException(status_code=400, detail="Issue is already awaiting department review")

    issue.status = IssueStatusEnum.PENDING_REVIEW.value
    issue.resolution_photo_key = payload.photo_key
    issue.resolution_note = payload.note.strip() if payload.note else None
    issue.resolved_by_user_id = None
    issue.resolved_at = None
    db.add(issue)
    db.add(
        IssueStatusHistory(
            issue_id=issue.id,
            status=IssueStatusEnum.PENDING_REVIEW.value,
            updated_by_user_id=user.id,
            note=issue.resolution_note or "Completion proof submitted for department review",
        )
    )
    db.commit()
    db.refresh(issue)
    return _to_issue_response(service, issue)
