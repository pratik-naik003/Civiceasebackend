from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import IssueStatusEnum
from app.models.issue import Issue, IssueAssignment, IssuePhoto, IssueStatusHistory
from app.services.ai.workflow import AIWorkflow


class IssueService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_issue(self, reporter_id: int, description: str, lat: float, lng: float, photo_key: str | None) -> Issue:
        issue = Issue(
            reporter_id=reporter_id,
            description=description,
            latitude=lat,
            longitude=lng,
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
