"""Integration and chaos-gate tests for SchedulerHarness (PR #85 features).

Covers: full lifecycle, chaos scenarios, failure paths, concurrency-safety
under single-threaded asyncio, all 10 features working together.
"""

import json
import unittest

from thinkbox.scheduler import (
    AdmissionRateLimiter,
    AnomalyDetector,
    ConfigValidator,
    DataIntegrityChecker,
    DeadLetterQueue,
    GracefulShutdownCoordinator,
    MemoryPressureMonitor,
    RetryStormGuard,
    SchemaVersionTracker,
    SchedulerHarness,
    SchedulerSentinel,
)


class TestSchedulerHarnessLifecycle(unittest.TestCase):
    """Happy-path lifecycle using all 10 features."""

    def setUp(self) -> None:
        self.harness = SchedulerHarness()

    def test_admit_goal_valid_config(self) -> None:
        receipt = self.harness.admit_goal("g1", {"required_field": "value"})
        self.assertTrue(receipt["admitted"])
        self.assertFalse(receipt["rate_limited"])
        self.assertTrue(receipt["config_valid"])

    def test_admit_goal_invalid_config(self) -> None:
        self.harness.validator.register_schema("test", ["req_field"], {"req_field": str})
        result = self.harness.get_validation_result({})
        self.assertFalse(result["valid"])
        self.assertFalse(result["is_valid_method"])

    def test_admit_goal_rate_limited(self) -> None:
        for i in range(100):
            self.harness.admit_goal(f"g{i}")
        receipt = self.harness.admit_goal("overflow")
        self.assertTrue(receipt["rate_limited"])

    def test_start_goal(self) -> None:
        receipt = self.harness.start_goal("g1", task_count=5)
        self.assertTrue(receipt["started"])
        self.assertEqual(receipt["status"], "running")

    def test_execute_step(self) -> None:
        self.harness.start_goal("g1")
        result = self.harness.execute_step("g1", "s1")
        self.assertTrue(result["executed"])

    def test_complete_goal(self) -> None:
        self.harness.start_goal("g1")
        self.harness.execute_step("g1", "s1")
        receipt = self.harness.complete_goal("g1")
        self.assertTrue(receipt["completed"])

    def test_full_lifecycle(self) -> None:
        g = "goal_alpha"
        r1 = self.harness.admit_goal(g, {"field": "ok"})
        self.assertTrue(r1["admitted"])
        self.harness.start_goal(g, task_count=3)
        for i in range(3):
            self.harness.execute_step(g, f"step_{i}")
        mem = self.harness.check_memory()
        self.assertIn("overall", mem)
        self.harness.complete_goal(g)
        stats = self.harness.get_harness_stats()
        self.assertEqual(stats["completed_goals"], 1)
        self.assertEqual(stats["steps_completed"], 3)

    def test_harness_log_populated(self) -> None:
        self.harness.admit_goal("g1")
        self.harness.start_goal("g1")
        self.harness.complete_goal("g1")
        log = self.harness.get_harness_log()
        events = [e["event"] for e in log]
        self.assertIn("admit_goal", events)
        self.assertIn("start_goal", events)
        self.assertIn("complete_goal", events)


