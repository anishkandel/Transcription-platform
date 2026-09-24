from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.services.zoom.oauth import ZoomAuthError, get_valid_access_token


class ZoomClient:
    """Zoom Meetings + RTMS REST client (assumes developer credentials exist)."""

    def __init__(
        self,
        settings: Settings,
        db: Session | None = None,
        *,
        app_user_id: str | None = None,
    ):
        self.settings = settings
        self.db = db
        self.app_user_id = app_user_id
        self.base_url = settings.zoom_api_base_url.rstrip("/")

    def _headers(self, access_token: str | None = None) -> dict[str, str]:
        if access_token is None:
            if self.db is None:
                raise ZoomAuthError("Database session required to resolve Zoom access token")
            access_token = get_valid_access_token(
                self.db,
                self.settings,
                user_id=self.app_user_id,
            )
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        retries: int = 3,
    ) -> Any:
        import time

        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(retries):
            with httpx.Client(timeout=45.0) as client:
                response = client.request(
                    method,
                    url,
                    headers=self._headers(access_token),
                    params=params,
                    json=json_body,
                )
            if response.status_code == 429:
                last_error = RuntimeError(
                    f"Zoom API {method} {path} failed (429): {response.text}"
                )
                time.sleep(0.8 * (attempt + 1))
                continue
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Zoom API {method} {path} failed ({response.status_code}): {response.text}"
                )
            if response.status_code == 204 or not response.content:
                return {"ok": True}
            return response.json()
        assert last_error is not None
        raise last_error

    def get_me(self) -> dict[str, Any]:
        return self._request("GET", "/users/me")

    def list_meetings(
        self,
        user_id: str = "me",
        meeting_type: str = "upcoming",
        page_size: int = 30,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/users/{user_id}/meetings",
            params={"type": meeting_type, "page_size": page_size},
        )

    def list_upcoming_including_invited(self, user_id: str = "me") -> dict[str, Any]:
        """Meetings the user hosts OR is invited to (Zoom: next ~24 hours only)."""
        return self._request("GET", f"/users/{user_id}/upcoming_meetings")

    def list_dashboard_meetings(self, user_id: str = "me") -> dict[str, Any]:
        """Merge hosted upcoming meetings with invited upcoming (24h) meetings."""
        hosted = self.list_meetings(user_id=user_id, meeting_type="upcoming")
        invited: dict[str, Any] = {"meetings": []}
        try:
            invited = self.list_upcoming_including_invited(user_id=user_id)
        except Exception:
            # Scope may be missing; still return hosted meetings.
            invited = {"meetings": [], "warning": "upcoming_meetings unavailable (add meeting:read:list_upcoming_meetings)"}

        by_id: dict[str, dict[str, Any]] = {}
        for item in hosted.get("meetings") or []:
            if not isinstance(item, dict):
                continue
            mid = str(item.get("id") or "")
            if not mid:
                continue
            row = dict(item)
            row["source"] = "hosted"
            row["is_host"] = True
            by_id[mid] = row

        for item in invited.get("meetings") or []:
            if not isinstance(item, dict):
                continue
            mid = str(item.get("id") or "")
            if not mid:
                continue
            if mid in by_id:
                by_id[mid]["is_host"] = bool(item.get("is_host", by_id[mid].get("is_host", True)))
                continue
            row = dict(item)
            row["source"] = "invited"
            row["is_host"] = bool(item.get("is_host", False))
            by_id[mid] = row

        meetings = sorted(
            by_id.values(),
            key=lambda m: str(m.get("start_time") or ""),
        )
        result: dict[str, Any] = {
            "meetings": meetings,
            "total_records": len(meetings),
            "hosted_count": len(hosted.get("meetings") or []),
            "invited_count": len(invited.get("meetings") or []),
        }
        if invited.get("warning"):
            result["warning"] = invited["warning"]
        return result

    def create_meeting(self, payload: dict[str, Any], user_id: str = "me") -> dict[str, Any]:
        return self._request("POST", f"/users/{user_id}/meetings", json_body=payload)

    def get_meeting(self, meeting_id: str) -> dict[str, Any]:
        return self._request("GET", f"/meetings/{meeting_id}")

    def update_meeting(self, meeting_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/meetings/{meeting_id}", json_body=payload)

    def delete_meeting(self, meeting_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/meetings/{meeting_id}")

    def start_rtms(self, meeting_id: str, client_id: str | None = None) -> dict[str, Any]:
        body = {
            "action": "start",
            "settings": {
                "client_id": client_id or self.settings.zoom_client_id,
            },
        }
        return self._request(
            "PATCH",
            f"/live_meetings/{meeting_id}/rtms_app/status",
            json_body=body,
        )

    def stop_rtms(self, meeting_id: str, client_id: str | None = None) -> dict[str, Any]:
        body = {
            "action": "stop",
            "settings": {
                "client_id": client_id or self.settings.zoom_client_id,
            },
        }
        return self._request(
            "PATCH",
            f"/live_meetings/{meeting_id}/rtms_app/status",
            json_body=body,
        )
