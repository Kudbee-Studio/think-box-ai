"""Hermetic Docker build contract checks (enterprise operator gate)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

GATE_ID = "docker-enterprise-contract"

_REQUIRED_DOCKERFILE_SNIPPETS: tuple[str, ...] = (
    "COPY thinkbox/",
    "PYTHONPATH=/app",
    "backend.main:app",
)

_REQUIRED_COMPOSE_SERVICES: tuple[str, ...] = ("api",)


@dataclass(frozen=True)
class DockerContractViolation:
    code: str
    message: str
    path: str | None = None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_docker_contract(repo_root: Path | None = None) -> tuple[bool, tuple[DockerContractViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[DockerContractViolation] = []

    dockerfile = root / "Dockerfile"
    if not dockerfile.is_file():
        violations.append(DockerContractViolation("dockerfile_missing", "Dockerfile not found"))
    else:
        body = _read(dockerfile)
        for snippet in _REQUIRED_DOCKERFILE_SNIPPETS:
            if snippet not in body:
                violations.append(
                    DockerContractViolation("dockerfile_snippet", f"missing {snippet}", path="Dockerfile"),
                )

    hermetic = root / "Dockerfile.hermetic"
    if not hermetic.is_file():
        violations.append(DockerContractViolation("dockerfile_hermetic", "Dockerfile.hermetic missing"))

    ignore = root / ".dockerignore"
    if not ignore.is_file():
        violations.append(DockerContractViolation("dockerignore", ".dockerignore missing"))

    compose = root / "docker-compose.yml"
    if not compose.is_file():
        violations.append(DockerContractViolation("compose_missing", "docker-compose.yml missing"))
    else:
        compose_body = _read(compose)
        for svc in _REQUIRED_COMPOSE_SERVICES:
            if f"{svc}:" not in compose_body:
                violations.append(
                    DockerContractViolation("compose_service", f"missing service {svc}", path="docker-compose.yml"),
                )

    nginx_docker = root / "deploy/nginx.docker.conf"
    if not nginx_docker.is_file():
        violations.append(DockerContractViolation("nginx_docker", "deploy/nginx.docker.conf missing"))

    return (len(violations) == 0, tuple(violations))


def docker_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    ok, violations = validate_docker_contract(repo_root)
    return {
        "gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
