from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionRecord, UserRecord, get_db
from app.deps import get_current_user
from app.schemas import ZoomMeetingCreate, ZoomMeetingUpdate, ZoomRTMSStartRequest
from app.services.auth_service import AuthError, create_oauth_state, parse_oauth_state
from app.services.zoom.client import ZoomClient
from app.services.zoom.oauth import (
    ZoomAuthError,
    build_authorize_url,
    disconnect_zoom_for_user,
    exchange_code_for_tokens,
    get_primary_token,
    get_token_for_user,
    get_valid_access_token,
    save_tokens,
    zoom_validation_response,
)
from app.services.zoom.rtms_live import extract_rtms_started_fields, live_rtms_consumer
from app.services.zoom.rtms_registry import rtms_session_registry
from app.services.zoom.rtms_runtime import summarize_and_store_rtms_event
from app.services.zoom.webhooks import summarize_webhook, verify_zoom_webhook_signature
from app.services.websocket_manager import hub

router = APIRouter(prefix="/api/zoom", tags=["zoom"])
logger = logging.getLogger(__name__)


def _parse_zoom_webhook_body(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace").strip()
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff").strip()
    if not text:
        return {}
    # Some clients accidentally double-encode JSON as a string.
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        try:
            inner = json.loads(text)
            if isinstance(inner, str):
                text = inner.strip()
        except json.JSONDecodeError:
            pass
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Zoom webhook JSON parse failed (%s). hex=%s preview=%r",
            exc,
            raw[:48].hex(),
            text[:300],
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid JSON webhook body: {exc}. "
                f"hex={raw[:24].hex()} preview={text[:80]!r}"
            ),
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Webhook JSON must be an object")
    return parsed


def _client(settings: Settings, db: Session, user: UserRecord) -> ZoomClient:
    return ZoomClient(settings, db=db, app_user_id=user.id)


def _resolve_rtms_session_id(
    db: Session,
    *,
    meeting_id: str | None,
    meeting_uuid: str | None = None,
    rtms_stream_id: str | None = None,
) -> str | None:
    session_id = rtms_session_registry.resolve_session_id(
        meeting_id,
        meeting_uuid,
        rtms_stream_id,
    )

    if session_id:
        return session_id

    if not meeting_id:
        return None

    record = db.scalars(
        select(SessionRecord)
        .where(SessionRecord.meeting_id == str(meeting_id))
        .order_by(SessionRecord.updated_at.desc())
    ).first()

    if not record:
        return None

    rtms_session_registry.bind(
        record.id,
        meeting_id=str(meeting_id),
        meeting_uuid=str(meeting_uuid) if meeting_uuid else None,
        rtms_stream_id=str(rtms_stream_id) if rtms_stream_id else None,
    )

    return record.id


