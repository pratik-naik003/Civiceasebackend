from typing import Any

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, status

from app.core.config import settings

_initialized = False


def _firebase_env_credentials() -> dict[str, Any] | None:
    # Use .env-based service account fields when provided (no JSON file needed).
    required = [
        settings.firebase_project_id,
        settings.firebase_private_key,
        settings.firebase_client_email,
    ]
    if not all(required):
        return None

    private_key = settings.firebase_private_key.replace("\\n", "\n")

    return {
        "type": "service_account",
        "project_id": settings.firebase_project_id,
        "private_key_id": settings.firebase_private_key_id or "",
        "private_key": private_key,
        "client_email": settings.firebase_client_email,
        "client_id": settings.firebase_client_id or "",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": settings.firebase_client_x509_cert_url or "",
    }


def initialize_firebase() -> None:
    global _initialized
    if _initialized:
        return

    env_cred_dict = _firebase_env_credentials()
    if env_cred_dict:
        cred = credentials.Certificate(env_cred_dict)
    elif settings.firebase_credentials_path:
        cred = credentials.Certificate(settings.firebase_credentials_path)
    else:
        return

    firebase_admin.initialize_app(cred)
    _initialized = True


def verify_firebase_token(token: str) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")

    initialize_firebase()
    try:
        # Revocation checks require an additional backend call and can cause
        # noisy auth failures in local/dev environments.
        decoded = auth.verify_id_token(
            token,
            check_revoked=False,
            clock_skew_seconds=60,
        )
    except Exception as exc:
        detail = "Invalid auth token"
        if str(settings.debug).lower() == "true":
            detail = f"Invalid auth token: {exc}"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail) from exc

    expected_project = settings.firebase_project_id
    if expected_project and decoded.get("aud") != expected_project:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token project mismatch")

    return decoded
