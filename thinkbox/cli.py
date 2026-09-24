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
from thinkbox.cli_dashboard import dashboard_status_report
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
from thinkbox.cli_live_gate import require_swarm_live_authorization
from thinkbox.cli_persist import (
    SQLiteIdentityStore,
    SQLiteTraceStore,
    init_persist_files,
    persist_paths_report,
    resolve_identity_db_path,
    resolve_trace_db_path,
    sync_identity_ledger_to_sqlite,
    sync_traces_to_sqlite,
)
from thinkbox.cli_phase2.integrate import dispatch_phase2, register_phase2_parser
from thinkbox.cli_shell import CliShell
from thinkbox.identity import IdentityLedger
from thinkbox.thinktrace import ThinkTraceCapture

__version__ = "0.178.0"


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


def cmd_swarm_live(args: argparse.Namespace) -> int:
    """Authorization check only — never calls live provider APIs."""
    ok, report = require_swarm_live_authorization()
    _emit(report, args, "Swarm live gate")
    return CLI_EXIT_OK if ok or getattr(args, "check_only", False) else CLI_EXIT_FAIL


def cmd_dashboard_status(args: argparse.Namespace) -> int:
    payload = dashboard_status_report(include_env=not args.no_env)
    _emit(payload, args, "Dashboard status (local)")
    return CLI_EXIT_OK


def cmd_persist_status(args: argparse.Namespace) -> int:
    payload = persist_paths_report()
    _emit(payload, args, "CLI persistence paths")
    return CLI_EXIT_OK


def cmd_persist_init(args: argparse.Namespace) -> int:
    payload = init_persist_files(seed=args.seed)
    _emit(payload, args, "CLI persistence init")
    return CLI_EXIT_OK


def cmd_persist_sync(args: argparse.Namespace) -> int:
    id_path = resolve_identity_db_path(args.identity_db)
    tr_path = resolve_trace_db_path(args.trace_db)
    ledger = IdentityLedger()
    if args.seed_identity:
        ledger.register(agent_id=args.seed_identity, capabilities=["cli:sync"], policy_version="phase2")
    id_count = sync_identity_ledger_to_sqlite(ledger, id_path)
    capture = ThinkTraceCapture()
    if args.seed_trace:
        capture.capture(args.seed_trace, "cli sync seed", evidence_refs=["ev:cli"])
    tr_count = sync_traces_to_sqlite(capture, tr_path)
    payload = {
        "identity_path": str(id_path),
        "trace_path": str(tr_path),
        "identity_rows": id_count,
        "trace_rows": tr_count,
        "evidence_label": "verified",
    }
    _emit(payload, args, "CLI persistence sync")
    return CLI_EXIT_OK


def cmd_identity_list(args: argparse.Namespace) -> int:
    path = resolve_identity_db_path(args.db)
    if not path.is_file():
        payload = {"path": str(path), "identities": [], "count": 0, "error": "database not found"}
        _emit(payload, args, "Identity list")
        return CLI_EXIT_FAIL
    store = SQLiteIdentityStore(path)
    try:
        rows = store.list_rows(limit=args.limit)
        payload = {"path": str(path), "identities": rows, "count": len(rows)}
        _emit(payload, args, "Identity list")
        return CLI_EXIT_OK
    finally:
        store.close()


def cmd_identity_path(args: argparse.Namespace) -> int:
    payload = {"path": str(resolve_identity_db_path(args.db)), "evidence_label": "verified"}
    _emit(payload, args, "Identity DB path")
    return CLI_EXIT_OK


def cmd_trace_list(args: argparse.Namespace) -> int:
    path = resolve_trace_db_path(args.db)
    if not path.is_file():
        payload = {"path": str(path), "traces": [], "count": 0, "error": "database not found"}
        _emit(payload, args, "Trace list")
        return CLI_EXIT_FAIL
    store = SQLiteTraceStore(path)
    try:
        grounded = None
        if args.grounded == "true":
            grounded = True
        elif args.grounded == "false":
            grounded = False
        rows = store.list_rows(limit=args.limit, grounded=grounded)
        payload = {"path": str(path), "traces": rows, "count": len(rows)}
        _emit(payload, args, "Trace list")
        return CLI_EXIT_OK
    finally:
        store.close()


