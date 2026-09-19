"""Installer for the KILO Agent Marketplace.

Validates, installs, and uninstalls agent packages.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from typing import Any, Dict, List, Optional

from .package import AgentPackageManifest
from .registry import InstalledPackage, PackageRegistry

logger = logging.getLogger(__name__)


class InstallError(Exception):
    pass


class ValidationError(Exception):
    pass


class PackageInstaller:
    """Validates and installs agent packages."""

    def __init__(self, registry: PackageRegistry, base_path: str = "/opt/thinkbox/agents") -> None:
        self._registry = registry
        self._base_path = base_path
        self._install_log: list[dict[str, Any]] = []

    @property
    def base_path(self) -> str:
        return self._base_path

    @property
    def install_count(self) -> int:
        return len(self._install_log)

    def validate(self, manifest: AgentPackageManifest) -> List[str]:
        errors: List[str] = []
        if not manifest.name:
            errors.append("Package name is required")
        if not manifest.version:
            errors.append("Package version is required")
        if not _is_valid_version(manifest.version):
            errors.append(
                f"Invalid version format: {manifest.version} (expected semver)"
            )
        if not manifest.entry_points:
            errors.append("Package must have at least one entry point")
        for ep in manifest.entry_points:
            if not ep.module:
                errors.append("Entry point module is required")
            if not ep.attribute:
                errors.append("Entry point attribute is required")
        for dep in manifest.dependencies:
            if not dep.name:
                errors.append("Dependency name is required")
            if not _is_valid_version_spec(dep.version_spec):
                errors.append(
                    f"Invalid version spec: {dep.version_spec} for {dep.name}"
                )
        if not manifest.verify_hash():
            errors.append("Package hash verification failed")
        return errors

    def install(
        self,
        manifest: AgentPackageManifest,
        install_path: Optional[str] = None,
    ) -> InstalledPackage:
        errors = self.validate(manifest)
        if errors:
            raise ValidationError(f"Validation failed: {'; '.join(errors)}")

        target_path = install_path or os.path.join(self._base_path, manifest.name)
        package_id = manifest.id

        if self._registry.is_installed(package_id):
            raise InstallError(f"Package already installed: {package_id}")

        self._registry.register_available(manifest)

        try:
            os.makedirs(target_path, exist_ok=True)
            manifest_path = os.path.join(target_path, "manifest.json")
            with open(manifest_path, "w") as f:
                json.dump(manifest.to_dict(), f, indent=2)
        except Exception as e:
            raise InstallError(f"Failed to write manifest: {e}")

        installed = self._registry.install(package_id, target_path)
        self._install_log.append(
            {
                "package": package_id,
                "path": target_path,
                "action": "install",
            }
        )
        logger.info(f"Successfully installed: {package_id}")
        return installed

    def install_from_dict(
        self,
        data: dict[str, Any],
        install_path: Optional[str] = None,
    ) -> InstalledPackage:
        manifest = AgentPackageManifest.from_dict(data)
        return self.install(manifest, install_path)

    def install_from_json(
        self,
        text: str,
        install_path: Optional[str] = None,
    ) -> InstalledPackage:
        manifest = AgentPackageManifest.from_json(text)
        return self.install(manifest, install_path)

    def uninstall(self, package_id: str) -> bool:
        installed = self._registry.get_installed(package_id)
        if installed is None:
            return False
        success = self._registry.uninstall(package_id)
        if success and os.path.isdir(installed.install_path):
            try:
                shutil.rmtree(installed.install_path)
            except Exception as e:
                logger.warning(f"Failed to remove install dir: {e}")
        self._install_log.append(
            {
                "package": package_id,
                "action": "uninstall",
            }
        )
        return success

    def list_installed(self) -> List[InstalledPackage]:
        return self._registry.list_installed()

    def get_install_log(self) -> List[dict[str, Any]]:
        return list(self._install_log)


def _is_valid_version(version: str) -> bool:
    import re
    return bool(re.match(r"^\d+\.\d+\.\d+$", version))


def _is_valid_version_spec(spec: str) -> bool:
    import re
    if spec == "*":
        return True
    return bool(re.match(r"^([><=!~]+)?\s*\d+\.\d+\.\d+$", spec))
