from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class AgentChatResponse(BaseModel):
    reply: str
    tool_used: str | None = None
    tool_result: dict | list | str | None = None
