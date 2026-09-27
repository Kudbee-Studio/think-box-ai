"""HTTP client with timeouts for long-range energy SDK (PR #193 F05)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_longrange_energy.config import SdkLrEnergyConfig
from thinkbox.kudbee_sdk_longrange_energy.errors import transport_error
from thinkbox.kudbee_sdk_longrange_energy.observability import correlation_headers, get_metrics
from thinkbox.kudbee_sdk_longrange_energy.transport import HttpTransport


@dataclass
class SdkLrEnergyHttpClient:
    config: SdkLrEnergyConfig
    transport: HttpTransport
    correlation_id: str | None = None

    def get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        headers = correlation_headers(self.config, self.correlation_id)
        get_metrics().record_request()
        resp = self.transport.request(
            "GET",
            url,
            headers,
            None,
            self.config.request_timeout_s,
        )
        if resp.status >= 400:
            raise transport_error("http error", status=resp.status)
        return json.loads(resp.body.decode("utf-8") or "{}")
