#!/usr/bin/env python3
"""Auto-capture hooks for session indexing.

Automatically captures session digests, decisions, corrections,
and environment notes when a session ends.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.indexing.database import init_db
from core.indexing.memory import SessionStore, ProjectMemory


class AutoCapture:
    """Automatically captures session information for indexing."""

    def __init__(self, project_path: str, db_path: Path | None = None):
        init_db(db_path)
        self.project_path = str(Path(project_path).resolve())
        self.sessions = SessionStore(self.project_path, db_path=db_path)
        self.memory = ProjectMemory(self.project_path, db_path=db_path)

    def capture_session_end(
        self,
        session_id: str,
        title: str,
        messages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Capture a completed session. Returns capture summary."""
        now = datetime.now(timezone.utc).isoformat()

        # Create session record
        self.sessions.create_session(session_id, title, metadata)

        # Store messages
        for msg in messages:
            self.sessions.add_message(
                session_id=session_id,
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                tool_name=msg.get("tool_name"),
                tool_args=msg.get("tool_args"),
            )

        # Extract and save key information
        captured = {
            "session_id": session_id,
            "title": title,
            "message_count": len(messages),
            "decisions": [],
            "corrections": [],
            "environment": [],
        }

        # Simple extraction heuristics
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            # Extract corrections (user telling agent it's wrong)
            if role == "user":
                lower = content.lower()
                if any(w in lower for w in ["no,", "wrong", "don't", "actually", "correction"]):
                    self.memory.save_correction(
                        f"correction_{session_id[:8]}",
                        content[:500],
                    )
                    captured["corrections"].append(content[:100])

                # Extract decisions
                if any(w in lower for w in ["decided", "let's use", "we'll go with", "use "]):
                    self.memory.remember(
                        f"decision_{session_id[:8]}",
                        content[:500],
                        source="auto",
                    )
                    captured["decisions"].append(content[:100])

                # Extract environment notes
                if any(w in lower for w in ["install", "setup", "configure", "run:", "port", "url:"]):
                    self.memory.save_environment(
                        f"env_{session_id[:8]}",
                        content[:500],
                    )
                    captured["environment"].append(content[:100])

        return captured

    def get_session_digest(self, session_id: str) -> str:
        """Generate a short digest of a session."""
        engine = __import__("core.indexing.search", fromlist=["SearchEngine"]).SearchEngine()
        messages = engine.read_session(session_id)

        if not messages:
            return "Empty session."

        # Simple digest: first user message + message count
        first_user = next((m for m in messages if m["role"] == "user"), None)
        summary = f"{len(messages)} messages"
        if first_user:
            summary += f" | Started: {first_user['content'][:80]}"

        return summary
