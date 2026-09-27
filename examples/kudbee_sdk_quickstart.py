#!/usr/bin/env python3
"""Hermetic Kudbee SDK quickstart (PR #177) — no live network required."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kudbee_sdk import (
    KudbeeHttpClient,
    bind_receipt_hermetic,
    load_config_from_env,
    negotiate,
)
from thinkbox.kudbee_sdk.dry_run import build_dry_run_transport
from thinkbox.kudbee_sdk.fixtures import load_fixture
from thinkbox.kudbee_sdk.health import fetch_health
from thinkbox.kudbee_sdk.negotiation import SDK_VERSION


def main() -> None:
    config = load_config_from_env({"KUDBEE_SDK_DRY_RUN": "1"})
    transport = build_dry_run_transport(config)
    client = KudbeeHttpClient(config=config, transport=transport)
    health = fetch_health(client)
    fixture = load_fixture("health_ok.json")
    caps = negotiate(("sessions", "tasks"), ("sessions", "tasks", "plugins"))
    proof = bind_receipt_hermetic("rcpt-demo", {"sdk_version": SDK_VERSION})
    print(
        {
            "ready": health.ready,
            "fixture_mode": fixture.get("mode"),
            "capabilities": caps.capabilities,
            "receipt_sha256": proof.payload_sha256[:16],
        },
    )


if __name__ == "__main__":
    main()