def cmd_trace_stats(args: argparse.Namespace) -> int:
    path = resolve_trace_db_path(args.db)
    if not path.is_file():
        payload = {"path": str(path), "stats": None, "error": "database not found"}
        _emit(payload, args, "Trace stats")
        return CLI_EXIT_FAIL
    store = SQLiteTraceStore(path)
    try:
        payload = {"path": str(path), "stats": store.stats()}
        _emit(payload, args, "Trace stats")
        return CLI_EXIT_OK
    finally:
        store.close()


def _shell_tokenize(line: str) -> list[str]:
    import shlex

    return shlex.split(line)


def shell_execute(argv: list[str]) -> int:
    """Map REPL tokens to hermetic inspect handlers (no network)."""
    if not argv:
        return CLI_EXIT_OK
    head = argv[0].lower()
    if head in ("help", "?"):
        print(
            "Commands: help, exit, env status, ledger verify, proof check PATH,\n"
            "  swarm agents|status, swarm live (gate only), dashboard status,\n"
            "  identity list, trace list, persist status\n"
        )
        return CLI_EXIT_OK
    if head == "env" and len(argv) >= 2 and argv[1].lower() == "status":
        return cmd_env_status(argparse.Namespace(json=False, command="env", env_command="status"))
    if head == "ledger" and len(argv) >= 2 and argv[1].lower() == "verify":
        path = argv[2] if len(argv) > 2 else None
        return cmd_ledger_verify(
            argparse.Namespace(json=False, command="ledger", ledger_command="verify", path=path, verbose=False)
        )
    if head == "proof" and len(argv) >= 3 and argv[1].lower() == "check":
        return cmd_proof_check(
            argparse.Namespace(
                json=False,
                command="proof",
                proof_command="check",
                path=argv[2],
                metrics_only=False,
            )
        )
    if head == "swarm":
        if len(argv) >= 2 and argv[1].lower() == "live":
            return cmd_swarm_live(argparse.Namespace(json=False, command="swarm", swarm_command="live", check_only=False))
        if len(argv) >= 2 and argv[1].lower() == "agents":
            return cmd_swarm_agents(
                argparse.Namespace(json=False, command="swarm", swarm_command="agents", proof_dir=None, limit=3)
            )
        if len(argv) >= 2 and argv[1].lower() == "status":
            return cmd_swarm_status(
                argparse.Namespace(json=False, command="swarm", swarm_command="status", proof_dir=None, limit=3)
            )
    if head == "dashboard" and len(argv) >= 2 and argv[1].lower() == "status":
        return cmd_dashboard_status(
            argparse.Namespace(json=False, command="dashboard", dashboard_command="status", no_env=False)
        )
    if head == "identity" and len(argv) >= 2 and argv[1].lower() == "list":
        return cmd_identity_list(
            argparse.Namespace(json=False, command="identity", identity_command="list", db=None, limit=20)
        )
    if head == "trace" and len(argv) >= 2 and argv[1].lower() == "list":
        return cmd_trace_list(
            argparse.Namespace(
                json=False, command="trace", trace_command="list", db=None, limit=20, grounded="any"
            )
        )
    if head == "persist" and len(argv) >= 2 and argv[1].lower() == "status":
        return cmd_persist_status(argparse.Namespace(json=False, command="persist", persist_command="status"))
    if head in _LIVE_COMMANDS:
        return cmd_swarm_live(argparse.Namespace(json=False, command="swarm", swarm_command="live", check_only=False))
    return CLI_EXIT_USAGE


_LIVE_COMMANDS = frozenset({"live", "swarm-live", "run-live"})


