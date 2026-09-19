"""Middleware: request-id + evidence_label on all control-plane responses."""

import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.base import BaseHTTPMiddleware

from thinkbox.dashboard_state import get_dashboard_state


class ControlPlaneMiddleware(BaseHTTPMiddleware):
    """Add request-id and evidence_label to all control-plane responses."""

    def __init__(self, app: FastAPI):
        super().__init__(app)
        self._app = app
        self._request_ids: Dict[str, str] = {}

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4().hex[:12])
        evidence_label = request.headers.get("x-evidence-label", "simulated")

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Evidence-Label"] = evidence_label

        return response


def setup_control_plane_middleware(app: FastAPI) -> None:
    """Register control-plane middleware."""
    app.add_middleware(ControlPlaneMiddleware)
