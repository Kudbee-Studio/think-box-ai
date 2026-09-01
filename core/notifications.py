"""Notification system for Think Box AI.

Supports: webhook, email (SMTP), and in-app notifications.
"""

from __future__ import annotations

import json
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from core.foundation.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Notification:
    id: str
    type: str  # job_complete, job_failed, alert, info
    title: str
    message: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    read: bool = False
    metadata: dict = field(default_factory=dict)


class NotificationStore:
    def __init__(self, path: Path = Path("data/notifications.jsonl")):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, notification: Notification):
        with open(self.path, "a") as f:
            f.write(json.dumps(notification.__dict__) + "\n")

    def list(self, unread_only: bool = False, limit: int = 50) -> list[Notification]:
        if not self.path.exists():
            return []
        notifications = []
        with open(self.path) as f:
            for line in f:
                data = json.loads(line.strip())
                if unread_only and data.get("read"):
                    continue
                notifications.append(Notification(**data))
        return notifications[-limit:]

    def mark_read(self, notification_id: str):
        # Rewrite file with marked read
        if not self.path.exists():
            return
        lines = []
        with open(self.path) as f:
            for line in f:
                data = json.loads(line.strip())
                if data["id"] == notification_id:
                    data["read"] = True
                lines.append(json.dumps(data))
        self.path.write_text("\n".join(lines) + "\n")


class WebhookDispatcher:
    def __init__(self):
        self.endpoints: list[dict] = []

    def register(self, url: str, events: list[str], secret: str = ""):
        self.endpoints.append({"url": url, "events": events, "secret": secret})

    async def dispatch(self, event: str, payload: dict):
        import urllib.request
        for ep in self.endpoints:
            if event not in ep["events"]:
                continue
            try:
                data = json.dumps({"event": event, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}).encode()
                req = urllib.request.Request(ep["url"], data=data, headers={"Content-Type": "application/json"})
                if ep["secret"]:
                    import hmac, hashlib
                    sig = hmac.new(ep["secret"].encode(), data, hashlib.sha256).hexdigest()
                    req.add_header("X-Signature", sig)
                urllib.request.urlopen(req, timeout=10)
            except Exception as e:
                logger.warning(f"Webhook dispatch failed: {e}")


class EmailNotifier:
    def __init__(self, host: str = "", port: int = 587, user: str = "", password: str = "", from_addr: str = ""):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_addr = from_addr

    def send(self, to: str, subject: str, body: str):
        if not self.host:
            logger.warning("Email not configured")
            return
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = to
        with smtplib.SMTP(self.host, self.port) as server:
            server.starttls()
            server.login(self.user, self.password)
            server.send_message(msg)
