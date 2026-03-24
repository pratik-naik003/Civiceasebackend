from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), index=True)
    priority_level: Mapped[str] = mapped_column(String(8), index=True)
    priority_score: Mapped[float] = mapped_column(Float, default=0.5)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    assigned_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    assigned_person_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_routing_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_routing_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cluster_id: Mapped[int | None] = mapped_column(ForeignKey("issue_clusters.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    reporter = relationship("User", back_populates="issues_reported")
    department = relationship("Department", back_populates="issues")
    photos = relationship("IssuePhoto", back_populates="issue", cascade="all, delete-orphan")
    assignments = relationship("IssueAssignment", back_populates="issue", cascade="all, delete-orphan")
    status_history = relationship("IssueStatusHistory", back_populates="issue", cascade="all, delete-orphan")
    cluster = relationship("IssueCluster", back_populates="issues")


class IssuePhoto(Base):
    __tablename__ = "issue_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), index=True)
    photo_key: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    issue = relationship("Issue", back_populates="photos")


class IssueAssignment(Base):
    __tablename__ = "issue_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    assigned_by: Mapped[str] = mapped_column(String(32), default="ai")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    issue = relationship("Issue", back_populates="assignments")


class IssueStatusHistory(Base):
    __tablename__ = "issue_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    issue = relationship("Issue", back_populates="status_history")
