from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class VoiceTokenRequest(BaseModel):
    room_name: str = Field(..., min_length=3, max_length=80)
    participant_name: str = Field(..., min_length=2, max_length=80)

    @field_validator("room_name", "participant_name")
    @classmethod
    def strip_and_validate(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value cannot be empty.")
        return cleaned


class VoiceTokenResponse(BaseModel):
    token: str
    room_name: str
    participant_name: str
    participant_identity: str
    server_url: str
    expires_in_seconds: int
