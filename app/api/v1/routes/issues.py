from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import DbSession, get_current_user, require_department_admin, require_main_admin, require_reporter
from app.models.issue import Issue, IssueStatusHistory
from app.models.user import User
from app.schemas.issue import (
    IssueCreate,
    IssueImageUploadRequest,
    IssueImageUploadResponse,
    IssueListResponse,
    IssueResponse,
    IssueStatusUpdate,
)
from app.services.issue_service import IssueService

router = APIRouter()


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
        ai_routing_reason=issue.ai_routing_reason,
        cluster_id=issue.cluster_id,
        photo_keys=service.get_issue_photo_keys(issue.id),
        photo_urls=service.get_issue_photo_urls(issue.id),
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


@router.post("/issues/images/upload-url", response_model=IssueImageUploadResponse)
def create_issue_image_upload_url(payload: IssueImageUploadRequest, db: DbSession, _: User = Depends(get_current_user)):
    service = IssueService(db)
    photo_key, signed_url = service.signed_issue_upload_url(payload.file_name)
    return IssueImageUploadResponse(photo_key=photo_key, signed_upload_url=signed_url)


@router.post("/issues", response_model=IssueResponse, status_code=status.HTTP_201_CREATED)
def create_issue(payload: IssueCreate, db: DbSession, user: User = Depends(require_reporter)):
    service = IssueService(db)
    issue = service.create_issue(
        reporter_id=user.id,
        title=payload.title,
        description=payload.description,
        lat=payload.location.lat if payload.location else None,
        lng=payload.location.lng if payload.location else None,
        photo_key=payload.photo_key,
    )
    return _to_issue_response(service, issue)


@router.get("/issues/me", response_model=IssueListResponse)
def my_issues(db: DbSession, user: User = Depends(get_current_user)):
    service = IssueService(db)
    issues = service.list_user_issues(user.id)
    return IssueListResponse(items=[_to_issue_response(service, issue) for issue in issues], total=len(issues))


@router.get("/issues/{issue_id}", response_model=IssueResponse)
def get_issue(issue_id: int, db: DbSession, user: User = Depends(get_current_user)):
    service = IssueService(db)
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.reporter_id != user.id:
        if issue.department_id is None:
            raise HTTPException(status_code=403, detail="Not allowed")
        require_department_admin(issue.department_id, user)

    return _to_issue_response(service, issue)


@router.patch("/issues/{issue_id}/status", response_model=IssueResponse)
def update_issue_status(issue_id: int, payload: IssueStatusUpdate, db: DbSession, user: User = Depends(get_current_user)):
    service = IssueService(db)
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if not issue.department_id:
        raise HTTPException(status_code=400, detail="Issue has no assigned department")

    require_department_admin(issue.department_id, user)

    if payload.status.value == "open":
        raise HTTPException(status_code=400, detail="Cannot move issue back to OPEN")

    issue.status = payload.status.value
    db.add(issue)
    db.add(IssueStatusHistory(issue_id=issue.id, status=issue.status, updated_by_user_id=user.id, note=payload.note))
    db.commit()
    db.refresh(issue)
    return _to_issue_response(service, issue)


@router.get("/issues", response_model=IssueListResponse)
def list_issues(
    db: DbSession,
    _: User = Depends(require_main_admin),
    status_filter: str | None = Query(default=None, alias="status"),
    priority_level: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    cluster_id: int | None = Query(default=None),
    sort: str = Query(default="created_desc"),
):
    service = IssueService(db)
    stmt = select(Issue)
    if status_filter:
        stmt = stmt.where(Issue.status == status_filter)
    if priority_level:
        stmt = stmt.where(Issue.priority_level == priority_level)
    if department_id:
        stmt = stmt.where(Issue.department_id == department_id)
    if cluster_id:
        stmt = stmt.where(Issue.cluster_id == cluster_id)

    if sort == "priority_desc":
        stmt = stmt.order_by(Issue.priority_score.desc(), Issue.created_at.desc())
    else:
        stmt = stmt.order_by(Issue.created_at.desc())

    items = db.scalars(stmt).all()
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    return IssueListResponse(items=[_to_issue_response(service, issue) for issue in items], total=total)


@router.get("/departments/{department_id}/issues", response_model=IssueListResponse)
def list_department_issues(department_id: int, db: DbSession, user: User = Depends(get_current_user)):
    service = IssueService(db)
    require_department_admin(department_id, user)
    items = db.scalars(select(Issue).where(Issue.department_id == department_id).order_by(Issue.priority_score.desc())).all()
    return IssueListResponse(items=[_to_issue_response(service, issue) for issue in items], total=len(items))
