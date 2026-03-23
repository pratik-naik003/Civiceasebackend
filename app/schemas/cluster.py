from datetime import datetime

from pydantic import BaseModel


class ClusterIssue(BaseModel):
    issue_id: int
    similarity_score: float


class ClusterResponse(BaseModel):
    id: int
    centroid_latitude: float
    centroid_longitude: float
    representative_text: str
    affected_count: int
    created_at: datetime
    updated_at: datetime


class ClusterDetailResponse(ClusterResponse):
    issues: list[ClusterIssue]