def cmd_shell(args: argparse.Namespace) -> int:
    if args.command_line:
        return shell_execute(_shell_tokenize(args.command_line))
    shell = CliShell(shell_execute)
    return shell.run(max_lines=args.max_lines or 0)


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

    swarm_live_parser = swarm_sub.add_parser(
        "live",
        help="Fail-closed live authorization check (no provider HTTP)",
    )
    swarm_live_parser.add_argument(
        "--check-only",
        action="store_true",
        help="Exit 0 even when unauthorized (report only)",
    )
    swarm_live_parser.add_argument("--json", action="store_true", help="Emit JSON")

    dash_parser = subparsers.add_parser("dashboard", help="Dashboard inspection (local state)")
    dash_sub = dash_parser.add_subparsers(dest="dashboard_command")
    dash_status_parser = dash_sub.add_parser("status", help="Read-only in-process dashboard summary")
    dash_status_parser.add_argument("--no-env", action="store_true", help="Omit redacted env block")
    dash_status_parser.add_argument("--json", action="store_true", help="Emit JSON")

    persist_parser = subparsers.add_parser("persist", help="CLI SQLite persistence paths")
    persist_sub = persist_parser.add_subparsers(dest="persist_command")
    persist_status_parser = persist_sub.add_parser("status", help="Show identity/trace DB paths")
    persist_status_parser.add_argument("--json", action="store_true", help="Emit JSON")
    persist_init_parser = persist_sub.add_parser("init", help="Create empty SQLite files")
    persist_init_parser.add_argument("--seed", action="store_true", help="Insert hermetic seed identity")
    persist_init_parser.add_argument("--json", action="store_true", help="Emit JSON")
    persist_sync_parser = persist_sub.add_parser("sync", help="Sync in-memory ledger/trace to SQLite")
    persist_sync_parser.add_argument("--identity-db", help="Identity SQLite path override")
    persist_sync_parser.add_argument("--trace-db", help="Trace SQLite path override")
    persist_sync_parser.add_argument("--seed-identity", help="Optional agent_id to register before sync")
    persist_sync_parser.add_argument("--seed-trace", help="Optional agent_id for a seed trace row")
    persist_sync_parser.add_argument("--json", action="store_true", help="Emit JSON")

    identity_parser = subparsers.add_parser("identity", help="Identity ledger SQLite (read-only)")
    identity_sub = identity_parser.add_subparsers(dest="identity_command")
    identity_list_parser = identity_sub.add_parser("list", help="List identities from SQLite")
    identity_list_parser.add_argument("--db", help="Identity DB path override")
    identity_list_parser.add_argument("--limit", type=int, default=50, help="Max rows")
    identity_list_parser.add_argument("--json", action="store_true", help="Emit JSON")
    identity_path_parser = identity_sub.add_parser("path", help="Print resolved identity DB path")
    identity_path_parser.add_argument("--db", help="Identity DB path override")
    identity_path_parser.add_argument("--json", action="store_true", help="Emit JSON")

    trace_parser = subparsers.add_parser("trace", help="Think-trace SQLite (read-only)")
    trace_sub = trace_parser.add_subparsers(dest="trace_command")
    trace_list_parser = trace_sub.add_parser("list", help="List recent traces")
    trace_list_parser.add_argument("--db", help="Trace DB path override")
    trace_list_parser.add_argument("--limit", type=int, default=30, help="Max rows")
    trace_list_parser.add_argument(
        "--grounded",
        choices=["any", "true", "false"],
        default="any",
        help="Filter by grounded flag",
    )
    trace_list_parser.add_argument("--json", action="store_true", help="Emit JSON")
    trace_stats_parser = trace_sub.add_parser("stats", help="Trace counts from SQLite")
    trace_stats_parser.add_argument("--db", help="Trace DB path override")
    trace_stats_parser.add_argument("--json", action="store_true", help="Emit JSON")

    shell_parser = subparsers.add_parser("shell", help="Local inspect REPL (no network)")
    shell_parser.add_argument("-c", "--command", dest="command_line", help="Run one REPL command and exit")
    shell_parser.add_argument(
        "--max-lines",
        type=int,
        default=0,
        help="Stop REPL after N input lines (0 = unlimited)",
    )

    register_phase2_parser(subparsers)

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
        if args.swarm_command == "live":
            return cmd_swarm_live(args)
        return CLI_EXIT_USAGE
    if args.command == "dashboard":
        if args.dashboard_command == "status":
            return cmd_dashboard_status(args)
        return CLI_EXIT_USAGE
    if args.command == "persist":
        if args.persist_command == "status":
            return cmd_persist_status(args)
        if args.persist_command == "init":
            return cmd_persist_init(args)
        if args.persist_command == "sync":
            return cmd_persist_sync(args)
        return CLI_EXIT_USAGE
    if args.command == "identity":
        if args.identity_command == "list":
            return cmd_identity_list(args)
        if args.identity_command == "path":
            return cmd_identity_path(args)
        return CLI_EXIT_USAGE
    if args.command == "trace":
        if args.trace_command == "list":
            return cmd_trace_list(args)
        if args.trace_command == "stats":
            return cmd_trace_stats(args)
        return CLI_EXIT_USAGE
    if args.command == "shell":
        return cmd_shell(args)
    if args.command == "cli":
        if not getattr(args, "cli_command", None):
            return CLI_EXIT_USAGE
        return dispatch_phase2(args)
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
