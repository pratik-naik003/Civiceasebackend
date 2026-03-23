from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommunityPostCreate(BaseModel):
    title: str = Field(min_length=4, max_length=220)
    body: str = Field(min_length=1, max_length=10000)
    image_keys: list[str] = Field(default_factory=list, max_length=8)


class CommunityPostVoteRequest(BaseModel):
    value: int = Field(..., ge=-1, le=1)


class CommunityCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    parent_comment_id: int | None = None


class CommunityCommentVoteRequest(BaseModel):
    value: int = Field(..., ge=-1, le=1)


class CommunityImageUploadRequest(BaseModel):
    file_name: str


class CommunityImageUploadResponse(BaseModel):
    image_key: str
    signed_upload_url: str | None = None


class CommunityPostResponse(BaseModel):
    id: int
    author_id: int
    title: str
    body: str
    score: int
    comment_count: int
    image_keys: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommunityCommentResponse(BaseModel):
    id: int
    post_id: int
    author_id: int
    parent_comment_id: int | None
    body: str
    score: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommunityCommentNode(CommunityCommentResponse):
    replies: list["CommunityCommentNode"] = Field(default_factory=list)


class CommunityPostDetailResponse(CommunityPostResponse):
    comments: list[CommunityCommentNode]


class VoteResponse(BaseModel):
    score: int
    user_vote: int


CommunityCommentNode.model_rebuild()
