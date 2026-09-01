"""Think Box CLI v5 — Full-featured command-line interface."""

from __future__ import annotations

import argparse
import sys

from think_box_ai import __version__

from .commands.serve import serve


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thinkbox",
        description="Think Box AI — Agent Execution Environment",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="JSON output")
    output.add_argument("--plain", action="store_true", help="Plain text output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-essential output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without executing")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    subparsers = parser.add_subparsers(dest="command")

    # ==========================================
    # 1. JOB COMMANDS
    # ==========================================
    job_p = subparsers.add_parser("job", help="Job management")
    job_sub = job_p.add_subparsers(dest="job_command")

    job_list = job_sub.add_parser("list", help="List all jobs")
    job_list.add_argument("-s", "--state", choices=["queue", "active", "done", "blocked"])
    job_list.add_argument("--limit", type=int, default=50)

    job_show = job_sub.add_parser("show", help="Show job details")
    job_show.add_argument("job_id")

    job_create = job_sub.add_parser("create", help="Create a job")
    job_create.add_argument("--intent", required=True)
    job_create.add_argument("--hat", default="researcher", choices=["researcher", "runner", "director", "camera", "jury"])
    job_create.add_argument("--file", help="JSON file with job data")

    job_submit = job_sub.add_parser("submit", help="Submit from template")
    job_submit.add_argument("template")
    job_submit.add_argument("args", nargs="*")

    job_run = job_sub.add_parser("run", help="Run queue worker")
    job_run.add_argument("--dry-run", action="store_true")

    job_cancel = job_sub.add_parser("cancel", help="Cancel a queued job")
    job_cancel.add_argument("job_id")

    job_retry = job_sub.add_parser("retry", help="Retry a blocked/failed job")
    job_retry.add_argument("job_id")

    job_diff = job_sub.add_parser("diff", help="Compare two jobs")
    job_diff.add_argument("id1")
    job_diff.add_argument("id2")

    # ==========================================
    # 2. MEMORY COMMANDS
    # ==========================================
    mem_p = subparsers.add_parser("memory", help="Project memory")
    mem_sub = mem_p.add_subparsers(dest="memory_command")

    mem_remember = mem_sub.add_parser("remember", help="Store a memory")
    mem_remember.add_argument("key")
    mem_remember.add_argument("value")
    mem_remember.add_argument("--category", default="fact", choices=["command", "preference", "fact", "result", "context"])
    mem_remember.add_argument("--importance", type=float, default=1.0)

    mem_recall = mem_sub.add_parser("recall", help="Recall a memory")
    mem_recall.add_argument("key")

    mem_search = mem_sub.add_parser("search", help="Search memories")
    mem_search.add_argument("query")
    mem_search.add_argument("--category", choices=["command", "preference", "fact", "result", "context"])
    mem_search.add_argument("--limit", type=int, default=10)

    mem_context = mem_sub.add_parser("context", help="Get current context")
    mem_context.add_argument("--limit", type=int, default=20)

    mem_list = mem_sub.add_parser("list", help="List all memories")
    mem_list.add_argument("--category", choices=["command", "preference", "fact", "result", "context"])

    mem_forget = mem_sub.add_parser("forget", help="Delete a memory")
    mem_forget.add_argument("key")

    # ==========================================
    # 3. CONFIG COMMANDS
    # ==========================================
    config_p = subparsers.add_parser("config", help="Configuration")
    config_sub = config_p.add_subparsers(dest="config_command")

    config_sub.add_parser("show", help="Show config")

    config_set = config_sub.add_parser("set", help="Set config value")
    config_set.add_argument("key")
    config_set.add_argument("value")

    config_profile = config_sub.add_parser("profile", help="Load profile")
    config_profile.add_argument("name")

    # ==========================================
    # 4. FINDINGS COMMANDS
    # ==========================================
    findings_p = subparsers.add_parser("findings", help="Findings browser")
    findings_sub = findings_p.add_subparsers(dest="findings_command")

    findings_sub.add_parser("list", help="List findings")

    findings_show = findings_sub.add_parser("show", help="Show finding details")
    findings_show.add_argument("name")

    findings_preview = findings_sub.add_parser("preview", help="Preview finding")
    findings_preview.add_argument("name")

    # ==========================================
    # 5. QUEUE COMMANDS
    # ==========================================
    queue_p = subparsers.add_parser("queue", help="GPU job queue")
    queue_sub = queue_p.add_subparsers(dest="queue_command")

    queue_sub.add_parser("status", help="Queue status")

    queue_add = queue_sub.add_parser("add", help="Add job to GPU queue")
    queue_add.add_argument("--intent", required=True)
    queue_add.add_argument("--priority", default="normal", choices=["urgent", "normal", "low"])

    queue_batch = queue_sub.add_parser("batch", help="Batch submit jobs")
    queue_batch.add_argument("--file", required=True, help="JSON file with jobs")

    queue_sub.add_parser("drain", help="Drain queue (when GPU starts)")

    # ==========================================
    # 6. SPAWN COMMANDS
    # ==========================================
    spawn_p = subparsers.add_parser("spawn", help="Spawn sub-agents")
    spawn_sub = spawn_p.add_subparsers(dest="spawn_command")

    spawn_researcher = spawn_sub.add_parser("researcher", help="Spawn researcher agent")
    spawn_researcher.add_argument("goal")
    spawn_researcher.add_argument("--wait", action="store_true")

    spawn_runner = spawn_sub.add_parser("runner", help="Spawn runner agent")
    spawn_runner.add_argument("goal")

    # ==========================================
    # 7. DOCTOR COMMAND
    # ==========================================
    subparsers.add_parser("doctor", help="System diagnostics")

    # ==========================================
    # 8. INIT COMMAND
    # ==========================================
    subparsers.add_parser("init", help="Initialize project")

    # ==========================================
    # 9. SERVE COMMAND
    # ==========================================
    serve_p = subparsers.add_parser("serve", help="Start backend server")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.add_argument("--reload", action="store_true")

    # ==========================================
    # 10. WATCH COMMAND
    # ==========================================
    watch_p = subparsers.add_parser("watch", help="Watch files and auto-reload")
    watch_p.add_argument("--path", default=".")
    watch_p.add_argument("--pattern", default="*.py")

    # ==========================================
    # 11. SEARCH COMMAND
    # ==========================================
    search_p = subparsers.add_parser("search", help="Full-text search")
    search_p.add_argument("query")
    search_p.add_argument("--type", choices=["jobs", "findings", "memory", "all"], default="all")
    search_p.add_argument("--limit", type=int, default=20)

    # ==========================================
    # 12. EXPORT COMMAND
    # ==========================================
    export_p = subparsers.add_parser("export", help="Export data")
    export_p.add_argument("what", choices=["jobs", "findings", "memory", "all"])
    export_p.add_argument("--format", choices=["json", "csv", "md"], default="json")
    export_p.add_argument("--output", "-o", help="Output file path")

    # ==========================================
    # 13. IMPORT COMMAND
    # ==========================================
    import_p = subparsers.add_parser("import", help="Import data")
    import_p.add_argument("file", help="File to import")
    import_p.add_argument("--type", choices=["jobs", "findings", "memory"], required=True)

    # ==========================================
    # 14. LOGS COMMAND
    # ==========================================
    logs_p = subparsers.add_parser("logs", help="View agent logs")
    logs_p.add_argument("--job", help="Filter by job ID")
    logs_p.add_argument("--tail", type=int, default=50)
    logs_p.add_argument("--follow", "-f", action="store_true")

    # ==========================================
    # 15. HISTORY COMMAND
    # ==========================================
    history_p = subparsers.add_parser("history", help="Command history")
    history_p.add_argument("--clear", action="store_true")
    history_p.add_argument("--limit", type=int, default=50)

    # ==========================================
    # 16. COMPLETION COMMAND
    # ==========================================
    completion_p = subparsers.add_parser("completion", help="Generate shell completion")
    completion_p.add_argument("shell", choices=["bash", "zsh", "fish"])

    # ==========================================
    # 17. STATUS COMMAND
    # ==========================================
    subparsers.add_parser("status", help="System status dashboard")

    # ==========================================
    # 18. REPL COMMAND
    # ==========================================
    subparsers.add_parser("repl", help="Interactive REPL mode")

    # ==========================================
    # 19. CURSOR COMMAND
    # ==========================================
    cursor_p = subparsers.add_parser("cursor", help="Cursor SDK integration")
    cursor_sub = cursor_p.add_subparsers(dest="cursor_command")

    cursor_run = cursor_sub.add_parser("run", help="Run Cursor agent")
    cursor_run.add_argument("prompt")
    cursor_run.add_argument("--runtime", default="local", choices=["local", "cloud"])
    cursor_run.add_argument("--model", default="composer-2.5")
    cursor_run.add_argument("--repo", help="Git repo URL (cloud mode)")

    cursor_list = cursor_sub.add_parser("list", help="List Cursor agents")
    cursor_list.add_argument("--runtime", default="local", choices=["local", "cloud", "all"])

    cursor_logs = cursor_sub.add_parser("logs", help="Get agent logs")
    cursor_logs.add_argument("agent_id")

    # ==========================================
    # 20. INCEPTION COMMAND
    # ==========================================
    inception_p = subparsers.add_parser("inception", help="Inception API (Mercury 2)")
    inception_sub = inception_p.add_subparsers(dest="inception_command")

    inception_run = inception_sub.add_parser("run", help="Run Mercury 2 prompt")
    inception_run.add_argument("prompt")
    inception_run.add_argument("--model", default="mercury-2")

    inception_sub.add_parser("models", help="List available models")
    inception_sub.add_parser("usage", help="Show usage stats")

    return parser


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    dispatch_command(args)


