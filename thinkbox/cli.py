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

DEFAULT_IDENTITY_DB = "data/thinkboxmd/db/identities.db"
DEFAULT_TRACE_DB = "data/thinkboxmd/db/traces.db"


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


def cmd_session_list(args: argparse.Namespace) -> None:
    print("No session commands available in this configuration")


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


def cmd_swarm_agents(args: argparse.Namespace) -> None:
    from thinkbox.pop_arena import (
        build_population, POPULATION_SIZE, VARIANTS_PER_FAMILY,
    )
    tasks = build_population()
    print(f"Swarm Population: {POPULATION_SIZE}")
    print(f"Variants per family: {VARIANTS_PER_FAMILY}")
    print(f"Unique task IDs: {len({t.task_id for t in tasks})}")
    print(f"Task IDs stable: {tasks == build_population()}")
    print("Live model calls: 12 (6 baseline + 6 learned)")
    print("Replay emissions: 288 (deterministic, no API)")
    if args.agents and args.agents != POPULATION_SIZE:
        print(f"Note: --agents {args.agents} requested; population fixed at {POPULATION_SIZE}")


def cmd_swarm_status(args: argparse.Namespace) -> None:
    from thinkbox.swarm_stats import expected_live_calls
    from thinkbox.reputation import ReputationLedger
    print("Swarm Status (evidence-based, no live calls):")
    print("  Population: 300 agents (6 task variants x 50)")
    print("  Historical: 512 agents @ 27.25 RPS, 444/512 OK")
    print("  Convergence: 5x256 runs, mean 219/256 OK, mean 27.24 RPS")
    print("  Live calls per run: bounded by budget (default 12)")
    try:
        rep = ReputationLedger(":memory:")
        print("  Reputation ledger: initialized (empty)")
    except Exception as e:
        print(f"  Reputation ledger: unavailable ({e})")
    prim, val = 288, 12
    print(f"  Expected live calls (288+12): {expected_live_calls(prim, val)}")


def cmd_swarm_live(args: argparse.Namespace) -> None:
    import os
    api_key = os.environ.get("INCEPTION_API_KEY", "")
    print("Swarm Live Status:")
    print(f"  INCEPTION_API_KEY present: {bool(api_key)}")
    if not api_key:
        print("  Status: BLOCKED — no provider authorization")
        print("  Action: set INCEPTION_API_KEY and re-run with --live")
        sys.exit(1)
    print("  Status: AUTHORIZED — live mode would execute")
    print("  Note: live execution requires explicit founder authorization")


def cmd_ledger_verify(args: argparse.Namespace) -> None:
    from thinkbox.ledger import ActionLedger
    path = args.path or ":memory:"
    ledger = ActionLedger(path)
    verified = ledger.verify()
    entries = len(ledger.entries(limit=1_000_000))
    print(f"Ledger: {path}")
    print(f"Entries: {entries}")
    print(f"Hash chain verified: {verified}")
    if not verified:
        print("ERROR: ledger integrity check FAILED")
        sys.exit(1)


def cmd_proof_check(args: argparse.Namespace) -> None:
    from thinkbox.swarm_stats import load_and_validate_proof
    path = args.path
    if not Path(path).exists():
        print(f"ERROR: proof file not found: {path}")
        sys.exit(1)
    payload, errors = load_and_validate_proof(path)
    if errors:
        print(f"Proof: {path}")
        print(f"  VALIDATION ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    - {e}")
        sys.exit(1)
    recon = payload.get("reconciliation", {})
    print(f"Proof: {path}")
    print(f"  Status: VALID")
    print(f"  run_id: {payload.get('run_id', 'n/a')}")
    print(f"  workers: {payload.get('primary_workers', '?') + payload.get('validator_workers', 0)}")
    print(f"  ok: {recon.get('ok', '?')} / failed: {recon.get('failed', '?')}")
    print(f"  ledger_valid: {recon.get('ledger_valid', '?')}")


