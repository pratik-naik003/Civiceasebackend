from fastapi import APIRouter, Depends

from app.core.deps import DbSession, get_current_user
from app.models.user import User
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services.agent.assistant_agent import AssistantAgent

router = APIRouter(prefix="/agent")


@router.post("/chat", response_model=AgentChatResponse)
def chat_with_agent(payload: AgentChatRequest, db: DbSession, user: User = Depends(get_current_user)):
    state = AssistantAgent(db, user).run(payload.message)
    return AgentChatResponse(
        reply=state.get("reply", "Done."),
        tool_used=state.get("tool_name"),
        tool_result=state.get("tool_result"),
    )
