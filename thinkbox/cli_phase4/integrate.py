"""CLI parser integration — enterprise upgrade commands (PR #196 F25)."""

from __future__ import annotations

import argparse
from typing import Any

from thinkbox.cli_inspect import CLI_EXIT_FAIL, CLI_EXIT_OK
from thinkbox.cli_phase4.errors import CliPhase4Error
from thinkbox.cli_phase4.formatters import OutputFormat, emit_formatted
from thinkbox.cli_phase4.sdk_bridge import cli_enterprise_lanes_summary, cli_enterprise_sdk_snapshot
from thinkbox.cli_phase4.status_report import cli_phase4_status_report


def _print_payload(args: argparse.Namespace, doc: Any) -> None:
    raw = getattr(args, "format", "json") or "json"
    try:
        fmt = OutputFormat(raw.lower())
    except ValueError:
        fmt = OutputFormat.JSON
    print(emit_formatted(doc, fmt))


def cmd_enterprise_status(args: argparse.Namespace) -> int:
    _print_payload(args, cli_phase4_status_report())
    return CLI_EXIT_OK


def cmd_enterprise_hub(args: argparse.Namespace) -> int:
    _print_payload(args, cli_enterprise_sdk_snapshot())
    return CLI_EXIT_OK


def cmd_enterprise_lanes(args: argparse.Namespace) -> int:
    _print_payload(args, cli_enterprise_lanes_summary())
    return CLI_EXIT_OK


def register_phase4_subcommands(cli_sub: Any) -> None:
    """Attach ``enterprise`` subcommands under ``thinkbox cli``."""
    ent = cli_sub.add_parser("enterprise", help="Enterprise lr-energy CLI upgrade (hermetic)")
    ent_sub = ent.add_subparsers(dest="enterprise_action")

    st = ent_sub.add_parser("status", help="Enterprise CLI + SDK status")
    st.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    st.set_defaults(cli_phase4_handler=cmd_enterprise_status)

    hub = ent_sub.add_parser("hub", help="Enterprise hub snapshot")
    hub.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    hub.set_defaults(cli_phase4_handler=cmd_enterprise_hub)

    lanes = ent_sub.add_parser("lanes", help="Enterprise lane registry summary")
    lanes.add_argument("--format", choices=["json", "table", "yaml"], default="json")
    lanes.set_defaults(cli_phase4_handler=cmd_enterprise_lanes)


def dispatch_phase4(args: argparse.Namespace) -> int | None:
    handler = getattr(args, "cli_phase4_handler", None)
    if handler is None:
        return None
    try:
        return handler(args)
    except CliPhase4Error:
        return CLI_EXIT_FAIL
