"""UpCloud execution provider for THINK BOX AI.

Implements ExecutionProvider for UpCloud infrastructure using the
UpCloud REST API. Uses only stdlib (urllib) — no external dependencies.

Authentication: reads `UPCLOUD_API_KEY` from environment (never logged,
never stored, never serialized).

All capability checks are honest: VERIFIED means the API call succeeded,
DENIED means the API returned an auth/permission error, NOT_TESTED means
the capability was not exercised, REQUIRES_ADMIN_APPROVAL means the
operation needs explicit approval before execution.
"""

from __future__ import annotations

import datetime
import json
import os
import urllib.error
import urllib.request
from typing import Any

from core.providers.execution import (
    CapabilityCheck,
    CapabilityStatus,
    ExecutionPlan,
    ExecutionProvider,
    ExecutionProviderCapabilities,
    ExecutionResult,
    EvidenceRecord,
    ProviderExecutionRegistry,
)
from core.foundation.errors import ProviderError, ProviderUnavailableError


@ProviderExecutionRegistry.register("upcloud")
class UpCloudExecutionProvider(ExecutionProvider):
    """UpCloud infrastructure provider via REST API."""

    BASE_URL = "https://api.upcloud.com/v1"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        super().__init__(config)
        self._api_key: str = config.get(
            "api_key", os.environ.get("UPCLOUD_API_KEY", "")
        )
        self._auth_checked = False
        self._auth_status = "untested"
        self._capabilities: ExecutionProviderCapabilities | None = None

    @property
    def provider_name(self) -> str:
        return "upcloud"

    def _auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _request(
        self, method: str, path: str, params: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any] | None]:
        url = f"{self.BASE_URL}{path}"
        data: bytes | None = None
        headers = {
            "Content-Type": "application/json",
            **self._auth_header(),
        }
        if params is not None:
            data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body) if body else None
                return resp.status, parsed
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if hasattr(e, "read") else ""
            try:
                parsed = json.loads(body) if body else None
            except (json.JSONDecodeError, ValueError):
                parsed = None
            return e.code, parsed
        except urllib.error.URLError as e:
            raise ProviderUnavailableError(
                f"UpCloud connection failed: {e.reason}"
            ) from e

    def check_auth(self) -> CapabilityCheck:
        self._auth_checked = True
        if not self._api_key:
            self._auth_status = "no_credentials"
            return CapabilityCheck(
                capability="authentication",
                status=CapabilityStatus.DENIED,
                detail="No UPCLOUD_API_KEY configured",
            )
        try:
            status, _ = self._request("GET", "/account")
            if status == 200:
                self._auth_status = "authenticated"
                return CapabilityCheck(
                    capability="authentication",
                    status=CapabilityStatus.VERIFIED,
                    detail="Authentication successful",
                )
            elif status == 401:
                self._auth_status = "denied"
                return CapabilityCheck(
                    capability="authentication",
                    status=CapabilityStatus.DENIED,
                    detail="HTTP 401 — invalid or expired API token",
                )
            elif status == 403:
                self._auth_status = "forbidden"
                return CapabilityCheck(
                    capability="authentication",
                    status=CapabilityStatus.REQUIRES_ADMIN_APPROVAL,
                    detail=f"HTTP 403 — access forbidden, admin approval required",
                )
            else:
                self._auth_status = f"http_{status}"
                return CapabilityCheck(
                    capability="authentication",
                    status=CapabilityStatus.DENIED,
                    detail=f"HTTP {status}",
                )
        except ProviderUnavailableError:
            self._auth_status = "unreachable"
            return CapabilityCheck(
                capability="authentication",
                status=CapabilityStatus.DENIED,
                detail="UpCloud API unreachable",
            )
        except Exception as e:
            self._auth_status = "error"
            return CapabilityCheck(
                capability="authentication",
                status=CapabilityStatus.DENIED,
                detail=f"Auth check failed: {e}",
            )

    def discover_capabilities(self) -> list[CapabilityCheck]:
        checks: list[CapabilityCheck] = []
        auth = self.check_auth()
        checks.append(auth)

        if auth.status == CapabilityStatus.DENIED:
            for cap in self._all_capability_names():
                checks.append(
                    CapabilityCheck(
                        capability=cap,
                        status=CapabilityStatus.NOT_TESTED,
                        detail="Auth denied; capabilities not tested",
                    )
                )
            self._capabilities = ExecutionProviderCapabilities()
            return checks
        if auth.status == CapabilityStatus.REQUIRES_ADMIN_APPROVAL:
            for cap in self._all_capability_names():
                checks.append(
                    CapabilityCheck(
                        capability=cap,
                        status=CapabilityStatus.REQUIRES_ADMIN_APPROVAL,
                        detail="Admin approval required for all operations",
                    )
                )
            self._capabilities = ExecutionProviderCapabilities()
            return checks

        capability_map: list[tuple[str, str]] = [
            ("list_servers", "/server"),
            ("get_server", "/server/0"),
            ("create_server", "/server", "POST"),
            ("delete_server", "/server/0", "DELETE"),
            ("list_storage", "/storage"),
            ("get_storage", "/storage/0"),
            ("create_storage", "/storage", "POST"),
            ("delete_storage", "/storage/0", "DELETE"),
            ("list_networks", "/network"),
            ("get_ip", "/iplist"),
            ("assign_ip", "/iplist/0", "POST"),
            ("list_locations", "/location"),
            ("discover_gpu", "/server?type=gpu"),
            ("check_availability", "/server", "HEAD"),
            ("create_server_from_template", "/server", "POST"),
            ("reboot_server", "/server/0/reboot", "POST"),
        ]

        for cap_name, path, *method in capability_map:
            http_method = method[0] if method else "GET"
            try:
                status, _ = self._request(http_method, path)
                if status == 200:
                    checks.append(
                        CapabilityCheck(
                            capability=cap_name,
                            status=CapabilityStatus.VERIFIED,
                            detail=f"HTTP {status}",
                        )
                    )
                elif status == 401:
                    checks.append(
                        CapabilityCheck(
                            capability=cap_name,
                            status=CapabilityStatus.DENIED,
                            detail=f"HTTP {status} — auth failed",
                        )
                    )
                elif status == 403:
                    checks.append(
                        CapabilityCheck(
                            capability=cap_name,
                            status=CapabilityStatus.REQUIRES_ADMIN_APPROVAL,
                            detail=f"HTTP {status} — permission denied",
                        )
                    )
                else:
                    checks.append(
                        CapabilityCheck(
                            capability=cap_name,
                            status=CapabilityStatus.NOT_TESTED,
                            detail=f"HTTP {status}",
                        )
                    )
            except Exception as e:
                checks.append(
                    CapabilityCheck(
                        capability=cap_name,
                        status=CapabilityStatus.NOT_TESTED,
                        detail=f"Check failed: {e}",
                    )
                )

        self._capabilities = ExecutionProviderCapabilities()
        for check in checks:
            self._set_capability_status(check.capability, check.status)
        return checks

    def _all_capability_names(self) -> list[str]:
        return [
            "list_servers", "get_server", "create_server", "delete_server",
            "list_storage", "get_storage", "create_storage", "delete_storage",
            "list_networks", "get_ip", "assign_ip", "list_locations",
            "discover_gpu", "check_availability", "create_server_from_template",
            "reboot_server",
        ]

    def _set_capability_status(
        self, capability: str, status: CapabilityStatus
    ) -> None:
        mapping = {
            "list_servers": "list_servers",
            "get_server": "get_server",
            "create_server": "create_server",
            "delete_server": "delete_server",
            "list_storage": "list_storage",
            "get_storage": "get_storage",
            "create_storage": "create_storage",
            "delete_storage": "delete_storage",
            "list_networks": "list_networks",
            "get_ip": "get_ip",
            "assign_ip": "assign_ip",
            "list_locations": "list_locations",
            "discover_gpu": "discover_gpu",
            "check_availability": "check_availability",
            "create_server_from_template": "create_server_from_template",
            "reboot_server": "reboot_server",
        }
        attr = mapping.get(capability)
        if attr and self._capabilities:
            setattr(self._capabilities, attr, status)

    def plan(
        self,
        job_id: str,
        actions: list[dict[str, Any]],
        dry_run: bool = True,
    ) -> ExecutionPlan:
        return super().plan(job_id, actions, dry_run=dry_run)

    def execute(
        self,
        job_id: str,
        action: str,
        params: dict[str, Any] | None = None,
        approve: bool = False,
    ) -> ExecutionResult:
        params = params or {}
        destructive = action in ("delete_server", "delete_storage")
        billable = action in ("create_server", "create_storage", "create_server_from_template")
        requires_approval = destructive or billable

        if requires_approval and not approve:
            self._record_evidence(
                job_id=job_id,
                action=action,
                auth_state=self._auth_status,
                result="DENIED — explicit approval required",
                verification="approval_required",
                dry_run=True,
            )
            return ExecutionResult(
                action=action,
                success=False,
                error=f"Action '{action}' requires explicit approval (destructive={destructive}, billable={billable})",
                dry_run=True,
            )

        if not self._auth_checked:
            self.check_auth()

        if self._auth_status != "authenticated":
            self._record_evidence(
                job_id=job_id,
                action=action,
                auth_state=self._auth_status,
                result="DENIED — not authenticated",
                verification="auth_failed",
                dry_run=False,
            )
            return ExecutionResult(
                action=action,
                success=False,
                error=f"Not authenticated (status: {self._auth_status})",
                dry_run=False,
            )

        method_map = {
            "list_servers": ("GET", "/server"),
            "get_server": ("GET", f"/server/{params.get('server_uuid', '0')}"),
            "create_server": ("POST", "/server"),
            "delete_server": ("DELETE", f"/server/{params.get('server_uuid', '0')}"),
            "list_storage": ("GET", "/storage"),
            "get_storage": ("GET", f"/storage/{params.get('storage_uuid', '0')}"),
            "create_storage": ("POST", "/storage"),
            "delete_storage": ("DELETE", f"/storage/{params.get('storage_uuid', '0')}"),
            "list_networks": ("GET", "/network"),
            "get_ip": ("GET", "/iplist"),
            "assign_ip": ("POST", f"/iplist/{params.get('ip_id', '0')}"),
            "list_locations": ("GET", "/location"),
            "discover_gpu": ("GET", "/server?type=gpu"),
            "reboot_server": ("POST", f"/server/{params.get('server_uuid', '0')}/reboot"),
        }

        if action not in method_map:
            self._record_evidence(
                job_id=job_id,
                action=action,
                auth_state=self._auth_status,
                result="DENIED — unknown action",
                verification="unknown_action",
                dry_run=False,
            )
            return ExecutionResult(
                action=action,
                success=False,
                error=f"Unknown action: {action}",
                dry_run=False,
            )

        method, path = method_map[action]
        try:
            status, body = self._request(method, path, params if method == "POST" else None)
            if status in (200, 201):
                resource_id = ""
                if body and isinstance(body, dict):
                    resource_id = body.get("uuid", body.get("id", ""))
                self._record_evidence(
                    job_id=job_id,
                    action=action,
                    auth_state=self._auth_status,
                    result="SUCCESS" if status == 200 else "CREATED",
                    resource_id=resource_id,
                    verification="http_ok",
                    dry_run=False,
                )
                return ExecutionResult(
                    action=action,
                    success=True,
                    resource_id=resource_id,
                    output=f"HTTP {status}",
                    dry_run=False,
                )
            else:
                detail = ""
                if body and isinstance(body, dict):
                    detail = json.dumps(body)[:200]
                self._record_evidence(
                    job_id=job_id,
                    action=action,
                    auth_state=self._auth_status,
                    result=f"FAILED — HTTP {status}",
                    verification=f"http_{status}",
                    dry_run=False,
                )
                return ExecutionResult(
                    action=action,
                    success=False,
                    error=f"HTTP {status}: {detail}",
                    dry_run=False,
                )
        except ProviderUnavailableError as e:
            self._record_evidence(
                job_id=job_id,
                action=action,
                auth_state=self._auth_status,
                result=f"FAILED — {e}",
                verification="connection_error",
                dry_run=False,
            )
            return ExecutionResult(
                action=action,
                success=False,
                error=str(e),
                dry_run=False,
            )
        except Exception as e:
            self._record_evidence(
                job_id=job_id,
                action=action,
                auth_state=self._auth_status,
                result=f"FAILED — {e}",
                verification="exception",
                dry_run=False,
            )
            return ExecutionResult(
                action=action,
                success=False,
                error=str(e),
                dry_run=False,
            )
