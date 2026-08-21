"""Embeddings service for semantic memory search.

Generates vector embeddings for memory entries and events using
sentence-transformers (all-MiniLM-L6-v2, ~80MB, runs locally).

This is the pgvector Semantic Layer (Issue #8 Stage 4 / Issue #9 enabler).

Usage:
    embeddings = EmbeddingService()
    vector = embeddings.embed("PostgreSQL preferred over Redis")
    # Returns list[float] of length 1536
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from typing import Any

from core.foundation.logging import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 1536
_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


class EmbeddingService:
    """Local embedding generation for semantic memory search.

    Uses sentence-transformers when available; falls back to a deterministic
    hash-based pseudo-embedding for environments without ML dependencies.
    """

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        """Initialize the embedding service.

        Args:
            model_name: Sentence-transformers model name (default: all-MiniLM-L6-v2)
        """
        self.model_name = model_name
        self._model = None
        self._dimension = EMBEDDING_DIM

    def _load_model(self) -> Any:
        """Lazily load the sentence-transformers model."""
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info("Loaded embedding model", extra={"model": self.model_name})
        except ImportError:
            logger.warning("sentence-transformers not installed, using hash-based fallback")
            self._model = False  # sentinel: fallback mode
        return self._model

    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (length 1536 for all-MiniLM-L6-v2)
        """
        model = self._load_model()

        if model is False:
            # Fallback: deterministic hash-based pseudo-embedding
            return self._hash_embedding(text)

        # Real model
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        model = self._load_model()
        if model is False:
            return [self._hash_embedding(t) for t in texts]

        vectors = model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def _hash_embedding(self, text: str) -> list[float]:
        """Deterministic fallback embedding using SHA-256 hashing.

        Produces a normalized vector of length EMBEDDING_DIM by folding
        hash bytes. Not semantically meaningful, but deterministic and
        dimensionally correct for schema validation.
        """
        # Use multiple hash rounds to fill the dimension
        vector = [0.0] * self._dimension
        text_bytes = text.encode("utf-8")
        for i in range(self._dimension):
            h = hashlib.sha256(text_bytes + i.to_bytes(4, "big")).digest()
            # Map first 4 bytes to [-1, 1]
            val = int.from_bytes(h[:4], "big") / (2**32) * 2 - 1
            vector[i] = val
        # L2 normalize
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension
