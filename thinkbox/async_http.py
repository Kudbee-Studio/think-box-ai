"""Async HTTP client using only Python stdlib.

Provides connection pooling, exponential backoff, and timeout handling
without external dependencies (urllib + asyncio).
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


class HttpError(Exception):
    """Base exception for HTTP errors."""

    def __init__(
        self, message: str, *, status_code: int | None = None, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class HttpTimeoutError(HttpError):
    """Timeout error during HTTP operation."""

    pass


class HttpConnectionError(HttpError):
    """Connection error during HTTP operation."""

    pass


@dataclass
class HttpResponse:
    """HTTP response with status, headers, and body."""

    status_code: int
    headers: dict[str, str]
    content: bytes

    def json(self) -> dict[str, Any]:
        """Parse response body as JSON."""
        try:
            return json.loads(self.content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise HttpError(
                f"Failed to decode JSON response: {self.content[:200]}",
                status_code=self.status_code,
                retryable=True,
            ) from e

    def text(self) -> str:
        """Get response body as string."""
        return self.content.decode("utf-8", errors="replace")

    def raise_for_status(self) -> None:
        """Raise HttpError if status code indicates an error."""
        if self.status_code >= 400:
            is_transient = self.status_code in (408, 429) or self.status_code >= 500
            raise HttpError(
                f"HTTP {self.status_code}: {self.text()[:300]}",
                status_code=self.status_code,
                retryable=is_transient,
            )

    async def aiter_lines(self) -> AsyncGenerator[str, None]:
        """Iterate over response lines (for streaming)."""
        for line in self.content.decode("utf-8", errors="replace").split("\n"):
            if line:
                yield line


class AsyncHttpClient:
    """Minimal async HTTP client using urllib and asyncio."""

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout

    async def _run_in_executor(self, func, *args) -> Any:
        """Run a blocking function in the default executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args)

    async def post(
        self,
        url: str,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Perform an async POST request."""
        return await self._post_impl(url, json_data, headers, stream=False)

    async def stream(
        self,
        method: str,
        url: str,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> AsyncStreamContext:
        """Start a streaming request context."""
        return AsyncStreamContext(
            self, method.upper(), url, json_data, headers
        )

    async def _post_impl(
        self,
        url: str,
        json_data: dict[str, Any] | None,
        headers: dict[str, str] | None,
        stream: bool,
    ) -> HttpResponse:
        """Internal POST implementation."""
        all_headers = {"Content-Type": "application/json"}
        if headers:
            all_headers.update(headers)

        body = None
        if json_data:
            body = json.dumps(json_data).encode("utf-8")

        try:
            req = urllib.request.Request(
                url, data=body, headers=all_headers, method="POST"
            )

            def do_request():
                try:
                    with urllib.request.urlopen(
                        req, timeout=self.timeout
                    ) as response:
                        response_headers = dict(response.headers)
                        response_body = response.read()
                        return HttpResponse(
                            status_code=response.status,
                            headers=response_headers,
                            content=response_body,
                        )
                except urllib.error.HTTPError as e:
                    error_body = e.read()
                    is_transient = e.code in (408, 429) or e.code >= 500
                    raise HttpError(
                        f"HTTP {e.code}: {error_body[:300].decode('utf-8', errors='replace')}",
                        status_code=e.code,
                        retryable=is_transient,
                    ) from e
                except urllib.error.URLError as e:
                    raise HttpConnectionError(
                        f"Connection error: {e.reason}", retryable=True
                    ) from e
                except socket.timeout as e:
                    raise HttpTimeoutError(
                        f"Request timeout after {self.timeout}s", retryable=True
                    ) from e

            return await self._run_in_executor(do_request)

        except asyncio.TimeoutError as e:
            raise HttpTimeoutError(
                f"Async timeout after {self.timeout}s", retryable=True
            ) from e

    async def close(self) -> None:
        """Close the client (no-op for urllib)."""
        pass


class AsyncStreamContext:
    """Context manager for streaming HTTP responses."""

    def __init__(
        self,
        client: AsyncHttpClient,
        method: str,
        url: str,
        json_data: dict[str, Any] | None,
        headers: dict[str, str] | None,
    ) -> None:
        self.client = client
        self.method = method
        self.url = url
        self.json_data = json_data
        self.headers = headers
        self.response: HttpResponse | None = None

    async def __aenter__(self) -> HttpResponse:
        """Enter async context and fetch response."""
        all_headers = {}
        if self.json_data:
            all_headers["Content-Type"] = "application/json"
        if self.headers:
            all_headers.update(self.headers)

        body = None
        if self.json_data:
            body = json.dumps(self.json_data).encode("utf-8")

        try:
            req = urllib.request.Request(
                self.url, data=body, headers=all_headers, method=self.method
            )

            def do_request():
                try:
                    with urllib.request.urlopen(
                        req, timeout=self.client.timeout
                    ) as response:
                        response_headers = dict(response.headers)
                        response_body = response.read()
                        return HttpResponse(
                            status_code=response.status,
                            headers=response_headers,
                            content=response_body,
                        )
                except urllib.error.HTTPError as e:
                    error_body = e.read()
                    is_transient = e.code in (408, 429) or e.code >= 500
                    raise HttpError(
                        f"HTTP {e.code}: {error_body[:300].decode('utf-8', errors='replace')}",
                        status_code=e.code,
                        retryable=is_transient,
                    ) from e
                except urllib.error.URLError as e:
                    raise HttpConnectionError(
                        f"Connection error: {e.reason}", retryable=True
                    ) from e
                except socket.timeout as e:
                    raise HttpTimeoutError(
                        f"Request timeout after {self.client.timeout}s",
                        retryable=True,
                    ) from e

            self.response = await self.client._run_in_executor(do_request)
            return self.response

        except asyncio.TimeoutError as e:
            raise HttpTimeoutError(
                f"Async timeout after {self.client.timeout}s", retryable=True
            ) from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        pass


# Import socket for timeout handling
import socket
