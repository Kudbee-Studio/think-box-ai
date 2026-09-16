"""CNC adapter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CADInterface(ABC):
    @abstractmethod
    def load_design(self, file_path: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def export_gcode(self, design: dict[str, Any]) -> str:
        ...


class MachineControllerInterface(ABC):
    @abstractmethod
    def send_command(self, command: str) -> str:
        ...

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def emergency_stop(self) -> bool:
        ...


class InspectionSystemInterface(ABC):
    @abstractmethod
    def measure(self, job_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def generate_report(self, job_id: str) -> str:
        ...


class SimulatorInterface(ABC):
    @abstractmethod
    def simulate(self, job_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def verify_toolpath(self, job_id: str) -> bool:
        ...


class ShopDatabaseInterface(ABC):
    @abstractmethod
    def get_material(self, grade: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_machine(self, name: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def log_operation(self, job_id: str, operation: str) -> bool:
        ...


class CNCAdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, Any] = {}

    def register(self, name: str, adapter: Any) -> None:
        self._adapters[name] = adapter

    def get(self, name: str) -> Any | None:
        return self._adapters.get(name)

    def list_adapters(self) -> list[str]:
        return list(self._adapters.keys())
