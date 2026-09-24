"""Map Zoom meetings to app transcription sessions for live RTMS."""

from __future__ import annotations

import threading
from typing import Any


class RtmsSessionRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # meeting_id / meeting_uuid / rtms_stream_id -> session_id
        self._keys: dict[str, str] = {}
        # session_id -> metadata
        self._by_session: dict[str, dict[str, Any]] = {}

    def bind(
        self,
        session_id: str,
        *,
        meeting_id: str | None = None,
        meeting_uuid: str | None = None,
        rtms_stream_id: str | None = None,
    ) -> None:
        with self._lock:
            meta = self._by_session.get(session_id, {"session_id": session_id})
            if meeting_id:
                meta["meeting_id"] = str(meeting_id)
                self._keys[str(meeting_id)] = session_id
            if meeting_uuid:
                meta["meeting_uuid"] = str(meeting_uuid)
                self._keys[str(meeting_uuid)] = session_id
            if rtms_stream_id:
                meta["rtms_stream_id"] = str(rtms_stream_id)
                self._keys[str(rtms_stream_id)] = session_id
            self._by_session[session_id] = meta

    def resolve_session_id(self, *candidates: str | None) -> str | None:
        with self._lock:
            for value in candidates:
                if not value:
                    continue
                found = self._keys.get(str(value))
                if found:
                    return found
        return None

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            meta = self._by_session.get(session_id)
            return dict(meta) if meta else None


rtms_session_registry = RtmsSessionRegistry()
