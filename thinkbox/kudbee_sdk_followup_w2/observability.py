"""Observability hooks for wave 2 SDK (PR #181 F17)."""

from __future__ import annotations

from dataclasses import dataclass, field

from thinkbox.kudbee_sdk_followup_w2.config import SdkFollowupW2Config


@dataclass
class SdkW2Metrics:
    requests: int = 0
    retries: int = 0
    webhook_verifications: int = 0

    def record_request(self) -> None:
        self.requests += 1

    def record_retry(self) -> None:
        self.retries += 1


_metrics = SdkW2Metrics()


def get_metrics() -> SdkW2Metrics:
    return _metrics


def correlation_headers(config: SdkFollowupW2Config, correlation_id: str | None) -> dict[str, str]:
    headers = {"accept": "application/json"}
    if correlation_id:
        headers[config.correlation_header] = correlation_id
    return headers


@dataclass
class TraceSpan:
    name: str
    attributes: dict[str, str] = field(default_factory=dict)

    def end(self) -> dict[str, str]:
        return {"span": self.name, **self.attributes}
