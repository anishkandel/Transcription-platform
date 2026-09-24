"""Papa Reo Streaming API client.

Protocol (per Te Hiku / Keoni):
1. POST /tuhi/create_session → websocket_url
2. Open WebSocket; send raw PCM bytes continuously
3. Receive JSON: {"confirmed": "...", "unconfirmed": "", "segment_id": "0"}
4. End by closing the socket (no explicit end control message required)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import array
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from websockets.asyncio.client import connect as ws_connect

from app.config import Settings
from app.services.speech.papa_reo import PapaReoError

logger = logging.getLogger(__name__)

PartialCallback = Callable[[dict[str, Any]], Awaitable[None] | None]

# Match the working standalone Papa Reo Streaming test:
# 16 kHz mono PCM16 input from Zoom, delivered to Papa Reo as 100 ms float32 chunks.
LIVE_STREAM_CHUNK_MS = 100
PCM16_BYTES_PER_SAMPLE = 2


def to_websocket_url(url: str) -> str:
    if url.startswith("https://"):
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
    return url


def _normalize_encoding(value: str | None) -> str:
    """Normalize Papa Reo streaming encoding to the API's expected PCM value."""
    encoding = (value or "pcm").strip().lower()
    if encoding in {"pcm", "pcm16", "l16", "linear16", "raw"}:
        return "pcm"
    return encoding or "pcm"


def pcm16_to_float32_bytes(pcm: bytes) -> bytes:
    """Convert little-endian signed PCM16 bytes to normalized float32 PCM bytes."""
    if not pcm:
        return b""

    if len(pcm) % 2:
        pcm = pcm[:-1]

    samples = array.array("h")
    samples.frombytes(pcm)

    if sys.byteorder != "little":
        samples.byteswap()

    float_samples = array.array(
        "f",
        (sample / 32768.0 for sample in samples),
    )

    if sys.byteorder != "little":
        float_samples.byteswap()

    return float_samples.tobytes()


def extract_transcript_fields(payload: Any) -> dict[str, Any]:
    """Parse Papa Reo streaming messages (confirmed/unconfirmed + legacy shapes)."""
    if isinstance(payload, str):
        text = payload.strip()
        return {
            "text": text,
            "confirmed": text,
            "unconfirmed": "",
            "segment_id": None,
            "is_final": False,
            "raw": payload,
        }

    if not isinstance(payload, dict):
        return {
            "text": "",
            "confirmed": "",
            "unconfirmed": "",
            "segment_id": None,
            "is_final": False,
            "raw": payload,
        }

    segment_id = payload.get("segment_id")
    if segment_id is not None:
        segment_id = str(segment_id)

    confirmed = payload.get("confirmed")
    unconfirmed = payload.get("unconfirmed")
    if isinstance(confirmed, str) or isinstance(unconfirmed, str):
        confirmed_text = confirmed.strip() if isinstance(confirmed, str) else ""
        unconfirmed_text = unconfirmed.strip() if isinstance(unconfirmed, str) else ""
        # Prefer confirmed for the segment line; fall back to unconfirmed while empty.
        text = confirmed_text or unconfirmed_text
        return {
            "text": text,
            "confirmed": confirmed_text,
            "unconfirmed": unconfirmed_text,
            "segment_id": segment_id,
            "is_final": False,
            "raw": payload,
        }

    candidates = [
        payload.get("transcription"),
        payload.get("transcript"),
        payload.get("text"),
        payload.get("partial"),
        payload.get("result"),
    ]
    text = ""
    for item in candidates:
        if isinstance(item, str) and item.strip():
            text = item.strip()
            break
        if isinstance(item, dict):
            nested = (
                item.get("transcription")
                or item.get("transcript")
                or item.get("text")
                or item.get("confirmed")
                or ""
            )
            if isinstance(nested, str) and nested.strip():
                text = nested.strip()
                break

    is_final = bool(
        payload.get("is_final")
        or payload.get("final")
        or payload.get("isFinal")
        or str(payload.get("type") or "").lower()
        in {"final", "transcript.final", "end"}
    )
    return {
        "text": text,
        "confirmed": text,
        "unconfirmed": "",
        "segment_id": segment_id,
        "is_final": is_final,
        "raw": payload,
    }


def audio_file_to_pcm16_mono(audio_path: Path, sample_rate: int = 16000) -> bytes:
    from pydub import AudioSegment

    audio = AudioSegment.from_file(audio_path)
    audio = audio.set_frame_rate(sample_rate).set_channels(1).set_sample_width(2)
    return bytes(audio.raw_data)


