"""Live Zoom RTMS media consumer → Papa Reo → WebSocket transcript.

Flow:
1. meeting.rtms_started webhook provides meeting_uuid, rtms_stream_id, server_urls
2. Signaling WebSocket handshake (msg_type 1)
3. Media WebSocket handshake for audio (msg_type 3, media_type 1)
4. CLIENT_READY_ACK on signaling socket (msg_type 7)
5. Receive MEDIA_DATA_AUDIO (msg_type 14), decode base64 PCM16 @ 16kHz mono
6. Prefer Papa Reo Streaming (raw PCM over WS); fall back to Standard WAV slices
7. Broadcast transcript updates to the linked app session
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import wave
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect as ws_connect

from app.config import Settings, get_settings
from app.db import SessionLocal, SessionRecord, TranscriptRecord
from app.services.speech.assembler import assemble_transcript_parts
from app.services.speech.papa_reo import PapaReoClient
from app.services.speech.streaming import PapaReoLiveStreamer
from app.services.websocket_manager import hub
from app.services.zoom.rtms_registry import rtms_session_registry

logger = logging.getLogger(__name__)

# Zoom RTMS message types
SIGNALING_HAND_SHAKE_REQ = 1
SIGNALING_HAND_SHAKE_RESP = 2
DATA_HAND_SHAKE_REQ = 3
DATA_HAND_SHAKE_RESP = 4
CLIENT_READY_ACK = 7
KEEP_ALIVE_REQ = 12
KEEP_ALIVE_RESP = 13
MEDIA_DATA_AUDIO = 14
MEDIA_DATA_TRANSCRIPT = 17

MEDIA_TYPE_AUDIO = 1

# 16-bit PCM mono @ 16 kHz
SAMPLE_RATE = 16000
BYTES_PER_SECOND = SAMPLE_RATE * 2
DEFAULT_CHUNK_SECONDS = 4.0
# Skip near-silence before Papa Reo (ASR often hallucinates on quiet noise).
SILENCE_RMS_THRESHOLD = 180.0


def _l16_be_to_pcm16le(data: bytes) -> bytes:
    """Convert Zoom RTMS L16 samples to little-endian PCM16 for WAV/Papa Reo.

    Zoom RTMS RAW audio with codec=L16 is linear 16-bit PCM. L16 uses network
    byte order, while WAV/AudioSegment PCM16 on our backend expects little-endian
    sample bytes. Swap each 16-bit sample before RMS checks, buffering, and WAV
    creation.
    """
    if len(data) < 2:
        return b""
    if len(data) % 2:
        data = data[:-1]
    converted = bytearray(len(data))
    converted[0::2] = data[1::2]
    converted[1::2] = data[0::2]
    return bytes(converted)


def _pcm16_rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    # Average absolute amplitude ≈ cheap RMS proxy for converted PCM16LE.
    n = len(pcm) // 2
    total = 0
    for i in range(0, n * 2, 2):
        sample = int.from_bytes(pcm[i : i + 2], "little", signed=True)
        total += abs(sample)
    return total / n if n else 0.0


def _pcm16_is_silent(pcm: bytes, threshold: float = SILENCE_RMS_THRESHOLD) -> bool:
    return _pcm16_rms(pcm) < threshold


def generate_rtms_signature(
    *,
    client_id: str,
    client_secret: str,
    meeting_uuid: str,
    rtms_stream_id: str,
) -> str:
    message = f"{client_id},{meeting_uuid},{rtms_stream_id}"
    return hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def extract_rtms_started_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Support both flat Zoom RTMS payloads and nested `object` shapes."""
    obj = payload.get("object") if isinstance(payload.get("object"), dict) else {}
    meeting_uuid = (
        payload.get("meeting_uuid")
        or obj.get("meeting_uuid")
        or obj.get("uuid")
        or payload.get("uuid")
    )
    meeting_id = (
        payload.get("meeting_id")
        or obj.get("meeting_id")
        or obj.get("id")
        or payload.get("id")
    )
    rtms_stream_id = (
        payload.get("rtms_stream_id")
        or obj.get("rtms_stream_id")
        or obj.get("stream_id")
    )
    server_urls = payload.get("server_urls") or obj.get("server_urls")
    return {
        "meeting_uuid": str(meeting_uuid) if meeting_uuid else None,
        "meeting_id": str(meeting_id) if meeting_id else None,
        "rtms_stream_id": str(rtms_stream_id) if rtms_stream_id else None,
        "server_urls": server_urls,
    }


