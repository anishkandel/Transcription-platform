from __future__ import annotations

import hashlib
import hmac
from typing import Any


def summarize_webhook(event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    obj = payload.get("object") if isinstance(payload, dict) else {}
    if not isinstance(obj, dict):
        obj = {}
    return {
        "event": event_name,
        "meeting_id": obj.get("id"),
        "uuid": obj.get("uuid"),
        "host_id": obj.get("host_id"),
        "topic": obj.get("topic"),
    }


def verify_zoom_webhook_signature(
    *,
    secret_token: str,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
) -> bool:
    """Optional request signature check for Zoom webhooks."""
    if not secret_token or not timestamp or not signature:
        return True
    message = f"v0:{timestamp}:{body.decode('utf-8')}"
    digest = hmac.new(
        secret_token.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)
