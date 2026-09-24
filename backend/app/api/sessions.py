from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import TranscriptRecord, SessionRecord, UserRecord, get_db
from app.deps import get_current_user
from app.schemas import (
    MockRtmsStartResponse,
    SessionCreate,
    SessionOut,
    TranscribeResponse,
    TranscriptOut,
)
from app.services.export_service import export_docx, export_json, export_txt
from app.services.speech.pipeline import PapaReoError, create_speech_pipeline
from app.services.websocket_manager import hub
from app.services.zoom.rtms_mock import MockRtmsError, start_mock_rtms_job

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_owned_session(db: Session, session_id: str, user: UserRecord) -> SessionRecord:
    record = db.get(SessionRecord, session_id)
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return record

def _get_session_transcript(
    db: Session,
    session_id: str,
) -> tuple[str, str, bool, datetime | None]:
    transcripts = list(
        db.scalars(
            select(TranscriptRecord)
            .where(TranscriptRecord.session_id == session_id)
            .order_by(TranscriptRecord.created_at.asc())
        )
    )

    if not transcripts:
        return "", "none", False, None

    rtms_providers = {
        "papa_reo_streaming_live_rtms",
        "papa_reo_standard_live_rtms",
    }

    rtms_transcripts = [
        transcript
        for transcript in transcripts
        if transcript.provider in rtms_providers and transcript.text
    ]

    if rtms_transcripts:
        text_parts = [
            transcript.text.strip()
            for transcript in rtms_transcripts
            if transcript.text and transcript.text.strip()
        ]

        combined_text = "\n".join(text_parts)

        providers = []
        for transcript in rtms_transcripts:
            if transcript.provider not in providers:
                providers.append(transcript.provider)

        provider = " + ".join(providers)
        is_final = all(transcript.is_final for transcript in rtms_transcripts)
        updated_at = max(
            (
                transcript.updated_at or transcript.created_at
                for transcript in rtms_transcripts
            ),
            default=None,
        )

        return combined_text, provider, is_final, updated_at

    transcript = transcripts[-1]

    return (
        transcript.text,
        transcript.provider,
        transcript.is_final,
        transcript.updated_at or transcript.created_at,
    )


@router.post("", response_model=SessionOut)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
) -> SessionRecord:
    record = SessionRecord(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=payload.title,
        platform=payload.platform,
        meeting_id=payload.meeting_id,
        source=payload.source,
        status="created",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[SessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
) -> list[SessionRecord]:
    return list(
        db.scalars(
            select(SessionRecord)
            .where(SessionRecord.user_id == user.id)
            .order_by(SessionRecord.created_at.desc())
        )
    )


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
) -> SessionRecord:
    return _get_owned_session(db, session_id, user)


@router.post("/{session_id}/stop", response_model=SessionOut)
def stop_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
) -> SessionRecord:
    record = _get_owned_session(db, session_id, user)
    record.status = "stopped"
    record.updated_at = _now()
    db.commit()
    db.refresh(record)
    return record


@router.post("/{session_id}/transcribe", response_model=TranscribeResponse)
async def transcribe_session_audio(
    session_id: str,
    audio_file: UploadFile = File(...),
    with_metadata: bool = Form(False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> TranscribeResponse:
    record = _get_owned_session(db, session_id, user)

    record.status = "transcribing"
    record.updated_at = _now()
    db.commit()

    suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
    target = settings.upload_path / session_id / f"upload{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = await audio_file.read()
    target.write_bytes(content)

    pipeline = create_speech_pipeline(settings)

    async def on_partial(message: dict) -> None:
        message["session_id"] = session_id
        await hub.broadcast(session_id, message)

    try:
        result = await pipeline.process_audio_auto(
            target,
            work_dir=settings.upload_path / session_id / "work",
            with_metadata=with_metadata,
            on_partial=on_partial,
        )
    except PapaReoError as exc:
        record.status = "error"
        record.updated_at = _now()
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        record.status = "error"
        record.updated_at = _now()
        db.commit()
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    transcript = TranscriptRecord(
        session_id=session_id,
        provider=str(result.get("provider") or "papa_reo_streaming"),
        text=str(result.get("transcription") or ""),
        is_final=True,
        duration_seconds=result.get("duration_seconds"),
    )
    db.add(transcript)
    record.status = "completed" if result.get("success") else "error"
    record.updated_at = _now()
    db.commit()

    await hub.broadcast(
        session_id,
        {
            "type": "transcript.final",
            "session_id": session_id,
            "text": transcript.text,
            "is_final": True,
            "provider": transcript.provider,
        },
    )

    return TranscribeResponse(
        session_id=session_id,
        success=bool(result.get("success")),
        transcription=transcript.text,
        provider=transcript.provider,
        duration_seconds=transcript.duration_seconds,
        chunks_processed=int(result.get("chunks_processed") or 1),
        detail=result.get("detail"),
        raw=result.get("raw") or {},
    )


@router.get("/{session_id}/transcript", response_model=TranscriptOut)
def get_transcript(
    session_id: str,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
) -> TranscriptOut:
    session = _get_owned_session(db, session_id, user)

    text, provider, is_final, updated_at = _get_session_transcript(
        db,
        session_id,
    )

    return TranscriptOut(
        session_id=session_id,
        text=text,
        provider=provider,
        is_final=is_final,
        duration_seconds=None,
        updated_at=updated_at or session.updated_at,
    )


@router.get("/{session_id}/export")
def export_transcript(
    session_id: str,
    format: str = "txt",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
):
    session = _get_owned_session(db, session_id, user)

    text, provider, is_final, updated_at = _get_session_transcript(
        db,
        session_id,
    )
    export_dir = settings.transcript_path / session_id
    export_dir.mkdir(parents=True, exist_ok=True)
    fmt = format.lower().strip()

    if fmt == "txt":
        path = export_txt(text, export_dir / "transcript.txt")
        media = "text/plain"
    elif fmt == "json":
        path = export_json(
            {
                "session_id": session_id,
                "title": session.title,
                "transcription": text,
                "provider": provider,
            },
            export_dir / "transcript.json",
        )
        media = "application/json"
    elif fmt == "docx":
        path = export_docx(text, export_dir / "transcript.docx", title=session.title)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        raise HTTPException(status_code=400, detail="Supported formats: txt, json, docx")

    return FileResponse(path, media_type=media, filename=path.name)


@router.post("/{session_id}/mock-rtms/start", response_model=MockRtmsStartResponse)
async def start_mock_rtms(
    session_id: str,
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> MockRtmsStartResponse:
    """Simulate Zoom RTMS using a local meeting recording.

    This path exercises the same downstream speech + websocket flow without a live Zoom meeting.
    """
    record = _get_owned_session(db, session_id, user)

    suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
    target = settings.upload_path / session_id / f"mock_source{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(await audio_file.read())

    record.platform = "mock"
    record.source = "mock_rtms"
    record.status = "mock_starting"
    record.updated_at = _now()
    db.commit()

    try:
        result = await start_mock_rtms_job(
            session_id=session_id,
            audio_path=target,
            settings=settings,
        )
    except MockRtmsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MockRtmsStartResponse(**result)
