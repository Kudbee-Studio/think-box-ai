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


class MachineAdapter(ABC):
    """Plugin interface for CNC machine adapters."""

    @abstractmethod
    def connect(self, config: dict[str, Any]) -> bool:
        ...

    @abstractmethod
    def disconnect(self) -> bool:
        ...

    @abstractmethod
    def send_gcode(self, gcode: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_machine_status(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def home_axes(self) -> bool:
        ...

    @abstractmethod
    def get_capabilities(self) -> dict[str, Any]:
        ...


class SimMachineAdapter(MachineAdapter):
    """Simulation-only machine adapter for testing and development."""

    def __init__(self, machine_name: str = "Simulated HAAS VF-2SS"):
        self.machine_name = machine_name
        self._connected = False
        self._status = {"status": "idle", "position": {"x": 0, "y": 0, "z": 0}}
        self._gcode_log: list[str] = []

    def connect(self, config: dict[str, Any]) -> bool:
        self._connected = True
        self._status = {"status": "connected", "position": {"x": 0, "y": 0, "z": 0}, "config": config}
        return True

    def disconnect(self) -> bool:
        self._connected = False
        self._status = {"status": "disconnected", "position": {"x": 0, "y": 0, "z": 0}}
        return True

    def send_gcode(self, gcode: str) -> dict[str, Any]:
        if not self._connected:
            return {"success": False, "error": "Not connected"}
        self._gcode_log.append(gcode)
        return {"success": True, "lines_sent": len(gcode.splitlines()), "gcode": gcode}

    def get_machine_status(self) -> dict[str, Any]:
        return {**self._status, "connected": self._connected, "evidence_label": "simulated"}

    def home_axes(self) -> bool:
        if not self._connected:
            return False
        self._status["position"] = {"x": 0, "y": 0, "z": 0}
        self._gcode_log.append("G28")
        return True

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "axes": 3,
            "max_spindle_rpm": 10000,
            "work_envelope_mm": {"x": 762, "y": 406, "z": 508},
            "tool_changer_slots": 20,
            "evidence_label": "simulated",
        }
