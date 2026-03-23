from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import DbSession, get_current_user, require_department_admin
from app.models.department import Department
from app.models.enums import UserRoleEnum
from app.models.user import User
from app.schemas.resource import ResourceCreate, ResourceResponse
from app.services.resource_service import ResourceService
from app.services.user_service import has_role

router = APIRouter()


def _publisher_label(role: str, department_name: str | None) -> str:
    if role == UserRoleEnum.MAIN_ADMIN.value:
        return "Main Admin"
    return department_name or "Department Admin"


def _to_response(service: ResourceService, resource) -> ResourceResponse:
    dept_name = service.get_department_name(resource.department_id)
    return ResourceResponse(
        id=resource.id,
        title=resource.title,
        link_url=resource.link_url,
        thumbnail_url=resource.thumbnail_url,
        department_id=resource.department_id,
        department_name=dept_name,
        published_by=_publisher_label(resource.created_by_role, dept_name),
        created_by_role=resource.created_by_role,
        created_at=resource.created_at,
        updated_at=resource.updated_at,
    )


@router.post("/resources", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
def create_resource(payload: ResourceCreate, db: DbSession, user: User = Depends(get_current_user)):
    is_main_admin = has_role(user, UserRoleEnum.MAIN_ADMIN)

    if is_main_admin:
        if payload.department_id is not None and not db.get(Department, payload.department_id):
            raise HTTPException(status_code=404, detail="Department not found")
        role = UserRoleEnum.MAIN_ADMIN.value
    else:
        if payload.department_id is None:
            raise HTTPException(status_code=400, detail="Department admin must provide department_id")
        if not db.get(Department, payload.department_id):
            raise HTTPException(status_code=404, detail="Department not found")
        require_department_admin(payload.department_id, user)
        role = UserRoleEnum.DEPARTMENT_ADMIN.value

    service = ResourceService(db)
    resource = service.create_resource(
        title=payload.title,
        link_url=payload.link_url,
        thumbnail_url=payload.thumbnail_url,
        department_id=payload.department_id,
        created_by_user_id=user.id,
        created_by_role=role,
    )
    return _to_response(service, resource)


@router.get("/resources", response_model=list[ResourceResponse])
def list_resources(
    db: DbSession,
    _: User = Depends(get_current_user),
    department_id: int | None = Query(default=None),
):
    service = ResourceService(db)
    resources = service.list_resources(department_id=department_id)
    return [_to_response(service, resource) for resource in resources]


@router.get("/resources/{resource_id}", response_model=ResourceResponse)
def get_resource(resource_id: int, db: DbSession, _: User = Depends(get_current_user)):
    service = ResourceService(db)
    resource = service.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return _to_response(service, resource)
