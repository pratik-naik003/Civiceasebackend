from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CommunityPost(Base):
    __tablename__ = "community_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(220), index=True)
    body: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    images = relationship("CommunityPostImage", back_populates="post", cascade="all, delete-orphan")
    votes = relationship("CommunityPostVote", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("CommunityComment", back_populates="post", cascade="all, delete-orphan")


class CommunityPostImage(Base):
    __tablename__ = "community_post_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("community_posts.id"), index=True)
    image_key: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    post = relationship("CommunityPost", back_populates="images")


class CommunityPostVote(Base):
    __tablename__ = "community_post_votes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_post_vote_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("community_posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    value: Mapped[int] = mapped_column(Integer)  # -1 or +1
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    post = relationship("CommunityPost", back_populates="votes")


class CommunityComment(Base):
    __tablename__ = "community_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("community_posts.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    parent_comment_id: Mapped[int | None] = mapped_column(ForeignKey("community_comments.id"), nullable=True, index=True)
    body: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    post = relationship("CommunityPost", back_populates="comments")
    votes = relationship("CommunityCommentVote", back_populates="comment", cascade="all, delete-orphan")


class CommunityCommentVote(Base):
    __tablename__ = "community_comment_votes"
    __table_args__ = (UniqueConstraint("comment_id", "user_id", name="uq_comment_vote_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey("community_comments.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    value: Mapped[int] = mapped_column(Integer)  # -1 or +1
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    comment = relationship("CommunityComment", back_populates="votes")
