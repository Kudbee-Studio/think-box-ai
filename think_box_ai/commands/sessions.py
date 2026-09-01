"""Session management commands."""

from __future__ import annotations

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.table import render_table
from ..utils.output import is_json_mode, output_json


def handle_session_command(args) -> None:
    from core.sessions import SessionManager

    mgr = SessionManager()
    sub = args.session_command

    if sub == "list":
        sessions = mgr.list_sessions(limit=args.limit, status_filter=args.status)
        if is_json_mode():
            output_json(sessions)
            return
        if not sessions:
            print(dim("  No sessions found."))
            return
        headers = ["Session ID", "Title", "Status", "Messages", "Tokens"]
        rows = []
        for s in sessions:
            rows.append([
                s["session_id"][:16],
                s["title"][:30],
                s["status"],
                str(s["message_count"]),
                str(s["total_tokens"]),
            ])
        print(bold(f"\n  Sessions ({len(sessions)}):"))
        print(render_table(headers, rows))

    elif sub == "show":
        session = mgr.get_session(args.session_id)
        if is_json_mode():
            output_json(session or {"error": "not found"})
            return
        if not session:
            print(yellow(f"  Session not found: {args.session_id}"))
            return
        print(bold(f"\n  Session: {session['session_id']}"))
        print(dim("  " + "─" * 50))
        print(f"  Title: {session['title']}")
        print(f"  Status: {session['status']}")
        print(f"  Messages: {session['message_count']}")
        print(f"  Total tokens: {session['total_tokens']}")
        if session.get("messages"):
            print(f"\n  {bold('Messages:')}")
            for m in session["messages"][-10:]:
                role_color = green if m["role"] == "user" else cyan
                print(f"    {role_color(m['role']):10} {m['content'][:80]}")

    elif sub == "search":
        results = mgr.search_sessions(args.query, limit=args.limit)
        if is_json_mode():
            output_json(results)
            return
        if not results:
            print(dim("  No sessions found."))
            return
        print(bold(f'\n  Search: "{args.query}"'))
        for s in results:
            print(f"    {cyan(s['session_id'][:16])} {s['title']}")

    elif sub == "create":
        session_id = mgr.create_session(title=args.title or "")
        if is_json_mode():
            output_json({"session_id": session_id})
            return
        print(green(f"  Created session: {session_id}"))

    elif sub == "delete":
        if mgr.delete_session(args.session_id):
            print(green(f"  Deleted: {args.session_id}"))
        else:
            print(yellow(f"  Not found: {args.session_id}"))
    else:
        print("Usage: thinkbox session {list|show|search|create|delete}")