def dispatch_command(args: argparse.Namespace) -> None:
    cmd = args.command

    if cmd == "job":
        _handle_job(args)
    elif cmd == "memory":
        _handle_memory(args)
    elif cmd == "config":
        _handle_config(args)
    elif cmd == "findings":
        _handle_findings(args)
    elif cmd == "queue":
        _handle_queue(args)
    elif cmd == "spawn":
        _handle_spawn(args)
    elif cmd == "doctor":
        _handle_doctor(args)
    elif cmd == "init":
        _handle_init(args)
    elif cmd == "serve":
        serve(args.host, args.port)
    elif cmd == "watch":
        _handle_watch(args)
    elif cmd == "search":
        _handle_search(args)
    elif cmd == "export":
        _handle_export(args)
    elif cmd == "import":
        _handle_import(args)
    elif cmd == "logs":
        _handle_logs(args)
    elif cmd == "history":
        _handle_history(args)
    elif cmd == "completion":
        _handle_completion(args)
    elif cmd == "status":
        _handle_status(args)
    elif cmd == "repl":
        _handle_repl(args)
    elif cmd == "cursor":
        _handle_cursor(args)
    elif cmd == "inception":
        _handle_inception(args)
    else:
        print(f"Unknown command: {cmd}")


def _handle_job(args: argparse.Namespace) -> None:
    from .commands.jobs import handle_job_command

    handle_job_command(args)


