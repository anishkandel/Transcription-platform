from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.db import SessionLocal, SessionRecord, TranscriptRecord
from app.services.speech.pipeline import create_speech_pipeline
from app.services.websocket_manager import hub
from app.services.zoom.rtms_runtime import summarize_and_store_rtms_event

logger = logging.getLogger(__name__)

_running_jobs: dict[str, asyncio.Task] = {}


class MockRtmsError(RuntimeError):
    pass


async def start_mock_rtms_job(
    *,
    session_id: str,
    audio_path: Path,
    settings: Settings,
) -> dict[str, Any]:
    if not settings.mock_rtms_enabled:
        raise MockRtmsError("Mock RTMS is disabled")

    if session_id in _running_jobs and not _running_jobs[session_id].done():
        raise MockRtmsError("Mock RTMS already running for this session")

    task = asyncio.create_task(
        _run_mock_rtms(session_id=session_id, audio_path=audio_path, settings=settings)
    )
    _running_jobs[session_id] = task
    return {
        "session_id": session_id,
        "status": "started",
        "mode": "mock_rtms_chunked_standard",
        "audio_path": str(audio_path),
    }


async def _run_mock_rtms(*, session_id: str, audio_path: Path, settings: Settings) -> None:
    """Mock Zoom RTMS by feeding short audio slices into Standard API."""
    work_dir = settings.upload_path / session_id / "mock_rtms"
    work_dir.mkdir(parents=True, exist_ok=True)
    local_audio = work_dir / audio_path.name
    if audio_path.resolve() != local_audio.resolve():
        shutil.copy2(audio_path, local_audio)

    summarize_and_store_rtms_event(
        "meeting.rtms_started",
        {
            "object": {
                "id": f"mock-{session_id}",
                "uuid": f"mock-uuid-{session_id}",
                "rtms_stream_id": f"mock-stream-{session_id}",
                "topic": "Mock RTMS stream",
            }
        },
        session_id=session_id,
        mode="mock",
    )

    await hub.broadcast(
        session_id,
        {
            "type": "mock.rtms_started",
            "session_id": session_id,
            "message": (
                "Mock Zoom RTMS started. Audio will be transcribed chunk-by-chunk "
                "with Papa Reo Standard API for a realtime-like UI."
            ),
            "provider": "papa_reo_standard_chunked",
        },
    )

    db: Session = SessionLocal()
    try:
        record = db.get(SessionRecord, session_id)
        if record:
            record.status = "mock_streaming"
            record.source = "mock_rtms"
            db.commit()
    finally:
        db.close()

    pipeline = create_speech_pipeline(settings)

    async def on_partial(message: dict[str, Any]) -> None:
        message["session_id"] = session_id
        message["source"] = "mock_rtms"
        await hub.broadcast(session_id, message)

    try:
        result = await pipeline.process_audio_file_progressive(
            local_audio,
            work_dir=work_dir / "progressive_work",
            on_partial=on_partial,
            chunk_seconds=settings.mock_rtms_chunk_seconds
            or settings.progressive_chunk_seconds,
            pace_delay_seconds=settings.progressive_delay_seconds,
        )

        final_text = str(result.get("transcription") or "")
        db = SessionLocal()
        try:
            db.add(
                TranscriptRecord(
                    session_id=session_id,
                    provider="papa_reo_standard_chunked",
                    text=final_text,
                    is_final=True,
                    duration_seconds=result.get("duration_seconds"),
                )
            )
            record = db.get(SessionRecord, session_id)
            if record:
                record.status = "completed" if result.get("success") else "error"
            db.commit()
        finally:
            db.close()

        await hub.broadcast(
            session_id,
            {
                "type": "transcript.final",
                "session_id": session_id,
                "text": final_text,
                "is_final": True,
                "provider": "papa_reo_standard_chunked",
                "source": "mock_rtms",
            },
        )
        await hub.broadcast(
            session_id,
            {
                "type": "mock.rtms_stopped",
                "session_id": session_id,
                "message": "Mock Zoom RTMS completed",
            },
        )
    except Exception as exc:
        logger.exception("Mock RTMS failed for session %s", session_id)
        db = SessionLocal()
        try:
            record = db.get(SessionRecord, session_id)
            if record:
                record.status = "error"
                db.commit()
        finally:
            db.close()
        await hub.broadcast(
            session_id,
            {
                "type": "mock.rtms_error",
                "session_id": session_id,
                "message": str(exc),
            },
        )
