"""ThinkBox CLI — main entrypoint for the ThinkBox AI engine."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from thinkbox.engine import ThinkBoxEngine, EngineConfig
from thinkbox.model_client import ModelConfig
from thinkbox.session import (
    create_session,
    get_current_session,
    get_environment,
    get_model_backend,
    get_session_sync,
)
from backend.audit_storage import list_sessions, list_audits


def cmd_run(args: argparse.Namespace) -> None:
    session = create_session()
    sync = get_session_sync()

    config = EngineConfig(
        model_config=ModelConfig(
            model=args.model or "llama3.1:8b",
            temperature=args.temperature or 0.1,
        ),
        speculative=not args.no_speculation,
    )
    engine = ThinkBoxEngine(config)

    print(f"ThinkBox Engine [{engine.engine_id}]")
    print(f"Session: {session.session_id}")
    print(f"Environment: {session.environment}")
    print(f"Model Backend: {session.model_backend}")
    print(f"Upstash Vector: {'connected' if sync.enabled else 'disabled'}")
    print(f"Goal: {args.goal}")
    print("-" * 50)

    async def run():
        result = await engine.execute_goal(args.goal)
        print("\n" + "=" * 50)
        print("Execution Complete")
        for key, value in result.items():
            print(f"  {key}: {value}")

    asyncio.run(run())


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn
    from backend.main import app

    print(f"ThinkBox Server starting on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


def cmd_benchmark(args: argparse.Namespace) -> None:
    config = EngineConfig(
        model_config=ModelConfig(
            model=args.model or "llama3.1:8b",
        ),
        speculative=True,
    )
    engine = ThinkBoxEngine(config)

    print(f"ThinkBox Benchmark [{engine.engine_id}]")
    print("-" * 50)

    async def run():
        goal = "Run a system benchmark: check CPU, memory, and disk usage"
        result = await engine.execute_goal(goal)
        print("\nBenchmark Results:")
        for key, value in result.items():
            print(f"  {key}: {value}")

        stats = engine.get_stats()
        print("\nEngine Stats:")
        print(f"  Events: {stats['events_processed']}")
        print(f"  Workers: {stats['autoscaler']['current_workers']}")

    asyncio.run(run())


def cmd_session_list(args: argparse.Namespace) -> None:
    sessions = list_sessions(limit=args.limit)
    if not sessions:
        print("No sessions found.")
        return

    print(f"{'Session ID':<40} {'Count':<8} {'Started':<25} {'Last Active':<25}")
    print("-" * 100)
    for s in sessions:
        print(f"{s['session_id']:<40} {s['audit_count']:<8} {s['started']:<25} {s['last_active']:<25}")


def cmd_session_inspect(args: argparse.Namespace) -> None:
    audits = list_audits(session_id=args.id, limit=args.limit)
    if not audits:
        print(f"No audit records found for session: {args.id}")
        return

    print(f"Session: {args.id}")
    print(f"Audit Records: {len(audits)}")
    print("-" * 80)
    for a in audits:
        print(f"  {a['timestamp']} | {a['action']:<20} | {a['outcome']:<10} | {a['actor']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="thinkbox", description="ThinkBox AI Engine")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Execute a goal")
    run_parser.add_argument("--goal", required=True, help="Goal string to execute")
    run_parser.add_argument("--model", default="llama3.1:8b", help="Model name")
    run_parser.add_argument("--temperature", type=float, default=0.1, help="Temperature")
    run_parser.add_argument("--no-speculation", action="store_true", help="Disable speculative execution")

    serve_parser = subparsers.add_parser("serve", help="Run the API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port")

    bench_parser = subparsers.add_parser("benchmark", help="Run benchmark")
    bench_parser.add_argument("--model", default="llama3.1:8b", help="Model name")

    session_parser = subparsers.add_parser("session", help="Session management")
    session_subparsers = session_parser.add_subparsers(dest="session_command")

    session_list_parser = session_subparsers.add_parser("list", help="List recent sessions")
    session_list_parser.add_argument("--limit", type=int, default=20, help="Max sessions to show")

    session_inspect_parser = session_subparsers.add_parser("inspect", help="Inspect a session")
    session_inspect_parser.add_argument("--id", required=True, help="Session ID to inspect")
    session_inspect_parser.add_argument("--limit", type=int, default=50, help="Max audit records")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "session":
        if args.session_command == "list":
            cmd_session_list(args)
        elif args.session_command == "inspect":
            cmd_session_inspect(args)
        else:
            session_parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
