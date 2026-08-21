"""PostgreSQL 19 + pgvector backed memory store for THINK BOX AI.

This module provides an async memory store using asyncpg and PostgreSQL 19 with
the pgvector extension for semantic search. When PostgreSQL is not available, it
falls back to the SQLite store for local development.

PostgreSQL 19 features used:
- ON CONFLICT DO SELECT for atomic get-or-create
- pgvector <=> operator for cosine similarity search
- JSONB for flexible metadata storage

Usage:
    store = PostgresMemoryStore("postgresql://kudbee:pass@localhost:5432/kudbee")
    await store.connect()
    store.put(entry)
    results = await store.semantic_search("how to handle timeouts", limit=5)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from core.foundation.errors import MemoryError, MemoryKeyError
from core.foundation.logging import get_logger
from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer

logger = get_logger(__name__)

# Embedding dimension for all-MiniLM-L6-v2
EMBEDDING_DIM = 1536


class PostgresMemoryStore:
    """Async PostgreSQL-backed memory store with vector search.

    Falls back to SQLite when PostgreSQL is unavailable. This allows the
    same code path to work in both local dev (SQLite) and production (PG).
    """

    def __init__(self, database_url: str | None = None, fallback_db_path: str = "memory.db") -> None:
        """Initialize the PostgreSQL memory store.

        Args:
            database_url: PostgreSQL connection URL. If None, uses DATABASE_URL env var.
            fallback_db_path: SQLite path used when PostgreSQL is unavailable.
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.fallback_db_path = fallback_db_path
        self._pool = None
        self._using_fallback = False
        self._fallback_store = None

    async def connect(self) -> None:
        """Connect to PostgreSQL or fall back to SQLite.

        Raises:
            MemoryError: If neither PostgreSQL nor SQLite can be initialized.
        """
        if not self.database_url:
            logger.warning("No DATABASE_URL set, falling back to SQLite")
            await self._use_fallback()
            return

        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=20,
                command_timeout=30,
            )
            # Verify connection
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            self._using_fallback = False
            logger.info("Connected to PostgreSQL 19 with pgvector")
        except ImportError:
            logger.warning("asyncpg not installed, falling back to SQLite")
            await self._use_fallback()
        except Exception as e:
            logger.warning(
                "PostgreSQL connection failed, falling back to SQLite",
                extra={"error": str(e)},
            )
            await self._use_fallback()

    async def _use_fallback(self) -> None:
        """Initialize SQLite fallback store."""
        try:
            from core.memory.store import MemoryStore

            self._fallback_store = MemoryStore(self.fallback_db_path)
            self._using_fallback = True
            logger.info("Using SQLite fallback store", extra={"path": self.fallback_db_path})
        except Exception as e:
            raise MemoryError(
                message=f"Failed to initialize fallback store: {e}",
                context={"path": self.fallback_db_path},
            ) from e

    @property
    def backend(self) -> str:
        """Return which backend is active."""
        return "postgres" if not self._using_fallback else "sqlite"

    async def close(self) -> None:
        """Close database connections."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
        if self._fallback_store is not None:
            self._fallback_store.close()

    # --- Core operations (delegate to fallback if needed) ---

    def put(self, entry: MemoryEntry) -> None:
        """Store a memory entry (sync interface for fallback compatibility)."""
        if self._using_fallback:
            self._fallback_store.put(entry)
            return
        # For async path, use the coroutine version
        raise MemoryError(
            message="Use async_put() with PostgreSQL backend",
            context={"key": entry.key},
        )

    async def async_put(self, entry: MemoryEntry) -> None:
        """Store a memory entry (async)."""
        if self._using_fallback:
            self._fallback_store.put(entry)
            return

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memory_entries
                    (key, layer, entry_type, value, agent_id, task_id, session_id, confidence, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $9)
                ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value,
                        confidence = EXCLUDED.confidence,
                        updated_at = EXCLUDED.updated_at,
                        layer = EXCLUDED.layer
                """,
                entry.key,
                entry.layer.value,
                entry.entry_type.value,
                json.dumps(entry.value),
                entry.agent_id,
                entry.task_id,
                entry.metadata.get("session_id", ""),
                entry.confidence,
                datetime.now(timezone.utc()).isoformat(),
            )

    async def get(self, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry by key."""
        if self._using_fallback:
            return self._fallback_store.get(key)

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM memory_entries WHERE key = $1", key)
            if row is None:
                return None
            return self._row_to_entry(row)

    async def delete(self, key: str) -> bool:
        """Delete a memory entry."""
        if self._using_fallback:
            return self._fallback_store.delete(key)

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            result = await conn.execute("DELETE FROM memory_entries WHERE key = $1", key)
            return result.split()[-1] == "1" if result else False

    async def query(
        self,
        layer: MemoryLayer | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        entry_type: MemoryEntryType | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """Query memory entries with optional filters."""
        if self._using_fallback:
            return self._fallback_store.query(layer, task_id, agent_id, entry_type, limit)

        assert self._pool is not None
        conditions = []
        params: list[Any] = []

        if layer is not None:
            conditions.append("layer = $" + str(len(params) + 1))
            params.append(layer.value)
        if task_id is not None:
            conditions.append("task_id = $" + str(len(params) + 1))
            params.append(task_id)
        if agent_id is not None:
            conditions.append("agent_id = $" + str(len(params) + 1))
            params.append(agent_id)
        if entry_type is not None:
            conditions.append("entry_type = $" + str(len(params) + 1))
            params.append(entry_type.value)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM memory_entries WHERE {where} ORDER BY created_at DESC LIMIT ${len(params)}",
                *params,
            )
            return [self._row_to_entry(row) for row in rows]

    # --- Vector search ---

    async def semantic_search(
        self,
        query_embedding: list[float],
        layer: MemoryLayer | None = None,
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> list[tuple[MemoryEntry, float]]:
        """Semantic search using pgvector cosine similarity.

        Args:
            query_embedding: Query embedding vector (1536 dims)
            layer: Optional memory layer filter
            limit: Max results
            min_confidence: Minimum confidence threshold

        Returns:
            List of (entry, similarity_score) tuples sorted by similarity
        """
        if self._using_fallback:
            # Fallback: no vector search, return recent entries
            logger.warning("Semantic search unavailable with SQLite fallback")
            entries = self._fallback_store.query(layer=layer, limit=limit)
            return [(e, 0.0) for e in entries]

        assert self._pool is not None
        conditions = ["mv.embedding IS NOT NULL"]
        params: list[Any] = [f"[{','.join(str(x) for x in query_embedding)}]"]

        if layer is not None:
            conditions.append("me.layer = $" + str(len(params) + 1))
            params.append(layer.value)
        if min_confidence > 0:
            conditions.append("me.confidence >= $" + str(len(params) + 1))
            params.append(min_confidence)

        params.append(limit)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT me.*, 1 - (mv.embedding <=> $1::vector) AS similarity
                FROM memory_entries me
                JOIN memory_vectors mv ON me.key = mv.entry_key
                WHERE {' AND '.join(conditions)}
                ORDER BY similarity DESC
                LIMIT ${len(params)}
                """,
                *params,
            )
            return [(self._row_to_entry(row), float(row["similarity"])) for row in rows]

    async def store_embedding(self, entry_key: str, embedding: list[float], content_text: str) -> None:
        """Store an embedding for a memory entry.

        Args:
            entry_key: Key of the memory entry
            embedding: Embedding vector (1536 dims)
            content_text: Text that was embedded
        """
        if self._using_fallback:
            logger.debug("Skipping embedding store (SQLite fallback)")
            return

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memory_vectors (entry_key, embedding, content_text)
                VALUES ($1, $2::vector, $3)
                ON CONFLICT (entry_key) DO UPDATE
                    SET embedding = EXCLUDED.embedding,
                        content_text = EXCLUDED.content_text
                """,
                entry_key,
                f"[{','.join(str(x) for x in embedding)}]",
                content_text,
            )

    # --- Event capture (Issue #8 Stage 1) ---

    async def store_event(self, event: Any) -> None:
        """Store a raw memory event.

        Args:
            event: MemoryEvent instance
        """
        if self._using_fallback:
            logger.debug("Storing event in fallback (as MemoryEntry)")
            self._fallback_store.put(
                MemoryEntry(
                    key=f"event:{event.id}",
                    layer=MemoryLayer.SESSION,
                    entry_type=MemoryEntryType.REASONING_STEP,
                    value={
                        "event_type": event.event_type.value,
                        "content": event.content,
                        "source": event.source.value,
                        "confidence": event.confidence,
                        "metadata": event.metadata,
                    },
                    agent_id=event.agent_id,
                    metadata={"session_id": event.session_id},
                )
            )
            return

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memory_events
                    (id, session_id, agent_id, timestamp, event_type, source, content, confidence, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                event.id,
                event.session_id,
                event.agent_id,
                event.timestamp,
                event.event_type.value,
                event.source.value,
                event.content,
                event.confidence,
                json.dumps(event.metadata),
            )

    async def store_prediction(self, prediction: dict[str, Any]) -> None:
        """Store a prediction memory.

        Args:
            prediction: Prediction record dict
        """
        if self._using_fallback:
            self._fallback_store.put(
                MemoryEntry(
                    key=f"prediction:{prediction['id']}",
                    layer=MemoryLayer.SESSION,
                    entry_type=MemoryEntryType.BENCHMARK,
                    value=prediction,
                    agent_id=prediction.get("agent_id", ""),
                    metadata={"session_id": prediction.get("session_id", "")},
                )
            )
            return

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO prediction_memories
                    (id, session_id, agent_id, prediction, expected_outcome, confidence,
                     actual_outcome, was_correct, feedback_source, outcome_timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (id) DO UPDATE
                    SET actual_outcome = EXCLUDED.actual_outcome,
                        was_correct = EXCLUDED.was_correct,
                        feedback_source = EXCLUDED.feedback_source,
                        outcome_timestamp = EXCLUDED.outcome_timestamp
                """,
                prediction["id"],
                prediction["session_id"],
                prediction["agent_id"],
                prediction["prediction"],
                prediction["expected_outcome"],
                prediction["confidence"],
                prediction.get("actual_outcome"),
                prediction.get("was_correct"),
                prediction.get("feedback_source", "user"),
                prediction.get("outcome_timestamp"),
            )

    # --- Helpers ---

    def _row_to_entry(self, row: Any) -> MemoryEntry:
        """Convert a DB row to a MemoryEntry."""
        value = row["value"] if isinstance(row["value"], dict) else json.loads(row["value"])
        metadata = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"])
        metadata.setdefault("session_id", row.get("session_id", ""))
        return MemoryEntry(
            key=row["key"],
            layer=MemoryLayer(row["layer"]),
            entry_type=MemoryEntryType(row["entry_type"]),
            value=value,
            agent_id=row["agent_id"],
            task_id=row["task_id"],
            created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
            metadata=metadata,
            confidence=row["confidence"],
        )
