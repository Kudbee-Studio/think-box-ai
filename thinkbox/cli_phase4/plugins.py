"""Hermetic plugin / extension registry stub (PR #196 F13)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CliPlugin:
    plugin_id: str
    version: str
    entrypoint: str


_BUILTIN: tuple[CliPlugin, ...] = (
    CliPlugin("core.inspect", "1.0", "thinkbox.cli_inspect"),
    CliPlugin("phase2.toolkit", "0.1", "thinkbox.cli_phase2"),
    CliPlugin("phase3.toolkit", "0.1", "thinkbox.cli_phase4"),
)


def list_plugins() -> tuple[CliPlugin, ...]:
    return _BUILTIN


def get_plugin(plugin_id: str) -> CliPlugin | None:
    for p in _BUILTIN:
        if p.plugin_id == plugin_id:
            return p
    return None
