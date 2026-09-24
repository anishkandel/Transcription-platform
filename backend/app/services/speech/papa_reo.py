from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from app.config import Settings


class PapaReoError(RuntimeError):
    pass


class PapaReoClient:
    """Client for Papa Reo speech services provided by Te Hiku Media."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.papareo_api_key.strip())

    def transcribe_file(
        self,
        audio_path: Path,
        with_metadata: bool = False,
        timeout: float = 180.0,
    ) -> dict[str, Any]:
        if not self.configured:
            raise PapaReoError(
                "PAPAREO_API_KEY is not configured. Add it to your .env file."
            )

        url = (
            self.settings.papareo_base_url.rstrip("/")
            + self.settings.papareo_transcribe_path
        )
        headers = {
            "Accept": "application/json",
            "Authorization": f"Token {self.settings.papareo_api_key}",
        }

        with audio_path.open("rb") as audio_fp:
            files = {"audio_file": (audio_path.name, audio_fp)}
            data = {"with_metadata": "true" if with_metadata else "false"}
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, files=files, data=data)

        try:
            payload = response.json()
        except Exception as exc:
            raise PapaReoError(
                f"Invalid JSON from Papa Reo (HTTP {response.status_code}): {response.text}"
            ) from exc

        if response.status_code != 200:
            detail = payload.get("detail") if isinstance(payload, dict) else payload
            raise PapaReoError(f"Papa Reo HTTP {response.status_code}: {detail}")

        return payload if isinstance(payload, dict) else {"raw": payload}

    def streaming_transcribe_stub(self, audio_chunk: bytes) -> dict[str, Any]:
        """Deprecated stub. Use PapaReoStreamingClient instead."""
        return {
            "success": False,
            "provider": "papa_reo_streaming",
            "detail": "Use SpeechPipeline.process_audio_file_streaming()",
            "bytes_received": len(audio_chunk),
        }
