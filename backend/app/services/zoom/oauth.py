from __future__ import annotations
from app.security import encrypt_secret, decrypt_secret

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import ZoomTokenRecord


class ZoomAuthError(RuntimeError):
    pass


def build_authorize_url(settings: Settings, state: str) -> str:
    if not settings.zoom_client_id:
        raise ZoomAuthError("ZOOM_CLIENT_ID is missing")
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": settings.zoom_client_id,
        "redirect_uri": settings.zoom_redirect_uri,
        "state": state,
    }
    scopes = " ".join(settings.zoom_oauth_scopes.split())
    if scopes:
        params["scope"] = scopes
    return f"{settings.zoom_oauth_authorize_url}?{urlencode(params)}"


def _basic_auth_header(settings: Settings) -> tuple[str, str]:
    return settings.zoom_client_id, settings.zoom_client_secret


def exchange_code_for_tokens(settings: Settings, code: str) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.zoom_redirect_uri,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            settings.zoom_oauth_token_url,
            data=data,
            auth=_basic_auth_header(settings),
        )
    if response.status_code >= 400:
        raise ZoomAuthError(f"Token exchange failed: {response.text}")
    return response.json()


def refresh_access_token(settings: Settings, refresh_token: str) -> dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            settings.zoom_oauth_token_url,
            data=data,
            auth=_basic_auth_header(settings),
        )
    if response.status_code >= 400:
        raise ZoomAuthError(f"Token refresh failed: {response.text}")
    return response.json()


def fetch_zoom_user(settings: Settings, access_token: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{settings.zoom_api_base_url}/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise ZoomAuthError(f"Failed to fetch Zoom user: {response.text}")
    return response.json()


def save_tokens(
    db: Session,
    settings: Settings,
    token_payload: dict[str, Any],
    *,
    app_user_id: str,
    user_payload: dict[str, Any] | None = None,
) -> ZoomTokenRecord:
    access_token = token_payload["access_token"]
    refresh_token = token_payload["refresh_token"]
    expires_in = int(token_payload.get("expires_in") or 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)

    if user_payload is None:
        try:
            user_payload = fetch_zoom_user(settings, access_token)
        except ZoomAuthError:
            # Binding can still succeed if meeting scopes exist but user:read:user was missing.
            user_payload = {
                "id": f"pending-{app_user_id[:8]}",
                "email": None,
                "display_name": "Zoom account (reconnect after adding user:read:user scope)",
            }

    zoom_user_id = str(user_payload.get("id") or f"pending-{app_user_id[:8]}")

    # Prefer the row already linked to this app user.
    record = db.scalar(select(ZoomTokenRecord).where(ZoomTokenRecord.user_id == app_user_id))
    if record is None:
        record = db.scalar(select(ZoomTokenRecord).where(ZoomTokenRecord.zoom_user_id == zoom_user_id))
    if record is None:
        record = ZoomTokenRecord(zoom_user_id=zoom_user_id)
        db.add(record)

    record.user_id = app_user_id
    record.zoom_user_id = zoom_user_id
    record.email = user_payload.get("email")
    record.display_name = user_payload.get("display_name") or user_payload.get("first_name")
    record.access_token = encrypt_secret(access_token,settings.zoom_token_encryption_key,)
    record.refresh_token = encrypt_secret(refresh_token, settings.zoom_token_encryption_key,
    )
    record.token_type = token_payload.get("token_type") or "bearer"
    record.scope = token_payload.get("scope")
    record.expires_at = expires_at
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


def get_token_for_user(db: Session, user_id: str) -> ZoomTokenRecord | None:
    return db.scalar(select(ZoomTokenRecord).where(ZoomTokenRecord.user_id == user_id))


def get_primary_token(db: Session) -> ZoomTokenRecord | None:
    """Legacy helper for webhooks/health when no app user context exists."""
    return db.scalar(select(ZoomTokenRecord).order_by(ZoomTokenRecord.updated_at.desc()))


def disconnect_zoom_for_user(db: Session, user_id: str) -> bool:
    record = get_token_for_user(db, user_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True


def get_valid_access_token(
    db: Session,
    settings: Settings,
    user_id: str | None = None,
) -> str:
    record = get_token_for_user(db, user_id) if user_id else get_primary_token(db)
    if record is None:
        raise ZoomAuthError("No Zoom account is linked. Connect Zoom from Scheduled Meetings.")

    now = datetime.now(timezone.utc)
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now:
        refresh_token = decrypt_secret(record.refresh_token,settings.zoom_token_encryption_key,)
        refreshed = refresh_access_token(settings, refresh_token)
        user_payload = {
            "id": record.zoom_user_id,
            "email": record.email,
            "display_name": record.display_name,
        }
        if not record.user_id:
            raise ZoomAuthError("Zoom token is not linked to an app user. Reconnect Zoom.")
        record = save_tokens(
            db,
            settings,
            refreshed,
            app_user_id=record.user_id,
            user_payload=user_payload,
        )

    return decrypt_secret(
    record.access_token,
    settings.zoom_token_encryption_key,
)


def zoom_validation_response(plain_token: str, secret_token: str) -> dict[str, str]:
    digest = hmac.new(
        secret_token.encode("utf-8"),
        plain_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {"plainToken": plain_token, "encryptedToken": digest}
