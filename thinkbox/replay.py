"""KUDBEE — Swarm Genome Replay.

Reproduces a past swarm run from its recorded genome (session metadata:
goal, engine config) and verifies it against the original summary.

Nondeterministic fields (total_time_ms, events) are excluded from MISMATCH
verdicts since timing and event counts vary between runs.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field, replace
from typing import Any

from thinkbox.engine import EngineConfig
from thinkbox.flightrecorder import FlightRecorder


class ReplayError(Exception):
    """Raised when a replay cannot be resolved, restored, or executed."""


@dataclass
class ReplayResult:
    session_id: str
    goal: str
    verdict: str
    genome_verified: bool
    original_summary: dict[str, Any] = field(default_factory=dict)
    replay_summary: dict[str, Any] = field(default_factory=dict)
    mismatch_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "verdict": self.verdict,
            "genome_verified": self.genome_verified,
            "original_summary": self.original_summary,
            "replay_summary": self.replay_summary,
            "mismatch_fields": list(self.mismatch_fields),
        }


class ReplayDriver:
    """Reproduce a past swarm run from session metadata and genome."""

    _NONDETERMINISTIC: frozenset[str] = frozenset({"total_time_ms", "events"})

    def __init__(
        self,
        session_manager: Any,
        flight_recorder: FlightRecorder,
    ) -> None:
        self._session_manager = session_manager
        self._flight_recorder = flight_recorder

    def resolve(self, session_id: str) -> str:
        metadata = self._get_metadata(session_id)
        goal = metadata.get("goal")
        if not goal:
            raise ReplayError(
                f"No goal found in metadata for session: {session_id}"
            )
        return goal

    def restore_config(self, session_id: str) -> EngineConfig:
        metadata = self._get_metadata(session_id)
        if "engine_config" not in metadata:
            raise ReplayError(
                f"No engine_config in metadata for session: {session_id}"
            )
        config_dict = metadata["engine_config"]
        if not isinstance(config_dict, dict):
            raise ReplayError(
                f"Invalid engine_config in metadata for session: {session_id}"
            )
        return self._dict_to_engine_config(config_dict)

    def execute(self, session_id: str) -> dict[str, Any]:
        goal = self.resolve(session_id)
        config = self.restore_config(session_id)
        from thinkbox.engine import ThinkBoxEngine

        engine = ThinkBoxEngine(config)
        return asyncio.run(engine.execute_goal(goal))

    def compare(
        self, original: dict[str, Any], replay: dict[str, Any]
    ) -> dict[str, Any]:
        compared: dict[str, Any] = {}
        mismatch_fields: list[str] = []
        all_keys = set(original) | set(replay)
        for key in sorted(all_keys):
            if key in self._NONDETERMINISTIC:
                continue
            orig_val = original.get(key)
            replay_val = replay.get(key)
            compared[key] = (orig_val, replay_val)
            if orig_val != replay_val:
                mismatch_fields.append(key)
        return {
            "verdict": "MISMATCH" if mismatch_fields else "MATCH",
            "mismatch_fields": mismatch_fields,
            "compared": compared,
        }

    def verify(self, session_id: str) -> bool:
        return self._flight_recorder.verify_genome(session_id)

    def run(
        self, session_id: str, original_summary: dict[str, Any] | None = None
    ) -> ReplayResult:
        goal = self.resolve(session_id)
        config = self.restore_config(session_id)
        genome_verified = self.verify(session_id)
        replay_summary = self.execute(session_id)
        original = original_summary or {}
        comparison = self.compare(original, replay_summary) if original else {
            "verdict": "MATCH",
            "mismatch_fields": [],
        }
        return ReplayResult(
            session_id=session_id,
            goal=goal,
            verdict=comparison["verdict"],
            genome_verified=genome_verified,
            original_summary=original,
            replay_summary=replay_summary,
            mismatch_fields=comparison["mismatch_fields"],
        )

    def _get_metadata(self, session_id: str) -> dict[str, Any]:
        session = self._session_manager.get_session(session_id)
        if not session:
            raise ReplayError(f"Session not found: {session_id}")
        metadata = session.get("metadata", "{}")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise ReplayError(
                    f"Invalid metadata JSON for session: {session_id}"
                )
        if not isinstance(metadata, dict):
            raise ReplayError(
                f"Metadata is not a dict for session: {session_id}"
            )
        return metadata

    @staticmethod
    def _dict_to_engine_config(config_dict: dict[str, Any]) -> EngineConfig:
        mc = config_dict.get("model_config", {})
        if isinstance(mc, dict):
            model_config = EngineConfig().model_config
            model_config = replace(
                model_config,
                model=mc.get("model", model_config.model),
                base_url=mc.get("base_url", model_config.base_url),
                temperature=mc.get("temperature", model_config.temperature),
                max_tokens=mc.get("max_tokens", model_config.max_tokens),
                timeout=mc.get("timeout", model_config.timeout),
                api_type=mc.get("api_type", model_config.api_type),
            )
        else:
            model_config = EngineConfig().model_config

        sc = config_dict.get("scaler_config", {})
        if isinstance(sc, dict):
            scaler_config = replace(
                EngineConfig().scaler_config,
                min_workers=sc.get("min_workers", 4),
                max_workers=sc.get("max_workers", 512),
                default_workers=sc.get("default_workers", 16),
                vram_threshold_high=sc.get("vram_threshold_high", 90.0),
                vram_threshold_low=sc.get("vram_threshold_low", 50.0),
                cpu_threshold_high=sc.get("cpu_threshold_high", 85.0),
                cpu_threshold_low=sc.get("cpu_threshold_low", 40.0),
                memory_threshold_high=sc.get("memory_threshold_high", 90.0),
                memory_threshold_low=sc.get("memory_threshold_low", 50.0),
                scale_down_factor=sc.get("scale_down_factor", 0.5),
                scale_up_factor=sc.get("scale_up_factor", 1.5),
                check_interval_seconds=sc.get("check_interval_seconds", 5.0),
            )
        else:
            scaler_config = EngineConfig().scaler_config

        return EngineConfig(
            model_config=model_config,
            scaler_config=scaler_config,
            speculative=config_dict.get("speculative", True),
            max_retries=config_dict.get("max_retries", 3),
            repo_path=config_dict.get("repo_path", "."),
        )
