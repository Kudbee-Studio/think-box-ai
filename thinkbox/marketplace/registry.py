"""Package registry for the KILO Agent Marketplace.

Tracks available and installed agent packages.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .package import AgentPackageManifest

logger = logging.getLogger(__name__)


@dataclass
class InstalledPackage:
    manifest: AgentPackageManifest
    install_path: str
    installed_at: float = field(default_factory=float)
    status: str = "installed"

    @property
    def id(self) -> str:
        return self.manifest.id


@dataclass
class PackageSearchResult:
    total: int
    packages: List[AgentPackageManifest]
    query: str


class PackageRegistry:
    """Registry for available and installed agent packages."""

    def __init__(self) -> None:
        self._available: Dict[str, AgentPackageManifest] = {}
        self._installed: Dict[str, InstalledPackage] = {}
        self._lock = threading.Lock()
        self._history: list[dict[str, Any]] = []

    @property
    def available_count(self) -> int:
        with self._lock:
            return len(self._available)

    @property
    def installed_count(self) -> int:
        with self._lock:
            return len(self._installed)

    def register_available(self, manifest: AgentPackageManifest) -> None:
        with self._lock:
            self._available[manifest.id] = manifest
            self._record("register_available", manifest.id)
            logger.info(f"Registered available package: {manifest.id}")

    def register_available_batch(self, manifests: List[AgentPackageManifest]) -> int:
        count = 0
        with self._lock:
            for manifest in manifests:
                self._available[manifest.id] = manifest
                count += 1
            self._record("register_available_batch", f"{count} packages")
        return count

    def install(
        self,
        package_id: str,
        install_path: str,
    ) -> InstalledPackage:
        with self._lock:
            manifest = self._available.get(package_id)
            if manifest is None:
                raise ValueError(f"Package not found: {package_id}")
            if package_id in self._installed:
                existing = self._installed[package_id]
                if existing.status == "installed":
                    raise ValueError(f"Package already installed: {package_id}")
            installed = InstalledPackage(
                manifest=manifest,
                install_path=install_path,
                installed_at=datetime.now(timezone.utc).timestamp(),
                status="installed",
            )
            self._installed[package_id] = installed
            self._record("install", package_id, {"path": install_path})
            logger.info(f"Installed package: {package_id} at {install_path}")
            return installed

    def uninstall(self, package_id: str) -> bool:
        with self._lock:
            installed = self._installed.get(package_id)
            if installed is None:
                return False
            installed.status = "uninstalled"
            self._record("uninstall", package_id)
            logger.info(f"Uninstalled package: {package_id}")
            return True

    def is_installed(self, package_id: str) -> bool:
        with self._lock:
            installed = self._installed.get(package_id)
            return installed is not None and installed.status == "installed"

    def get_installed(self, package_id: str) -> Optional[InstalledPackage]:
        with self._lock:
            return self._installed.get(package_id)

    def list_installed(self) -> List[InstalledPackage]:
        with self._lock:
            return [p for p in self._installed.values() if p.status == "installed"]

    def list_available(self) -> List[AgentPackageManifest]:
        with self._lock:
            return list(self._available.values())

    def search(self, query: str) -> PackageSearchResult:
        with self._lock:
            query_lower = query.lower()
            matches = []
            for manifest in self._available.values():
                if (
                    query_lower in manifest.name.lower()
                    or query_lower in manifest.description.lower()
                    or any(query_lower in tag.lower() for tag in manifest.tags)
                    or any(query_lower in cap.lower() for cap in manifest.capabilities)
                ):
                    matches.append(manifest)
            return PackageSearchResult(
                total=len(matches),
                packages=matches,
                query=query,
            )

    def get_available(self, package_id: str) -> Optional[AgentPackageManifest]:
        with self._lock:
            return self._available.get(package_id)

    def get_history(self) -> List[dict[str, Any]]:
        with self._lock:
            return list(self._history)

    def _record(
        self, action: str, target: str, details: dict[str, Any] | None = None
    ) -> None:
        self._history.append(
            {
                "action": action,
                "target": target,
                "details": details or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
