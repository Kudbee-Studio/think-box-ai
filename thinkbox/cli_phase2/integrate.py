"""CLI parser integration for Phase 2 deepen commands (PR #178 F25)."""

from __future__ import annotations

import argparse
import json
from typing import Any

from thinkbox.cli_inspect import CLI_EXIT_FAIL, CLI_EXIT_OK
from thinkbox.cli_phase2.dry_run import simulate_post
from thinkbox.cli_phase2.errors import CliToolkitError
from thinkbox.cli_phase2.inspect_status import cli_health_report
from thinkbox.cli_phase2.receipt_bind import bind_receipt_hermetic
from thinkbox.cli_phase2.streaming import parse_sse_chunk
from thinkbox.cli_phase2.websocket_envelope import validate_ws_message


def cmd_cli_health(args: argparse.Namespace) -> int:
    payload = cli_health_report(use_fixture_transport=not args.no_fixture)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"KUDBEECLI Phase 2 health ({payload['cli_phase2_version']})")
        print(f"  capabilities: {', '.join(payload['capabilities']) or '(none)'}")
        health = payload.get("health") or {}
        print(f"  health.status: {health.get('status', 'n/a')}")
        print(f"  live_api_called: {payload['live_api_called']}")
    return CLI_EXIT_OK


def cmd_cli_dry_run(args: argparse.Namespace) -> int:
    result = simulate_post(args.path, {"goal": args.goal})
    payload: dict[str, Any] = {
        "dry_run": True,
        "path": args.path,
        "result": {"simulated": result.simulated, "payload": result.payload},
        "live_api_called": False,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2))
    return CLI_EXIT_OK


def cmd_cli_receipt_bind(args: argparse.Namespace) -> int:
    try:
        body = json.loads(args.payload)
    except json.JSONDecodeError:
        print("Invalid JSON payload", file=__import__("sys").stderr)
        return CLI_EXIT_FAIL
    if not isinstance(body, dict):
        print("Payload must be a JSON object", file=__import__("sys").stderr)
        return CLI_EXIT_FAIL
    proof = bind_receipt_hermetic(args.receipt_id, body)
    payload = {
        "receipt_id": proof.receipt_id,
        "payload_sha256": proof.payload_sha256,
        "bound": proof.bound,
        "live_api_called": False,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"receipt={proof.receipt_id} sha256={proof.payload_sha256}")
    return CLI_EXIT_OK


def cmd_cli_envelope(args: argparse.Namespace) -> int:
    try:
        doc = json.loads(args.json_body)
    except json.JSONDecodeError:
        return CLI_EXIT_FAIL
    if args.kind == "sse":
        chunk = args.json_body if args.raw else json.dumps(doc)
        events, remainder = parse_sse_chunk(chunk)
        payload = {
            "kind": "sse",
            "events": [
                {"event": e.event, "data": e.data, "id": e.id} for e in events
            ],
            "remainder": remainder,
            "live_api_called": False,
        }
    else:
        try:
            validate_ws_message(doc)
            payload = {"kind": "ws", "valid": True, "error": None, "live_api_called": False}
        except CliToolkitError as exc:
            payload = {
                "kind": "ws",
                "valid": False,
                "error": str(exc),
                "live_api_called": False,
            }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2))
    return CLI_EXIT_OK if payload.get("valid", True) else CLI_EXIT_FAIL


def register_phase2_parser(subparsers: Any) -> None:
    """Attach ``cli`` subcommand group to the root thinkbox parser."""
    cli_parser = subparsers.add_parser("cli", help="KUDBEECLI Phase 2 deepen (hermetic)")
    cli_sub = cli_parser.add_subparsers(dest="cli_command")

    health_p = cli_sub.add_parser("health", help="Redacted env + toolkit health (hermetic)")
    health_p.add_argument("--no-fixture", action="store_true", help="Skip in-memory health fetch")
    health_p.add_argument("--json", action="store_true", help="Emit JSON")

    dry_p = cli_sub.add_parser("dry-run", help="Simulate a CLI POST via dry-run transport")
    dry_p.add_argument("--path", default="/v1/think", help="Simulated path")
    dry_p.add_argument("--goal", default="hermetic-cli-dry-run", help="Goal string in body")
    dry_p.add_argument("--json", action="store_true", help="Emit JSON")

    bind_p = cli_sub.add_parser("receipt-bind", help="Hermetic receipt SHA-256 bind")
    bind_p.add_argument("receipt_id", help="Receipt identifier")
    bind_p.add_argument("payload", help="JSON object string")
    bind_p.add_argument("--json", action="store_true", help="Emit JSON")

    env_p = cli_sub.add_parser("envelope", help="Inspect SSE chunk or WS envelope offline")
    env_p.add_argument("--kind", choices=["sse", "ws"], default="ws")
    env_p.add_argument("json_body", help="Raw SSE text or JSON WS message")
    env_p.add_argument("--raw", action="store_true", help="Treat json_body as raw SSE chunk")
    env_p.add_argument("--json", action="store_true", help="Emit JSON")


def dispatch_phase2(args: argparse.Namespace) -> int:
    if args.cli_command == "health":
        return cmd_cli_health(args)
    if args.cli_command == "dry-run":
        return cmd_cli_dry_run(args)
    if args.cli_command == "receipt-bind":
        return cmd_cli_receipt_bind(args)
    if args.cli_command == "envelope":
        return cmd_cli_envelope(args)
    return CLI_EXIT_FAIL
