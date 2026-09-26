from __future__ import annotations
from sqlalchemy import text
from app.db import SessionLocal
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.sessions import router as sessions_router
from app.api.zoom import router as zoom_router
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.schemas import HealthOut
from app.services.speech.papa_reo import PapaReoClient
from app.services.websocket_manager import hub
from app.services.zoom.oauth import get_primary_token

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Meeting transcription prototype for Te Hiku Media: "
        "app auth + Zoom OAuth binding + meetings API + Mock RTMS + Papa Reo + web UI."
    ),
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(zoom_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    client = PapaReoClient(settings)
    db = SessionLocal()
    try:
        connected = get_primary_token(db) is not None
    finally:
        db.close()
    return HealthOut(
        status="ok",
        app=settings.app_name,
        papareo_configured=client.configured,
        zoom_configured=bool(settings.zoom_client_id and settings.zoom_client_secret),
        zoom_user_connected=connected,
        zoom_rtms_enabled=settings.zoom_rtms_enabled,
        mock_rtms_enabled=settings.mock_rtms_enabled,
    )


@app.websocket("/ws/sessions/{session_id}")
async def session_ws(session_id: str, websocket: WebSocket) -> None:
    await hub.connect(session_id, websocket)
    try:
        await websocket.send_json(
            {
                "type": "connection.ready",
                "session_id": session_id,
                "message": "WebSocket connected. Waiting for transcript updates.",
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(session_id, websocket)


@app.get("/debug/db")
def debug_db():
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT
                current_database() AS database,
                current_user AS user,
                inet_server_addr()::text AS server_addr,
                inet_server_port() AS server_port,
                (SELECT COUNT(*) FROM sessions) AS session_count
        """)).mappings().one()

        return dict(row)
    finally:
        db.close()
