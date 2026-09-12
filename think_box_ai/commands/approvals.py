"""Human-in-the-loop commands — approvals and feedback."""

from __future__ import annotations

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.table import render_table
from ..utils.output import is_json_mode, output_json


def handle_approval_command(args) -> None:
    from core.hitl import ApprovalManager, FeedbackManager
    from core.hitl import FeedbackType

    sub = args.approval_command

    if sub == "pending":
        mgr = ApprovalManager()
        pending = mgr.get_pending()
        if is_json_mode():
            output_json(pending)
            return
        if not pending:
            print(dim("  No pending approvals."))
            return
        headers = ["ID", "Tool", "Reason", "Requested"]
        rows = []
        for p in pending:
            rows.append([
                p["id"],
                p["tool_name"],
                p["reason"][:30] if p["reason"] else "-",
                p["created_at"][:19],
            ])
        print(bold(f"\n  Pending Approvals ({len(pending)}):"))
        print(render_table(headers, rows))

    elif sub == "approve":
        mgr = ApprovalManager()
        if mgr.approve(args.approval_id):
            print(green(f"  Approved: {args.approval_id}"))
        else:
            print(yellow(f"  Not found or already resolved: {args.approval_id}"))

    elif sub == "deny":
        mgr = ApprovalManager()
        if mgr.deny(args.approval_id):
            print(green(f"  Denied: {args.approval_id}"))
        else:
            print(yellow(f"  Not found or already resolved: {args.approval_id}"))
    else:
        print("Usage: thinkbox approval {pending|approve|deny}")
