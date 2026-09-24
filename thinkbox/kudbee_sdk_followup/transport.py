"""Hermetic transport abstraction (PR #179 F15)."""

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
    """Deterministic transport for hermetic tests and dry-run."""

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
            return HttpResponse(status=404, headers={}, body=b"{}")
        return self.routes[key]
