"""Memory and search commands for Think Box CLI."""

from __future__ import annotations

import json
from pathlib import Path

from ..ui.colors import colorize, bold, dim, green, yellow
from ..ui.table import render_table, render_key_value
from ..utils.output import output_json, is_json_mode

from core.indexing.database import init_db, project_hash
from core.indexing.search import SearchEngine
from core.indexing.memory import ProjectMemory, SessionStore


def memory_search(query: str, project: str | None = None, limit: int = 10) -> None:
    """Search across messages and memory."""
    init_db()
    engine = SearchEngine()

    # Search messages
    msg_results = engine.search_messages(query, project=project, limit=limit)

    # Search memory
    mem_results = engine.search_memory(query, project=project, limit=limit)

    if is_json_mode():
        output_json({
            "messages": [{"id": r.id, "session_id": r.session_id, "snippet": r.snippet, "rank": r.rank} for r in msg_results],
            "memory": [{"key": r.key, "value": r.value, "source": r.source} for r in mem_results],
        })
        return

    print(bold(f'\nSearch: "{query}"'))
    print(dim("  " + "─" * 40))

    if msg_results:
        print(f"\n  {bold('Messages')} ({len(msg_results)}):")
        for r in msg_results:
            print(f"    [{r.role}] {r.snippet[:100]}...")

    if mem_results:
        print(f"\n  {bold('Memory')} ({len(mem_results)}):")
        for r in mem_results:
            print(f"    {r.key}: {r.value[:100]}")

    if not msg_results and not mem_results:
        print(dim("  No results found."))


def memory_show(session_id: str) -> None:
    """Show full session transcript."""
    init_db()
    engine = SearchEngine()
    messages = engine.read_session(session_id)

    if is_json_mode():
        output_json(messages)
        return

    if not messages:
        print(f"Session not found: {session_id}")
        return

    print(bold(f"\nSession: {session_id}"))
    print(dim(f"  {len(messages)} messages\n"))

    for msg in messages:
        role_color = green if msg["role"] == "user" else yellow
        print(f"  {role_color(msg['role'].upper())}: {msg['content'][:200]}")
        if msg.get("tool_name"):
            print(f"    [Tool: {msg['tool_name']}]")
        print()


def memory_list(project: str | None = None) -> None:
    """List project memory."""
    init_db()
    if not project:
        project = str(Path.cwd())
    pm = ProjectMemory(project)
    memories = pm.list_all()

    if is_json_mode():
        output_json(memories)
        return

    if not memories:
        print("No memory found for this project.")
        return

    print(bold("\nProject Memory:"))
    for m in memories:
        print(f"  {m['key']}: {m['value'][:100]} ({m['source']})")


def memory_remember(key: str, value: str, project: str | None = None, source: str = "explicit") -> None:
    """Store a memory."""
    init_db()
    if not project:
        project = str(Path.cwd())
    pm = ProjectMemory(project)
    pm.remember(key, value, source=source)
    print(f"Remembered: {key}")


def memory_forget(key: str, project: str | None = None) -> None:
    """Delete a memory."""
    init_db()
    if not project:
        project = str(Path.cwd())
    pm = ProjectMemory(project)
    if pm.forget(key):
        print(f"Forgot: {key}")
    else:
        print(f"Not found: {key}")


def memory_context(project: str | None = None) -> None:
    """Get project startup context."""
    init_db()
    engine = SearchEngine()
    if not project:
        project = str(Path.cwd())
    context = engine.get_project_context(project)

    if is_json_mode():
        output_json(context)
        return

    print(bold("\nProject Context:"))
    print(dim(f"  Hash: {context['project_hash']}"))

    if context["recent_sessions"]:
        print(f"\n  {bold('Recent Sessions:')}")
        for s in context["recent_sessions"]:
            print(f"    {s['title']} ({s['updated_at']})")

    if context["memory"]:
        print(f"\n  {bold('Memory:')}")
        for m in context["memory"]:
            print(f"    {m['key']}: {m['value'][:80]}")
