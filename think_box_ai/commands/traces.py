"""Trace and observability commands."""

from __future__ import annotations

from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.table import render_table
from ..utils.output import is_json_mode, output_json


def handle_trace_command(args) -> None:
    from core.observability import get_trace, list_traces, get_metrics

    sub = args.trace_command

    if sub == "list":
        traces = list_traces(limit=args.limit, status_filter=args.status)
        if is_json_mode():
            output_json(traces)
            return
        if not traces:
            print(dim("  No traces found."))
            return
        headers = ["Trace ID", "Goal", "Status", "Cost", "Duration"]
        rows = []
        for t in traces:
            rows.append([
                t["trace_id"][:12],
                t["goal"][:40],
                t["status"],
                f"${t['cost_usd']:.4f}",
                f"{t['duration_ms']:.0f}ms",
            ])
        print(bold(f"\n  Traces ({len(traces)}):"))
        print(render_table(headers, rows))

    elif sub == "show":
        trace = get_trace(args.trace_id)
        if is_json_mode():
            output_json(trace or {"error": "not found"})
            return
        if not trace:
            print(yellow(f"  Trace not found: {args.trace_id}"))
            return
        print(bold(f"\n  Trace: {trace['trace_id']}"))
        print(dim("  " + "─" * 50))
        print(f"  Goal: {trace['goal']}")
        print(f"  Status: {trace['status']}")
        print(f"  Tokens: {trace['total_tokens_input']} in / {trace['total_tokens_output']} out")
        print(f"  Cost: ${trace['total_cost_usd']:.6f}")
        print(f"  Duration: {trace['total_duration_ms']:.0f}ms")
        if trace.get("spans"):
            print(f"\n  {bold('Spans:')}")
            for s in trace["spans"]:
                status_icon = green("✓") if s["status"] == "ok" else yellow("✗")
                print(f"    {status_icon} {s['type']:12} {s['name'][:40]:40} {s['duration_ms']:.0f}ms")

    elif sub == "metrics":
        metrics = get_metrics()
        if is_json_mode():
            output_json(metrics)
            return
        print(bold("\n  Observability Metrics:"))
        print(dim("  " + "─" * 40))
        for key, value in metrics.items():
            print(f"    {bold(key):25} {value}")
    else:
        print("Usage: thinkbox trace {list|show|metrics}")
