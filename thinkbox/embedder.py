"""Embedding helper for Think Box AI.

Provides pluggable embedder implementations for generating dense vectors
to send to Upstash Vector (dense index requires a vector field on every
upsert).

Production usage: OpenAICompatEmbedder POSTs to the /embeddings endpoint
of any OpenAI-compatible provider (e.g. Mercury 2 at api.inceptionlabs.ai).

Test usage: DeterministicEmbedder generates stable hash-based vectors
for unit tests only — it does NOT produce semantically meaningful
embeddings and must never be used in production.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class EmbeddingError(Exception):
    error_type: str = "embedder_error"
    message: str = "Embedding generation failed"

    def __str__(self) -> str:
        return f"[{self.error_type}] {self.message}"


class Embedder(ABC):
    """Abstract embedder — produces dense vectors for a list of texts."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...


class OpenAICompatEmbedder(Embedder):
    """Embedder using any OpenAI-compatible /embeddings endpoint.

    Reads THINKBOX_OPENAI_COMPAT_API_KEY and THINKBOX_OPENAI_COMPAT_BASE_URL
    from the environment. Posts to {base_url}/embeddings with the standard
    OpenAI request shape.

    Suitable for production use with providers that expose an embeddings
    route (Mercury 2 / Inception / OpenAI / Groq / Together / vLLM / Ollama
    with embedding support).
    """

    DEFAULT_DIMENSION = 1536

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("THINKBOX_OPENAI_COMPAT_API_KEY", "")
        self._base_url = (base_url or os.environ.get("THINKBOX_OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self._model = os.environ.get("THINKBOX_EMBED_MODEL", self._default_model())
        self._dimension = self.DEFAULT_DIMENSION

    @staticmethod
    def _default_model() -> str:
        # Chat models (THINKBOX_DEFAULT_MODEL) are not embedding models; this
        # default matches the 1536-dim Upstash dense index.
        return "text-embedding-3-small"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._api_key:
            raise EmbeddingError(
                message="No THINKBOX_OPENAI_COMPAT_API_KEY configured — "
                "set it to use OpenAI-compatible embeddings, or use "
                "DeterministicEmbedder for unit tests only"
            )
        if not texts:
            return []

        payload = {
            "model": self._model,
            "input": texts,
        }

        def _fetch() -> list[list[float]]:
            req = urllib.request.Request(
                f"{self._base_url}/embeddings",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    vectors = [item["embedding"] for item in body.get("data", [])]
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, "read") else ""
                raise EmbeddingError(
                    message=f"Embeddings endpoint HTTP {e.code}: {body}"
                ) from e
            except urllib.error.URLError as e:
                raise EmbeddingError(
                    message=f"Embeddings endpoint unreachable: {e.reason}"
                ) from e
            if len(vectors) != len(texts):
                raise EmbeddingError(
                    message=f"Embeddings endpoint returned {len(vectors)} vectors for {len(texts)} inputs"
                )
            for vec in vectors:
                if len(vec) != self._dimension:
                    raise EmbeddingError(
                        message=f"Embedding model {self._model!r} returned dimension {len(vec)}, "
                        f"expected {self._dimension}; set THINKBOX_EMBED_MODEL to a {self._dimension}-dim model"
                    )
            return vectors

        return _fetch()


class DeterministicEmbedder(Embedder):
    """Deterministic hash-based embedder — unit tests ONLY.

    Generates stable 1536-dim vectors from text hashes. Does NOT produce
    semantically meaningful embeddings. Must never be used in production
    or for any real Upstash Vector upsert.

    Used exclusively in unit tests where no live embedding provider is
    available, to verify the upsert payload shape without making network
    calls.
    """

    DIMENSION = 1536

    @property
    def dimension(self) -> int:
        return self.DIMENSION

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [self._vector_for(text) for text in texts]

    @staticmethod
    def _vector_for(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        out: list[float] = []
        while len(out) < DeterministicEmbedder.DIMENSION:
            out.extend(v / 255.0 for v in digest)
            digest = hashlib.sha256(digest).digest()
        return out[: DeterministicEmbedder.DIMENSION]