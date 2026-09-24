"""Aggregate wave 3 SDK client facade (PR #191 F22)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_followup_w3.config import SdkFollowupW3Config, load_config_from_env
from thinkbox.kudbee_sdk_followup_w3.dry_run import build_dry_run_transport
from thinkbox.kudbee_sdk_followup_w3.health import fetch_health
from thinkbox.kudbee_sdk_followup_w3.http_client import SdkFollowupW3HttpClient
from thinkbox.kudbee_sdk_followup_w3.negotiation import negotiate


@dataclass
class KudbeeSdkFollowupW3Client:
    config: SdkFollowupW3Config
    http: SdkFollowupW3HttpClient

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> KudbeeSdkFollowupW3Client:
        cfg = load_config_from_env({**(environ or {}), "KUDBEE_SDK_FOLLOWUP_W3_DRY_RUN": "true"})
        transport = build_dry_run_transport(cfg)
        return cls(config=cfg, http=SdkFollowupW3HttpClient(cfg, transport))

    def capabilities(self) -> dict[str, Any]:
        body = self.http.get_json("/api/sdk/v3/capabilities")
        caps = negotiate(
            ("sessions", "tasks", "webhooks", "occupancy", "twin_federation"),
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

    def twin_federation(self) -> dict[str, Any]:
        body = self.http.get_json("/api/sdk/v3/twin/federation")
        return {
            "peer_count": int(body.get("peer_count", 0)),
            "peers": list(body.get("peers") or []),
            "live_api_called": False,
        }
