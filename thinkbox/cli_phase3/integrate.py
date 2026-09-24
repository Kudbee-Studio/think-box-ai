"""CLI parser integration for Phase 3 deepen commands (PR #180 F25)."""

from __future__ import annotations

import argparse
import json
from typing import Any

from thinkbox.cli_inspect import CLI_EXIT_FAIL, CLI_EXIT_OK, CLI_EXIT_USAGE
from thinkbox.cli_phase3.batch_parallel import run_batch_bounded
from thinkbox.cli_phase3.cassette import replay_cassette
from thinkbox.cli_phase3.completion import bash_completion_script
from thinkbox.cli_phase3.errors import CliPhase3Error
from thinkbox.cli_phase3.event_filter import filter_events
from thinkbox.cli_phase3.formatters import OutputFormat, emit_formatted
from thinkbox.cli_phase3.help_ux import format_help_catalog
from thinkbox.cli_phase3.job_cancel import cancel_job_hermetic
from thinkbox.cli_phase3.job_mirror import create_job_hermetic
from thinkbox.cli_phase3.job_status import job_status_hermetic
from thinkbox.cli_phase3.observability import get_metrics
from thinkbox.cli_phase3.plugins import list_plugins
from thinkbox.cli_phase3.profile import list_profiles, resolve_active_profile
from thinkbox.cli_phase3.sdk_bridge import cli_sdk_dry_run
from thinkbox.cli_phase3.status_report import cli_phase3_status_report
from thinkbox.cli_phase3.stream_tail import tail_lines
from thinkbox.cli_phase3.workflow import WorkflowStep, run_workflow


def _output_format(args: argparse.Namespace) -> OutputFormat:
    raw = getattr(args, "format", "json") or "json"
    try:
        return OutputFormat(raw.lower())
    except ValueError:
        return OutputFormat.JSON


def _print_payload(args: argparse.Namespace, doc: Any, table_rows: list[dict[str, Any]] | None = None) -> None:
    fmt = _output_format(args)
    print(emit_formatted(doc, fmt, table_rows=table_rows))


def cmd_phase3_status(args: argparse.Namespace) -> int:
    get_metrics().record_command("status")
    payload = cli_phase3_status_report()
    _print_payload(args, payload)
    return CLI_EXIT_OK


def cmd_phase3_profile(args: argparse.Namespace) -> int:
    get_metrics().record_command("profile")
    if args.list:
        payload = {"profiles": list_profiles(), "live_api_called": False}
    else:
        prof = resolve_active_profile()
        payload = {
            "name": prof.name,
            "dry_run": prof.dry_run,
            "output_format": prof.output_format,
            "live_api_called": False,
        }
    _print_payload(args, payload)
    return CLI_EXIT_OK


def cmd_phase3_format_demo(args: argparse.Namespace) -> int:
    rows = [{"key": "alpha", "value": 1}, {"key": "beta", "value": 2}]
    _print_payload(args, {"demo": True}, table_rows=rows if _output_format(args) == OutputFormat.TABLE else None)
    if _output_format(args) != OutputFormat.TABLE:
        _print_payload(args, rows)
    return CLI_EXIT_OK


def cmd_phase3_workflow(args: argparse.Namespace) -> int:
    steps = (
        WorkflowStep("echo", "dry-run"),
        WorkflowStep("status", "status"),
    )

    def runner(cmd: str) -> dict[str, Any]:
        if cmd == "dry-run":
            return cli_sdk_dry_run("/v1/think", {"goal": args.goal})
        return {"command": cmd, "ok": True}

    result = run_workflow(steps, runner)
    _print_payload(args, {"ok": result.ok, "steps": list(result.steps), "live_api_called": False})
    return CLI_EXIT_OK if result.ok else CLI_EXIT_FAIL


def cmd_phase3_cassette(args: argparse.Namespace) -> int:
    get_metrics().cassette_replays += 1
    payload = replay_cassette(args.name)
    _print_payload(args, payload)
    return CLI_EXIT_OK


def cmd_phase3_job(args: argparse.Namespace) -> int:
    if args.job_action == "create":
        res = create_job_hermetic(args.goal)
        payload = {
            "job_id": res.job_id,
            "status": res.status,
            "payload_sha256": res.payload_sha256,
            "live_api_called": False,
        }
    elif args.job_action == "status":
        st = job_status_hermetic(args.job_id)
        payload = {
            "job_id": st.job_id,
            "status": st.status,
            "progress": st.progress,
            "detail": st.detail,
        }
    else:
        cancel = cancel_job_hermetic(args.job_id)
        payload = {
            "job_id": cancel.job_id,
            "cancelled": cancel.cancelled,
            "reason": cancel.reason,
            "live_api_called": False,
        }
    _print_payload(args, payload)
    return CLI_EXIT_OK


def cmd_phase3_tail(args: argparse.Namespace) -> int:
    lines = tail_lines(args.text, args.lines)
    payload = {"lines": [{"n": ln.line_no, "text": ln.text} for ln in lines]}
    _print_payload(args, payload)
    return CLI_EXIT_OK


def cmd_phase3_plugins(args: argparse.Namespace) -> int:
    payload = {
        "plugins": [
            {"id": p.plugin_id, "version": p.version, "entry": p.entrypoint}
            for p in list_plugins()
        ],
        "live_api_called": False,
    }
    _print_payload(args, payload)
    return CLI_EXIT_OK


