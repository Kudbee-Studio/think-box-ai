"""ThinkBox CLI — main entrypoint for the ThinkBox AI engine."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from thinkbox.concurrent_goals import (
    BudgetContentionPolicy,
    ConcurrentGoalSpec,
    ConcurrentGoalsRunner,
    StressTestConfig,
    StressTestRunner,
)
from thinkbox.engine import EngineConfig, ThinkBoxEngine
from thinkbox.model_client import ModelConfig
from thinkbox.session import create_session, get_session_sync

from backend.audit_storage import list_audits, list_sessions
from thinkbox.cli_inspect import (
    CLI_EXIT_FAIL,
    CLI_EXIT_OK,
    CLI_EXIT_USAGE,
    default_proof_dir,
    discover_proof_files,
    format_human,
    ledger_verify_report,
    proof_check_report,
    redacted_environment_snapshot,
    resolve_ledger_path,
    swarm_agents_rollup,
    swarm_status_summary,
)

__version__ = "0.128.0"


def _emit(payload: dict, args: argparse.Namespace, title: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(format_human(payload, title))


def cmd_run(args: argparse.Namespace) -> int:
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
    return CLI_EXIT_OK


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn
    from backend.main import app

    print(f"ThinkBox Server starting on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
    return CLI_EXIT_OK


def cmd_benchmark(args: argparse.Namespace) -> int:
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
    return CLI_EXIT_OK


def cmd_stress_test(args: argparse.Namespace) -> int:
    """Run a concurrency stress test."""
    from thinkbox.pop_arena import VerifiedRetryConfig, system_prompt_for_v2

    async def run():
        def _sub(family: str, variant: str) -> dict:
            prompt, spec = system_prompt_for_v2(family, variant)
            return {
                "description": prompt,
                "family": family,
                "variant": variant,
                "spec": spec,
                "depends_on": [],
            }

        def goal_factory(i: int) -> ConcurrentGoalSpec:
            st = _sub("compute", "add_small")
            return ConcurrentGoalSpec(
                goal=f"stress-goal-{i}",
                subtasks=[
                    {
                        "description": st["description"],
                        "family": "compute",
                        "variant": "add_small",
                        "spec": st["spec"],
                        "depends_on": [],
                    }
                ],
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

        complete_async = lambda p: asyncio.sleep(0.01) or '{"answer": 42}'
        result = await StressTestRunner(ConcurrentGoalsRunner()).run_stress_test(
            config=config,
            complete_async=complete_async,
        )
        print("\nStress Test Results:")
        print(f"  Total Calls: {result.total_calls}")
        print(f"  Total Retries: {result.total_retries}")
        print(f"  Budget Exhausted: {result.total_budget_exhausted}")
        print(f"  Fairness Index: {result.fairness_index}")
        print(f"  Duration: {result.duration_seconds:.3f}s")
        print(f"  Peak Concurrency: {result.peak_concurrency}")
        print(f"  Completed Goals: {result.completed_goals}")
        print(f"  Failed Goals: {result.failed_goals}")
        if args.output:
            Path(args.output).write_text(
                json.dumps(
                    {
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
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"Results saved to {args.output}")

    asyncio.run(run())
    return CLI_EXIT_OK


def cmd_session_list(args: argparse.Namespace) -> int:
    sessions = list_sessions(limit=args.limit)
    if args.min_audits > 0:
        sessions = [s for s in sessions if s["audit_count"] >= args.min_audits]
    payload = {"sessions": sessions, "count": len(sessions)}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if not sessions:
            print("No sessions found in audit log.")
        else:
            print(f"Sessions ({len(sessions)}):")
            for s in sessions:
                print(
                    f"  {s['session_id']}  audits={s['audit_count']}  "
                    f"started={s['started']}  last={s['last_active']}"
                )
    return CLI_EXIT_OK


def cmd_session_inspect(args: argparse.Namespace) -> int:
    audits = list_audits(session_id=args.id, limit=args.limit)
    if not audits:
        print(f"No audit records found for session: {args.id}")
        return CLI_EXIT_FAIL
    if args.json:
        print(json.dumps({"session_id": args.id, "audits": audits}, indent=2))
        return CLI_EXIT_OK
    print(f"Session: {args.id}")
    print(f"Audit Records: {len(audits)}")
    print("-" * 80)
    for a in audits:
        print(f"  {a['timestamp']} | {a['action']:<20} | {a['outcome']:<10} | {a['actor']}")
    return CLI_EXIT_OK


def cmd_env_status(args: argparse.Namespace) -> int:
    payload = redacted_environment_snapshot()
    _emit(payload, args, "Environment status (redacted)")
    return CLI_EXIT_OK


def cmd_ledger_verify(args: argparse.Namespace) -> int:
    path = resolve_ledger_path(args.path)
    if path is None:
        payload = {
            "valid": False,
            "errors": ["ledger database not found — set THINKBOX_LEDGER_PATH or create data/thinkboxmd/db/action_ledger.db"],
        }
        _emit(payload, args, "Ledger verify")
        return CLI_EXIT_FAIL
    report = ledger_verify_report(path, verbose=args.verbose)
    _emit(report, args, "Ledger verify")
    return CLI_EXIT_OK if report["valid"] else CLI_EXIT_FAIL


def cmd_proof_check(args: argparse.Namespace) -> int:
    path = Path(args.path)
    report = proof_check_report(path, metrics_only=args.metrics_only)
    _emit(report, args, "Proof check")
    return CLI_EXIT_OK if report.get("valid") else CLI_EXIT_FAIL


def cmd_swarm_agents(args: argparse.Namespace) -> int:
    proof_dir = Path(args.proof_dir) if args.proof_dir else default_proof_dir()
    paths = discover_proof_files(proof_dir, args.limit)
    rollup = swarm_agents_rollup(paths)
    payload = {**rollup.to_dict(), "proof_dir": str(proof_dir), "proof_files": [str(p) for p in paths]}
    _emit(payload, args, "Swarm agents rollup")
    return CLI_EXIT_OK


def cmd_swarm_status(args: argparse.Namespace) -> int:
    proof_dir = Path(args.proof_dir) if args.proof_dir else default_proof_dir()
    paths = discover_proof_files(proof_dir, args.limit)
    payload = swarm_status_summary(paths)
    payload["proof_dir"] = str(proof_dir)
    payload["proof_files"] = [str(p) for p in paths]
    _emit(payload, args, "Swarm status")
    return CLI_EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thinkbox",
        description="ThinkBox AI Engine — execution, stress tests, and hermetic governance inspection",
    )
    parser.add_argument("--version", action="version", version=f"thinkbox {__version__}")
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
    stress_parser.add_argument(
        "--policy",
        choices=["fair_share", "priority", "fifo"],
        default="fair_share",
        help="Budget contention policy",
    )
    stress_parser.add_argument("--duration", type=float, default=60.0, help="Max duration in seconds")
    stress_parser.add_argument("--output", help="Output JSON file for results")

    session_parser = subparsers.add_parser("session", help="Session management (audit log)")
    session_sub = session_parser.add_subparsers(dest="session_command")

    session_list_parser = session_sub.add_parser("list", help="List recent sessions")
    session_list_parser.add_argument("--limit", type=int, default=20, help="Max sessions to show")
    session_list_parser.add_argument("--min-audits", type=int, default=0, help="Filter by minimum audit count")
    session_list_parser.add_argument("--json", action="store_true", help="Emit JSON")

    session_inspect_parser = session_sub.add_parser("inspect", help="Inspect a session")
    session_inspect_parser.add_argument("--id", required=True, help="Session ID to inspect")
    session_inspect_parser.add_argument("--limit", type=int, default=50, help="Max audit records")
    session_inspect_parser.add_argument("--json", action="store_true", help="Emit JSON")

    env_parser = subparsers.add_parser("env", help="Environment inspection (redacted)")
    env_sub = env_parser.add_subparsers(dest="env_command")
    env_status_parser = env_sub.add_parser("status", help="Redacted environment and substrate status")
    env_status_parser.add_argument("--json", action="store_true", help="Emit JSON")

    ledger_parser = subparsers.add_parser("ledger", help="Action ledger governance")
    ledger_sub = ledger_parser.add_subparsers(dest="ledger_command")
    ledger_verify_parser = ledger_sub.add_parser("verify", help="Verify hash chain integrity")
    ledger_verify_parser.add_argument("--path", help="Ledger SQLite path (default: auto-resolve)")
    ledger_verify_parser.add_argument("--verbose", action="store_true", help="Include entry counts")
    ledger_verify_parser.add_argument("--json", action="store_true", help="Emit JSON")

    proof_parser = subparsers.add_parser("proof", help="Swarm proof artifacts")
    proof_sub = proof_parser.add_subparsers(dest="proof_command")
    proof_check_parser = proof_sub.add_parser("check", help="Validate a big_swarm proof JSON")
    proof_check_parser.add_argument("path", help="Path to proof JSON file")
    proof_check_parser.add_argument("--metrics-only", action="store_true", help="Emit metrics subset only")
    proof_check_parser.add_argument("--json", action="store_true", help="Emit JSON")

    swarm_parser = subparsers.add_parser("swarm", help="Swarm evidence (read-only)")
    swarm_sub = swarm_parser.add_subparsers(dest="swarm_command")
    swarm_agents_parser = swarm_sub.add_parser("agents", help="Aggregate worker roles from proofs")
    swarm_agents_parser.add_argument("--limit", type=int, default=5, help="Number of recent proofs to scan")
    swarm_agents_parser.add_argument("--proof-dir", help="Directory containing big_swarm_*.json")
    swarm_agents_parser.add_argument("--json", action="store_true", help="Emit JSON")

    swarm_status_parser = swarm_sub.add_parser("status", help="Convergence summary from recent proofs")
    swarm_status_parser.add_argument("--limit", type=int, default=5, help="Number of recent proofs to scan")
    swarm_status_parser.add_argument("--proof-dir", help="Directory containing big_swarm_*.json")
    swarm_status_parser.add_argument("--json", action="store_true", help="Emit JSON")

    return parser


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "run":
        return cmd_run(args)
    if args.command == "serve":
        return cmd_serve(args)
    if args.command == "benchmark":
        return cmd_benchmark(args)
    if args.command == "stress":
        return cmd_stress_test(args)
    if args.command == "session":
        if args.session_command == "list":
            return cmd_session_list(args)
        if args.session_command == "inspect":
            return cmd_session_inspect(args)
        return CLI_EXIT_USAGE
    if args.command == "env":
        if args.env_command == "status":
            return cmd_env_status(args)
        return CLI_EXIT_USAGE
    if args.command == "ledger":
        if args.ledger_command == "verify":
            return cmd_ledger_verify(args)
        return CLI_EXIT_USAGE
    if args.command == "proof":
        if args.proof_command == "check":
            return cmd_proof_check(args)
        return CLI_EXIT_USAGE
    if args.command == "swarm":
        if args.swarm_command == "agents":
            return cmd_swarm_agents(args)
        if args.swarm_command == "status":
            return cmd_swarm_status(args)
        return CLI_EXIT_USAGE
    return CLI_EXIT_USAGE


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(CLI_EXIT_USAGE)
    code = dispatch(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
