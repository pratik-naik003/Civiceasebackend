from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.enums import IssueStatusEnum
from app.models.issue import Issue, IssueAssignment, IssuePhoto, IssueStatusHistory
from app.services.storage.service import StorageService
from app.services.ai.workflow import AIWorkflow


class IssueService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = StorageService()

    def create_issue(self, reporter_id: int, title: str, description: str, lat: float | None, lng: float | None, photo_key: str | None) -> Issue:
        issue = Issue(
            reporter_id=reporter_id,
            title=title,
            description=description,
            latitude=lat if lat is not None else 0.0,
            longitude=lng if lng is not None else 0.0,
            status=IssueStatusEnum.OPEN.value,
            priority_level="p2",
            priority_score=0.5,
        )
        self.db.add(issue)
        self.db.flush()

        if photo_key:
            self.db.add(IssuePhoto(issue_id=issue.id, photo_key=photo_key))

        self.db.add(IssueStatusHistory(issue_id=issue.id, status=IssueStatusEnum.OPEN.value, updated_by_user_id=reporter_id))
        self.db.flush()

        ai_state = AIWorkflow(self.db).run(issue)
        issue.department_id = ai_state["routed_department_id"]
        issue.ai_routing_reason = ai_state["routing_reason"]
        issue.ai_routing_confidence = ai_state["routing_confidence"]
        issue.ai_model_used = ai_state["model"]
        issue.priority_score = ai_state["priority_score"]
        issue.priority_level = ai_state["priority_level"]
        issue.cluster_id = ai_state["cluster_id"]

        if issue.department_id:
            self.db.add(
                IssueAssignment(
                    issue_id=issue.id,
                    department_id=issue.department_id,
                    assigned_by="ai",
                    confidence=issue.ai_routing_confidence,
                    reason=issue.ai_routing_reason,
                )
            )

        self.db.add(issue)
        self.db.commit()
        self.db.refresh(issue)
        return issue

    def list_user_issues(self, reporter_id: int) -> list[Issue]:
        return self.db.scalars(select(Issue).where(Issue.reporter_id == reporter_id).order_by(Issue.created_at.desc())).all()

    def get_issue_photo_keys(self, issue_id: int) -> list[str]:
        rows = self.db.scalars(select(IssuePhoto).where(IssuePhoto.issue_id == issue_id)).all()
        return [row.photo_key for row in rows]

    def get_issue_photo_urls(self, issue_id: int) -> list[str]:
        urls: list[str] = []
        for key in self.get_issue_photo_keys(issue_id):
            signed = self.storage.signed_photo_url(key)
            if signed:
                urls.append(signed)
        return urls

    def get_department_name(self, department_id: int | None) -> str | None:
        if department_id is None:
            return None
        department = self.db.get(Department, department_id)
        return department.name if department else None

    def signed_issue_upload_url(self, file_name: str) -> tuple[str, str | None]:
        safe_name = file_name.replace("\\", "_").replace("/", "_")
        photo_key = f"issues/{safe_name}"
        return photo_key, self.storage.signed_upload_url(photo_key)