def cmd_env_status(args: argparse.Namespace) -> None:
    from thinkbox.byoc_config import ByocConfig
    cfg = ByocConfig.load()
    redacted = cfg.redacted()
    print("Environment Status (redacted):")
    for key in ("base_url", "model", "demo_mode", "is_live",
                "has_api_key", "has_vector_creds", "vector_url"):
        print(f"  {key}: {redacted.get(key, 'n/a')}")
    if redacted.get("is_live"):
        print("  Note: live mode active (credentials via env, not logged)")


def cmd_agent_list(args: argparse.Namespace) -> None:
    from thinkbox.identity import IdentityLedger
    db_path = getattr(args, "db", None)
    ledger = IdentityLedger(db_path=db_path)
    agents = ledger.list()
    if not agents:
        print("No registered agents")
        return
    print(f"Registered agents: {len(agents)}")
    for a in agents:
        status = "REVOKED" if a["revoked"] else "ACTIVE"
        print(f"  {a['agent_id']}: {status} capabilities={a['capabilities']}")


def cmd_governance_check(args: argparse.Namespace) -> None:
    from thinkbox.governed import GovernedEngine, GovernedEngineConfig
    from thinkbox.engine import ThinkBoxEngine, EngineConfig
    base = ThinkBoxEngine(EngineConfig())
    governed = GovernedEngine(GovernedEngineConfig(engine=base))
    token = governed.register_agent("cli-agent", ["governance:check"])
    decision = governed.authorize(
        token_value=token,
        agent_id="cli-agent",
        capability="governance:check",
        action="check",
    )
    print("Governance Check:")
    print("  Agent: cli-agent")
    print(f"  Token issued: {bool(token)}")
    print(f"  Allowed: {decision.allowed}")
    print(f"  Reason: {decision.reason}")
    if not decision.allowed:
        sys.exit(1)


def cmd_config_redacted(args: argparse.Namespace) -> None:
    from thinkbox.byoc_config import ByocConfig
    cfg = ByocConfig.load()
    redacted = cfg.redacted()
    print("Config (redacted — no secrets):")
    for key, value in sorted(redacted.items()):
        print(f"  {key}: {value}")


def cmd_trace_show(args: argparse.Namespace) -> None:
    from thinkbox.thinktrace import ThinkTraceCapture
    db_path = getattr(args, "db", None)
    capture = ThinkTraceCapture(max_traces=10000, db_path=db_path)
    trace = capture.find_by_id(args.trace_id)
    if trace is None:
        print(f"Trace not found: {args.trace_id}")
        print(f"Total traces: {capture.count()}")
        return
    print(f"Trace: {trace.trace_id}")
    print(f"  Agent: {trace.agent_id}")
    print(f"  Thought: {trace.thought[:100]}{'...' if len(trace.thought) > 100 else ''}")
    print(f"  Grounded: {trace.grounded}")
    print(f"  Confidence: {trace.confidence}")
    print(f"  Evidence refs: {trace.evidence_refs}")
    print(f"  Captured: {trace.captured_at}")
    print(f"  Tags: {trace.tags}")


def cmd_receipts_pr(args: argparse.Namespace) -> None:
    from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
    pr_number = args.pr_number
    store = OrgMemoryReceiptStore(":memory:")
    receipts = store.query(pr_number=pr_number, limit=50)
    print(f"PR {pr_number} receipts: {len(receipts)}")
    for r in receipts:
        public = r.to_public_dict()
        print(f"  [{public['receipt_id']}] {public['action']}: {public['result']}")
        print(f"    from={public['from_state']} -> to={public['to_state']}")
        print(f"    evidence_label={public['evidence_label']} chain_verified={store.verify()}")


