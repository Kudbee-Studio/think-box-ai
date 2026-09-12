"""Cost tracking and budget commands."""

from __future__ import annotations

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.table import render_table
from ..utils.output import is_json_mode, output_json


def handle_cost_command(args) -> None:
    from core.cost_tracker import estimate_cost, estimate_tokens, MODEL_PRICING, BudgetManager

    sub = args.cost_command

    if sub == "estimate":
        tokens_in = args.tokens_input or estimate_tokens(args.text or "")
        tokens_out = args.tokens_output or 0
        cost = estimate_cost(tokens_in, tokens_out, args.model)
        if is_json_mode():
            output_json(cost.to_dict())
            return
        print(bold(f"\n  Cost Estimate ({args.model}):"))
        print(dim("  " + "─" * 40))
        print(f"    Input tokens:  {cost.tokens_input:>10}  ${cost.cost_input:.6f}")
        print(f"    Output tokens: {cost.tokens_output:>10}  ${cost.cost_output:.6f}")
        print(f"    {bold('Total'):26}  ${cost.cost_total:.6f}")

    elif sub == "models":
        if is_json_mode():
            output_json(MODEL_PRICING)
            return
        headers = ["Model", "$/1M input", "$/1M output"]
        rows = []
        for model, pricing in sorted(MODEL_PRICING.items()):
            rows.append([
                model,
                f"${pricing['input']:.2f}",
                f"${pricing['output']:.2f}",
            ])
        print(bold("\n  Model Pricing (per 1M tokens):"))
        print(render_table(headers, rows))

    elif sub == "budget":
        from core.cost_tracker import BudgetManager
        bm = BudgetManager(max_cost_usd=args.max_cost or 10.0)
        if is_json_mode():
            output_json(bm.to_dict())
            return
        print(bold("\n  Budget Manager:"))
        print(dim("  " + "─" * 40))
        print(f"    Max cost: ${bm.max_cost_usd:.2f}")
        print(f"    Remaining: ${bm.remaining_budget:.2f}")
        print(f"    Max tokens: {bm.max_tokens:,}")
    else:
        print("Usage: thinkbox cost {estimate|models|budget}")


def is_json_style() -> bool:
    return "--json" in __import__("sys").argv
