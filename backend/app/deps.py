from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import UserRecord, get_db
from app.services.auth_service import (
    COOKIE_NAME,
    AuthError,
    decode_access_token,
    get_user_by_id,
)


def _extract_token(
    request: Request,
    kk_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> str | None:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return kk_session


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    kk_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> UserRecord:
    token = _extract_token(request, kk_session)
    if not token:
        raise HTTPException(status_code=401, detail="Please sign in first")
    try:
        user_id = decode_access_token(token, settings)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found. Please sign in again")
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    kk_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> UserRecord | None:
    token = _extract_token(request, kk_session)
    if not token:
        return None
    try:
        user_id = decode_access_token(token, settings)
    except AuthError:
        return None
    return get_user_by_id(db, user_id)
