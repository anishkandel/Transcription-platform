from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Kaituhi Korero"
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    public_backend_url: str = "http://127.0.0.1:8000"
    public_frontend_url: str = "http://127.0.0.1:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Prefer one shared DB under the Compose volume ./data (see docker-compose.yml).
    # Local uvicorn from backend/: set DATABASE_URL in project .env to
    # sqlite:///../data/kaituhi.db so it matches Docker.
    database_url: str
    upload_dir: str = "./data/uploads"
    transcript_dir: str = "./data/transcripts"


    papareo_api_key: str = ""
    papareo_base_url: str = "https://api.papareo.io"
    papareo_transcribe_path: str = "/tuhi/transcribe"
    papareo_create_session_path: str = "/tuhi/create_session"
    papareo_mode: str = "streaming"  # streaming | standard
    papareo_stream_encoding: str = "pcm"
    papareo_stream_sample_rate: int = 16000
    papareo_stream_channels: int = 1
    papareo_stream_chunk_bytes: int = 3200  # ~100ms at 16kHz mono PCM16
    papareo_stream_pace_realtime: bool = True

    # Zoom OAuth app credentials (assume available)
    zoom_account_id: str = ""
    zoom_client_id: str = ""
    zoom_client_secret: str = ""
    zoom_redirect_uri: str = "http://127.0.0.1:8000/api/zoom/oauth/callback"
    zoom_webhook_secret_token: str = ""
    zoom_rtms_enabled: bool = True
    zoom_auto_start_rtms_on_meeting_started: bool = True
    zoom_oauth_authorize_url: str = "https://zoom.us/oauth/authorize"
    zoom_oauth_token_url: str = "https://zoom.us/oauth/token"
    zoom_api_base_url: str = "https://api.zoom.us/v2"
    # Must also be enabled on the Marketplace app (Scopes tab).
    zoom_oauth_scopes: str = (
        "user:read:user "
        "meeting:read:list_meetings "
        "meeting:read:list_upcoming_meetings "
        "meeting:read:meeting "
        "meeting:write:meeting "
        "meeting:update:meeting "
        "meeting:delete:meeting "
        "meeting:update:participant_rtms_app_status "
        "meeting:read:meeting_audio"
    )
    zoom_token_encryption_key: str

    # Mock RTMS testing without a live Zoom meeting
    mock_rtms_enabled: bool = True
    mock_rtms_chunk_seconds: int = 60
    mock_rtms_realtime_delay: bool = False

    vad_enabled: bool = False
    max_standard_audio_seconds: int = 300
    default_chunk_seconds: int = 240
    progressive_chunk_seconds: int = 20
    progressive_delay_seconds: float = 0.35

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def transcript_path(self) -> Path:
        path = Path(self.transcript_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    if settings.app_env.lower() == "production":
        if settings.database_url.startswith("sqlite"):
            raise RuntimeError(
                "DATABASE_URL must use PostgreSQL in production."
            )

        if settings.secret_key == "change-me-in-production":
            raise RuntimeError(
                "SECRET_KEY must be configured in production."
            )

        if not settings.papareo_api_key:
            raise RuntimeError(
                "PAPAREO_API_KEY must be configured in production."
            )

        if not settings.zoom_client_id or not settings.zoom_client_secret:
            raise RuntimeError(
                "Zoom credentials must be configured in production."
            )

    Path("data").mkdir(parents=True, exist_ok=True)
    settings.upload_path
    settings.transcript_path

    return settings
