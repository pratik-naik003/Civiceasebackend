from supabase import Client, create_client

from app.core.config import settings


class StorageService:
    def __init__(self) -> None:
        self._client: Client | None = None
        if settings.supabase_url and settings.supabase_service_role_key:
            self._client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    def signed_photo_url(self, photo_key: str) -> str | None:
        if not self._client:
            return None
        response = self._client.storage.from_(settings.supabase_bucket).create_signed_url(photo_key, 3600)
        return response.get("signedURL")

    def signed_upload_url(self, file_key: str) -> str | None:
        if not self._client:
            return None
        try:
            response = self._client.storage.from_(settings.supabase_bucket).create_signed_upload_url(file_key)
            return response.get("signed_url") or response.get("signedURL")
        except Exception:
            return None
