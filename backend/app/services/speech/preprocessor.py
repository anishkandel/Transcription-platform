from __future__ import annotations

from pathlib import Path

from app.config import Settings


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def split_audio_file(
    source: Path,
    output_dir: Path,
    chunk_seconds: int,
) -> list[Path]:
    """Split long audio into WAV chunks using pydub/ffmpeg when available.

    Always export as WAV. Exporting as `m4a` fails with some ffmpeg builds
    because `m4a` is not a valid ffmpeg muxer name.
    """
    try:
        from pydub import AudioSegment
    except Exception:
        return [source]

    output_dir.mkdir(parents=True, exist_ok=True)
    audio = AudioSegment.from_file(source)
    duration_ms = len(audio)
    max_ms = max(int(chunk_seconds) * 1000, 1000)

    chunks: list[Path] = []
    index = 0
    for start in range(0, duration_ms, max_ms):
        end = min(start + max_ms, duration_ms)
        piece = audio[start:end]
        out = output_dir / f"{source.stem}_chunk_{index:03d}.wav"
        # Use wav explicitly to avoid ffmpeg muxer issues with m4a/mp4 aliases.
        piece.export(out, format="wav")
        chunks.append(out)
        index += 1

    return chunks or [source]


def describe_audio(settings: Settings, source: Path) -> dict:
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(source)
        return {
            "path": str(source),
            "duration_seconds": round(len(audio) / 1000.0, 2),
            "channels": audio.channels,
            "frame_rate": audio.frame_rate,
            "needs_chunking": (len(audio) / 1000.0) > settings.max_standard_audio_seconds,
        }
    except Exception as exc:  # pragma: no cover - best effort metadata
        return {
            "path": str(source),
            "duration_seconds": None,
            "error": str(exc),
            "needs_chunking": False,
        }
