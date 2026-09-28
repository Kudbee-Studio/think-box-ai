"""Health check and readiness probe endpoints.

Provides liveness and readiness checks for Kubernetes-style orchestration
and operational monitoring.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    status: HealthStatus
    message: str
    timestamp: str
    details: dict[str, Any]

    def __post_init__(self):
        """Normalize timestamp."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "details": self.details,
        }

    def is_healthy(self) -> bool:
        """Check if status is healthy."""
        return self.status == HealthStatus.HEALTHY


class HealthCheck:
    """Base health check."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def check(self) -> HealthCheckResult:
        """Run health check."""
        raise NotImplementedError


class ComponentHealthCheck(HealthCheck):
    """Health check for a specific component."""

    def __init__(
        self, name: str, check_fn: Optional[Any] = None, timeout: int = 5
    ) -> None:
        super().__init__(name)
        self.check_fn = check_fn
        self.timeout = timeout

    async def check(self) -> HealthCheckResult:
        """Run health check with timeout."""
        if not self.check_fn:
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="No check function provided",
                timestamp="",
                details={"component": self.name},
            )

        try:
            if asyncio.iscoroutinefunction(self.check_fn):
                result = await asyncio.wait_for(self.check_fn(), timeout=self.timeout)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.check_fn
                )

            if isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                message = f"{self.name} is {'healthy' if result else 'unhealthy'}"
            elif isinstance(result, HealthCheckResult):
                return result
            else:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Invalid result from {self.name}",
                    timestamp="",
                    details={"component": self.name, "result": str(result)},
                )

            return HealthCheckResult(
                status=status,
                message=message,
                timestamp="",
                details={"component": self.name},
            )

        except asyncio.TimeoutError:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"{self.name} check timed out",
                timestamp="",
                details={"component": self.name, "timeout": self.timeout},
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"{self.name} check failed: {str(e)}",
                timestamp="",
                details={"component": self.name, "error": str(e)},
            )


class HealthProbe:
    """Orchestrated health checks for the system."""

    def __init__(self) -> None:
        self.checks: dict[str, HealthCheck] = {}

    def add_check(self, check: HealthCheck) -> None:
        """Add a health check."""
        self.checks[check.name] = check

    async def check_liveness(self) -> HealthCheckResult:
        """Check if system is alive (basic connectivity).

        Returns HEALTHY if the system is running and responsive.
        """
        try:
            # Basic connectivity check
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="System is alive and responsive",
                timestamp="",
                details={"checks_available": len(self.checks)},
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Liveness check failed: {str(e)}",
                timestamp="",
                details={"error": str(e)},
            )

    async def check_readiness(self) -> HealthCheckResult:
        """Check if system is ready to accept traffic.

        Returns HEALTHY only if all critical checks pass.
        """
        if not self.checks:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                message="No health checks registered",
                timestamp="",
                details={},
            )

        results: dict[str, dict[str, Any]] = {}
        all_healthy = True
        has_degraded = False

        for name, check in self.checks.items():
            result = await check.check()
            results[name] = result.to_dict()

            if result.status == HealthStatus.UNHEALTHY:
                all_healthy = False
            elif result.status == HealthStatus.DEGRADED:
                has_degraded = True

        # Determine overall status
        if all_healthy and not has_degraded:
            status = HealthStatus.HEALTHY
            message = "All systems ready"
        elif all_healthy and has_degraded:
            status = HealthStatus.DEGRADED
            message = "System ready but some components degraded"
        else:
            status = HealthStatus.UNHEALTHY
            message = "System not ready; critical checks failed"

        return HealthCheckResult(
            status=status,
            message=message,
            timestamp="",
            details={"checks": results, "total": len(self.checks)},
        )

    async def check_all(self) -> dict[str, HealthCheckResult]:
        """Run all health checks and return results."""
        results = {
            "liveness": await self.check_liveness(),
            "readiness": await self.check_readiness(),
        }

        # Individual check results
        for name, check in self.checks.items():
            results[f"check_{name}"] = await check.check()

        return results


# Standard health checks
class ModelProviderHealthCheck(ComponentHealthCheck):
    """Check model provider connectivity."""

    def __init__(self, timeout: int = 10) -> None:
        async def check_provider() -> bool:
            # Placeholder: actual implementation would test provider connectivity
            return True

        super().__init__("model_provider", check_provider, timeout)


class MemoryStoreHealthCheck(ComponentHealthCheck):
    """Check memory store connectivity."""

    def __init__(self, timeout: int = 5) -> None:
        async def check_memory() -> bool:
            # Placeholder: actual implementation would test memory store
            return True

        super().__init__("memory_store", check_memory, timeout)


class GovernanceHealthCheck(ComponentHealthCheck):
    """Check governance subsystem."""

    def __init__(self, timeout: int = 5) -> None:
        async def check_governance() -> bool:
            # Placeholder: actual implementation would test governance
            return True

        super().__init__("governance", check_governance, timeout)


# Example usage
async def example_health_checks() -> None:
    """Example of using health checks."""
    probe = HealthProbe()

    # Add standard checks
    probe.add_check(ModelProviderHealthCheck())
    probe.add_check(MemoryStoreHealthCheck())
    probe.add_check(GovernanceHealthCheck())

    # Check liveness (should always succeed if system is running)
    liveness = await probe.check_liveness()
    print(f"Liveness: {liveness.to_dict()}")

    # Check readiness (all checks must pass)
    readiness = await probe.check_readiness()
    print(f"Readiness: {readiness.to_dict()}")

    # Check all
    all_checks = await probe.check_all()
    for name, result in all_checks.items():
        print(f"{name}: {result.status.value}")


if __name__ == "__main__":
    asyncio.run(example_health_checks())
