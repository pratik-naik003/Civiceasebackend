from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class IssueCluster(Base):
    __tablename__ = "issue_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    centroid_latitude: Mapped[float] = mapped_column(Float)
    centroid_longitude: Mapped[float] = mapped_column(Float)
    representative_text: Mapped[str] = mapped_column(Text)
    affected_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    issues = relationship("Issue", back_populates="cluster")
    members = relationship("ClusterMember", back_populates="cluster", cascade="all, delete-orphan")


class ClusterMember(Base):
    __tablename__ = "cluster_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("issue_clusters.id"), index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), unique=True, index=True)
    similarity_score: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    cluster = relationship("IssueCluster", back_populates="members")
