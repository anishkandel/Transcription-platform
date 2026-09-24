from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class TranscriptHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id].add(websocket)

    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(session_id)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections.get(session_id, set()))

        stale: list[WebSocket] = []
        data = json.dumps(message)
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception:
                stale.append(ws)

        for ws in stale:
            await self.disconnect(session_id, ws)


hub = TranscriptHub()