class TestSchedulerHarnessFailureHandling(unittest.TestCase):
    """Failure paths and DeadLetterQueue integration."""

    def setUp(self) -> None:
        self.harness = SchedulerHarness()

    def test_handle_failure_retry_allowed(self) -> None:
        self.harness.start_goal("g1")
        result = self.harness.handle_failure("g1", "s1", "boom", retry_count=0)
        self.assertTrue(result["retry_allowed"])
        self.assertIsNone(result["dead_letter"])

    def test_handle_failure_dead_letter(self) -> None:
        self.harness.start_goal("g1")
        result = self.harness.handle_failure("g1", "s1", "boom", retry_count=5)
        self.assertIsNotNone(result["dead_letter"])
        self.assertEqual(result["dead_letter"]["status"], "dead")

    def test_dlq_get_by_reason(self) -> None:
        self.harness.dlq.enqueue("g1", "g1", "err1", "task_failure", 3)
        by_reason = self.harness.dlq.get_by_reason("task_failure")
        self.assertEqual(len(by_reason), 1)

    def test_dlq_requeue(self) -> None:
        self.harness.dlq.enqueue("g1", "g1", "err", "task_failure", 3)
        requeued = self.harness.dlq.requeue("g1", "manual")
        self.assertTrue(requeued)

    def test_dlq_discard(self) -> None:
        self.harness.dlq.enqueue("g1", "g1", "err", "task_failure", 3)
        discarded = self.harness.dlq.discard("g1")
        self.assertTrue(discarded)
        self.assertEqual(self.harness.dlq.get_size(), 0)

    def test_retry_storm_guard_blocks(self) -> None:
        guard = RetryStormGuard(max_retries_per_second=2)
        self.assertTrue(guard.allow_retry())
        self.assertTrue(guard.allow_retry())
        self.assertFalse(guard.allow_retry())

    def test_memory_pressure_monitor_check(self) -> None:
        monitor = MemoryPressureMonitor(warning_threshold=10, critical_threshold=50)
        monitor.register_tracker("test_tracker", lambda: 5, 10)
        result = monitor.check()
        self.assertEqual(result["overall"], "healthy")

    def test_memory_pressure_critical(self) -> None:
        monitor = MemoryPressureMonitor(warning_threshold=10, critical_threshold=50)
        monitor.register_tracker("big", lambda: 100, 100)
        result = monitor.check()
        self.assertEqual(result["overall"], "critical")
        self.assertEqual(result["violations"], 1)


class TestSchedulerHarnessChaosGate(unittest.TestCase):
    """Chaos-gate tests: simulate chaos and verify the harness
    degrades gracefully instead of crashing.
    """

    def setUp(self) -> None:
        self.harness = SchedulerHarness()

    def test_chaos_admit_then_shutdown(self) -> None:
        self.harness.admit_goal("g1")
        self.harness.start_goal("g1")
        self.harness.initiate_shutdown()
        status = self.harness.shutdown.get_status()
        self.assertTrue(status["stopping"])

    def test_chaos_failure_without_start(self) -> None:
        result = self.harness.handle_failure("g1", "s1", "unknown goal", retry_count=0)
        self.assertTrue(result["retry_allowed"])

    def test_chaos_complete_unknown_goal(self) -> None:
        result = self.harness.complete_goal("nonexistent")
        self.assertTrue(result["completed"])

    def test_chaos_schema_check_empty(self) -> None:
        result = self.harness.check_schema()
        self.assertIn("compatible", result)

    def test_chaos_anomaly_detect_no_data(self) -> None:
        result = self.harness.detect_anomaly("unknown_metric")
        self.assertEqual(result["anomaly"], False)
        self.assertIn("reason", result)

    def test_chaos_sentinel_no_health(self) -> None:
        result = self.harness.sentinel_act({})
        self.assertEqual(result["count"], 0)

    def test_chaos_memory_no_trackers(self) -> None:
        result = self.harness.check_memory()
        self.assertEqual(result["trackers"], {})

    def test_chaos_concurrent_admissions_and_shutdown(self) -> None:
        for i in range(50):
            self.harness.admit_goal(f"g{i}", {"i": i})
        self.harness.initiate_shutdown()
        stats = self.harness.get_harness_stats()
        self.assertGreaterEqual(stats["admission_total"], 50)

    def test_chaos_dlq_overflow(self) -> None:
        for i in range(1005):
            self.harness.dlq.enqueue(f"g{i}", f"g{i}", "err", "test", 0)
        stats = self.harness.dlq.get_stats()
        self.assertLessEqual(stats["size"], self.harness.dlq.max_size)

    def test_chaos_rapid_failures(self) -> None:
        self.harness.start_goal("g1")
        for i in range(10):
            self.harness.handle_failure("g1", f"s{i}", f"err{i}", retry_count=5)
        stats = self.harness.get_harness_stats()
        self.assertGreater(stats["dlq_size"], 0)