def _pick_signaling_url(server_urls: Any) -> str | None:
    if isinstance(server_urls, str):
        # Zoom may send comma-separated URLs; prefer the first ws/wss entry.
        for part in (p.strip() for p in server_urls.split(",")):
            if part.startswith("ws"):
                return part
        return None
    if isinstance(server_urls, dict):
        for key in ("signaling", "all", "audio"):
            value = server_urls.get(key)
            if isinstance(value, str) and value.startswith("ws"):
                return value
    if isinstance(server_urls, list):
        for value in server_urls:
            if isinstance(value, str) and value.startswith("ws"):
                return value
    return None


def _pick_media_audio_url(media_server: dict[str, Any]) -> str | None:
    urls = media_server.get("server_urls") if isinstance(media_server, dict) else None
    if isinstance(urls, str) and urls.startswith("ws"):
        return urls
    if isinstance(urls, dict):
        for key in ("audio", "all", "transcript"):
            value = urls.get(key)
            if isinstance(value, str) and value.startswith("ws"):
                return value
    return None


def _pcm16_to_wav_path(pcm: bytes, path: Path, sample_rate: int = SAMPLE_RATE) -> Path:
    """Write little-endian PCM16 mono audio to a WAV file.

    Uses Python's standard-library wave module instead of pydub/audioop so this
    works cleanly on Python 3.13, where audioop was removed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return path


class LiveRtmsConsumer:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    async def handle_rtms_started(
        self,
        summary: dict[str, Any],
        raw_payload: dict[str, Any],
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        settings = settings or get_settings()
        fields = extract_rtms_started_fields(raw_payload)
        meeting_uuid = fields["meeting_uuid"] or summary.get("uuid")
        meeting_id = fields["meeting_id"] or summary.get("meeting_id")
        rtms_stream_id = fields["rtms_stream_id"] or summary.get("rtms_stream_id")

        session_id = rtms_session_registry.resolve_session_id(
            meeting_id,
            meeting_uuid,
            rtms_stream_id,
            summary.get("session_id"),
        )
        # Auto-start / Surface may fire before the Session page click. Fall back to
        # the latest app session that already has this Zoom meeting_id.
        if not session_id and meeting_id:
            session_id = self._resolve_session_from_db(str(meeting_id))
        if session_id and meeting_uuid:
            rtms_session_registry.bind(
                session_id,
                meeting_id=str(meeting_id) if meeting_id else None,
                meeting_uuid=str(meeting_uuid),
                rtms_stream_id=str(rtms_stream_id) if rtms_stream_id else None,
            )

        signaling_url = _pick_signaling_url(fields["server_urls"])
        connect_info = {
            "meeting_id": meeting_id,
            "meeting_uuid": meeting_uuid,
            "rtms_stream_id": rtms_stream_id,
            "session_id": session_id,
            "signaling_url": signaling_url,
            "server_urls_preview": str(fields["server_urls"])[:160] if fields["server_urls"] else None,
            "status": "starting" if signaling_url else "missing_server_urls",
        }
        print(f"[zoom-rtms] handle_rtms_started {connect_info!r}", flush=True)

        if not meeting_uuid or not rtms_stream_id or not signaling_url:
            print(f"[zoom-rtms] missing fields, abort: {connect_info!r}", flush=True)
            logger.warning("RTMS started but missing fields: %s", connect_info)
            if session_id:
                await hub.broadcast(
                    session_id,
                    {
                        "type": "zoom.rtms_error",
                        "session_id": session_id,
                        "message": (
                            "meeting.rtms_started received but missing meeting_uuid / "
                            "rtms_stream_id / server_urls. Check webhook payload."
                        ),
                        "connect_info": connect_info,
                    },
                )
            return connect_info

        if not settings.zoom_client_id or not settings.zoom_client_secret:
            connect_info["status"] = "missing_zoom_credentials"
            print(f"[zoom-rtms] missing Zoom credentials", flush=True)
            return connect_info

        key = str(rtms_stream_id)
        existing = self._tasks.get(key)
        if existing and not existing.done():
            connect_info["status"] = "already_running"
            print(f"[zoom-rtms] consumer already running for {key}", flush=True)
            return connect_info

        task = asyncio.create_task(
            self._run_stream(
                settings=settings,
                session_id=session_id,
                meeting_id=str(meeting_id) if meeting_id else None,
                meeting_uuid=str(meeting_uuid),
                rtms_stream_id=str(rtms_stream_id),
                signaling_url=signaling_url,
            )
        )
        self._tasks[key] = task
        connect_info["status"] = "consumer_started"
        print(f"[zoom-rtms] consumer_started session_id={session_id!r}", flush=True)
        return connect_info

    async def stop_stream(self, rtms_stream_id: str | None) -> None:
        if not rtms_stream_id:
            return
        task = self._tasks.pop(str(rtms_stream_id), None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _run_stream(
        self,
        *,
        settings: Settings,
        session_id: str | None,
        meeting_id: str | None,
        meeting_uuid: str,
        rtms_stream_id: str,
        signaling_url: str,
    ) -> None:
        signature = generate_rtms_signature(
            client_id=settings.zoom_client_id,
            client_secret=settings.zoom_client_secret,
            meeting_uuid=meeting_uuid,
            rtms_stream_id=rtms_stream_id,
        )
        # Late Open-session bind: pick up session_id even if webhook arrived first.
        if not session_id:
            session_id = rtms_session_registry.resolve_session_id(
                meeting_id, meeting_uuid, rtms_stream_id
            )
            if not session_id and meeting_id:
                session_id = self._resolve_session_from_db(meeting_id)
        print(
            f"[zoom-rtms] connecting signaling session={session_id!r} "
            f"url={signaling_url[:80]!r}",
            flush=True,
        )
        logger.info(
            "Connecting RTMS signaling for meeting_uuid=%s stream=%s session=%s",
            meeting_uuid,
            rtms_stream_id,
            session_id,
        )
        if session_id:
            await hub.broadcast(
                session_id,
                {
                    "type": "zoom.rtms_connecting",
                    "session_id": session_id,
                    "meeting_id": meeting_id,
                    "message": "Connecting to Zoom RTMS signaling/media sockets...",
                },
            )
            self._set_session_status(session_id, "live_rtms")

        try:
            async with ws_connect(signaling_url, max_size=8 * 1024 * 1024) as signaling_ws:
                await signaling_ws.send(
                    json.dumps(
                        {
                            "msg_type": SIGNALING_HAND_SHAKE_REQ,
                            "protocol_version": 1,
                            "sequence": 0,
                            "meeting_uuid": meeting_uuid,
                            "rtms_stream_id": rtms_stream_id,
                            "signature": signature,
                        }
                    )
                )

                media_task: asyncio.Task | None = None
                async for raw in signaling_ws:
                    msg = self._parse_message(raw)
                    if not msg:
                        continue
                    msg_type = msg.get("msg_type")

                    if msg_type == KEEP_ALIVE_REQ:
                        await signaling_ws.send(
                            json.dumps(
                                {
                                    "msg_type": KEEP_ALIVE_RESP,
                                    "timestamp": msg.get("timestamp"),
                                }
                            )
                        )
                        continue

                    if msg_type == SIGNALING_HAND_SHAKE_RESP and msg.get("status_code") == 0:
                        media_url = _pick_media_audio_url(msg.get("media_server") or {})
                        if not media_url:
                            raise RuntimeError(f"No media audio URL in handshake: {msg}")
                        if media_task is None or media_task.done():
                            media_task = asyncio.create_task(
                                self._consume_media(
                                    settings=settings,
                                    session_id=session_id,
                                    meeting_id=meeting_id,
                                    meeting_uuid=meeting_uuid,
                                    rtms_stream_id=rtms_stream_id,
                                    signature=signature,
                                    media_url=media_url,
                                    signaling_ws=signaling_ws,
                                )
                            )
                        continue

                    if msg_type == SIGNALING_HAND_SHAKE_RESP:
                        raise RuntimeError(f"Signaling handshake failed: {msg}")

                if media_task and not media_task.done():
                    media_task.cancel()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[zoom-rtms] stream failed: {exc!r}", flush=True)
            logger.exception("RTMS stream failed for %s", rtms_stream_id)
            if session_id:
                await hub.broadcast(
                    session_id,
                    {
                        "type": "zoom.rtms_error",
                        "session_id": session_id,
                        "message": str(exc),
                    },
                )
                self._set_session_status(session_id, "error")
        finally:
            self._tasks.pop(rtms_stream_id, None)

    async def _consume_media(
        self,
        *,
        settings: Settings,
        session_id: str | None,
        meeting_id: str | None,
        meeting_uuid: str,
        rtms_stream_id: str,
        signature: str,
        media_url: str,
        signaling_ws: Any,
    ) -> None:
        logger.info("Connecting RTMS media socket %s", media_url)
        pcm_buffer = bytearray()
        parts: list[str] = []
        chunk_index = 0
        unbound_drop_logs = 0
        chunk_bytes = int(DEFAULT_CHUNK_SECONDS * BYTES_PER_SECOND)
        client = PapaReoClient(settings)
        work_dir = settings.upload_path / (session_id or "rtms") / "live_rtms"
        work_dir.mkdir(parents=True, exist_ok=True)
        capture_path = work_dir / "captured_zoom.wav"

        capture_wav = wave.open(str(capture_path), "wb")
        capture_wav.setnchannels(1)
        capture_wav.setsampwidth(2)
        capture_wav.setframerate(SAMPLE_RATE)

        print(
            f"[zoom-rtms] recording received audio to {capture_path}",
            flush=True,
        )

        prefer_streaming = (settings.papareo_mode or "streaming").lower().strip() == "streaming"
        live_streamer: PapaReoLiveStreamer | None = None
        use_streaming = False

        async def _on_stream_update(message: dict[str, Any]) -> None:
            nonlocal session_id
            active = session_id or rtms_session_registry.resolve_session_id(
                meeting_id, meeting_uuid, rtms_stream_id
            )
            if not active:
                return
            session_id = active
            text = str(message.get("text") or "")
            segment = str(message.get("segment") or "")
            await hub.broadcast(
                session_id,
                {
                    "type": message.get("type") or "transcript.partial",
                    "session_id": session_id,
                    "segment": segment,
                    "text": text,
                    "segment_id": message.get("segment_id"),
                    "confirmed": message.get("confirmed", ""),
                    "unconfirmed": message.get("unconfirmed", ""),
                    "is_final": bool(message.get("is_final")),
                    "provider": message.get("provider") or "papa_reo_streaming_live_rtms",
                    "source": "live_rtms",
                    "raw": message.get("raw"),
                },
            )
            if text:
                self._upsert_transcript(
                    session_id,
                    text,
                    provider="papa_reo_streaming_live_rtms",
                )

        if prefer_streaming:
            try:
                live_streamer = PapaReoLiveStreamer(settings, on_update=_on_stream_update)
                await live_streamer.start()
                use_streaming = True
            except Exception as exc:
                print(f"[zoom-rtms] streaming unavailable, using Standard slices: {exc}", flush=True)
                live_streamer = None
                use_streaming = False

        provider_note = (
            "papa_reo_streaming_live_rtms" if use_streaming else "papa_reo_standard_live_rtms"
        )
        if session_id:
            await hub.broadcast(
                session_id,
                {
                    "type": "zoom.rtms_media_connected",
                    "session_id": session_id,
                    "message": (
                        "RTMS media connected. Streaming PCM to Papa Reo..."
                        if use_streaming
                        else "RTMS media connected. Waiting for audio (Standard slices)..."
                    ),
                    "provider": provider_note,
                },
            )

        try:
            async with ws_connect(media_url, max_size=16 * 1024 * 1024) as media_ws:
                await media_ws.send(
                    json.dumps(
                        {
                            "msg_type": DATA_HAND_SHAKE_REQ,
                            "protocol_version": 1,
                            "sequence": 0,
                            "meeting_uuid": meeting_uuid,
                            "rtms_stream_id": rtms_stream_id,
                            "signature": signature,
                            "media_type": MEDIA_TYPE_AUDIO,
                            "payload_encryption": False,
                            "media_params": {
                                "audio": {
                                    # Zoom: RTP=1, RAW=2. L16 (codec=1) only works with RAW.
                                    "content_type": 2,
                                    "sample_rate": 1,  # 16 kHz
                                    "channel": 1,  # mono
                                    "codec": 1,  # L16 / PCM16
                                    "data_opt": 1,  # mixed stream
                                    "send_rate": 100,
                                }
                            },
                        }
                    )
                )

                async for raw in media_ws:
                    msg = self._parse_message(raw)
                    if not msg:
                        continue
                    msg_type = msg.get("msg_type")

                    if msg_type == KEEP_ALIVE_REQ:
                        await media_ws.send(
                            json.dumps(
                                {
                                    "msg_type": KEEP_ALIVE_RESP,
                                    "timestamp": msg.get("timestamp"),
                                }
                            )
                        )
                        continue

                    if msg_type == DATA_HAND_SHAKE_RESP:
                        if msg.get("status_code") != 0:
                            raise RuntimeError(f"Media handshake failed: {msg}")
                        await signaling_ws.send(
                            json.dumps(
                                {
                                    "msg_type": CLIENT_READY_ACK,
                                    "rtms_stream_id": rtms_stream_id,
                                }
                            )
                        )
                        if session_id:
                            await hub.broadcast(
                                session_id,
                                {
                                    "type": "zoom.rtms_ready",
                                    "session_id": session_id,
                                    "message": "RTMS ready — speak in the Zoom meeting",
                                },
                            )
                        continue

                    if msg_type == MEDIA_DATA_TRANSCRIPT and session_id:
                        content = msg.get("content")
                        text = ""
                        if isinstance(content, dict):
                            text = str(
                                content.get("text") or content.get("transcript") or ""
                            )
                        elif isinstance(content, str):
                            text = content
                        text = text.strip()
                        if text:
                            parts.append(text)
                            display = assemble_transcript_parts(parts)
                            await hub.broadcast(
                                session_id,
                                {
                                    "type": "transcript.partial",
                                    "session_id": session_id,
                                    "segment": text,
                                    "text": display,
                                    "is_final": False,
                                    "provider": "zoom_rtms_transcript",
                                    "source": "live_rtms",
                                },
                            )
                        continue

                    if msg_type != MEDIA_DATA_AUDIO:
                        continue

                    content = (
                        msg.get("content") if isinstance(msg.get("content"), dict) else {}
                    )
                    b64 = content.get("data")
                    if not isinstance(b64, str) or not b64:
                        continue
                    try:
                       frame = base64.b64decode(b64)
                    except Exception:
                        logger.debug("Bad RTMS audio base64", exc_info=True)
                        continue
                    capture_wav.writeframes(frame)

                    print(
                        f"[zoom-rtms] AUDIO RECEIVED bytes={len(frame)} "
                        f"user={content.get('user_name')} "
                        f"timestamp={content.get('timestamp')}",
                        flush=True,
                    )

                    active_session = session_id or rtms_session_registry.resolve_session_id(
                        meeting_id, meeting_uuid, rtms_stream_id
                    )
                    if not active_session:
                        if unbound_drop_logs < 3:
                            unbound_drop_logs += 1
                            print(
                                "[zoom-rtms] audio frame dropped: no session bound yet "
                                f"(stream={rtms_stream_id})",
                                flush=True,
                            )
                        continue
                    session_id = active_session

                    if use_streaming and live_streamer is not None:
                        # Papa Reo Streaming does its own VAD — forward PCM continuously.
                        try:
                            await live_streamer.send_pcm(frame)
                        except Exception:
                            logger.exception("Papa Reo live send failed; falling back to Standard")
                            use_streaming = False
                            await live_streamer.close()
                            live_streamer = None
                        continue

                    pcm_buffer.extend(frame)
                    while len(pcm_buffer) >= chunk_bytes:
                        slice_pcm = bytes(pcm_buffer[:chunk_bytes])
                        del pcm_buffer[:chunk_bytes]
                        level = _pcm16_rms(slice_pcm)
                        if level < SILENCE_RMS_THRESHOLD:
                            print(
                                f"[zoom-rtms] skipping quiet chunk={chunk_index} "
                                f"bytes={len(slice_pcm)} level={level:.1f}",
                                flush=True,
                            )
                            chunk_index += 1
                            continue

                        current_chunk = chunk_index
                        print(
                            f"[zoom-rtms] sending Papa Reo chunk={current_chunk} "
                            f"bytes={len(slice_pcm)} level={level:.1f}",
                            flush=True,
                        )
                        text = await self._transcribe_pcm_slice(
                            client=client,
                            pcm=slice_pcm,
                            work_dir=work_dir,
                            chunk_index=current_chunk,
                        )
                        print(
                            f"[zoom-rtms] Papa Reo chunk={current_chunk} text={text!r}",
                            flush=True,
                        )
                        chunk_index += 1
                        if text:
                            parts.append(text)
                            display = assemble_transcript_parts(parts)
                            await hub.broadcast(
                                session_id,
                                {
                                    "type": "transcript.partial",
                                    "session_id": session_id,
                                    "chunk_index": chunk_index,
                                    "segment": text,
                                    "text": display,
                                    "is_final": False,
                                    "provider": "papa_reo_standard_live_rtms",
                                    "source": "live_rtms",
                                },
                            )
                            self._upsert_transcript(session_id, display)
        finally:
            if live_streamer is not None:
                await live_streamer.close()
            capture_wav.close()    
            print(f"[zoom-rtms] saved Zoom capture: {capture_path}",
              flush=True,
    )

    async def _transcribe_pcm_slice(
        self,
        *,
        client: PapaReoClient,
        pcm: bytes,
        work_dir: Path,
        chunk_index: int,
    ) -> str:
        wav_path = work_dir / f"slice_{chunk_index:05d}.wav"
        await asyncio.to_thread(_pcm16_to_wav_path, pcm, wav_path)
        try:
            result = await asyncio.to_thread(client.transcribe_file, wav_path, False)
        except Exception:
            logger.exception("Papa Reo failed on RTMS audio slice %s", chunk_index)
            return ""
        return str(result.get("transcription") or "").strip()

    @staticmethod
    def _parse_message(raw: Any) -> dict[str, Any] | None:
        try:
            if isinstance(raw, bytes):
                return json.loads(raw.decode("utf-8"))
            if isinstance(raw, str):
                return json.loads(raw)
        except Exception:
            return None
        return None

    @staticmethod
    def _resolve_session_from_db(meeting_id: str) -> str | None:
        from sqlalchemy import select

        db = SessionLocal()
        try:
            record = db.scalars(
                select(SessionRecord)
                .where(SessionRecord.meeting_id == meeting_id)
                .order_by(SessionRecord.updated_at.desc())
            ).first()
            return record.id if record else None
        finally:
            db.close()

    @staticmethod
    def _set_session_status(session_id: str, status: str) -> None:
        db = SessionLocal()
        try:
            record = db.get(SessionRecord, session_id)
            if record:
                record.status = status
                record.source = "zoom"
                db.commit()
        finally:
            db.close()

    @staticmethod
    def _upsert_transcript(
        session_id: str,
        text: str,
        *,
        provider: str = "papa_reo_standard_live_rtms",
    ) -> None:
        """Store one live transcript snapshot per session/provider.

        Streaming sends many revisions of the same segment. Creating a new DB row
        for every revision makes the UI/export appear duplicated. Update the latest
        live snapshot instead.
        """
        from sqlalchemy import select

        db = SessionLocal()
        try:
            record = db.scalars(
                select(TranscriptRecord)
                .where(
                    TranscriptRecord.session_id == session_id,
                    TranscriptRecord.provider == provider,
                )
                .order_by(TranscriptRecord.id.desc())
            ).first()

            if record is None:
                record = TranscriptRecord(
                    session_id=session_id,
                    provider=provider,
                    text=text,
                    is_final=False,
                )
                db.add(record)
            else:
                record.text = text
                record.is_final = False

            db.commit()
        finally:
            db.close()

def _finalize_transcript(
    session_id: str,
    *,
    provider: str = "papa_reo_standard_live_rtms",
) -> None:
    from sqlalchemy import select

    db = SessionLocal()

    try:
        record = db.scalars(
            select(TranscriptRecord)
            .where(
                TranscriptRecord.session_id == session_id,
                TranscriptRecord.provider == provider,
            )
            .order_by(TranscriptRecord.id.desc())
        ).first()

        if record is not None:
            record.is_final = True
            db.commit()

    finally:
        db.close()

live_rtms_consumer = LiveRtmsConsumer()
