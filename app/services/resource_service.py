from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.resource import Resource


class ResourceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_resource(
        self,
        *,
        title: str,
        link_url: str,
        thumbnail_url: str | None,
        department_id: int | None,
        created_by_user_id: int,
        created_by_role: str,
    ) -> Resource:
        resource = Resource(
            title=title,
            link_url=link_url,
            thumbnail_url=thumbnail_url,
            department_id=department_id,
            created_by_user_id=created_by_user_id,
            created_by_role=created_by_role,
        )
        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)
        return resource

    def list_resources(self, department_id: int | None = None) -> list[Resource]:
        stmt = select(Resource)
        if department_id is not None:
            stmt = stmt.where(Resource.department_id == department_id)
        stmt = stmt.order_by(Resource.created_at.desc())
        return self.db.scalars(stmt).all()

    def get_department_name(self, department_id: int | None) -> str | None:
        if department_id is None:
            return None
        department = self.db.get(Department, department_id)
        return department.name if department else None

    def get_resource(self, resource_id: int) -> Resource | None:
        return self.db.get(Resource, resource_id)
