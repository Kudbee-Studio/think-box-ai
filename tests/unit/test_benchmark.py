"""Unit tests for thinkbox.benchmark — high-throughput benchmarking."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from thinkbox.benchmark import (
    BenchmarkResult,
    BenchmarkSuite,
    _get_system_info,
    generate_markdown_report,
    save_report,
)


class TestBenchmarkResult(unittest.TestCase):
    def test_to_dict(self) -> None:
        result = BenchmarkResult(
            worker_count=4, total_tasks=50, successful_tasks=48,
            failed_tasks=2, total_time_ms=1000.0, tokens_per_second=100.0,
            avg_latency_ms=20.0, ttft_ms=5.0,
            cpu_percent=50.0, memory_percent=60.0, vram_percent=30.0,
        )
        d = result.to_dict()
        self.assertEqual(d["worker_count"], 4)
        self.assertEqual(d["successful_tasks"], 48)
        self.assertEqual(d["failed_tasks"], 2)
        self.assertAlmostEqual(d["total_time_ms"], 1000.0)
        self.assertAlmostEqual(d["tokens_per_second"], 100.0)

    def test_to_dict_defaults(self) -> None:
        result = BenchmarkResult(
            worker_count=1, total_tasks=10, successful_tasks=10,
            failed_tasks=0, total_time_ms=100.0, tokens_per_second=10.0,
            avg_latency_ms=10.0, ttft_ms=2.0,
        )
        d = result.to_dict()
        self.assertEqual(d["cpu_percent"], 0.0)
        self.assertEqual(d["memory_percent"], 0.0)
        self.assertEqual(d["vram_percent"], 0.0)


class TestBenchmarkSuite(unittest.TestCase):
    def test_defaults(self) -> None:
        suite = BenchmarkSuite()
        self.assertEqual(len(suite.results), 0)
        self.assertEqual(suite.timestamp, "")
        self.assertEqual(suite.system_info, {})


class TestGenerateMarkdownReport(unittest.TestCase):
    def test_empty_suite(self) -> None:
        suite = BenchmarkSuite(timestamp="2026-01-01", system_info={"platform": "Linux"})
        report = generate_markdown_report(suite)
        self.assertIn("ThinkBox High-Throughput Benchmark Report", report)
        self.assertIn("2026-01-01", report)
        self.assertIn("Linux", report)

    def test_with_results(self) -> None:
        suite = BenchmarkSuite(
            timestamp="2026-01-01",
            system_info={"platform": "Linux", "cpu_count": 8},
            results=[
                BenchmarkResult(
                    worker_count=4, total_tasks=50, successful_tasks=50,
                    failed_tasks=0, total_time_ms=500.0, tokens_per_second=200.0,
                    avg_latency_ms=10.0, ttft_ms=2.0,
                ),
                BenchmarkResult(
                    worker_count=8, total_tasks=50, successful_tasks=48,
                    failed_tasks=2, total_time_ms=400.0, tokens_per_second=250.0,
                    avg_latency_ms=8.0, ttft_ms=1.5,
                ),
            ],
        )
        report = generate_markdown_report(suite)
        self.assertIn("Results Summary", report)
        self.assertIn("4", report)
        self.assertIn("8", report)
        self.assertIn("Optimal Configuration", report)
        self.assertIn("250.0", report)


class TestGetSystemInfo(unittest.TestCase):
    def test_returns_dict(self) -> None:
        info = _get_system_info()
        self.assertIsInstance(info, dict)
        self.assertIn("platform", info)
        self.assertIn("python_version", info)
        self.assertIn("cpu_count", info)


class TestSaveReport(unittest.TestCase):
    def test_saves_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_benchmark.md"
            suite = BenchmarkSuite(
                timestamp="2026-01-01",
                results=[
                    BenchmarkResult(
                        worker_count=1, total_tasks=10, successful_tasks=10,
                        failed_tasks=0, total_time_ms=100.0, tokens_per_second=10.0,
                        avg_latency_ms=10.0, ttft_ms=2.0,
                    ),
                ],
            )
            save_report(suite, output_path=str(path))
            self.assertTrue(path.exists())
            content = path.read_text()
            self.assertIn("Benchmark", content)
