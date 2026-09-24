from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import (
    RtmsStreamRecord,
    TranscriptRecord,
    SessionRecord,
    SessionLocal,
)
from app.services.zoom.rtms_live import extract_rtms_started_fields
from app.services.zoom.webhooks import summarize_webhook


def summarize_and_store_rtms_event(
    event_name: str,
    payload: dict[str, Any],
    *,
    session_id: str | None = None,
    mode: str = "live",
) -> dict[str, Any]:
    summary = summarize_webhook(event_name, payload)
    fields = extract_rtms_started_fields(payload)

    # Zoom's actual webhook payload body.
    event_payload = payload.get("payload")
    if not isinstance(event_payload, dict):
        event_payload = {}

    meeting_id_value = (
        fields.get("meeting_id")
        or summary.get("meeting_id")
    )

    meeting_uuid = (
        fields.get("meeting_uuid")
        or event_payload.get("meeting_uuid")
        or summary.get("uuid")
    )

    rtms_stream_id = (
        fields.get("rtms_stream_id")
        or event_payload.get("rtms_stream_id")
    )

    raw_stop_reason = event_payload.get("stop_reason")

    if raw_stop_reason is None:
        raw_stop_reason = payload.get("stop_reason")

    if raw_stop_reason is None:
        raw_stop_reason = summary.get("stop_reason")

    try:
        stop_reason = (
            int(raw_stop_reason)
            if raw_stop_reason is not None
            else None
        )
    except (TypeError, ValueError):
        stop_reason = None

    is_started = event_name.endswith("rtms_started")
    is_stopped = event_name.endswith("rtms_stopped")

    now = datetime.now(timezone.utc)

    resolved_meeting_id = (
        str(meeting_id_value)
        if meeting_id_value
        else None
    )

    resolved_session_id = session_id

    db: Session = SessionLocal()

    try:
        # If the in-memory registry did not provide a session,
        # recover it from PostgreSQL using the Zoom meeting ID.
        if resolved_session_id is None and resolved_meeting_id:
            session_record = db.scalars(
                select(SessionRecord)
                .where(SessionRecord.meeting_id == resolved_meeting_id)
                .order_by(SessionRecord.updated_at.desc())
            ).first()

            if session_record is not None:
                resolved_session_id = session_record.id

        record: RtmsStreamRecord | None = None

        # Best match: RTMS stream ID.
        if rtms_stream_id:
            record = db.scalar(
                select(RtmsStreamRecord)
                .where(
                    RtmsStreamRecord.rtms_stream_id
                    == str(rtms_stream_id)
                )
                .order_by(RtmsStreamRecord.id.desc())
            )

        # Fallback: latest active stream for this meeting UUID.
        if record is None and meeting_uuid:
            record = db.scalar(
                select(RtmsStreamRecord)
                .where(
                    RtmsStreamRecord.meeting_uuid
                    == str(meeting_uuid),
                    RtmsStreamRecord.status != "stopped",
                )
                .order_by(RtmsStreamRecord.id.desc())
            )

        if record is None:
            # No existing stream found, so create one.
            record = RtmsStreamRecord(
                session_id=resolved_session_id,
                meeting_id=resolved_meeting_id or "unknown",
                meeting_uuid=(
                    str(meeting_uuid)
                    if meeting_uuid
                    else None
                ),
                rtms_stream_id=(
                    str(rtms_stream_id)
                    if rtms_stream_id
                    else None
                ),
                status=(
                    "stopped"
                    if is_stopped
                    else "started"
                    if is_started
                    else "updated"
                ),
                mode=mode,
                raw_json=json.dumps(payload),
                stop_reason=stop_reason if is_stopped else None,
                stopped_at=now if is_stopped else None,
                updated_at=now,
            )

            db.add(record)

        else:
            # Keep information already stored if the stopped webhook
            # does not send it again.
            if resolved_meeting_id is None:
                resolved_meeting_id = record.meeting_id

            if resolved_session_id is None:
                resolved_session_id = record.session_id

            # The stop webhook may not contain meeting_id.
            # Recover the app session using the meeting_id already
            # stored on the RTMS record.
            if resolved_session_id is None and resolved_meeting_id:
                session_record = db.scalars(
                    select(SessionRecord)
                    .where(
                        SessionRecord.meeting_id
                        == resolved_meeting_id
                    )
                    .order_by(SessionRecord.updated_at.desc())
                ).first()

                if session_record is not None:
                    resolved_session_id = session_record.id

            # Backfill the RTMS record once we know the session.
            if resolved_session_id:
                record.session_id = resolved_session_id

            if meeting_id_value:
                record.meeting_id = str(meeting_id_value)

            if meeting_uuid:
                record.meeting_uuid = str(meeting_uuid)

            if rtms_stream_id:
                record.rtms_stream_id = str(rtms_stream_id)

            record.mode = mode
            record.raw_json = json.dumps(payload)
            record.updated_at = now

            if is_stopped:
                record.status = "stopped"
                record.stop_reason = stop_reason
                record.stopped_at = now

            elif is_started:
                record.status = "started"

            else:
                record.status = "updated"

        # Finalise the RTMS transcripts and app session when RTMS stops.
        if is_stopped:
            final_session_id = (
                resolved_session_id
                or record.session_id
            )

            if final_session_id:
                transcripts = list(
                    db.scalars(
                        select(TranscriptRecord)
                        .where(
                            TranscriptRecord.session_id
                            == final_session_id,
                            TranscriptRecord.provider.in_(
                                [
                                    "papa_reo_streaming_live_rtms",
                                    "papa_reo_standard_live_rtms",
                                ]
                            ),
                        )
                    )
                )

                for transcript in transcripts:
                    transcript.is_final = True

                session_record = db.get(
                    SessionRecord,
                    final_session_id,
                )

                if session_record is not None:
                    session_record.status = "completed"
                    session_record.updated_at = now

        db.commit()

    finally:
        db.close()

    summary["meeting_id"] = resolved_meeting_id or "unknown"
    summary["uuid"] = meeting_uuid
    summary["rtms_stream_id"] = rtms_stream_id
    summary["server_urls"] = fields.get("server_urls")
    summary["session_id"] = resolved_session_id

    if is_stopped:
        summary["stop_reason"] = stop_reason

    return summary