"""Agent package format and manifest schema for the KILO Agent Marketplace."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class PackageDependency:
    name: str
    version_spec: str = "*"
    optional: bool = False

    def matches(self, version: str) -> bool:
        if self.version_spec == "*":
            return True
        return _version_satisfies(version, self.version_spec)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version_spec": self.version_spec,
            "optional": self.optional,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackageDependency:
        return cls(
            name=data["name"],
            version_spec=data.get("version_spec", "*"),
            optional=data.get("optional", False),
        )


@dataclass
class PackageEntryPoint:
    module: str
    attribute: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "attribute": self.attribute,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackageEntryPoint:
        return cls(
            module=data["module"],
            attribute=data["attribute"],
            description=data.get("description", ""),
        )


@dataclass
class AgentPackageManifest:
    name: str
    version: str
    manifest_version: str = "1.0"
    description: str = ""
    author: str = ""
    license: str = ""
    entry_points: list[PackageEntryPoint] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[PackageDependency] = field(default_factory=list)
    min_python: str = "3.10"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    package_hash: str = ""
    signed_by: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def id(self) -> str:
        return f"{self.name}@{self.version}"

    def compute_hash(self) -> str:
        payload = json.dumps(
            {
                "name": self.name,
                "version": self.version,
                "manifest_version": self.manifest_version,
                "description": self.description,
                "author": self.author,
                "license": self.license,
                "entry_points": [e.to_dict() for e in self.entry_points],
                "capabilities": self.capabilities,
                "dependencies": [d.to_dict() for d in self.dependencies],
                "min_python": self.min_python,
                "tags": self.tags,
                "metadata": self.metadata,
            },
            sort_keys=True,
            default=str,
        ).encode()
        return hashlib.sha256(payload).hexdigest()[:32]

    def verify_hash(self) -> bool:
        if not self.package_hash:
            return False
        return self.package_hash == self.compute_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "manifest_version": self.manifest_version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "entry_points": [e.to_dict() for e in self.entry_points],
            "capabilities": self.capabilities,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "min_python": self.min_python,
            "tags": self.tags,
            "metadata": self.metadata,
            "package_hash": self.package_hash,
            "signed_by": self.signed_by,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentPackageManifest:
        entry_points = [
            PackageEntryPoint.from_dict(ep) for ep in data.get("entry_points", [])
        ]
        dependencies = [
            PackageDependency.from_dict(d) for d in data.get("dependencies", [])
        ]
        return cls(
            name=data["name"],
            version=data["version"],
            manifest_version=data.get("manifest_version", "1.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            license=data.get("license", ""),
            entry_points=entry_points,
            capabilities=data.get("capabilities", []),
            dependencies=dependencies,
            min_python=data.get("min_python", "3.10"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            package_hash=data.get("package_hash", ""),
            signed_by=data.get("signed_by"),
            created_at=data.get(
                "created_at", datetime.now(timezone.utc).isoformat()
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> AgentPackageManifest:
        return cls.from_dict(json.loads(text))


def _version_satisfies(version: str, spec: str) -> bool:
    if spec == "*":
        return True
    match = re.match(r"^([><=!~]+)?\s*(\d+\.\d+\.\d+)$", spec)
    if not match:
        return False
    op, target = match.groups()
    op = op or "=="
    return _compare_versions(version, target, op)


def _parse_version(v: str) -> tuple[int, int, int]:
    parts = v.split(".")
    return (
        int(parts[0]) if len(parts) > 0 else 0,
        int(parts[1]) if len(parts) > 1 else 0,
        int(parts[2]) if len(parts) > 2 else 0,
    )


def _compare_versions(a: str, b: str, op: str) -> bool:
    va = _parse_version(a)
    vb = _parse_version(b)
    if op == "==":
        return va == vb
    elif op == "!=":
        return va != vb
    elif op == ">":
        return va > vb
    elif op == ">=":
        return va >= vb
    elif op == "<":
        return va < vb
    elif op == "<=":
        return va <= vb
    elif op == "~=":
        return va[0] == vb[0] and va >= vb
    return False
