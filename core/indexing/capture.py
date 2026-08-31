#!/usr/bin/env python3
"""Auto-capture hooks for session indexing."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.indexing.database import init_db
from core.indexing.memory import SessionStore, ProjectMemory


class AutoCapture:
    def __init__(self, project_path: str, db_path: Path | None = None):
        init_db(db_path)
        self.project_path = str(Path(project_path).resolve())
        self.sessions = SessionStore(self.project_path, db_path=db_path)
        self.memory = ProjectMemory(self.project_path, db_path=db_path)

    def capture_session_end(self, session_id: str, title: str, messages: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.sessions.create_session(session_id, title, metadata)
        for msg in messages:
            self.sessions.add_message(
                session_id=session_id,
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                tool_name=msg.get("tool_name"),
                tool_args=msg.get("tool_args"),
            )

        captured = {"session_id": session_id, "title": title, "message_count": len(messages), "decisions": [], "corrections": [], "environment": []}

        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")
            if role == "user":
                lower = content.lower()
                if any(w in lower for w in ["no,", "wrong,", "don't", "actually", "correction"]):
                    self.memory.save_correction(f"correction_{session_id[:8]}", content[:500])
                    captured["corrections"].append(content[:100])
                if any(w in lower for w in ["decided", "let's use", "we'll go with", "use "]):
                    self.memory.remember(f"decision_{session_id[:8]}", content[:500], source="auto")
                    captured["decisions"].append(content[:100])
                if any(w in lower for w in ["install", "setup", "configure", "run:", "port", "url:"]):
                    self.memory.save_environment(f"env_{session_id[:8]}", content[:500])
                    captured["environment"].append(content[:100])
        return captured

    def get_session_digest(self, session_id: str) -> str:
        from core.indexing.search import SearchEngine
        engine = SearchEngine()
        messages = engine.read_session(session_id)
        if not messages:
            return "Empty session."
        first_user = next((m for m in messages if m["role"] == "user"), None)
        summary = f"{len(messages)} messages"
        if first_user:
            summary += f" | Started: {first_user['content'][:80]}"
        return summary
