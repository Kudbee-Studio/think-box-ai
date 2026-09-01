"""Memory commands handler."""

from __future__ import annotations

from ..utils.output import is_json_mode, output_json

from core.indexing.database import init_db
from core.indexing.search import SearchEngine
from core.indexing.memory import ProjectMemory


def handle_memory_command(args) -> None:
    sub = args.memory_command

    if sub == "remember":
        _memory_remember(args)
    elif sub == "recall":
        _memory_recall(args)
    elif sub == "search":
        _memory_search(args)
    elif sub == "context":
        _memory_context(args)
    elif sub == "list":
        _memory_list(args)
    elif sub == "forget":
        _memory_forget(args)
    else:
        print("Usage: thinkbox memory {remember|recall|search|context|list|forget}")


def _memory_remember(args) -> None:
    init_db()
    from pathlib import Path
    project = str(Path.cwd())
    pm = ProjectMemory(project)
    pm.remember(args.key, args.value, source="explicit")

    if is_json_mode():
        output_json({"status": "remembered", "key": args.key})
        return

    from ..ui.colors import green
    print(green(f"  Remembered: {args.key}"))


def _memory_recall(args) -> None:
    init_db()
    from pathlib import Path
    project = str(Path.cwd())
    pm = ProjectMemory(project)
    result = pm.get(args.key)

    if is_json_mode():
        output_json({"key": args.key, "value": result})
        return

    from ..ui.colors import bold, dim
    if result:
        print(bold(f"\n  {args.key}:"))
        print(f"  {result}")
    else:
        print(dim(f"  Not found: {args.key}"))


def _memory_search(args) -> None:
    init_db()
    engine = SearchEngine()
    results = engine.search_memory(args.query, limit=args.limit)

    if is_json_mode():
        output_json([{"key": r.key, "value": r.value, "source": r.source} for r in results])
        return

    from ..ui.colors import bold, dim
    print(bold(f'\n  Search: "{args.query}"'))
    if results:
        for r in results:
            print(f"    {r.key}: {r.value[:100]}")
    else:
        print(dim("  No results found."))


def _memory_context(args) -> None:
    init_db()
    engine = SearchEngine()
    from pathlib import Path
    project = str(Path.cwd())
    context = engine.get_project_context(project)

    if is_json_mode():
        output_json(context)
        return

    from ..ui.colors import bold, dim
    print(bold("\n  Project Context:"))
    print(dim(f"    Hash: {context['project_hash']}"))
    if context.get("recent_sessions"):
        print(f"\n  {bold('Recent Sessions:')}")
        for s in context["recent_sessions"][:args.limit]:
            print(f"    {s['title']} ({s['updated_at']})")


def _memory_list(args) -> None:
    init_db()
    from pathlib import Path
    project = str(Path.cwd())
    pm = ProjectMemory(project)
    memories = pm.list_all()

    if args.category:
        memories = [m for m in memories if m.get("category") == args.category]

    if is_json_mode():
        output_json(memories)
        return

    from ..ui.colors import bold, dim
    if not memories:
        print(dim("  No memories found."))
        return

    print(bold(f"\n  Memories ({len(memories)}):"))
    for m in memories:
        print(f"    {m['key']}: {m['value'][:80]} ({m.get('source', 'unknown')})")


def _memory_forget(args) -> None:
    init_db()
    from pathlib import Path
    project = str(Path.cwd())
    pm = ProjectMemory(project)
    result = pm.forget(args.key)

    if is_json_mode():
        output_json({"status": "forgotten" if result else "not_found", "key": args.key})
        return

    from ..ui.colors import green, yellow
    if result:
        print(green(f"  Forgot: {args.key}"))
    else:
        print(yellow(f"  Not found: {args.key}"))
