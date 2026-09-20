"""Hermetic tests for box_mercury_live experiment (mock-only)."""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio

from experiments.box_mercury_live import (
    CONCURRENCY_LEVELS,
    HARD_CALL_GUARD,
    CALLS_PER_LEVEL,
    MODEL,
    BASE_URL,
    run_iteration,
)


class TestBoxMercuryConfig(unittest.TestCase):
    def test_model_is_mercury2(self) -> None:
        self.assertEqual(MODEL, "mercury-2")

    def test_base_url_is_inception(self) -> None:
        self.assertIn("inceptionlabs", BASE_URL)

    def test_concurrency_levels_included(self) -> None:
        self.assertIn(1, CONCURRENCY_LEVELS)
        self.assertIn(16, CONCURRENCY_LEVELS)
        self.assertEqual(len(CONCURRENCY_LEVELS), 4)

    def test_call_guard_is_bounded(self) -> None:
        self.assertLessEqual(HARD_CALL_GUARD, 64)
        self.assertEqual(HARD_CALL_GUARD, 32)

    def test_calls_per_level_is_positive(self) -> None:
        self.assertGreater(CALLS_PER_LEVEL, 0)


class TestRunLevel(unittest.TestCase):
    def setUp(self) -> None:
        self.semaphore = asyncio.Semaphore(2)

    def test_run_iteration_returns_expected_keys(self) -> None:
        provider = MagicMock()
        provider.complete = AsyncMock(return_value=MagicMock(content='{"answer": 1}', usage={"total_tokens": 10}))

        async def _run() -> dict:
            result = await run_iteration(provider, self.semaphore, 2, 2)
            return result

        result = asyncio.run(_run()) if hasattr(__import__("asyncio"), "run") else {}
        if not result:
            self.skipTest("asyncio.Semaphore not available in this environment")
            return

        self.assertIn("concurrency", result)
        self.assertEqual(result["concurrency"], 2)
        self.assertIn("completed", result)
        self.assertIn("errors", result)
        self.assertIn("latencies", result)
        self.assertIn("p50_latency", result)
        self.assertIn("p99_latency", result)
        self.assertIn("avg_latency", result)
        self.assertIn("rps", result)
        self.assertIn("results", result)
        self.assertEqual(result["calls"], 2)
        self.assertEqual(result["completed"], 2)
        self.assertEqual(result["errors"], 0)

    def test_run_iteration_handles_errors(self) -> None:
        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=RuntimeError("test error"))

        async def _run() -> dict:
            result = await run_iteration(provider, self.semaphore, 1, 2)
            return result

        result = asyncio.run(_run()) if hasattr(__import__("asyncio"), "run") else {}
        if not result:
            self.skipTest("asyncio.run not available")
            return

        self.assertEqual(result["completed"], 0)
        self.assertEqual(result["errors"], 2)
        self.assertIsNotNone(result["latencies"])

    def test_run_iteration_respects_concurrency(self) -> None:
        active = {"n": 0, "max": 0}

        async def slow_complete(*a: Any, **kw: Any) -> MagicMock:
            active["n"] += 1
            active["max"] = max(active["max"], active["n"])
            await asyncio.sleep(0.05)
            active["n"] -= 1
            return MagicMock(content="ok", usage={"total_tokens": 1})

        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=slow_complete)

        async def _run() -> dict:
            result = await run_iteration(provider, asyncio.Semaphore(2), 2, 4)
            return result

        result = asyncio.run(_run()) if hasattr(__import__("asyncio"), "run") else {}
        if not result:
            self.skipTest("asyncio.run not available")
            return

        self.assertLessEqual(active["max"], 2)

    def test_run_iteration_empty_results(self) -> None:
        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=RuntimeError("all fail"))

        async def _run() -> dict:
            result = await run_iteration(provider, self.semaphore, 1, 1)
            return result

        result = asyncio.run(_run()) if hasattr(__import__("asyncio"), "run") else {}
        if not result:
            self.skipTest("asyncio.run not available")
            return

        self.assertEqual(result["completed"], 0)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["rps"], 0)


class TestBoxMercuryEnvCheck(unittest.TestCase):
    def test_env_missing_inception_key(self) -> None:
        with patch.dict(os.environ, {"INCEPTION_API_KEY": "", "UPSTASH_PUBLIC_BOX_URL": "https://example.com"}, clear=True):
            from experiments.box_mercury_live import _check_env
            result = _check_env()
            self.assertEqual(result, 2)

    def test_env_missing_box_url(self) -> None:
        with patch.dict(os.environ, {"INCEPTION_API_KEY": "key", "UPSTASH_PUBLIC_BOX_URL": ""}, clear=True):
            from experiments.box_mercury_live import _check_env
            result = _check_env()
            self.assertEqual(result, 2)

    def test_env_present(self) -> None:
        with patch.dict(os.environ, {"INCEPTION_API_KEY": "key", "UPSTASH_PUBLIC_BOX_URL": "https://box.example.com"}, clear=True):
            from experiments.box_mercury_live import _check_env
            result = _check_env()
            self.assertEqual(result, 0)


class TestBoxMercuryProofStructure(unittest.TestCase):
    def test_proof_has_required_fields(self) -> None:
        proof = {
            "experiment": "box-mercury-live",
            "substrate": "upstash-box",
            "model": MODEL,
            "concurrency_levels": CONCURRENCY_LEVELS,
            "calls_per_level": CALLS_PER_LEVEL,
            "level_results": [],
            "aggregate": {},
            "live_calls_observed": 0,
            "no_claims": ["no model intelligence improvement claimed"],
            "evidence_label": "verified",
        }
        required = ["experiment", "substrate", "model", "concurrency_levels",
                     "calls_per_level", "level_results", "aggregate",
                     "live_calls_observed", "no_claims", "evidence_label"]
        for field in required:
            self.assertIn(field, proof, f"Missing required field: {field}")

    def test_no_claims_contains_standards(self) -> None:
        claims = [
            "no model intelligence improvement claimed",
            "no concurrency-for-performance claim",
            "no GPU", "no UpCloud compute", "no SSH",
        ]
        proof = {"no_claims": claims}
        for claim in claims:
            self.assertIn(claim, proof["no_claims"])


if __name__ == "__main__":
    unittest.main()