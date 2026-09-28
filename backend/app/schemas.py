import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str = "Untitled session"
    platform: Literal["zoom", "file", "nextcloud", "bbb", "mock"] = "zoom"
    meeting_id: str | None = None
    source: Literal["manual", "zoom", "mock_rtms"] = "manual"

    scheduled_start: datetime | None = None
    duration_minutes: int | None = None
    participants: list[str] = Field(default_factory=list)


class SessionOut(BaseModel):
    id: str
    user_id: str | None = None
    title: str
    status: str
    platform: str
    meeting_id: str | None = None
    source: str = "manual"

    scheduled_start: datetime | None = None
    duration_minutes: int | None = None
    participants: list[str] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TranscriptOut(BaseModel):
    session_id: str
    text: str
    provider: str
    is_final: bool
    duration_seconds: float | None = None
    updated_at: datetime | None = None


class TranscribeResponse(BaseModel):
    session_id: str
    success: bool
    transcription: str
    provider: str
    duration_seconds: float | None = None
    chunks_processed: int = 1
    detail: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ZoomRTMSStartRequest(BaseModel):
    client_id: str | None = None
    session_id: str | None = None


class ZoomMeetingCreate(BaseModel):
    topic: str = "Kaituhi Korero meeting"
    type: int = 2  # scheduled
    start_time: str | None = None  # ISO8601 local wall time, used with timezone
    duration: int = 60
    timezone: str = "Pacific/Auckland"
    agenda: str | None = None
    # Invitee emails (Zoom settings.meeting_invitees)
    attendees: list[str] = Field(default_factory=list)


class ZoomMeetingUpdate(BaseModel):
    topic: str | None = None
    start_time: str | None = None
    duration: int | None = None
    timezone: str | None = None
    agenda: str | None = None


class HealthOut(BaseModel):
    status: str
    app: str
    papareo_configured: bool
    zoom_configured: bool
    zoom_user_connected: bool
    zoom_rtms_enabled: bool
    mock_rtms_enabled: bool


class MockRtmsStartResponse(BaseModel):
    session_id: str
    status: str
    mode: str
    audio_path: str


class RtmsStreamOut(BaseModel):
    id: int
    session_id: str | None = None
    meeting_id: str
    meeting_uuid: str | None = None
    rtms_stream_id: str | None = None
    status: str
    mode: str
    stop_reason: int | None = None
    created_at: datetime
    stopped_at: datetime | None = None
    updated_at: datetime

    class Config:
        from_attributes = True    
