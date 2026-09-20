"""KUDBEE Control Fabric — Live substrate binding.

Binds Think Boxes and the control fabric to the actual running substrate
instead of a hardcoded string. Detects the Upstash Box (the Firecracker-
class microVM we run inside), probes available isolation tools, and
persists Think Box snapshots to the Upstash Vector memory layer so work
survives box restarts — the system of record above the model session.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.workspace import ThinkBox


def detect_substrate() -> str:
    """Return the live substrate from the environment we actually run in."""
    box_url = os.environ.get("UPSTASH_PUBLIC_BOX_URL", "")
    if box_url:
        try:
            from urllib.parse import urlparse

            host = urlparse(box_url).hostname or "upstash-box"
            return host
        except Exception:
            return "upstash-box"
    if os.environ.get("THINKBOX_UPCLOUD_API_TOKEN"):
        return "upcloud-gpu"
    if os.environ.get("CI"):
        return "ci"
    return "local"


@dataclass
class IsolationProbe:
    tool: str
    available: bool
    path: str = ""


@dataclass
class SubstrateReport:
    substrate: str
    isolation_tools: list[IsolationProbe] = field(default_factory=list)
    vector_sync: bool = False
    box_url: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "substrate": self.substrate,
            "isolation_tools": {p.tool: p.available for p in self.isolation_tools},
            "vector_sync": self.vector_sync,
            "box_url": self.box_url,
            "timestamp": self.timestamp,
        }


class SubstrateProbe:
    """Detects the running substrate and its isolation capabilities."""

    TOOLS = ("unshare", "bwrap", "docker", "podman", "firecracker-jailer", "cloudflared")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reports: list[SubstrateReport] = []

    def probe(self) -> SubstrateReport:
        box_url = os.environ.get("UPSTASH_PUBLIC_BOX_URL", "")
        vector = bool(os.environ.get("UPSTASH_VECTOR_REST_URL") and os.environ.get("UPSTASH_VECTOR_REST_TOKEN"))
        tools = [IsolationProbe(tool=t, available=bool(shutil.which(t)), path=shutil.which(t) or "") for t in self.TOOLS]
        report = SubstrateReport(
            substrate=detect_substrate(),
            isolation_tools=tools,
            vector_sync=vector,
            box_url=box_url,
        )
        with self._lock:
            self._reports.append(report)
        return report

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            if limit <= 0:
                return []
            return [r.to_dict() for r in self._reports[-limit:]]


class ThinkBoxVectorSync:
    """Persists Think Box snapshots to the Upstash Vector memory layer.

    Uses a deterministic 1536-dim vector derived from the snapshot id so a
    box can be recovered by its box_id after a substrate restart. Matches
    the proven REST shape: /upsert (POST), /fetch (POST), /delete (POST).
    """

    DIMENSIONS = 1536

    def __init__(self) -> None:
        self._url = os.environ.get("UPSTASH_VECTOR_REST_URL", "").rstrip("/")
        self._token = os.environ.get("UPSTASH_VECTOR_REST_TOKEN", "")
        self._enabled = bool(self._url and self._token)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @staticmethod
    def _vector_for(snapshot_id: str) -> list[float]:
        digest = hashlib.sha256(snapshot_id.encode()).digest()
        # Expand 32 bytes into a deterministic 1536-dim vector in [0,1).
        out: list[float] = []
        while len(out) < ThinkBoxVectorSync.DIMENSIONS:
            out.extend(v / 255.0 for v in digest)
            digest = hashlib.sha256(digest).digest()
        return out[: ThinkBoxVectorSync.DIMENSIONS]

    def snapshot(self, box: ThinkBox) -> bool:
        if not self._enabled:
            return False
        payload = [{
            "id": f"thinkbox:{box.box_id}",
            "vector": self._vector_for(box.box_id),
            "metadata": box.snapshot(),
        }]
        return self._request("/upsert", payload)

    def fetch(self, box_id: str) -> dict[str, Any] | None:
        if not self._enabled:
            return None
        body = self._request_raw("/fetch", {"ids": [f"thinkbox:{box_id}"], "includeMetadata": True})
        if not body:
            return None
        try:
            results = body.get("result", [])
            return results[0].get("metadata") if results else None
        except (AttributeError, KeyError):
            return None

    def delete(self, box_id: str) -> bool:
        if not self._enabled:
            return False
        return self._request("/delete", {"ids": [f"thinkbox:{box_id}"]})

    def _request(self, path: str, payload: Any) -> bool:
        return self._request_raw(path, payload) is not None

    def _request_raw(self, path: str, payload: Any) -> dict[str, Any] | None:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            self._url + path,
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except (urllib.error.HTTPError, OSError):
            return None


def bind_think_box(box: ThinkBox, sync: ThinkBoxVectorSync | None = None) -> dict[str, Any]:
    """Bind a Think Box to the live substrate and memory layer."""
    sync = sync or ThinkBoxVectorSync()
    substrate = detect_substrate()
    box.substrate = substrate
    persisted = sync.snapshot(box)
    return {
        "box_id": box.box_id,
        "substrate": substrate,
        "persisted": persisted,
    }