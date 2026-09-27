"""Aggregate wave 2 SDK client facade (PR #181 F22)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_followup_w2.config import SdkFollowupW2Config, load_config_from_env
from thinkbox.kudbee_sdk_followup_w2.dry_run import build_dry_run_transport
from thinkbox.kudbee_sdk_followup_w2.health import fetch_health
from thinkbox.kudbee_sdk_followup_w2.http_client import SdkFollowupW2HttpClient
from thinkbox.kudbee_sdk_followup_w2.negotiation import negotiate


@dataclass
class KudbeeSdkFollowupW2Client:
    config: SdkFollowupW2Config
    http: SdkFollowupW2HttpClient

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> KudbeeSdkFollowupW2Client:
        cfg = load_config_from_env({**(environ or {}), "KUDBEE_SDK_FOLLOWUP_W2_DRY_RUN": "true"})
        transport = build_dry_run_transport(cfg)
        return cls(config=cfg, http=SdkFollowupW2HttpClient(cfg, transport))

    def capabilities(self) -> dict[str, Any]:
        body = self.http.get_json("/api/sdk/v2/capabilities")
        caps = negotiate(
            ("sessions", "tasks", "webhooks", "occupancy"),
            tuple(body.get("capabilities") or ()),
        )
        return {
            "capabilities": list(caps.capabilities),
            "api_version": caps.api_version,
            "live_api_called": False,
        }

    def health(self) -> dict[str, Any]:
        status = fetch_health(self.http)
        return {"ready": status.ready, "detail": status.detail, "live_api_called": False}
