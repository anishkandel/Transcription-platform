from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import UserRecord, ZoomTokenRecord

COOKIE_NAME = "kk_session"
TOKEN_HOURS = 24 * 7


class AuthError(RuntimeError):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_HOURS),
        "typ": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired session") from exc
    user_id = payload.get("sub")
    if not user_id or payload.get("typ") != "access":
        raise AuthError("Invalid session token")
    return str(user_id)


def create_oauth_state(user_id: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "uid": user_id,
        "purpose": "zoom_oauth",
        "iat": now,
        "exp": now + timedelta(minutes=20),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def parse_oauth_state(state: str, settings: Settings) -> str:
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired Zoom OAuth state") from exc
    if payload.get("purpose") != "zoom_oauth" or not payload.get("uid"):
        raise AuthError("Invalid Zoom OAuth state")
    return str(payload["uid"])


def get_user_by_email(db: Session, email: str) -> UserRecord | None:
    return db.scalar(select(UserRecord).where(UserRecord.email == email.lower().strip()))


def get_user_by_id(db: Session, user_id: str) -> UserRecord | None:
    return db.get(UserRecord, user_id)


def register_user(db: Session, *, email: str, password: str, name: str = "") -> UserRecord:
    cleaned = email.lower().strip()
    if not cleaned or "@" not in cleaned:
        raise AuthError("A valid email is required")
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters")
    if get_user_by_email(db, cleaned):
        raise AuthError("An account with this email already exists")

    user = UserRecord(
        id=str(uuid.uuid4()),
        email=cleaned,
        password_hash=hash_password(password),
        name=(name or cleaned.split("@")[0]).strip(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> UserRecord:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password")
    return user


def user_has_zoom(db: Session, user_id: str) -> bool:
    return (
        db.scalar(select(ZoomTokenRecord.id).where(ZoomTokenRecord.user_id == user_id).limit(1))
        is not None
    )


def serialize_user(db: Session, user: UserRecord) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "zoom_connected": user_has_zoom(db, user.id),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
