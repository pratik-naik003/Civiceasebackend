import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.deps import DbSession, get_current_user
from app.models.user import User
from app.schemas.chatbot import ChatbotMessageRequest, ChatbotSessionResponse, ChatbotTurnResponse
from app.services.chatbot.service import ComplaintChatbotService

router = APIRouter(prefix="/chatbot")


def _sse_payload(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@router.post("/sessions", response_model=ChatbotSessionResponse, status_code=status.HTTP_201_CREATED)
def create_chatbot_session(db: DbSession, user: User = Depends(get_current_user)):
    service = ComplaintChatbotService(db, user)
    session = service.create_session()
    return ChatbotSessionResponse.model_validate(service.build_session_response(session))


@router.get("/sessions/{session_id}", response_model=ChatbotSessionResponse)
def get_chatbot_session(session_id: str, db: DbSession, user: User = Depends(get_current_user)):
    service = ComplaintChatbotService(db, user)
    try:
        session = service.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatbotSessionResponse.model_validate(service.build_session_response(session))


@router.post("/message", response_model=ChatbotTurnResponse)
def send_chatbot_message(payload: ChatbotMessageRequest, db: DbSession, user: User = Depends(get_current_user)):
    service = ComplaintChatbotService(db, user)
    try:
        state = service.run_turn(
            payload.session_id,
            message=payload.message,
            photo_keys=payload.photo_keys,
            location=payload.location,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ChatbotTurnResponse.model_validate(service.build_turn_response(state))


@router.post("/message/stream")
def stream_chatbot_message(payload: ChatbotMessageRequest, db: DbSession, user: User = Depends(get_current_user)):
    service = ComplaintChatbotService(db, user)
    try:
        service.get_session(payload.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def event_stream():
        try:
            for event in service.stream_turn(
                payload.session_id,
                message=payload.message,
                photo_keys=payload.photo_keys,
                location=payload.location,
            ):
                yield _sse_payload(event)
        except Exception as exc:  # pragma: no cover
            yield _sse_payload({"type": "error", "detail": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


