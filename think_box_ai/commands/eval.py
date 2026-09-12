"""Evaluation commands."""

from __future__ import annotations

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.table import render_table
from ..utils.output import is_json_mode, output_json


def handle_eval_command(args) -> None:
    from core.evaluation import EvalSuite

    suite = EvalSuite()
    sub = args.eval_command

    if sub == "list":
        cases = suite.list_cases(tag_filter=args.tag)
        if is_json_mode():
            output_json(cases)
            return
        if not cases:
            print(dim("  No evaluation cases."))
            return
        headers = ["ID", "Name", "Goal", "Tags"]
        rows = []
        for c in cases:
            rows.append([
                c["id"][:12],
                c["name"][:25],
                c["goal"][:40],
                ", ".join(c.get("tags", [])),
            ])
        print(bold(f"\n  Eval Cases ({len(cases)}):"))
        print(render_table(headers, rows))

    elif sub == "add":
        case_id = suite.add_case(
            name=args.name,
            goal=args.goal,
            expected_output=args.expected,
            expected_tools=args.tools.split(",") if args.tools else None,
            tags=args.tag.split(",") if args.tag else None,
        )
        if is_json_mode():
            output_json({"case_id": case_id})
            return
        print(green(f"  Added eval case: {case_id}"))

    elif sub == "results":
        results = suite.get_results(case_id=args.case_id, limit=args.limit)
        if is_json_mode():
            output_json(results)
            return
        if not results:
            print(dim("  No results."))
            return
        headers = ["Case", "Status", "Score", "Duration", "Cost"]
        rows = []
        for r in results:
            status_color = green if r["status"] == "pass" else yellow
            rows.append([
                r["case_id"][:12],
                status_color(r["status"]),
                f"{r['score']:.1f}",
                f"{r['duration_ms']:.0f}ms",
                f"${r['cost_usd']:.4f}",
            ])
        print(bold(f"\n  Eval Results ({len(results)}):"))
        print(render_table(headers, rows))

    elif sub == "summary":
        summary = suite.get_summary()
        if is_json_mode():
            output_json(summary)
            return
        print(bold("\n  Eval Summary:"))
        print(dim("  " + "─" * 40))
        for key, value in summary.items():
            print(f"    {bold(key):20} {value}")
    else:
        print("Usage: thinkbox eval {list|add|results|summary}")
