"""THINK stash writer — persist reasoning payloads to Upstash Vector."""

from __future__ import annotations

import hashlib
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.byoc_config import ByocConfig
from thinkbox.embedder import DeterministicEmbedder, EmbeddingError

logger = logging.getLogger(__name__)


@dataclass
class ThinkStashEntry:
    stash_id: str = ""
    session_id: str = ""
    burst_id: str = ""
    reasoning_sha256: str = ""
    vector_id: str = ""
    proof_receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    evidence_label: str = "simulated"


class ThinkStashWriter:
    """Write THINK entries to Upstash Vector.

    Embeds reasoning text via DeterministicEmbedder (tests) or
    OpenAICompatEmbedder (live). Upserts with dense vector + metadata.
    Raises EmbeddingError on failure (never silent False).
    """

    def __init__(self, config: ByocConfig | None = None) -> None:
        self._config = config or ByocConfig.load()
        self._url = self._config.vector_url.rstrip("/") if self._config.vector_url else ""
        self._token = self._config.vector_token
        self._enabled = bool(self._url and self._token)
        self._embedder = self._make_embedder()

    def _make_embedder(self) -> DeterministicEmbedder | None:
        if self._config.is_mock or not self._config.api_key:
            return DeterministicEmbedder()
        from thinkbox.embedder import OpenAICompatEmbedder

        try:
            return OpenAICompatEmbedder(
                api_key=self._config.api_key,
                base_url=self._config.base_url,
            )
        except Exception:
            return DeterministicEmbedder()

    def redacted_config(self) -> dict[str, Any]:
        return self._config.redacted()

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._embedder is None:
            raise EmbeddingError(message="No embedder available")
        return self._embedder.embed(texts)

    def _upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._enabled:
            raise EmbeddingError(message="Upstash Vector not configured")
        import urllib.request as _urllib_request

        url = f"{self._url}/upsert"
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
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode() if hasattr(e, "read") else ""
            raise EmbeddingError(message=f"Upsert HTTP {e.code}: {body}") from e
        except Exception as e:
            raise EmbeddingError(message=f"Upsert failed: {e}") from e

    def write(self, entry: ThinkStashEntry) -> ThinkStashEntry:
        """Upsert a THINK stash entry. Returns entry with vector_id set."""
        if not entry.created_at:
            entry.created_at = datetime.now(timezone.utc).isoformat()

        text = json.dumps(entry.__dict__, sort_keys=True, default=str)
        vectors = self._embed([text])

        if vectors:
            entry.vector_id = hashlib.sha256(text.encode()).hexdigest()[:32]
            payload = {
                "id": entry.stash_id or entry.vector_id,
                "vector": vectors[0],
                "metadata": {
                    "session_id": entry.session_id,
                    "burst_id": entry.burst_id,
                    "reasoning_sha256": entry.reasoning_sha256,
                    "vector_id": entry.vector_id,
                    "proof_receipt_id": entry.proof_receipt_id,
                    "evidence_label": entry.evidence_label,
                    "created_at": entry.created_at,
                    **entry.metadata,
                },
            }
            result = self._upsert(payload)
            logger.info("Stashed THINK %s to vector", entry.stash_id or entry.vector_id)
        else:
            entry.vector_id = hashlib.sha256(text.encode()).hexdigest()[:32]
            logger.info("Stashed THINK %s (no vector)", entry.stash_id or entry.vector_id)

        return entry

    def write_batch(self, entries: list[ThinkStashEntry]) -> list[ThinkStashEntry]:
        return [self.write(e) for e in entries]