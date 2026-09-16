"""Tenant boundary for CNC manufacturing."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class TenantPlan(str, Enum):
    FREE = "free"
    PROFESSIONAL = "professional"
    SHOP = "shop"
    ENTERPRISE = "enterprise"
    AUTONOMOUS = "autonomous"


@dataclass
class TenantPermission:
    permission_id: str = ""
    tenant_id: str = ""
    resource: str = ""
    action: str = ""
    granted: bool = True

    def __post_init__(self) -> None:
        if not self.permission_id:
            self.permission_id = f"perm-{uuid.uuid4().hex[:8]}"

    def model_dump(self) -> dict[str, Any]:
        return {"permission_id": self.permission_id, "tenant_id": self.tenant_id, "resource": self.resource, "action": self.action, "granted": self.granted}


@dataclass
class Tenant:
    tenant_id: str = ""
    name: str = ""
    domain: str = ""
    plan: str = "professional"
    max_jobs: int = 100
    users: list[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.tenant_id:
            self.tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def model_dump(self) -> dict[str, Any]:
        return {"tenant_id": self.tenant_id, "name": self.name, "domain": self.domain, "plan": self.plan, "max_jobs": self.max_jobs, "users": self.users, "created_at": self.created_at}


class TenantBoundary:
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.permissions: list[TenantPermission] = []

    def check_access(self, resource: str, action: str) -> bool:
        for p in self.permissions:
            if p.resource == resource and p.action == action and p.granted:
                return True
        return False

    def grant_permission(self, resource: str, action: str) -> TenantPermission:
        perm = TenantPermission(tenant_id=self.tenant.tenant_id, resource=resource, action=action)
        self.permissions.append(perm)
        return perm

    def model_dump(self) -> dict[str, Any]:
        return {"tenant": self.tenant.model_dump(), "permissions": [p.model_dump() for p in self.permissions]}


class TenantStore:
    def __init__(self, storage_path: str = "data/cnc/tenants"):
        self.storage_path = Path(storage_path)
        self._tenants: list[Tenant] = []
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        for f in self.storage_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                tenant = Tenant(**data)
                self._tenants.append(tenant)
            except (json.JSONDecodeError, ValueError):
                continue

    def _save(self, tenant: Tenant) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        f = self.storage_path / f"{tenant.tenant_id}.json"
        f.write_text(json.dumps(tenant.model_dump(), indent=2))

    def create_tenant(self, name: str, domain: str = "", plan: str = "professional", max_jobs: int = 100) -> Tenant:
        tenant = Tenant(name=name, domain=domain, plan=plan, max_jobs=max_jobs)
        self._tenants.append(tenant)
        self._save(tenant)
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        for t in self._tenants:
            if t.tenant_id == tenant_id:
                return t
        return None

    def list_tenants(self) -> list[Tenant]:
        return self._tenants
