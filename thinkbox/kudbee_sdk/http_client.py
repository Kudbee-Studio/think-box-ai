"""HTTP client with timeouts and retries (PR #177 F05)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk.config import KudbeeSdkConfig
from thinkbox.kudbee_sdk.errors import KudbeeSdkError, transport_error
from thinkbox.kudbee_sdk.observability import correlation_headers
from thinkbox.kudbee_sdk.retry import RetryPolicy, default_retry_policy, run_with_retry
from thinkbox.kudbee_sdk.transport import HttpTransport


def _is_retriable(exc: Exception) -> bool:
    if isinstance(exc, KudbeeSdkError):
        return exc.code == "KUD_BEE_TRANSPORT" and exc.context.get("status", 0) >= 500
    return False


@dataclass
class KudbeeHttpClient:
    config: KudbeeSdkConfig
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

        return run_with_retry(self.retry_policy, "GET", _once, _is_retriable)