class TestSchedulerHarnessAllFeaturesTogether(unittest.TestCase):
    """Verify every PR #85 feature produces inspectable output."""

    def setUp(self) -> None:
        self.harness = SchedulerHarness()

    def test_admission_feature(self) -> None:
        stats = self.harness.admission.get_stats()
        self.assertIn("total_admitted", stats)
        self.assertIn("total_blocked", stats)

    def test_retry_guard_feature(self) -> None:
        stats = self.harness.retry_guard.get_stats()
        self.assertIn("allowed", stats)
        self.assertIn("blocked", stats)

    def test_dlq_feature(self) -> None:
        self.harness.dlq.enqueue("g1", "g1", "e", "r", 0)
        stats = self.harness.dlq.get_stats()
        self.assertEqual(stats["size"], 1)

    def test_memory_feature(self) -> None:
        self.harness.memory.register_tracker("m1", lambda: 5, 10)
        stats = self.harness.memory.get_stats()
        self.assertEqual(stats["trackers"], 1)

    def test_sentinel_feature(self) -> None:
        result = self.harness.sentinel.act({"g1": "degraded"})
        self.assertEqual(result["count"], 1)
        stats = self.harness.sentinel.get_stats()
        self.assertEqual(stats["recovered"], 1)

    def test_shutdown_feature(self) -> None:
        self.harness.shutdown.start_goal("g1")
        self.harness.shutdown.initiate_shutdown()
        self.assertFalse(self.harness.shutdown.is_ready_to_stop())
        self.harness.shutdown.complete_goal("g1")
        self.assertTrue(self.harness.shutdown.is_ready_to_stop())

    def test_integrity_feature(self) -> None:
        ok = self.harness.integrity.verify("d1", "data")
        self.assertTrue(ok)
        stats = self.harness.integrity.get_stats()
        self.assertEqual(stats["verified"], 1)

    def test_schema_feature(self) -> None:
        self.harness.schema.record_version("comp1", "1.0")
        result = self.harness.schema.check_compatibility()
        self.assertIn("compatible", result)
        stats = self.harness.schema.get_stats()
        self.assertEqual(stats["components"], 2)

    def test_anomaly_feature(self) -> None:
        for v in [1.0, 1.0, 1.0, 10.0]:
            self.harness.anomaly.record("m1", v)
        result = self.harness.detect_anomaly("m1")
        self.assertIn("anomaly", result)
        stats = self.harness.anomaly.get_stats()
        self.assertEqual(stats["metrics"], 1)

    def test_validator_feature(self) -> None:
        result = self.harness.get_validation_result({"required": "val"})
        self.assertTrue(result["valid"])
        self.assertTrue(result["is_valid_method"])


class TestConfigValidatorFixed(unittest.TestCase):
    """Verify ConfigValidator.is_valid() is now functional."""

    def test_is_valid_with_errors(self) -> None:
        validator = ConfigValidator()
        validator.register_schema("test", ["req"], {"req": str})
        validator.validate({})
        self.assertFalse(validator.is_valid())

    def test_is_valid_without_errors(self) -> None:
        validator = ConfigValidator()
        validator.register_schema("test", ["req"], {"req": str})
        validator.validate({"req": "ok"})
        self.assertTrue(validator.is_valid())

    def test_is_valid_get_errors_populated(self) -> None:
        validator = ConfigValidator()
        validator.register_schema("test", ["req"], {"req": str})
        validator.validate({})
        errors = validator.get_errors()
        self.assertEqual(len(errors), 1)

    def test_is_valid_after_validate_feature_config(self) -> None:
        validator = ConfigValidator()
        validator.register_schema("feat1", ["f1"], {"f1": str})
        validator.validate_feature_config("feat1", {})
        self.assertFalse(validator.is_valid())


class TestSchedulerHarnessStats(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = SchedulerHarness()

    def test_stats_initial_state(self) -> None:
        stats = self.harness.get_harness_stats()
        self.assertEqual(stats["goals"], 0)
        self.assertEqual(stats["dlq_size"], 0)
        self.assertEqual(stats["completed_goals"], 0)

    def test_stats_after_lifecycle(self) -> None:
        self.harness.admit_goal("g1")
        self.harness.start_goal("g1", task_count=2)
        self.harness.execute_step("g1", "s1")
        self.harness.execute_step("g1", "s2")
        self.harness.complete_goal("g1")
        stats = self.harness.get_harness_stats()
        self.assertEqual(stats["goals"], 1)
        self.assertEqual(stats["steps_completed"], 2)
        self.assertEqual(stats["completed_goals"], 1)