class StreamingTranscriptState:
    """Assemble Papa Reo segment updates into a display transcript."""

    def __init__(self) -> None:
        self._segment_order: list[str] = []
        self._confirmed_by_segment: dict[str, str] = {}
        self._active_segment_id: str | None = None
        self._active_unconfirmed: str = ""
        self._legacy_partial: str = ""

    def apply_fields(self, fields: dict[str, Any]) -> tuple[str, str, bool]:
        """Apply one API message.

        Returns (display_text, segment_text_for_ui, segment_just_finalized).
        """
        segment_id = fields.get("segment_id")
        confirmed = str(fields.get("confirmed") or "").strip()
        unconfirmed = str(fields.get("unconfirmed") or "").strip()
        legacy_text = str(fields.get("text") or "").strip()
        is_final = bool(fields.get("is_final"))

        finalized = False
        segment_text = ""

        if segment_id is not None:
            if (
                self._active_segment_id is not None
                and segment_id != self._active_segment_id
                and self._confirmed_by_segment.get(self._active_segment_id)
            ):
                finalized = True

            if segment_id not in self._confirmed_by_segment:
                self._segment_order.append(segment_id)
                self._confirmed_by_segment[segment_id] = ""

            if confirmed:
                self._confirmed_by_segment[segment_id] = confirmed
            elif legacy_text and not self._confirmed_by_segment[segment_id]:
                self._confirmed_by_segment[segment_id] = legacy_text

            self._active_segment_id = segment_id
            self._active_unconfirmed = unconfirmed
            self._legacy_partial = ""
            segment_text = self._confirmed_by_segment[segment_id] or unconfirmed
        elif is_final and legacy_text:
            # Legacy final without segment_id: append as its own line.
            sid = f"legacy-{len(self._segment_order)}"
            self._segment_order.append(sid)
            self._confirmed_by_segment[sid] = legacy_text
            self._legacy_partial = ""
            self._active_unconfirmed = ""
            segment_text = legacy_text
            finalized = True
        elif legacy_text:
            self._legacy_partial = legacy_text
            segment_text = legacy_text

        return self.display_text(), segment_text, finalized

    def display_text(self) -> str:
        lines = [
            self._confirmed_by_segment[sid]
            for sid in self._segment_order
            if self._confirmed_by_segment.get(sid)
        ]
        if self._active_unconfirmed:
            # Show hypothesis only when confirmed for active segment is still empty,
            # or append lightly — prefer replacing via confirmed updates.
            active = self._active_segment_id
            if active and not self._confirmed_by_segment.get(active):
                lines.append(self._active_unconfirmed)
        if self._legacy_partial:
            lines.append(self._legacy_partial)
        return "\n".join(lines)


class PapaReoStreamingClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.papareo_api_key.strip())

    def create_session(
        self,
        *,
        media_encoding: str | None = None,
        sample_rate: int | None = None,
        number_of_channels: int | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            raise PapaReoError("PAPAREO_API_KEY is not configured")

        url = (
            self.settings.papareo_base_url.rstrip("/")
            + self.settings.papareo_create_session_path
        )
        headers = {
            "Accept": "application/json",
            "Authorization": f"Token {self.settings.papareo_api_key}",
            "Content-Type": "application/json",
        }
        encoding = _normalize_encoding(
            media_encoding or self.settings.papareo_stream_encoding
        )
        rate = (
            self.settings.papareo_stream_sample_rate
            if sample_rate is None
            else sample_rate
        )
        channels = (
            self.settings.papareo_stream_channels
            if number_of_channels is None
            else number_of_channels
        )
        # Match Te Hiku sample client; keep flat fields for older variants.
        body = {
            "config": {
                "encoding": encoding,
                "sample_rate": rate,
                "channels": channels,
            },
            "media_encoding": encoding,
            "sample_rate": rate,
            "number_of_channels": channels,
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=body)

        try:
            payload = response.json()
        except Exception as exc:
            raise PapaReoError(
                f"Invalid JSON from create_session (HTTP {response.status_code}): {response.text}"
            ) from exc

        if response.status_code >= 400:
            raise PapaReoError(f"create_session failed ({response.status_code}): {payload}")

        if not isinstance(payload, dict) or not payload.get("websocket_url"):
            raise PapaReoError(f"create_session missing websocket_url: {payload}")
        return payload

    async def stream_pcm_and_collect(
        self,
        *,
        websocket_url: str,
        pcm_bytes: bytes,
        on_update: PartialCallback | None = None,
        chunk_bytes: int | None = None,
        pace_realtime: bool = True,
    ) -> dict[str, Any]:
        ws_url = to_websocket_url(websocket_url)
        state = StreamingTranscriptState()
        raw_events: list[Any] = []
        sample_rate = self.settings.papareo_stream_sample_rate
        channels = self.settings.papareo_stream_channels
        bytes_per_second = max(
            sample_rate * channels * PCM16_BYTES_PER_SAMPLE,
            1,
        )
        chunk_size = chunk_bytes or int(
            bytes_per_second * (LIVE_STREAM_CHUNK_MS / 1000)
        )
        headers = {"Authorization": f"Token {self.settings.papareo_api_key}"}

        async with ws_connect(
            ws_url,
            additional_headers=headers,
            max_size=8 * 1024 * 1024,
        ) as ws:
            receiver_done = asyncio.Event()

            async def receiver() -> None:
                try:
                    async for message in ws:
                        if isinstance(message, bytes):
                            try:
                                payload = json.loads(message.decode("utf-8"))
                            except Exception:
                                continue
                        else:
                            try:
                                payload = json.loads(message)
                            except Exception:
                                payload = {"text": str(message)}

                        raw_events.append(payload)
                        fields = extract_transcript_fields(payload)
                        display, segment, finalized = state.apply_fields(fields)
                        if on_update and (segment or finalized or display):
                            maybe = on_update(
                                {
                                    "type": (
                                        "transcript.final_segment"
                                        if finalized or fields["is_final"]
                                        else "transcript.partial"
                                    ),
                                    "text": display,
                                    "segment": segment,
                                    "segment_id": fields.get("segment_id"),
                                    "is_final": bool(finalized or fields["is_final"]),
                                    "provider": "papa_reo_streaming",
                                    "raw": fields["raw"],
                                }
                            )
                            if asyncio.iscoroutine(maybe):
                                await maybe
                finally:
                    receiver_done.set()

            recv_task = asyncio.create_task(receiver())
            try:
                for index in range(0, len(pcm_bytes), chunk_size):
                    # pcm_bytes is PCM16 input; Papa Reo Streaming expects float32 PCM.
                    chunk = pcm_bytes[index : index + chunk_size]
                    float32_chunk = pcm16_to_float32_bytes(chunk)
                    await ws.send(float32_chunk)
                    if pace_realtime:
                        # Pace using the original PCM16 duration.
                        await asyncio.sleep(len(chunk) / bytes_per_second)

                # Keoni: end by closing the socket — no end control frame required.
                # Give the server a short window to flush last segment updates, then close.
                try:
                    await asyncio.wait_for(receiver_done.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass
                with contextlib.suppress(Exception):
                    await ws.close()
                try:
                    await asyncio.wait_for(receiver_done.wait(), timeout=15.0)
                except asyncio.TimeoutError:
                    logger.info("Streaming receiver wait timed out; returning collected text")
            finally:
                recv_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await recv_task

        final_text = state.display_text()
        event_count = len(raw_events)
        if final_text:
            detail = None
        elif event_count == 0:
            detail = (
                "Streaming finished with no messages from Papa Reo. "
                "Check API key / streaming permission and websocket connectivity."
            )
        else:
            detail = (
                f"Streaming finished with {event_count} message(s) but no transcript text "
                "could be parsed. Papa Reo response shape may differ from expected fields."
            )
        return {
            "success": bool(final_text),
            "transcription": final_text,
            "provider": "papa_reo_streaming",
            "raw": {"events": raw_events[-50:]},
            "detail": detail,
        }


class PapaReoLiveStreamer:
    """Long-lived Streaming session for live Zoom RTMS PCM."""

    def __init__(self, settings: Settings, on_update: PartialCallback | None = None):
        self.settings = settings
        self.on_update = on_update
        self._client = PapaReoStreamingClient(settings)
        self._ws: Any = None
        self._recv_task: asyncio.Task | None = None
        self._send_task: asyncio.Task | None = None
        self._send_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._pcm_buffer = bytearray()
        self._state = StreamingTranscriptState()
        self._closed = False

    @property
    def display_text(self) -> str:
        return self._state.display_text()

    async def start(self) -> dict[str, Any]:
        session = await asyncio.to_thread(self._client.create_session)
        ws_url = to_websocket_url(str(session["websocket_url"]))
        headers = {"Authorization": f"Token {self.settings.papareo_api_key}"}
        self._ws = await ws_connect(
            ws_url,
            additional_headers=headers,
            max_size=8 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=60,
            close_timeout=10,
        )
        self._closed = False
        self._pcm_buffer.clear()
        self._send_queue = asyncio.Queue()
        self._send_task = asyncio.create_task(self._sender())
        self._recv_task = asyncio.create_task(self._receiver())
        print(
            f"[papa-reo-stream] live session started session_id={session.get('session_id')!r}",
            flush=True,
        )
        return session

    async def send_pcm(self, pcm: bytes) -> None:
        """Accept arbitrary Zoom PCM16 frames and queue fixed 100 ms chunks.

        Zoom normally sends according to the RTMS send_rate, but a received frame can
        still be larger than one Papa Reo streaming chunk. Buffering here makes the
        live path match the standalone test that worked reliably.
        """
        if self._closed or not self._ws or not pcm:
            return

        if self._send_task is not None and self._send_task.done():
            # Surface sender failures to the RTMS caller so it can fall back cleanly.
            self._send_task.result()

        sample_rate = self.settings.papareo_stream_sample_rate
        channels = self.settings.papareo_stream_channels
        pcm16_chunk_bytes = int(
            sample_rate
            * channels
            * PCM16_BYTES_PER_SAMPLE
            * (LIVE_STREAM_CHUNK_MS / 1000)
        )

        self._pcm_buffer.extend(pcm)

        while len(self._pcm_buffer) >= pcm16_chunk_bytes:
            chunk = bytes(self._pcm_buffer[:pcm16_chunk_bytes])
            del self._pcm_buffer[:pcm16_chunk_bytes]
            await self._send_queue.put(chunk)

    async def _sender(self) -> None:
        """Send 100 ms PCM16 chunks to Papa Reo as paced float32 PCM."""
        assert self._ws is not None

        interval = LIVE_STREAM_CHUNK_MS / 1000
        loop = asyncio.get_running_loop()
        next_send_at = loop.time()

        try:
            while True:
                pcm16_chunk = await self._send_queue.get()

                try:
                    if pcm16_chunk is None:
                        return

                    float32_chunk = pcm16_to_float32_bytes(pcm16_chunk)

                    if float32_chunk:
                        await self._ws.send(float32_chunk)

                    next_send_at += interval
                    delay = next_send_at - loop.time()

                    if delay > 0:
                        await asyncio.sleep(delay)
                    else:
                        # If the event loop was delayed, do not accumulate timing drift.
                        next_send_at = loop.time()

                finally:
                    self._send_queue.task_done()

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Papa Reo live sender ended with error")
            raise
        
        

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        # Flush the last partial PCM16 block before ending the stream.
        if self._pcm_buffer and self._send_task is not None and not self._send_task.done():
            await self._send_queue.put(bytes(self._pcm_buffer))
            self._pcm_buffer.clear()

        if self._send_task is not None:
            if not self._send_task.done():
                await self._send_queue.put(None)
                try:
                    await asyncio.wait_for(self._send_task, timeout=5.0)
                except asyncio.TimeoutError:
                    self._send_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await self._send_task
            else:
                with contextlib.suppress(Exception):
                    self._send_task.result()
            self._send_task = None

        # Give Papa Reo a short chance to emit the last confirmed update.
        if self._ws is not None:
            await asyncio.sleep(0.5)
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None

        if self._recv_task is not None:
            self._recv_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._recv_task
            self._recv_task = None

    async def _receiver(self) -> None:
        assert self._ws is not None
        try:
            async for message in self._ws:
                if isinstance(message, bytes):
                    try:
                        payload = json.loads(message.decode("utf-8"))
                    except Exception:
                        continue
                else:
                    try:
                        payload = json.loads(message)
                    except Exception:
                        payload = {"text": str(message)}

                fields = extract_transcript_fields(payload)
                display, segment, finalized = self._state.apply_fields(fields)
                if self.on_update and (segment or finalized or display):
                    maybe = self.on_update(
                        {
                            "type": (
                                "transcript.final_segment"
                                if finalized or fields["is_final"]
                                else "transcript.partial"
                            ),
                            "text": display,
                            "segment": segment,
                            "segment_id": fields.get("segment_id"),
                            "confirmed": fields.get("confirmed", ""),
                            "unconfirmed": fields.get("unconfirmed", ""),
                            "is_final": bool(finalized or fields["is_final"]),
                            "provider": "papa_reo_streaming_live_rtms",
                            "raw": fields["raw"],
                        }
                    )
                    if asyncio.iscoroutine(maybe):
                        await maybe
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Papa Reo live stream receiver ended with error")