def cmd_phase3_capabilities(args: argparse.Namespace) -> int:
    payload = cli_phase3_status_report()
    slim = {
        "capabilities": payload["capabilities"],
        "feature_flags": payload["feature_flags"],
        "matrix": payload["capability_matrix"],
        "live_api_called": False,
    }
    _print_payload(args, slim)
    return CLI_EXIT_OK


def cmd_phase3_batch(args: argparse.Namespace) -> int:
    get_metrics().batch_runs += 1
    items = {f"k{i}": g for i, g in enumerate(args.goals)}
    result = run_batch_bounded(
        items,
        lambda goal: create_job_hermetic(goal).job_id,
        max_workers=args.parallel,
    )
    payload = {
        "ok_count": result.ok_count,
        "fail_count": result.fail_count,
        "results": [{"key": r.key, "ok": r.ok, "value": r.value} for r in result.results],
        "live_api_called": False,
    }
    _print_payload(args, payload)
    return CLI_EXIT_OK if result.fail_count == 0 else 5


def cmd_phase3_completion(args: argparse.Namespace) -> int:
    if args.shell == "bash":
        print(bash_completion_script())
    else:
        print(format_help_catalog())
    return CLI_EXIT_OK


def cmd_phase3_events_filter(args: argparse.Namespace) -> int:
    try:
        events = json.loads(args.json_events)
    except json.JSONDecodeError:
        return CLI_EXIT_FAIL
    if not isinstance(events, list):
        return CLI_EXIT_FAIL
    filtered = filter_events(
        events,
        event_type=args.type or None,
        min_id=args.min_id,
    )
    _print_payload(args, {"events": filtered, "count": len(filtered)})
    return CLI_EXIT_OK


def register_phase3_subcommands(cli_sub: Any) -> None:
    """Attach Phase 3 subcommands under existing ``thinkbox cli`` group."""
    st = cli_sub.add_parser("status", help="Phase 3 toolkit status (hermetic)")
    st.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    st.set_defaults(cli_phase3_handler=cmd_phase3_status)

    pr = cli_sub.add_parser("profile", help="List or show active CLI profile")
    pr.add_argument("--list", action="store_true", help="List profile names")
    pr.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    pr.set_defaults(cli_phase3_handler=cmd_phase3_profile)

    fd = cli_sub.add_parser("format-demo", help="Demonstrate output formatters")
    fd.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    fd.set_defaults(cli_phase3_handler=cmd_phase3_format_demo)

    wf = cli_sub.add_parser("workflow-run", help="Run a hermetic multi-step workflow")
    wf.add_argument("--goal", default="workflow-demo")
    wf.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    wf.set_defaults(cli_phase3_handler=cmd_phase3_workflow)

    cr = cli_sub.add_parser("cassette-replay", help="Replay offline cassette")
    cr.add_argument("name", default="health_flow", nargs="?")
    cr.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    cr.set_defaults(cli_phase3_handler=cmd_phase3_cassette)

    job = cli_sub.add_parser("job", help="Hermetic job lifecycle mirror")
    job_sub = job.add_subparsers(dest="job_action")
    jc = job_sub.add_parser("create", help="Create job")
    jc.add_argument("goal", help="Goal string")
    jc.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    jc.set_defaults(cli_phase3_handler=cmd_phase3_job)
    js = job_sub.add_parser("status", help="Job status")
    js.add_argument("job_id")
    js.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    js.set_defaults(cli_phase3_handler=cmd_phase3_job)
    jx = job_sub.add_parser("cancel", help="Cancel job")
    jx.add_argument("job_id")
    jx.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    jx.set_defaults(cli_phase3_handler=cmd_phase3_job)

    tl = cli_sub.add_parser("tail", help="Tail lines from text (offline)")
    tl.add_argument("text", help="Multiline text or path placeholder string")
    tl.add_argument("--lines", type=int, default=5)
    tl.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    tl.set_defaults(cli_phase3_handler=cmd_phase3_tail)

    pl = cli_sub.add_parser("plugins", help="List hermetic plugin registry")
    pl.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    pl.set_defaults(cli_phase3_handler=cmd_phase3_plugins)

    cap = cli_sub.add_parser("capabilities", help="Capability matrix + flags")
    cap.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    cap.set_defaults(cli_phase3_handler=cmd_phase3_capabilities)

    bt = cli_sub.add_parser("batch", help="Bounded parallel job create")
    bt.add_argument("goals", nargs="+", help="Goals to process")
    bt.add_argument("--parallel", type=int, default=4)
    bt.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    bt.set_defaults(cli_phase3_handler=cmd_phase3_batch)

    cp = cli_sub.add_parser("completion", help="Emit bash completion or help catalog")
    cp.add_argument("--shell", choices=["bash", "help"], default="bash")
    cp.set_defaults(cli_phase3_handler=cmd_phase3_completion)

    ev = cli_sub.add_parser("events-filter", help="Filter offline event JSON list")
    ev.add_argument("json_events", help="JSON array of events")
    ev.add_argument("--type", default="")
    ev.add_argument("--min-id", type=int, default=None)
    ev.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    ev.set_defaults(cli_phase3_handler=cmd_phase3_events_filter)


def dispatch_phase3(args: argparse.Namespace) -> int | None:
    handler = getattr(args, "cli_phase3_handler", None)
    if handler is None:
        return None
    try:
        return handler(args)
    except CliPhase3Error:
        return CLI_EXIT_FAIL

