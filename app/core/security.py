from typing import Any

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, status

from app.core.config import settings

_initialized = False


def initialize_firebase() -> None:
    global _initialized
    if _initialized:
        return

    if not settings.firebase_credentials_path:
        return

    cred = credentials.Certificate(settings.firebase_credentials_path)
    firebase_admin.initialize_app(cred)
    _initialized = True


def verify_firebase_token(token: str) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")

    initialize_firebase()
    try:
        decoded = auth.verify_id_token(token, check_revoked=True)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token") from exc

    expected_project = settings.firebase_project_id
    if expected_project and decoded.get("aud") != expected_project:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token project mismatch")

    return decoded
