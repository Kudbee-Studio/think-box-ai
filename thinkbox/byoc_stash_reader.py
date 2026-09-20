"""THINK stash reader / similarity reuse from Upstash Vector."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from thinkbox.byoc_config import ByocConfig
from thinkbox.embedder import EmbeddingError

logger = logging.getLogger(__name__)


class ThinkStashReader:
    """Read / search THINK stash from Upstash Vector.

    Reuses similarity endpoints for retrieval.
    """

    def __init__(self, config: ByocConfig | None = None) -> None:
        self._config = config or ByocConfig.load()
        self._url = self._config.vector_url.rstrip("/") if self._config.vector_url else ""
        self._token = self._config.vector_token
        self._enabled = bool(self._url and self._token)

    def redacted_config(self) -> dict[str, Any]:
        return self._config.redacted()

    def fetch(self, stash_id: str) -> dict[str, Any] | None:
        """Fetch a single entry by ID."""
        if not self._enabled:
            return None
        import urllib.request as _urllib_request

        url = f"{self._url}/fetch"
        data = json.dumps({"ids": [stash_id], "includeMetadata": True}).encode()
        req = _urllib_request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with _urllib_request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                results = body.get("result", [])
                if results:
                    return results[0]
        except urllib.error.HTTPError as e:
            logger.warning("Fetch HTTP %d for %s", e.code, stash_id)
        except Exception as e:
            logger.warning("Fetch failed for %s: %s", stash_id, e)
        return None

    def search(self, query_vector: list[float], top_k: int = 5, namespace: str = "") -> list[dict[str, Any]]:
        """Search for similar THINK entries by vector similarity."""
        if not self._enabled:
            return []
        import urllib.request as _urllib_request

        url = f"{self._url}/search"
        payload: dict[str, Any] = {
            "vector": query_vector,
            "topK": top_k,
            "includeMetadata": True,
        }
        if namespace:
            payload["namespace"] = namespace
        data = json.dumps(payload).encode()
        req = _urllib_request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with _urllib_request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                results = body.get("result", [])
                return [
                    {
                        "id": r.get("id", ""),
                        "score": r.get("score", 0.0),
                        "metadata": r.get("metadata", {}),
                    }
                    for r in results
                ]
        except Exception as e:
            logger.warning("Search failed: %s", e)
            return []

    def delete(self, stash_id: str) -> bool:
        """Delete a THINK stash entry."""
        if not self._enabled:
            return False
        import urllib.request as _urllib_request

        url = f"{self._url}/delete"
        data = json.dumps({"ids": [stash_id]}).encode()
        req = _urllib_request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with _urllib_request.urlopen(req, timeout=15) as resp:
                return resp.status == 200
        except Exception:
            return False