def _handle_memory(args: argparse.Namespace) -> None:
    from .commands.memory import handle_memory_command

    handle_memory_command(args)


def _handle_config(args: argparse.Namespace) -> None:
    from .commands.config import handle_config_command

    handle_config_command(args)


def _handle_findings(args: argparse.Namespace) -> None:
    from .commands.findings import handle_findings_command

    handle_findings_command(args)


def _handle_queue(args: argparse.Namespace) -> None:
    from .commands.queue import handle_queue_command

    handle_queue_command(args)


def _handle_spawn(args: argparse.Namespace) -> None:
    from .commands.spawn import handle_spawn_command

    handle_spawn_command(args)


def _handle_doctor(args: argparse.Namespace) -> None:
    from .commands.doctor import handle_doctor

    handle_doctor(args)


def _handle_init(args: argparse.Namespace) -> None:
    from .commands.init import handle_init

    handle_init(args)


def _handle_watch(args: argparse.Namespace) -> None:
    from .commands.watch import handle_watch

    handle_watch(args)


def _handle_search(args: argparse.Namespace) -> None:
    from .commands.search import handle_search

    handle_search(args)


def _handle_export(args: argparse.Namespace) -> None:
    from .commands.export import handle_export

    handle_export(args)


def _handle_import(args: argparse.Namespace) -> None:
    from .commands.import_data import handle_import

    handle_import(args)


def _handle_logs(args: argparse.Namespace) -> None:
    from .commands.logs import handle_logs

    handle_logs(args)


def _handle_history(args: argparse.Namespace) -> None:
    from .commands.history import handle_history

    handle_history(args)


def _handle_completion(args: argparse.Namespace) -> None:
    from .commands.completion import handle_completion

    handle_completion(args)


def _handle_status(args: argparse.Namespace) -> None:
    from .commands.status import handle_status

    handle_status(args)


def _handle_repl(args: argparse.Namespace) -> None:
    from .commands.repl import handle_repl

    handle_repl(args)


def _handle_cursor(args: argparse.Namespace) -> None:
    from .commands.cursor import handle_cursor_command

    handle_cursor_command(args)


def _handle_inception(args: argparse.Namespace) -> None:
    from .commands.inception import handle_inception_command

    handle_inception_command(args)


if __name__ == "__main__":
    main()