@router.get("/oauth/start")
def zoom_oauth_start(
    user: UserRecord = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Return Zoom authorize URL for the signed-in app user (cookie-friendly)."""
    if not settings.zoom_client_id or not settings.zoom_client_secret:
        raise HTTPException(
            status_code=400,
            detail="ZOOM_CLIENT_ID / ZOOM_CLIENT_SECRET missing in backend .env. Restart uvicorn after editing.",
        )
    try:
        state = create_oauth_state(user.id, settings)
        url = build_authorize_url(settings, state=state)
    except (ZoomAuthError, AuthError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "authorize_url": url,
        "redirect_uri": settings.zoom_redirect_uri,
        "zoom_client_configured": True,
    }


@router.get("/oauth/login")
def zoom_oauth_login(
    user: UserRecord = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    started = zoom_oauth_start(user=user, settings=settings)
    return RedirectResponse(started["authorize_url"])


@router.get("/oauth/callback")
def zoom_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    frontend = settings.public_frontend_url.rstrip("/")

    if error:
        detail = error_description or error
        return RedirectResponse(f"{frontend}/scheduled?zoom_error={detail}")

    if not code:
        return RedirectResponse(f"{frontend}/scheduled?zoom_error=Missing+OAuth+code")
    if not state:
        return RedirectResponse(
            f"{frontend}/scheduled?zoom_error=Missing+OAuth+state.+Sign+in+and+Connect+Zoom+again."
        )
    try:
        app_user_id = parse_oauth_state(state, settings)
        token_payload = exchange_code_for_tokens(settings, code)
        record = save_tokens(db, settings, token_payload, app_user_id=app_user_id)
    except (ZoomAuthError, AuthError) as exc:
        from urllib.parse import quote

        return RedirectResponse(f"{frontend}/scheduled?zoom_error={quote(str(exc))}")

    return RedirectResponse(
        f"{frontend}/scheduled?connected=1&user={record.zoom_user_id}"
    )


@router.post("/oauth/disconnect")
def zoom_oauth_disconnect(
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    removed = disconnect_zoom_for_user(db, user.id)
    return {"disconnected": removed}


@router.get("/oauth/status")
def zoom_oauth_status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    record = get_token_for_user(db, user.id)
    return {
        "connected": record is not None,
        "zoom_client_configured": bool(settings.zoom_client_id and settings.zoom_client_secret),
        "user": None
        if record is None
        else {
            "zoom_user_id": record.zoom_user_id,
            "email": record.email,
            "display_name": record.display_name,
            "expires_at": record.expires_at.isoformat(),
            "scope": record.scope,
        },
    }


@router.get("/me")
def zoom_me(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return _client(settings, db, user).get_me()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/meetings")
def list_meetings(
    meeting_type: str = "upcoming",
    include_invited: bool = True,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        client = _client(settings, db, user)
        if include_invited and meeting_type in {"upcoming", "combined"}:
            return client.list_dashboard_meetings()
        return client.list_meetings(meeting_type=meeting_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/meetings")
def create_meeting(
    payload: ZoomMeetingCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "topic": payload.topic,
        "type": payload.type,
        "duration": payload.duration,
        "timezone": payload.timezone,
    }
    if payload.start_time:
        body["start_time"] = payload.start_time
    if payload.agenda:
        body["agenda"] = payload.agenda

    emails = [
        email.strip()
        for email in payload.attendees
        if isinstance(email, str) and "@" in email.strip()
    ]
    if emails:
        body["settings"] = {
            "meeting_invitees": [{"email": email} for email in emails],
            "email_notification": True,
        }

    try:
        return _client(settings, db, user).create_meeting(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/meetings/{meeting_id}")
def get_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return _client(settings, db, user).get_meeting(meeting_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/meetings/{meeting_id}")
def update_meeting(
    meeting_id: str,
    payload: ZoomMeetingUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    body = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        return _client(settings, db, user).update_meeting(meeting_id, body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/meetings/{meeting_id}")
def delete_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return _client(settings, db, user).delete_meeting(meeting_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/meetings/{meeting_id}/rtms/bind")
def bind_rtms_session(
    meeting_id: str,
    payload: ZoomRTMSStartRequest,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    """Bind an app session to a Zoom meeting so auto RTMS can push transcripts."""
    if not payload.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    record = db.get(SessionRecord, payload.session_id)
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    record.meeting_id = str(meeting_id)
    record.platform = "zoom"
    record.source = "zoom"
    record.status = "waiting_rtms"
    db.commit()
    rtms_session_registry.bind(payload.session_id, meeting_id=str(meeting_id))
    print(
        f"[zoom-rtms] bound session={payload.session_id} meeting_id={meeting_id}",
        flush=True,
    )
    return {
        "meeting_id": str(meeting_id),
        "session_id": payload.session_id,
        "status": "bound",
        "note": "Start/join the Zoom meeting. Transcripts appear when RTMS auto-starts.",
    }


@router.post("/meetings/{meeting_id}/rtms/start")
async def start_rtms(
    meeting_id: str,
    payload: ZoomRTMSStartRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    if not settings.zoom_rtms_enabled:
        raise HTTPException(
            status_code=400,
            detail="ZOOM_RTMS_ENABLED is false. Use Mock RTMS for local transcription demos.",
        )
    try:
        result = _client(settings, db, user).start_rtms(meeting_id, client_id=payload.client_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    print(f"[zoom-rtms-start] meeting_id={meeting_id} result={result!r}", flush=True)

    if payload.session_id:
        rtms_session_registry.bind(payload.session_id, meeting_id=meeting_id)
        record = db.get(SessionRecord, payload.session_id)
        if record and record.user_id == user.id:
            record.meeting_id = str(meeting_id)
            record.platform = "zoom"
            record.source = "zoom"
            record.status = "live_rtms_starting"
            db.commit()
        await hub.broadcast(
            payload.session_id,
            {
                "type": "zoom.rtms_start_requested",
                "session_id": payload.session_id,
                "meeting_id": meeting_id,
                "result": result,
                "message": (
                    "RTMS start requested. Waiting for Zoom webhook meeting.rtms_started "
                    "(requires public webhook URL / ngrok)."
                ),
            },
        )
    return {
        "meeting_id": meeting_id,
        "session_id": payload.session_id,
        "result": result,
        "note": (
            "Audio/transcript begins after Zoom sends meeting.rtms_started to your webhook. "
            "Keep ngrok pointed at the backend and Event Subscription enabled."
        ),
    }


@router.post("/meetings/{meeting_id}/rtms/stop")
def stop_rtms(
    meeting_id: str,
    payload: ZoomRTMSStartRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: UserRecord = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        result = _client(settings, db, user).stop_rtms(meeting_id, client_id=payload.client_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"meeting_id": meeting_id, "result": result}


@router.post("/webhook")
async def zoom_webhook(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    raw = await request.body()
    timestamp = request.headers.get("x-zm-request-timestamp")
    signature = request.headers.get("x-zm-signature")
    content_type = request.headers.get("content-type", "")
    logger.info(
        "Zoom webhook hit bytes=%s content_type=%s has_signature=%s",
        len(raw),
        content_type,
        bool(signature),
    )
    print(
        f"[zoom-webhook] bytes={len(raw)} content_type={content_type!r} "
        f"preview={raw[:120]!r}",
        flush=True,
    )
    if not verify_zoom_webhook_signature(
        secret_token=settings.zoom_webhook_secret_token,
        timestamp=timestamp,
        signature=signature,
        body=raw,
    ):
        raise HTTPException(status_code=401, detail="Invalid Zoom webhook signature")

    body = _parse_zoom_webhook_body(raw)
    event = body.get("event")
    print(f"[zoom-webhook] event={event!r}", flush=True)

    if event == "endpoint.url_validation":
        payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
        plain_token = str(payload.get("plainToken") or body.get("plainToken") or "")
        if not settings.zoom_webhook_secret_token:
            raise HTTPException(status_code=400, detail="ZOOM_WEBHOOK_SECRET_TOKEN missing")
        if not plain_token:
            raise HTTPException(status_code=400, detail="Missing plainToken for URL validation")
        return JSONResponse(
            zoom_validation_response(plain_token, settings.zoom_webhook_secret_token)
        )

    if not event:
        logger.warning("Zoom webhook missing event field: %s", body)
        return {"status": "ignored", "detail": "missing event"}

    payload = body.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    summary = summarize_webhook(str(event), payload)

    if event == "meeting.started":
        detail = "meeting.started received"
        rtms_result = None
        if settings.zoom_auto_start_rtms_on_meeting_started and settings.zoom_rtms_enabled:
            meeting_id = str(summary.get("meeting_id") or "")
            if meeting_id:
                try:
                    get_valid_access_token(db, settings)
                    rtms_result = ZoomClient(settings, db=db).start_rtms(meeting_id)
                    detail = "meeting.started received and RTMS start requested"
                except Exception as exc:
                    detail = f"meeting.started received; RTMS start failed: {exc}"
        return {
            "status": "received",
            "detail": detail,
            "summary": summary,
            "rtms_result": rtms_result,
        }

    if event == "meeting.rtms_started":
        fields = extract_rtms_started_fields(payload)
        session_id = _resolve_rtms_session_id(
            db,
            meeting_id=fields.get("meeting_id"),
            meeting_uuid=fields.get("meeting_uuid"),
            rtms_stream_id=fields.get("rtms_stream_id"),
        )
        stored = summarize_and_store_rtms_event(
            "meeting.rtms_started",
            payload,
            session_id=session_id,
            mode="live",
        )
        connect_info = await live_rtms_consumer.handle_rtms_started(
            stored,
            payload,
            settings=settings,
        )
        if session_id:
            await hub.broadcast(
                session_id,
                {
                    "type": "zoom.rtms_started",
                    "session_id": session_id,
                    "summary": stored,
                    "connect_info": connect_info,
                    "message": "Zoom RTMS started — connecting media consumer",
                },
            )
        return {
            "status": "received",
            "detail": "meeting.rtms_started handled",
            "summary": stored,
            "connect_info": connect_info,
        }

    if event == "meeting.rtms_stopped":
        fields = extract_rtms_started_fields(payload)
        session_id = _resolve_rtms_session_id(
            db,
            meeting_id=fields.get("meeting_id"),
            meeting_uuid=fields.get("meeting_uuid"),
            rtms_stream_id=fields.get("rtms_stream_id"),
        )
        summarize_and_store_rtms_event(
            "meeting.rtms_stopped",
            payload,
            session_id=session_id,
            mode="live",
        )
        await live_rtms_consumer.stop_stream(fields.get("rtms_stream_id"))
        if session_id:
            await hub.broadcast(
                session_id,
                {
                    "type": "zoom.rtms_stopped",
                    "session_id": session_id,
                    "message": "Zoom RTMS stopped",
                },
            )
            record = db.get(SessionRecord, session_id)
            if record:
                record.status = "completed"
                db.commit()
        return {"status": "received", "detail": "meeting.rtms_stopped handled", "summary": summary}

    return {"status": "ignored", "detail": f"Unhandled event: {event}", "summary": summary}
