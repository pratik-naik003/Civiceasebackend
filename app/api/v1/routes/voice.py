from __future__ import annotations

import re
from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from livekit.api import AccessToken, LiveKitAPI, VideoGrants
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest
from livekit.protocol.room import CreateRoomRequest, ListRoomsRequest

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.voice import VoiceTokenRequest, VoiceTokenResponse

router = APIRouter(prefix="/voice")
VOICE_AGENT_NAME = "civicease-voice"


def _slugify_identity(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "participant"


def _build_token_response(room_name: str, participant_name: str) -> VoiceTokenResponse:
    if not settings.livekit_url or not settings.livekit_api_key or not settings.livekit_api_secret:
        raise HTTPException(
            status_code=500,
            detail="LiveKit server credentials are not configured on the API server.",
        )

    participant_identity = f"{_slugify_identity(participant_name)}-{uuid4().hex[:8]}"
    grant = VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
        can_publish_sources=["microphone"],
    )
    token = (
        AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(participant_identity)
        .with_name(participant_name)
        .with_grants(grant)
        .with_ttl(timedelta(minutes=settings.livekit_token_ttl_minutes))
        .to_jwt()
    )

    return VoiceTokenResponse(
        token=token,
        room_name=room_name,
        participant_name=participant_name,
        participant_identity=participant_identity,
        server_url=settings.livekit_url,
        expires_in_seconds=settings.livekit_token_ttl_minutes * 60,
    )


async def _ensure_voice_agent_dispatch(room_name: str) -> None:
    try:
        async with LiveKitAPI(
            url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        ) as livekit_api:
            rooms = await livekit_api.room.list_rooms(ListRoomsRequest(names=[room_name]))
            if not rooms.rooms:
                await livekit_api.room.create_room(CreateRoomRequest(name=room_name))

            dispatches = await livekit_api.agent_dispatch.list_dispatch(room_name)
            if any(dispatch.agent_name == VOICE_AGENT_NAME for dispatch in dispatches):
                return

            await livekit_api.agent_dispatch.create_dispatch(
                CreateAgentDispatchRequest(
                    room=room_name,
                    agent_name=VOICE_AGENT_NAME,
                    metadata="civicease-voice",
                )
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Voice agent worker could not be dispatched to the room.",
        ) from exc


@router.post("/token", response_model=VoiceTokenResponse)
async def create_voice_token(payload: VoiceTokenRequest, _: User = Depends(get_current_user)) -> VoiceTokenResponse:
    response = _build_token_response(room_name=payload.room_name, participant_name=payload.participant_name)
    await _ensure_voice_agent_dispatch(payload.room_name)
    return response


@router.get("/token", response_model=VoiceTokenResponse)
async def get_voice_token(
    room_name: str = Query(..., min_length=3, max_length=80),
    participant_name: str = Query(..., min_length=2, max_length=80),
    _: User = Depends(get_current_user),
) -> VoiceTokenResponse:
    payload = VoiceTokenRequest(room_name=room_name, participant_name=participant_name)
    response = _build_token_response(room_name=payload.room_name, participant_name=payload.participant_name)
    await _ensure_voice_agent_dispatch(payload.room_name)
    return response
