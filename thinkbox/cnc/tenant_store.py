"""Tenant store for CNC manufacturing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thinkbox.cnc.tenant import Tenant


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
        self.storage_path.mkdir(parents=True, exist_ok=True)
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
