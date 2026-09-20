"""GitHub webhook receiver — signature verification + governed lifecycle dispatch."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Request, Response

from thinkbox.admission import AdmissionGate
from thinkbox.github_webhook import (
    DEFAULT_WEBHOOK_AGENT_ID,
    GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY,
    GitHubWebhookLifecycleService,
)
from thinkbox.governance_token import GovernanceTokenService
from thinkbox.identity import IdentityLedger
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pr_lifecycle_event_hooks import PRLifecycleEventCoordinator

github_webhook_router = APIRouter(
    prefix="/api/v1/github",
    tags=["github", "lifecycle"],
)

_DEFAULT_DB = os.getenv(
    "THINKBOX_ORG_MEMORY_DB",
    os.path.join("data", "thinkboxmd", "db", "org_memory_receipts.db"),
)


def _webhook_secret() -> str:
    return os.getenv("WEBHOOK_SECRET", os.getenv("GITHUB_WEBHOOK_SECRET", ""))


def _governance_token_value() -> str:
    return os.getenv("THINKBOX_GITHUB_WEBHOOK_GOVERNANCE_TOKEN", "")


def _agent_id() -> str:
    return os.getenv("THINKBOX_GITHUB_WEBHOOK_AGENT_ID", DEFAULT_WEBHOOK_AGENT_ID)


def build_github_webhook_service(
    *,
    webhook_secret: str,
    governance_token: str,
    agent_id: str,
    db_path: str | None = None,
    test_mode: bool = True,
) -> GitHubWebhookLifecycleService:
    """Construct a webhook service (used by tests and the FastAPI route)."""
    store = OrgMemoryReceiptStore(db_path or _DEFAULT_DB)
    coordinator = PRLifecycleEventCoordinator(store, test_mode=test_mode)
    tokens = GovernanceTokenService(
        signing_key=os.getenv("THINKBOX_GOVERNANCE_SIGNING_KEY", "github-webhook-dev-key"),
    )
    identities = IdentityLedger()
    identities.register(agent_id=agent_id, capabilities=[GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY])
    gate = AdmissionGate(tokens, identities)
    return GitHubWebhookLifecycleService(
        webhook_secret=webhook_secret,
        store=store,
        coordinator=coordinator,
        gate=gate,
        governance_token=governance_token,
        agent_id=agent_id,
    )


@lru_cache(maxsize=1)
def _cached_service() -> GitHubWebhookLifecycleService:
    return build_github_webhook_service(
        webhook_secret=_webhook_secret(),
        governance_token=_governance_token_value(),
        agent_id=_agent_id(),
        test_mode=os.getenv("THINKBOX_GITHUB_WEBHOOK_TEST_MODE", "true").lower() != "false",
    )


def reset_github_webhook_service_cache() -> None:
    """Clear the process-local service singleton (tests)."""
    _cached_service.cache_clear()


@github_webhook_router.post("/webhook")
async def receive_github_webhook(request: Request) -> Response:
    """Receive GitHub deliveries; verify HMAC; never auto-merge."""
    body = await request.body()
    event_type = request.headers.get("X-GitHub-Event", "")
    signature = request.headers.get("X-Hub-Signature-256")
    service = _cached_service()
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    drill_corr = request.headers.get("X-Thinkbox-Live-Drill-Correlation", "")
    result = service.process(
        body,
        event_type,
        signature,
        delivery_id=delivery_id or None,
        drill_correlation_id=drill_corr or None,
    )
    import json

    return Response(
        content=json.dumps(result.to_response_body()),
        status_code=result.http_status,
        media_type="application/json",
    )


@github_webhook_router.get("/webhook/health")
async def github_webhook_health() -> dict[str, Any]:
    """Non-secret readiness probe for webhook configuration."""
    secret_configured = bool(_webhook_secret())
    token_configured = bool(_governance_token_value())
    return {
        "webhook_secret_configured": secret_configured,
        "governance_token_configured": token_configured,
        "agent_id": _agent_id(),
        "capability": GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY,
        "auto_merge": False,
        "evidence_label": "simulated",
    }
