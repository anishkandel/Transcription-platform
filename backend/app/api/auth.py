from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import UserRecord, get_db
from app.deps import get_current_user
from app.services.auth_service import (
    COOKIE_NAME,
    TOKEN_HOURS,
    AuthError,
    authenticate_user,
    create_access_token,
    register_user,
    serialize_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env.lower() == "production",
        max_age=TOKEN_HOURS * 3600,
        path="/",
    )


@router.post("/register")
def register(
    payload: RegisterBody,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        user = register_user(
            db,
            email=str(payload.email),
            password=payload.password,
            name=payload.name,
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = create_access_token(user.id, settings)
    _set_session_cookie(response, token, settings)
    # Also return token for browsers/proxies where Set-Cookie is unreliable (e.g. Docker).
    return {"user": serialize_user(db, user), "access_token": token}


@router.post("/login")
def login(
    payload: LoginBody,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        user = authenticate_user(db, email=str(payload.email), password=payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    token = create_access_token(user.id, settings)
    _set_session_cookie(response, token, settings)
    return {"user": serialize_user(db, user), "access_token": token}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
) -> dict:
    return {"user": serialize_user(db, user)}
