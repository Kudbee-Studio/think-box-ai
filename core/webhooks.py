"""Webhook system for Think Box AI.

Ingest webhooks from external sources, dispatch to registered endpoints.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.foundation.logging import get_logger

logger = get_logger(__name__)


class WebhookIngest:
    """Receive and verify incoming webhooks."""

    def __init__(self, secret: str = ""):
        self.secret = secret
        self.events_log = Path("data/webhook_events.jsonl")
        self.events_log.parent.mkdir(parents=True, exist_ok=True)

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify HMAC signature."""
        if not self.secret:
            return True
        expected = hmac.new(self.secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def ingest(self, event_type: str, payload: dict, source: str = "unknown") -> dict:
        """Process an incoming webhook event."""
        event = {
            "id": f"wh_{int(time.time() * 1000)}",
            "type": event_type,
            "source": source,
            "payload": payload,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.events_log, "a") as f:
            f.write(json.dumps(event) + "\n")
        logger.info(f"Webhook ingested: {event_type} from {source}")
        return event

    def list_events(self, event_type: str | None = None, limit: int = 50) -> list[dict]:
        if not self.events_log.exists():
            return []
        events = []
        with open(self.events_log) as f:
            for line in f:
                e = json.loads(line.strip())
                if event_type and e["type"] != event_type:
                    continue
                events.append(e)
        return events[-limit:]


class WebhookDispatch:
    """Dispatch events to registered endpoints."""

    def __init__(self):
        self._endpoints: list[dict] = []
        self._load_endpoints()

    def _load_endpoints(self):
        config = Path("data/webhook_endpoints.json")
        if config.exists():
            self._endpoints = json.loads(config.read_text())

    def _save_endpoints(self):
        Path("data/webhook_endpoints.json").write_text(json.dumps(self._endpoints, indent=2))

    def register(self, name: str, url: str, events: list[str], secret: str = ""):
        endpoint = {"name": name, "url": url, "events": events, "secret": secret, "active": True}
        self._endpoints.append(endpoint)
        self._save_endpoints()
        logger.info(f"Webhook endpoint registered: {name}")

    def unregister(self, name: str):
        self._endpoints = [e for e in self._endpoints if e["name"] != name]
        self._save_endpoints()

    async def dispatch(self, event_type: str, payload: dict):
        import urllib.request
        for ep in self._endpoints:
            if not ep.get("active"):
                continue
            if event_type not in ep["events"]:
                continue
            try:
                data = json.dumps({
                    "event": event_type,
                    "payload": payload,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }).encode()
                req = urllib.request.Request(ep["url"], data=data, headers={"Content-Type": "application/json"})
                if ep.get("secret"):
                    sig = hmac.new(ep["secret"].encode(), data, hashlib.sha256).hexdigest()
                    req.add_header("X-Signature", sig)
                urllib.request.urlopen(req, timeout=10)
                logger.info(f"Dispatched {event_type} to {ep['name']}")
            except Exception as e:
                logger.warning(f"Dispatch failed to {ep['name']}: {e}")
