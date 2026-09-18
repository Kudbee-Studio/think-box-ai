"""ThinkBox CLI — main entrypoint for the ThinkBox AI engine."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from thinkbox.concurrent_goals import (
    ConcurrentGoalsRunner, ConcurrentGoalSpec, ConcurrentGoalsConfig,
    BudgetContentionPolicy, StressTestConfig, StressTestRunner,
)
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


def cmd_stress_test(args: argparse.Namespace) -> None:
    """Run a concurrency stress test."""
    from thinkbox.concurrent_goals import (
        ConcurrentGoalsRunner, StressTestConfig, BudgetContentionPolicy,
    )
    from thinkbox.pop_arena import VerifiedRetryConfig

    async def run():
        # Default goal factory
        from thinkbox.pop_arena import system_prompt_for_v2
        def _sub(family: str, variant: str) -> dict:
            prompt, spec = system_prompt_for_v2(family, variant)
            return {"description": prompt, "family": family, "variant": variant,
                    "spec": spec, "depends_on": []}
        def goal_factory(i: int) -> ConcurrentGoalSpec:
            return ConcurrentGoalSpec(
                goal=f"stress-goal-{i}",
                subtasks=[{"description": _sub("compute", "add_small")["description"],
                          "family": "compute", "variant": "add_small",
                          "spec": _sub("compute", "add_small")["spec"],
                          "depends_on": []}],
                budget_config=VerifiedRetryConfig(max_calls=5, max_retries=1),
                priority=i % 10,
            )

        config = StressTestConfig(
            num_goals=args.num_goals,
            max_calls_global=args.max_calls,
            max_retries_global=args.max_retries,
            contention_policy=BudgetContentionPolicy(args.policy),
            max_duration_seconds=args.duration,
            goal_factory=goal_factory,
        )

        runner = ConcurrentGoalsRunner()
        complete_async = lambda p: asyncio.sleep(0.01) or '{"answer": 42}'
        result = await StressTestRunner(ConcurrentGoalsRunner()).run_stress_test(
            config=config,
            complete_async=complete_async,
        )
        print(f"\nStress Test Results:")
        print(f"  Total Calls: {result.total_calls}")
        print(f"  Total Retries: {result.total_retries}")
        print(f"  Budget Exhausted: {result.total_budget_exhausted}")
        print(f"  Fairness Index: {result.fairness_index}")
        print(f"  Duration: {result.duration_seconds:.3f}s")
        print(f"  Peak Concurrency: {result.peak_concurrency}")
        print(f"  Completed Goals: {result.completed_goals}")
        print(f"  Failed Goals: {result.failed_goals}")
        print(f"  Per-Goal Calls: {result.per_goal_calls}")
        print(f"  Per-Goal Retries: {result.per_goal_retries}")
        if args.output:
            Path(args.output).write_text(json.dumps({
                "total_calls": result.total_calls,
                "total_retries": result.total_retries,
                "total_budget_exhausted": result.total_budget_exhausted,
                "fairness_index": result.fairness_index,
                "duration_seconds": result.duration_seconds,
                "peak_concurrency": result.peak_concurrency,
                "completed_goals": result.completed_goals,
                "failed_goals": result.failed_goals,
                "per_goal_calls": result.per_goal_calls,
                "per_goal_retries": result.per_goal_retries,
            }, indent=2))
            print(f"Results saved to {args.output}")

    asyncio.run(run())
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

    stress_parser = subparsers.add_parser("stress", help="Run concurrency stress test")
    stress_parser.add_argument("--num-goals", type=int, default=10, help="Number of concurrent goals")
    stress_parser.add_argument("--max-calls", type=int, default=50, help="Global max calls budget")
    stress_parser.add_argument("--max-retries", type=int, default=1, help="Global max retries")
    stress_parser.add_argument("--policy", choices=["fair_share", "priority", "fifo"],
                               default="fair_share", help="Budget contention policy")
    stress_parser.add_argument("--duration", type=float, default=60.0, help="Max duration in seconds")
    stress_parser.add_argument("--output", help="Output JSON file for results")

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
    elif args.command == "stress":
        cmd_stress_test(args)
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
