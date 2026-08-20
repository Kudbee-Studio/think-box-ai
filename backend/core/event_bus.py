"""Event bus for kudbEE — broadcasts events to all connected WebSocket clients."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from backend.core.events import EventType, create_event


class EventBus:
    """Async event bus that broadcasts to all connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: set[Any] = set()
        self._lock = asyncio.Lock()

    async def register(self, ws: Any) -> None:
        """Register a WebSocket client."""
        async with self._lock:
            self._clients.add(ws)

    async def unregister(self, ws: Any) -> None:
        """Unregister a WebSocket client."""
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, event_type: EventType, data: dict[str, Any]) -> None:
        """Broadcast an event to all connected clients."""
        event = create_event(event_type, data)
        dead: list[Any] = []

        async with self._lock:
            for ws in list(self._clients):
                try:
                    await ws.send_json(event)
                except Exception:
                    dead.append(ws)

            for ws in dead:
                self._clients.discard(ws)

    async def broadcast_thought(self, thought: str, status: str = "thinking") -> None:
        """Broadcast a thought event."""
        await self.broadcast(EventType.THOUGHT, {"content": thought, "status": status})

    async def broadcast_token(self, token: str) -> None:
        """Broadcast a streamed token."""
        await self.broadcast(EventType.TOKEN, {"value": token})

    async def broadcast_tool_call(self, tool: str, args: dict[str, Any]) -> None:
        """Broadcast a tool call event."""
        await self.broadcast(EventType.TOOL_CALL, {"tool": tool, "args": args})

    async def broadcast_tool_result(self, tool: str, result: dict[str, Any]) -> None:
        """Broadcast a tool result event."""
        await self.broadcast(EventType.TOOL_RESULT, {"tool": tool, "result": result})

    async def broadcast_file_update(self, path: str, action: str, summary: str = "") -> None:
        """Broadcast a file update event."""
        await self.broadcast(EventType.FILE_UPDATE, {"path": path, "action": action, "summary": summary})

    async def broadcast_task_update(self, task_id: str, status: str, description: str = "") -> None:
        """Broadcast a task update event."""
        await self.broadcast(EventType.TASK_UPDATE, {"task_id": task_id, "status": status, "description": description})

    async def broadcast_memory_update(self, scope: str, key: str, value: Any) -> None:
        """Broadcast a memory update event."""
        await self.broadcast(EventType.MEMORY_UPDATE, {"scope": scope, "key": key, "value": value})

    async def broadcast_risky_action(self, action_id: str, description: str, risk_level: str = "medium") -> None:
        """Broadcast a risky action requiring approval."""
        await self.broadcast(EventType.RISKY_ACTION, {
            "action_id": action_id,
            "description": description,
            "risk_level": risk_level,
        })

    async def broadcast_status(self, status: str) -> None:
        """Broadcast a status change event."""
        await self.broadcast(EventType.STATUS, {"status": status})


# Global event bus instance
event_bus = EventBus()
