"""HTTP client with timeouts and retry stubs (PR #191 F05)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_followup_w3.config import SdkFollowupW3Config
from thinkbox.kudbee_sdk_followup_w3.errors import SdkFollowupW3Error, transport_error
from thinkbox.kudbee_sdk_followup_w3.observability import correlation_headers, get_metrics
from thinkbox.kudbee_sdk_followup_w3.retry import RetryPolicy, default_retry_policy, run_with_retry
from thinkbox.kudbee_sdk_followup_w3.transport import HttpTransport


def _is_retriable(exc: Exception) -> bool:
    if isinstance(exc, SdkFollowupW3Error):
        return exc.code == "SDK_W3_TRANSPORT" and exc.context.get("status", 0) >= 500
    return False


@dataclass
class SdkFollowupW3HttpClient:
    config: SdkFollowupW3Config
    transport: HttpTransport
    retry_policy: RetryPolicy | None = None
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if self.retry_policy is None:
            self.retry_policy = default_retry_policy(self.config.max_retries + 1)

    def get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        headers = correlation_headers(self.config, self.correlation_id)

        def _once(_attempt: int) -> dict[str, Any]:
            get_metrics().record_request()
            resp = self.transport.request(
                "GET",
                url,
                headers,
                None,
                self.config.request_timeout_s,
            )
            if resp.status >= 500:
                raise transport_error("server error", status=resp.status)
            if resp.status >= 400:
                raise transport_error("client error", status=resp.status)
            return json.loads(resp.body.decode("utf-8") or "{}")

        return run_with_retry(_once, self.retry_policy, _is_retriable)