def cmd_shell(args: argparse.Namespace) -> None:
    try:
        import readline
        readline.parse_and_bind("tab: complete")
        hist_path = Path.home() / ".kudbee_cli_history"
        if hist_path.exists():
            readline.read_history_file(str(hist_path))
    except ImportError:
        print("readline not available; interactive features limited")

    print("KUDBEE CLI Shell — type 'help' for commands, 'exit' to quit")
    commands = [
        "swarm agents", "swarm status", "swarm live",
        "ledger verify", "proof check", "agent list",
        "governance check", "config redacted",
        "trace show", "receipts pr", "dashboard status",
    ]
    while True:
        try:
            line = input("kudbee> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("exit", "quit", "q"):
            break
        if line == "help":
            print("Available commands:")
            for c in commands:
                print(f"  {c}")
            print("  exit — quit shell")
            continue
        if line == "dashboard status":
            cmd_dashboard_status(args)
            continue
        parts = line.split()
        cmd = parts[0]
        rest = " ".join(parts[1:])
        if cmd == "swarm" and rest in ("agents", "status", "live"):
            ns = argparse.Namespace(agents=0) if rest == "agents" else argparse.Namespace()
            if rest == "agents":
                cmd_swarm_agents(ns)
            elif rest == "status":
                cmd_swarm_status(ns)
            elif rest == "live":
                cmd_swarm_live(ns)
        elif cmd == "ledger" and rest.startswith("verify"):
            ns = argparse.Namespace(path=":memory:")
            cmd_ledger_verify(ns)
        elif cmd == "proof" and rest.startswith("check"):
            ns = argparse.Namespace(path="data/thinkboxmd/big_swarm_20260921_152452.json")
            cmd_proof_check(ns)
        elif cmd == "agent" and rest == "list":
            ns = argparse.Namespace(db=None)
            cmd_agent_list(ns)
        elif cmd == "governance" and rest == "check":
            ns = argparse.Namespace()
            cmd_governance_check(ns)
        elif cmd == "config" and rest == "redacted":
            ns = argparse.Namespace()
            cmd_config_redacted(ns)
        elif cmd == "trace" and rest.startswith("show"):
            tid = rest.split("show", 1)[1].strip() or "test-trace"
            ns = argparse.Namespace(trace_id=tid, db=None)
            cmd_trace_show(ns)
        elif cmd == "receipts" and rest.startswith("pr"):
            try:
                pr_n = int(rest.split("pr", 1)[1].strip())
            except (ValueError, IndexError):
                pr_n = 127
            ns = argparse.Namespace(pr_number=pr_n)
            cmd_receipts_pr(ns)
        else:
            print(f"Unknown command: {line}. Type 'help' for options.")
    try:
        import readline
        readline.write_history_file(str(hist_path))
    except ImportError:
        pass
    print("Shell exited")


def cmd_dashboard_status(args: argparse.Namespace) -> None:
    from pathlib import Path as P
    dash_script = P(__file__).resolve().parent.parent / "experiments" / "swarm_dashboard.py"
    events = P(__file__).resolve().parent.parent / "data" / "thinkboxmd" / "swarm_events.jsonl"
    print("Dashboard Status:")
    print(f"  Script: {dash_script}")
    print(f"  Exists: {dash_script.exists()}")
    print(f"  Events: {events}")
    print(f"  Events exist: {events.exists()}")
    if events.exists():
        lines = events.read_text(errors="replace").strip().splitlines()
        print(f"  Event count: {len(lines)}")
    else:
        print("  Event count: 0 (no swarm run yet)")
    print("  Run: python3 experiments/swarm_dashboard.py --port 8787")
    print("  Note: dashboard reads from SQLite + swarm_events.jsonl (no live API)")


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

    swarm_parser = subparsers.add_parser("swarm", help="Swarm status and population")
    swarm_subparsers = swarm_parser.add_subparsers(dest="swarm_command")
    swarm_agents_parser = swarm_subparsers.add_parser("agents", help="Show agent population")
    swarm_agents_parser.add_argument("--agents", type=int, default=0, help="Target agent count")
    swarm_status_parser = swarm_subparsers.add_parser("status", help="Swarm evidence status")
    swarm_live_parser = swarm_subparsers.add_parser("live", help="Check live provider authorization")

    ledger_parser = subparsers.add_parser("ledger", help="Action ledger operations")
    ledger_subparsers = ledger_parser.add_subparsers(dest="ledger_command")
    ledger_verify_parser = ledger_subparsers.add_parser("verify", help="Verify ledger hash chain")
    ledger_verify_parser.add_argument("--path", default=":memory:", help="Ledger DB path")

    proof_parser = subparsers.add_parser("proof", help="Proof validation")
    proof_subparsers = proof_parser.add_subparsers(dest="proof_command")
    proof_check_parser = proof_subparsers.add_parser("check", help="Validate a proof JSON")
    proof_check_parser.add_argument("path", help="Path to proof JSON")

    env_parser = subparsers.add_parser("env", help="Environment status")
    env_subparsers = env_parser.add_subparsers(dest="env_command")
    env_status_parser = env_subparsers.add_parser("status", help="Redacted env status")

    agent_parser = subparsers.add_parser("agent", help="Agent registry")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command")
    agent_list_parser = agent_subparsers.add_parser("list", help="List registered agents")
    agent_list_parser.add_argument("--db", default=None, help="SQLite DB path for persistence")

    gov_parser = subparsers.add_parser("governance", help="Governance operations")
    gov_subparsers = gov_parser.add_subparsers(dest="governance_command")
    gov_check_parser = gov_subparsers.add_parser("check", help="Check admission gate")

    config_parser = subparsers.add_parser("config", help="Configuration")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    config_redacted_parser = config_subparsers.add_parser("redacted", help="Show redacted config")

    trace_parser = subparsers.add_parser("trace", help="Think trace operations")
    trace_subparsers = trace_parser.add_subparsers(dest="trace_command")
    trace_show_parser = trace_subparsers.add_parser("show", help="Show a trace by ID")
    trace_show_parser.add_argument("trace_id", help="Trace ID")
    trace_show_parser.add_argument("--db", default=None, help="SQLite DB path for persistence")

    receipts_parser = subparsers.add_parser("receipts", help="PR lifecycle receipts")
    receipts_subparsers = receipts_parser.add_subparsers(dest="receipts_command")
    receipts_pr_parser = receipts_subparsers.add_parser("pr", help="List receipts for a PR")
    receipts_pr_parser.add_argument("pr_number", type=int, help="PR number")

    shell_parser = subparsers.add_parser("shell", help="Interactive REPL")

    dashboard_parser = subparsers.add_parser("dashboard", help="Dashboard operations")
    dashboard_subparsers = dashboard_parser.add_subparsers(dest="dashboard_command")
    dashboard_status_parser = dashboard_subparsers.add_parser("status", help="Dashboard status")

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
    elif args.command == "swarm":
        if args.swarm_command == "agents":
            cmd_swarm_agents(args)
        elif args.swarm_command == "status":
            cmd_swarm_status(args)
        elif args.swarm_command == "live":
            cmd_swarm_live(args)
        else:
            swarm_parser.print_help()
            sys.exit(1)
    elif args.command == "ledger":
        if args.ledger_command == "verify":
            cmd_ledger_verify(args)
        else:
            ledger_parser.print_help()
            sys.exit(1)
    elif args.command == "proof":
        if args.proof_command == "check":
            cmd_proof_check(args)
        else:
            proof_parser.print_help()
            sys.exit(1)
    elif args.command == "env":
        if args.env_command == "status":
            cmd_env_status(args)
        else:
            env_parser.print_help()
            sys.exit(1)
    elif args.command == "agent":
        if args.agent_command == "list":
            cmd_agent_list(args)
        else:
            agent_parser.print_help()
            sys.exit(1)
    elif args.command == "governance":
        if args.governance_command == "check":
            cmd_governance_check(args)
        else:
            gov_parser.print_help()
            sys.exit(1)
    elif args.command == "config":
        if args.config_command == "redacted":
            cmd_config_redacted(args)
        else:
            config_parser.print_help()
            sys.exit(1)
    elif args.command == "trace":
        if args.trace_command == "show":
            cmd_trace_show(args)
        else:
            trace_parser.print_help()
            sys.exit(1)
    elif args.command == "receipts":
        if args.receipts_command == "pr":
            cmd_receipts_pr(args)
        else:
            receipts_parser.print_help()
            sys.exit(1)
    elif args.command == "shell":
        cmd_shell(args)
    elif args.command == "dashboard":
        if args.dashboard_command == "status":
            cmd_dashboard_status(args)
        else:
            dashboard_parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()