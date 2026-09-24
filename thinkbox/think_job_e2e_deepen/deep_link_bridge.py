"""Bridge to control-plane deep links for Think Job watch (PR #183 F20)."""

from __future__ import annotations

from typing import Any

from thinkbox.control_plane_deep_link import THINK_JOB_STATUS_PAGE, build_think_job_watch_href


def deep_link_bridge_summary(receipt_id: str = "rcpt-demo") -> dict[str, Any]:
    href = build_think_job_watch_href(receipt_id=receipt_id, auto_watch=True)
    return {
        "page": THINK_JOB_STATUS_PAGE,
        "href": href,
        "hermetic": True,
        "live_api_called": False,
    }
