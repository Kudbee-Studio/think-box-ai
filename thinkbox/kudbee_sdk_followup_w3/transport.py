"""Hermetic transport abstraction for wave 3 (PR #191 F12)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_s: float,
    ) -> HttpResponse:
        ...


@dataclass
class InMemoryTransport:
    routes: dict[tuple[str, str], HttpResponse]

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_s: float,
    ) -> HttpResponse:
        key = (method.upper(), url)
        if key not in self.routes:
            return HttpResponse(
                status=404,
                headers={"x-kudbee-transport": "in-memory-miss"},
                body=b'{"error":"route_not_registered","live_api_called":false}',
            )
        return self.routes[key]
