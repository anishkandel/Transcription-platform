from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.config import Settings
from app.services.speech.assembler import assemble_transcript_parts
from app.services.speech.papa_reo import PapaReoClient, PapaReoError
from app.services.speech.preprocessor import describe_audio, split_audio_file
from app.services.speech.streaming import (
    PapaReoStreamingClient,
    audio_file_to_pcm16_mono,
)
from app.services.speech.vad import maybe_apply_vad

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


async def _emit(on_partial: ProgressCallback | None, message: dict[str, Any]) -> None:
    if not on_partial:
        return
    maybe = on_partial(message)
    if asyncio.iscoroutine(maybe):
        await maybe


class SpeechPipeline:
    """Intern 1 speech module used by the Intern 3 backend integration layer."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = PapaReoClient(settings)
        self.streaming_client = PapaReoStreamingClient(settings)

    async def process_audio_file_progressive(
        self,
        audio_path: Path,
        work_dir: Path,
        with_metadata: bool = False,
        on_partial: ProgressCallback | None = None,
        chunk_seconds: int | None = None,
        pace_delay_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Simulate realtime output using Standard API on small audio chunks.

        This is the fallback when Papa Reo Streaming permission is unavailable:
        split audio -> transcribe each chunk -> push line-by-line updates over WebSocket.
        """
        work_dir.mkdir(parents=True, exist_ok=True)
        local_copy = work_dir / audio_path.name
        if audio_path.resolve() != local_copy.resolve():
            shutil.copy2(audio_path, local_copy)

        info = describe_audio(self.settings, local_copy)
        prepared = maybe_apply_vad(local_copy, self.settings.vad_enabled)
        seconds = chunk_seconds or self.settings.progressive_chunk_seconds
        chunks = split_audio_file(prepared, work_dir / "chunks", seconds)

        parts: list[str] = []
        raw_results: list[dict[str, Any]] = []
        total_duration = 0.0
        delay = (
            self.settings.progressive_delay_seconds
            if pace_delay_seconds is None
            else pace_delay_seconds
        )

        await _emit(
            on_partial,
            {
                "type": "transcript.started",
                "text": "",
                "chunks_total": len(chunks),
                "provider": "papa_reo_standard_chunked",
                "is_final": False,
            },
        )

        for index, chunk in enumerate(chunks):
            result = await asyncio.to_thread(
                self.client.transcribe_file,
                chunk,
                with_metadata,
            )
            text = str(result.get("transcription") or "").strip()
            if text:
                parts.append(text)
            raw_results.append(result)
            duration = result.get("duration")
            if isinstance(duration, (int, float)):
                total_duration += float(duration)

            display = assemble_transcript_parts(parts)
            await _emit(
                on_partial,
                {
                    "type": "transcript.partial",
                    "chunk_index": index,
                    "chunks_total": len(chunks),
                    "segment": text,
                    "text": display,
                    "is_final": False,
                    "provider": "papa_reo_standard_chunked",
                },
            )
            if delay > 0:
                await asyncio.sleep(delay)

        final_text = assemble_transcript_parts(parts)
        return {
            "success": bool(final_text),
            "transcription": final_text,
            "provider": "papa_reo_standard_chunked",
            "duration_seconds": total_duration or info.get("duration_seconds"),
            "chunks_processed": len(chunks),
            "audio_info": info,
            "raw": {"chunks": raw_results},
            "detail": None if final_text else "No transcript text returned.",
        }

    def process_audio_file(
        self,
        audio_path: Path,
        work_dir: Path,
        with_metadata: bool = False,
        on_partial: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Synchronous Standard API helper (non-progressive)."""
        work_dir.mkdir(parents=True, exist_ok=True)
        local_copy = work_dir / audio_path.name
        if audio_path.resolve() != local_copy.resolve():
            shutil.copy2(audio_path, local_copy)

        info = describe_audio(self.settings, local_copy)
        prepared = maybe_apply_vad(local_copy, self.settings.vad_enabled)
        chunks = split_audio_file(
            prepared,
            work_dir / "chunks",
            self.settings.default_chunk_seconds,
        )

        parts: list[str] = []
        raw_results: list[dict[str, Any]] = []
        total_duration = 0.0

        for index, chunk in enumerate(chunks):
            result = self.client.transcribe_file(chunk, with_metadata=with_metadata)
            text = str(result.get("transcription") or "").strip()
            parts.append(text)
            raw_results.append(result)
            duration = result.get("duration")
            if isinstance(duration, (int, float)):
                total_duration += float(duration)
            if on_partial:
                on_partial(
                    {
                        "type": "transcript.partial",
                        "chunk_index": index,
                        "chunks_total": len(chunks),
                        "text": assemble_transcript_parts(parts),
                        "is_final": False,
                        "provider": "papa_reo_standard",
                    }
                )

        final_text = assemble_transcript_parts(parts)
        return {
            "success": bool(success := bool(final_text)),
            "transcription": final_text,
            "provider": "papa_reo_standard",
            "duration_seconds": total_duration or info.get("duration_seconds"),
            "chunks_processed": len(chunks),
            "audio_info": info,
            "raw": {"chunks": raw_results},
            "detail": None if success else "No transcript text returned.",
        }

    async def process_audio_file_streaming(
        self,
        audio_path: Path,
        work_dir: Path,
        on_partial: ProgressCallback | None = None,
        pace_realtime: bool | None = None,
    ) -> dict[str, Any]:
        work_dir.mkdir(parents=True, exist_ok=True)
        local_copy = work_dir / audio_path.name
        if audio_path.resolve() != local_copy.resolve():
            shutil.copy2(audio_path, local_copy)

        prepared = maybe_apply_vad(local_copy, self.settings.vad_enabled)
        info = describe_audio(self.settings, prepared)
        session = self.streaming_client.create_session()
        pcm = audio_file_to_pcm16_mono(
            prepared,
            sample_rate=self.settings.papareo_stream_sample_rate,
        )

        async def _forward(message: dict[str, Any]) -> None:
            await _emit(on_partial, message)

        result = await self.streaming_client.stream_pcm_and_collect(
            websocket_url=str(session["websocket_url"]),
            pcm_bytes=pcm,
            on_update=_forward,
            pace_realtime=(
                self.settings.papareo_stream_pace_realtime
                if pace_realtime is None
                else pace_realtime
            ),
        )
        result["audio_info"] = info
        result["streaming_session_id"] = session.get("session_id")
        result["duration_seconds"] = info.get("duration_seconds")
        return result

    async def process_audio_auto(
        self,
        audio_path: Path,
        work_dir: Path,
        with_metadata: bool = False,
        on_partial: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        mode = (self.settings.papareo_mode or "standard").lower().strip()
        if mode == "streaming":
            try:
                return await self.process_audio_file_streaming(
                    audio_path,
                    work_dir,
                    on_partial=on_partial,
                )
            except PapaReoError as exc:
                # Automatic fallback when streaming permission is missing.
                if "streaming" in str(exc).lower() and "permission" in str(exc).lower():
                    await _emit(
                        on_partial,
                        {
                            "type": "transcript.fallback",
                            "text": "",
                            "message": (
                                "Streaming permission unavailable; "
                                "falling back to chunked Standard API."
                            ),
                            "is_final": False,
                            "provider": "papa_reo_standard_chunked",
                        },
                    )
                    return await self.process_audio_file_progressive(
                        audio_path,
                        work_dir,
                        with_metadata=with_metadata,
                        on_partial=on_partial,
                    )
                raise

        # Default / standard: progressive chunked Standard API for realtime-like UI.
        return await self.process_audio_file_progressive(
            audio_path,
            work_dir,
            with_metadata=with_metadata,
            on_partial=on_partial,
        )


def create_speech_pipeline(settings: Settings) -> SpeechPipeline:
    return SpeechPipeline(settings)


__all__ = ["SpeechPipeline", "create_speech_pipeline", "PapaReoError"]
