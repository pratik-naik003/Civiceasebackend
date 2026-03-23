from dataclasses import dataclass

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from app.models.community import (
    CommunityComment,
    CommunityCommentVote,
    CommunityPost,
    CommunityPostImage,
    CommunityPostVote,
)
from app.services.storage.service import StorageService


@dataclass
class VoteResult:
    score: int
    user_vote: int


class CommunityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = StorageService()

    def create_post(self, author_id: int, title: str, body: str, image_keys: list[str]) -> CommunityPost:
        post = CommunityPost(author_id=author_id, title=title, body=body)
        self.db.add(post)
        self.db.flush()

        for key in image_keys:
            self.db.add(CommunityPostImage(post_id=post.id, image_key=key))

        self.db.commit()
        self.db.refresh(post)
        return post

    def list_posts(self, sort: str = "hot") -> list[CommunityPost]:
        stmt: Select[tuple[CommunityPost]] = select(CommunityPost)
        if sort == "new":
            stmt = stmt.order_by(CommunityPost.created_at.desc())
        elif sort == "top":
            stmt = stmt.order_by(CommunityPost.score.desc(), CommunityPost.created_at.desc())
        else:
            stmt = stmt.order_by(CommunityPost.score.desc(), CommunityPost.comment_count.desc(), CommunityPost.created_at.desc())
        return self.db.scalars(stmt).all()

    def create_comment(self, post_id: int, author_id: int, body: str, parent_comment_id: int | None) -> CommunityComment:
        if parent_comment_id is not None:
            parent = self.db.get(CommunityComment, parent_comment_id)
            if not parent or parent.post_id != post_id:
                raise ValueError("Invalid parent comment")

        post = self.db.get(CommunityPost, post_id)
        if not post:
            raise ValueError("Post not found")

        comment = CommunityComment(post_id=post_id, author_id=author_id, body=body, parent_comment_id=parent_comment_id)
        self.db.add(comment)
        post.comment_count += 1
        self.db.add(post)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def vote_post(self, post_id: int, user_id: int, value: int) -> VoteResult:
        if value not in (-1, 1):
            raise ValueError("Vote value must be -1 or 1")

        post = self.db.get(CommunityPost, post_id)
        if not post:
            raise ValueError("Post not found")

        existing = self.db.scalar(select(CommunityPostVote).where(CommunityPostVote.post_id == post_id, CommunityPostVote.user_id == user_id))

        if existing:
            post.score -= existing.value
            existing.value = value
            post.score += value
            self.db.add(existing)
        else:
            self.db.add(CommunityPostVote(post_id=post_id, user_id=user_id, value=value))
            post.score += value

        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return VoteResult(score=post.score, user_vote=value)

    def vote_comment(self, comment_id: int, user_id: int, value: int) -> VoteResult:
        if value not in (-1, 1):
            raise ValueError("Vote value must be -1 or 1")

        comment = self.db.get(CommunityComment, comment_id)
        if not comment:
            raise ValueError("Comment not found")

        existing = self.db.scalar(
            select(CommunityCommentVote).where(CommunityCommentVote.comment_id == comment_id, CommunityCommentVote.user_id == user_id)
        )

        if existing:
            comment.score -= existing.value
            existing.value = value
            comment.score += value
            self.db.add(existing)
        else:
            self.db.add(CommunityCommentVote(comment_id=comment_id, user_id=user_id, value=value))
            comment.score += value

        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return VoteResult(score=comment.score, user_vote=value)

    def get_post(self, post_id: int) -> CommunityPost | None:
        return self.db.get(CommunityPost, post_id)

    def list_post_comments(self, post_id: int) -> list[CommunityComment]:
        return self.db.scalars(
            select(CommunityComment).where(CommunityComment.post_id == post_id).order_by(desc(CommunityComment.score), CommunityComment.created_at.asc())
        ).all()

    def get_post_image_keys(self, post_id: int) -> list[str]:
        rows = self.db.scalars(select(CommunityPostImage).where(CommunityPostImage.post_id == post_id)).all()
        return [row.image_key for row in rows]

    def signed_upload_url(self, file_name: str) -> tuple[str, str | None]:
        safe_name = file_name.replace("\\", "_").replace("/", "_")
        image_key = f"community/{safe_name}"
        return image_key, self.storage.signed_upload_url(image_key)
