from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import DbSession, get_current_user
from app.models.user import User
from app.schemas.community import (
    CommunityCommentCreate,
    CommunityCommentNode,
    CommunityCommentResponse,
    CommunityCommentVoteRequest,
    CommunityImageUploadRequest,
    CommunityImageUploadResponse,
    CommunityPostCreate,
    CommunityPostDetailResponse,
    CommunityPostResponse,
    CommunityPostVoteRequest,
    VoteResponse,
)
from app.services.community_service import CommunityService

router = APIRouter(prefix="/community")


def _post_to_response(service: CommunityService, post) -> CommunityPostResponse:
    return CommunityPostResponse(
        id=post.id,
        author_id=post.author_id,
        title=post.title,
        body=post.body,
        score=post.score,
        comment_count=post.comment_count,
        image_keys=service.get_post_image_keys(post.id),
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _build_comment_tree(comments: list) -> list[CommunityCommentNode]:
    nodes = {
        c.id: CommunityCommentNode(
            id=c.id,
            post_id=c.post_id,
            author_id=c.author_id,
            parent_comment_id=c.parent_comment_id,
            body=c.body,
            score=c.score,
            created_at=c.created_at,
            updated_at=c.updated_at,
            replies=[],
        )
        for c in comments
    }
    roots: list[CommunityCommentNode] = []

    for c in comments:
        node = nodes[c.id]
        if c.parent_comment_id and c.parent_comment_id in nodes:
            nodes[c.parent_comment_id].replies.append(node)
        else:
            roots.append(node)

    return roots


@router.post("/images/upload-url", response_model=CommunityImageUploadResponse)
def create_image_upload_url(payload: CommunityImageUploadRequest, db: DbSession, _: User = Depends(get_current_user)):
    service = CommunityService(db)
    image_key, signed_url = service.signed_upload_url(payload.file_name)
    return CommunityImageUploadResponse(image_key=image_key, signed_upload_url=signed_url)


@router.post("/posts", response_model=CommunityPostResponse, status_code=status.HTTP_201_CREATED)
def create_post(payload: CommunityPostCreate, db: DbSession, user: User = Depends(get_current_user)):
    service = CommunityService(db)
    post = service.create_post(user.id, payload.title, payload.body, payload.image_keys)
    return _post_to_response(service, post)


@router.get("/posts", response_model=list[CommunityPostResponse])
def list_posts(db: DbSession, _: User = Depends(get_current_user), sort: str = Query(default="hot")):
    service = CommunityService(db)
    posts = service.list_posts(sort=sort)
    return [_post_to_response(service, post) for post in posts]


@router.get("/posts/{post_id}", response_model=CommunityPostDetailResponse)
def get_post(post_id: int, db: DbSession, _: User = Depends(get_current_user)):
    service = CommunityService(db)
    post = service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = service.list_post_comments(post_id)
    return CommunityPostDetailResponse(
        **_post_to_response(service, post).model_dump(),
        comments=_build_comment_tree(comments),
    )


@router.post("/posts/{post_id}/vote", response_model=VoteResponse)
def vote_post(post_id: int, payload: CommunityPostVoteRequest, db: DbSession, user: User = Depends(get_current_user)):
    service = CommunityService(db)
    try:
        vote = service.vote_post(post_id=post_id, user_id=user.id, value=payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return VoteResponse(score=vote.score, user_vote=vote.user_vote)


@router.post("/posts/{post_id}/comments", response_model=CommunityCommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment(post_id: int, payload: CommunityCommentCreate, db: DbSession, user: User = Depends(get_current_user)):
    service = CommunityService(db)
    try:
        comment = service.create_comment(
            post_id=post_id,
            author_id=user.id,
            body=payload.body,
            parent_comment_id=payload.parent_comment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return comment


@router.get("/posts/{post_id}/comments", response_model=list[CommunityCommentNode])
def list_comments(post_id: int, db: DbSession, _: User = Depends(get_current_user)):
    service = CommunityService(db)
    if not service.get_post(post_id):
        raise HTTPException(status_code=404, detail="Post not found")
    comments = service.list_post_comments(post_id)
    return _build_comment_tree(comments)


@router.post("/comments/{comment_id}/vote", response_model=VoteResponse)
def vote_comment(comment_id: int, payload: CommunityCommentVoteRequest, db: DbSession, user: User = Depends(get_current_user)):
    service = CommunityService(db)
    try:
        vote = service.vote_comment(comment_id=comment_id, user_id=user.id, value=payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return VoteResponse(score=vote.score, user_vote=vote.user_vote)
