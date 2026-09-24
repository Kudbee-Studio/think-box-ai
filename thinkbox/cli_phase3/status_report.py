"""Phase 3 status report for operators (PR #180 F24)."""

from __future__ import annotations

from typing import Any

from thinkbox.cli_phase3.capability_matrix import build_capability_matrix, feature_flags
from thinkbox.cli_phase3.config import load_phase3_config_from_env
from thinkbox.cli_phase3.negotiation import CLI_PHASE3_VERSION, negotiate_phase3
from thinkbox.cli_phase3.observability import get_metrics
from thinkbox.cli_phase3.plugins import list_plugins
from thinkbox.cli_phase3.profile import resolve_active_profile
from thinkbox.cli_phase3.secrets import scan_cli_examples


def cli_phase3_status_report() -> dict[str, Any]:
    profile = resolve_active_profile()
    cfg = load_phase3_config_from_env()
    caps = negotiate_phase3(
        ("job_mirror", "cassette", "batch", "format"),
        ("job_mirror", "cassette", "batch", "format", "swarm_live"),
    )
    secret_hits = scan_cli_examples()
    return {
        "cli_phase3_version": CLI_PHASE3_VERSION,
        "profile": profile.name,
        "config": cfg.redacted_summary(),
        "capabilities": list(caps.capabilities),
        "feature_flags": feature_flags(),
        "plugins": [p.plugin_id for p in list_plugins()],
        "capability_matrix": [
            {
                "capability": r.capability,
                "phase2": r.phase2,
                "phase3": r.phase3,
                "live_required": r.live_required,
            }
            for r in build_capability_matrix()
        ],
        "metrics": get_metrics().snapshot(),
        "cli_example_secret_hits": len(secret_hits),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
