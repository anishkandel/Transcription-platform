"""Optional Voice Activity Detection helpers.

VAD is disabled by default. Enable only if silence/noise hurts quality or cost.
"""

from __future__ import annotations

from pathlib import Path


def maybe_apply_vad(audio_path: Path, enabled: bool) -> Path:
    if not enabled:
        return audio_path

    # Placeholder for WebRTC/Silero VAD integration.
    # Keep identity transform for the prototype so the pipeline stays runnable.
    return audio_path
