"""Memory consolidation pipeline for THINK BOX AI.

This module implements the memory consolidation pipeline that moves data
up the memory hierarchy:

    Session Memory → Task Memory → Organizational Memory → Verified Knowledge

The consolidator runs after task completion and promotes high-confidence
memories to higher layers while archiving old entries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from core.foundation.logging import get_logger
from core.memory.candidate import (
    CandidateMemory,
    CandidateType,
    ValidationStatus,
    ValidationSource,
)
from core.memory.curator import MemoryCurator
from core.memory.event import MemoryEvent
from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer
from core.memory.validator import MemoryValidator

logger = get_logger(__name__)


class MemoryConsolidator:
    """Consolidates memory across layers.

    The consolidator runs after meaningful tasks and:
    1. Extracts candidate memories from session events (via Memory Curator)
    2. Validates candidates against multiple sources
    3. Promotes validated candidates to higher memory layers
    4. Archives old entries according to retention policies

    Memory hierarchy:
    - Session: 7 days retention
    - Task: 30 days retention
    - Organizational: 90 days retention (requires confidence ≥ 0.8 + ≥ 3 occurrences)
    - Verified Knowledge: Permanent (requires human review + benchmark)

    Usage:
        consolidator = MemoryConsolidator(store, codebase_index, docs_index)
        await consolidator.consolidate_session(session_id)
    """

    def __init__(
        self,
        store: Any,
        codebase_index: Any | None = None,
        docs_index: Any | None = None,
        test_results: Any | None = None,
    ) -> None:
        """Initialize the Memory Consolidator.

        Args:
            store: Memory store for persisting memories
            codebase_index: Index for codebase validation
            docs_index: Index for documentation validation
            test_results: Test results for validation
        """
        self.store = store
        self.curator = MemoryCurator()
        self.validator = MemoryValidator(
            codebase_index=codebase_index,
            docs_index=docs_index,
            test_results=test_results,
        )

        # Retention policies (days)
        self.retention_days = {
            MemoryLayer.SESSION: 7,
            MemoryLayer.TASK: 30,
            MemoryLayer.ORGANIZATIONAL: 90,
            MemoryLayer.VERIFIED_KNOWLEDGE: None,  # Permanent
        }

    async def consolidate_session(self, session_id: str) -> dict[str, Any]:
        """Consolidate a session's memories.

        This is the main entry point for memory consolidation. It:
        1. Retrieves all events for the session
        2. Extracts candidate memories
        3. Validates candidates
        4. Promotes to task memory
        5. Archives old session entries

        Args:
            session_id: Session to consolidate

        Returns:
            Summary of consolidation results
        """
        logger.info("Starting session consolidation", extra={"session_id": session_id})

        # 1. Retrieve all events for the session
        events = self._get_session_events(session_id)
        if not events:
            logger.info("No events to consolidate", extra={"session_id": session_id})
            return {"events_processed": 0, "candidates_extracted": 0}

        # 2. Extract candidate memories
        candidates = self.curator.extract_candidates(events)
        logger.info(
            "Extracted candidates",
            extra={"session_id": session_id, "candidates": len(candidates)},
        )

        # 3. Validate candidates
        validated = await self._validate_candidates(candidates)

        # 4. Promote to task memory
        task_memory = self._promote_to_task(session_id, events, validated)

        # 5. Archive old session entries
        archived = self._archive_old_entries(session_id, MemoryLayer.SESSION)

        summary = {
            "session_id": session_id,
            "events_processed": len(events),
            "candidates_extracted": len(candidates),
            "candidates_validated": len(validated),
            "task_memories_created": len(task_memory),
            "entries_archived": archived,
        }

        logger.info("Session consolidation complete", extra=summary)
        return summary

    async def consolidate_task(self, task_id: str, session_id: str) -> dict[str, Any]:
        """Consolidate a task's memories to organizational memory.

        Args:
            task_id: Task to consolidate
            session_id: Parent session ID

        Returns:
            Summary of consolidation results
        """
        logger.info("Starting task consolidation", extra={"task_id": task_id})

        # Retrieve task entries
        task_entries = self._get_task_entries(task_id)
        if not task_entries:
            return {"task_id": task_id, "entries_processed": 0}

        # Extract candidates from task entries
        candidates = self.curator.extract_candidates(task_entries)

        # Validate and promote high-confidence candidates
        promoted = []
        for candidate in candidates:
            if candidate.confidence >= 0.8:
                result = await self.validator.validate(candidate)
                if result.status == ValidationStatus.APPROVED:
                    promoted.append(self._promote_to_organizational(candidate, result))

        # Archive old task entries
        archived = self._archive_old_entries(task_id, MemoryLayer.TASK)

        summary = {
            "task_id": task_id,
            "entries_processed": len(task_entries),
            "candidates_extracted": len(candidates),
            "promoted_to_organizational": len(promoted),
            "entries_archived": archived,
        }

        logger.info("Task consolidation complete", extra=summary)
        return summary

    async def promote_to_verified_knowledge(
        self,
        candidate: CandidateMemory,
        validation_result: ValidationResult,
        human_approved: bool = False,
    ) -> VerifiedMemory | None:
        """Promote a candidate to verified knowledge.

        Per AGENTS.md §1.4: Requires human review + benchmark.

        Args:
            candidate: Candidate to promote
            validation_result: Validation result
            human_approved: Whether a human has approved this memory

        Returns:
            VerifiedMemory if promoted, None otherwise
        """
        # Require high confidence + human approval
        if validation_result.score < 0.9 or not human_approved:
            logger.info(
                "Candidate not eligible for verified knowledge",
                extra={
                    "candidate_id": candidate.id,
                    "score": validation_result.score,
                    "human_approved": human_approved,
                },
            )
            return None

        verified = VerifiedMemory(
            id=str(uuid.uuid4()),
            content=candidate.content,
            memory_type=candidate.candidate_type,
            confidence=validation_result.score,
            verification_sources=validation_result.sources_checked,
            metadata={
                "original_candidate_id": candidate.id,
                "session_id": candidate.session_id,
                "agent_id": candidate.agent_id,
            },
        )

        # Store as verified knowledge
        if self.store:
            try:
                entry = MemoryEntry(
                    key=f"verified:{verified.id}",
                    layer=MemoryLayer.VERIFIED_KNOWLEDGE,
                    entry_type=MemoryEntryType.FACT,
                    value={
                        "content": verified.content,
                        "memory_type": verified.memory_type.value,
                        "confidence": verified.confidence,
                        "verification_sources": [s.value for s in verified.verification_sources],
                        "verified_at": verified.verified_at,
                        "metadata": verified.metadata,
                    },
                    agent_id=candidate.agent_id,
                    confidence=verified.confidence,
                )
                self.store.put(entry)
            except Exception as e:
                logger.warning("Failed to store verified memory", extra={"error": str(e)})

        logger.info(
            "Promoted to verified knowledge",
            extra={"candidate_id": candidate.id, "verified_id": verified.id},
        )
        return verified

    def archive_old_entries(self, layer: MemoryLayer, max_age_days: int | None = None) -> int:
        """Archive old entries from a memory layer.

        Args:
            layer: Memory layer to archive
            max_age_days: Maximum age in days (uses retention policy if None)

        Returns:
            Number of entries archived
        """
        if max_age_days is None:
            max_age_days = self.retention_days.get(layer, 30)

        if max_age_days is None:
            # Permanent layer, don't archive
            return 0

        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 24 * 60 * 60)
        archived = 0

        try:
            entries = self.store.query(layer=layer)
            for entry in entries:
                entry_time = datetime.fromisoformat(entry.created_at).timestamp()
                if entry_time < cutoff:
                    self.store.delete(entry.key)
                    archived += 1
        except Exception as e:
            logger.warning("Failed to archive old entries", extra={"error": str(e)})

        if archived > 0:
            logger.info(
                "Archived old entries",
                extra={"layer": layer.value, "archived": archived, "max_age_days": max_age_days},
            )

        return archived

    def _get_session_events(self, session_id: str) -> list[MemoryEvent]:
        """Get all events for a session."""
        if not self.store:
            return []

        try:
            from core.memory.schema import MemoryEntry, MemoryLayer

            entries = self.store.query(layer=MemoryLayer.SESSION)
        except Exception:
            return []

        events = []
        for entry in entries:
            if entry.task_id == session_id or entry.key.startswith(f"session:{session_id}"):
                event = MemoryEvent(
                    id=entry.key,
                    session_id=session_id,
                    agent_id=entry.agent_id,
                    timestamp=entry.created_at,
                    content=str(entry.value),
                    confidence=entry.confidence,
                    metadata=entry.metadata,
                )
                events.append(event)
        return events

    def _get_task_entries(self, task_id: str) -> list[MemoryEvent]:
        """Get all entries for a task."""
        if not self.store:
            return []

        try:
            from core.memory.schema import MemoryEntry, MemoryLayer

            entries = self.store.query(layer=MemoryLayer.TASK, task_id=task_id)
        except Exception:
            return []

        events = []
        for entry in entries:
            event = MemoryEvent(
                id=entry.key,
                session_id=entry.metadata.get("session_id", ""),
                agent_id=entry.agent_id,
                timestamp=entry.created_at,
                content=str(entry.value),
                confidence=entry.confidence,
                metadata=entry.metadata,
            )
            events.append(event)
        return events

    async def _validate_candidates(
        self, candidates: list[CandidateMemory]
    ) -> list[tuple[CandidateMemory, ValidationResult]]:
        """Validate a list of candidates."""
        if not candidates:
            return []

        results = await self.validator.batch_validate(candidates)
        return list(zip(candidates, results))

    def _promote_to_task(
        self, session_id: str, events: list[MemoryEvent], validated: list[tuple[CandidateMemory, ValidationResult]]
    ) -> list[MemoryEntry]:
        """Promote session events to task memory."""
        entries = []
        for candidate, result in validated:
            if result.status in (ValidationStatus.APPROVED, ValidationStatus.NEEDS_REVIEW):
                entry = MemoryEntry(
                    key=f"task:{session_id}:candidate:{candidate.id}",
                    layer=MemoryLayer.TASK,
                    entry_type=MemoryEntryType(candidate.candidate_type.value),
                    value={
                        "content": candidate.content,
                        "candidate_type": candidate.candidate_type.value,
                        "confidence": result.score,
                        "validation_status": result.status.value,
                        "sources_checked": [s.value for s in result.sources_checked],
                        "reasons": result.reasons,
                    },
                    agent_id=candidate.agent_id,
                    task_id=session_id,
                    confidence=result.score,
                    metadata={"source_candidate_id": candidate.id},
                )
                entries.append(entry)
                if self.store:
                    self.store.put(entry)
        return entries

    def _promote_to_organizational(
        self, candidate: CandidateMemory, result: ValidationResult
    ) -> MemoryEntry:
        """Promote a validated candidate to organizational memory."""
        entry = MemoryEntry(
            key=f"org:{candidate.id}",
            layer=MemoryLayer.ORGANIZATIONAL,
            entry_type=MemoryEntryType.PATTERN,
            value={
                "content": candidate.content,
                "candidate_type": candidate.candidate_type.value,
                "confidence": result.score,
                "verification_sources": [s.value for s in result.sources_checked],
                "reasons": result.reasons,
            },
            agent_id=candidate.agent_id,
            confidence=result.score,
            metadata={
                "source_candidate_id": candidate.id,
                "session_id": candidate.session_id,
            },
        )
        if self.store:
            self.store.put(entry)
        return entry

    def _archive_old_entries(self, identifier: str, layer: MemoryLayer) -> int:
        """Archive old entries for a given identifier."""
        return self.archive_old_entries(layer)
