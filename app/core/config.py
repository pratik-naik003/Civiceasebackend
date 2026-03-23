from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CivicEase Backend"
    app_env: str = "dev"
    debug: str = Field(default="true", alias="DEBUG")

    database_url: str = Field(
        default="sqlite:///./civicease.db",
        alias="DATABASE_URL",
    )

    firebase_project_id: str | None = Field(default=None, alias="FIREBASE_PROJECT_ID")
    firebase_credentials_path: str | None = Field(default=None, alias="FIREBASE_CREDENTIALS_PATH")

    cerebras_api_key: str | None = Field(default=None, alias="CEREBRAS_API_KEY")
    cerebras_model: str = Field(default="llama-4-scout-17b-16e-instruct", alias="CEREBRAS_MODEL")
    cerebras_base_url: str = Field(default="https://api.cerebras.ai/v1", alias="CEREBRAS_BASE_URL")

    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_service_role_key: str | None = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_bucket: str = Field(default="issue-photos", alias="SUPABASE_BUCKET")

    cluster_geo_threshold_meters: float = Field(default=120.0, alias="CLUSTER_GEO_THRESHOLD_METERS")
    cluster_text_threshold: float = Field(default=0.45, alias="CLUSTER_TEXT_THRESHOLD")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
