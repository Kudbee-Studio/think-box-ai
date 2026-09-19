"""Publisher for the KILO Agent Marketplace.

Validates, signs, and publishes agent packages.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .package import AgentPackageManifest
from .registry import PackageRegistry

logger = logging.getLogger(__name__)


class PublishError(Exception):
    pass


@dataclass
class PublishRecord:
    package_id: str
    action: str
    timestamp: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)


class PackagePublisher:
    """Publishes and manages agent packages."""

    def __init__(
        self,
        registry: PackageRegistry,
        signing_key: str | None = None,
    ) -> None:
        self.registry = registry
        self._key = signing_key or "default-publish-key"
        self._published: list[PublishRecord] = []

    @property
    def published_count(self) -> int:
        return len(self._published)

    def publish(
        self,
        manifest: AgentPackageManifest,
        sign: bool = True,
    ) -> AgentPackageManifest:
        manifest.package_hash = manifest.compute_hash()
        if sign:
            manifest.signed_by = self._sign_manifest(manifest)
        self.registry.register_available(manifest)
        self._published.append(
            PublishRecord(
                package_id=manifest.id,
                action="publish",
                details={"signed": sign, "signed_by": manifest.signed_by},
            )
        )
        logger.info(f"Published package: {manifest.id}")
        return manifest

    def publish_from_dict(
        self,
        data: dict[str, Any],
        sign: bool = True,
    ) -> AgentPackageManifest:
        manifest = AgentPackageManifest.from_dict(data)
        return self.publish(manifest, sign)

    def update(
        self,
        manifest: AgentPackageManifest,
        sign: bool = True,
    ) -> AgentPackageManifest:
        existing = self.registry.get_available(manifest.id)
        if existing is None:
            raise PublishError(f"Package not found: {manifest.id}")
        manifest.package_hash = manifest.compute_hash()
        if sign:
            manifest.signed_by = self._sign_manifest(manifest)
        self.registry.register_available(manifest)
        self._published.append(
            PublishRecord(
                package_id=manifest.id,
                action="update",
                details={"signed": sign},
            )
        )
        logger.info(f"Updated package: {manifest.id}")
        return manifest

    def deprecate(self, package_id: str) -> bool:
        manifest = self.registry.get_available(package_id)
        if manifest is None:
            return False
        manifest.metadata["deprecated"] = True
        manifest.metadata["deprecated_at"] = datetime.now(timezone.utc).isoformat()
        self._published.append(
            PublishRecord(
                package_id=package_id,
                action="deprecate",
            )
        )
        logger.info(f"Deprecated package: {package_id}")
        return True

    def verify_signature(self, manifest: AgentPackageManifest) -> bool:
        if not manifest.signed_by:
            return False
        expected = self._sign_manifest(manifest)
        return manifest.signed_by == expected

    def list_published(self) -> List[PublishRecord]:
        return list(self._published)

    def get_publish_history(self, package_id: str) -> List[PublishRecord]:
        return [r for r in self._published if r.package_id == package_id]

    def _sign_manifest(self, manifest: AgentPackageManifest) -> str:
        data = manifest.to_dict()
        data.pop("signed_by", None)
        payload = json.dumps(data, sort_keys=True, default=str).encode()
        return hmac.new(self._key.encode(), payload, hashlib.sha256).hexdigest()[:32]
