"""Occupancy mesh stub for hermetic SDK consumers (PR #191 F14)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OccupancyCell:
    cell_id: str
    load: float
    admitted: bool = True


@dataclass
class OccupancyMeshStub:
    cells: list[OccupancyCell] = field(default_factory=list)

    def register(self, cell_id: str, load: float = 0.0) -> OccupancyCell:
        cell = OccupancyCell(cell_id=cell_id, load=load)
        self.cells.append(cell)
        return cell

    def snapshot(self) -> dict[str, Any]:
        return {
            "cells": [{"cell_id": c.cell_id, "load": c.load, "admitted": c.admitted} for c in self.cells],
            "live_api_called": False,
            "evidence_label": "simulated",
        }
