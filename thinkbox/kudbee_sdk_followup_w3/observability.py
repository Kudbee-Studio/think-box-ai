"""Observability hooks for wave 3 SDK (PR #191 F17)."""

from __future__ import annotations

from dataclasses import dataclass, field

from thinkbox.kudbee_sdk_followup_w3.config import SdkFollowupW3Config


@dataclass
class SdkW3Metrics:
    requests: int = 0
    retries: int = 0
    webhook_verifications: int = 0

    def record_request(self) -> None:
        self.requests += 1

    def record_retry(self) -> None:
        self.retries += 1


_metrics = SdkW3Metrics()


def get_metrics() -> SdkW3Metrics:
    return _metrics


def correlation_headers(config: SdkFollowupW3Config, correlation_id: str | None) -> dict[str, str]:
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
