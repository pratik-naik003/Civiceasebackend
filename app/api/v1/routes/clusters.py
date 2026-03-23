from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.deps import DbSession, require_main_admin
from app.models.cluster import ClusterMember, IssueCluster
from app.models.user import User
from app.schemas.cluster import ClusterDetailResponse, ClusterIssue, ClusterResponse

router = APIRouter()


@router.get("/clusters", response_model=list[ClusterResponse])
def list_clusters(db: DbSession, _: User = Depends(require_main_admin)):
    return db.scalars(select(IssueCluster).order_by(IssueCluster.affected_count.desc())).all()


@router.get("/clusters/{cluster_id}", response_model=ClusterDetailResponse)
def get_cluster(cluster_id: int, db: DbSession, _: User = Depends(require_main_admin)):
    cluster = db.get(IssueCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    members = db.scalars(select(ClusterMember).where(ClusterMember.cluster_id == cluster_id)).all()
    issues = [ClusterIssue(issue_id=m.issue_id, similarity_score=m.similarity_score) for m in members]

    return ClusterDetailResponse(
        id=cluster.id,
        centroid_latitude=cluster.centroid_latitude,
        centroid_longitude=cluster.centroid_longitude,
        representative_text=cluster.representative_text,
        affected_count=cluster.affected_count,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        issues=issues,
    )
