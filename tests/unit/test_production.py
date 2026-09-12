"""Unit tests for thinkbox/production.py — Phase 10 production hardening."""

import time
import unittest
from thinkbox.production import (
    AlertManager,
    AlertSeverity,
    ConfigValidation,
    ErrorRecovery,
    GracefulShutdown,
    HealthCheckSystem,
    LoadBalancer,
    MetricsCollector,
    RateLimiter,
    RequestDeduplication,
    SlidingWindow,
    TokenBucket,
    Tracing,
    Backend,
)


class TestHealthCheckSystem(unittest.TestCase):
    def test_register_and_check(self):
        hc = HealthCheckSystem()
        hc.register("db", lambda: type("O", (), {"component": "db", "healthy": True, "message": "ok"})())
        status = hc.check("db")
        self.assertTrue(status.healthy)

    def test_unregistered_returns_not_healthy(self):
        hc = HealthCheckSystem()
        status = hc.check("missing")
        self.assertFalse(status.healthy)

    def test_readiness_aggregates(self):
        hc = HealthCheckSystem()
        hc.register("a", lambda: type("O", (), {"component": "a", "healthy": True, "message": ""})())
        hc.register("b", lambda: type("O", (), {"component": "b", "healthy": False, "message": "down"})())
        readiness = hc.readiness()
        self.assertEqual(readiness["status"], "not_ready")


class TestMetricsCollector(unittest.TestCase):
    def test_counter_and_gauge(self):
        mc = MetricsCollector()
        mc.increment("requests", 1.0, {"method": "GET"})
        mc.gauge("memory_mb", 128.0)
        snap = mc.snapshot()
        self.assertEqual(len(snap), 2)

    def test_histogram(self):
        mc = MetricsCollector()
        mc.histogram("latency", 0.05)
        snap = mc.snapshot()
        self.assertEqual(snap[0]["kind"], "histogram")

    def test_prometheus_render(self):
        mc = MetricsCollector()
        mc.gauge("uptime", 100.0, {"env": "prod"})
        text = mc.render_prometheus()
        self.assertIn('uptime{env="prod"} 100.0', text)


class TestGracefulShutdown(unittest.TestCase):
    def test_acquire_release(self):
        gs = GracefulShutdown()
        self.assertTrue(gs.acquire())
        gs.release()

    def test_blocks_after_begin(self):
        gs = GracefulShutdown()
        gs.begin()
        self.assertFalse(gs.acquire())

    def test_drain(self):
        gs = GracefulShutdown(drain_timeout=1.0)
        gs.acquire()
        gs.release()
        result = gs.drain()
        self.assertEqual(result["status"], "drained")


class TestConfigValidation(unittest.TestCase):
    def test_valid_config(self):
        validator = ConfigValidation({
            "host": {"type": "str", "required": True},
            "port": {"type": "int", "required": True, "min": 1, "max": 65535},
        })
        result = validator.validate({"host": "localhost", "port": 8080})
        self.assertEqual(result.errors, [])
        self.assertEqual(result.data["host"], "localhost")

    def test_missing_required(self):
        validator = ConfigValidation({"port": {"type": "int", "required": True}})
        result = validator.validate({})
        self.assertIn("missing required key: port", result.errors)

    def test_type_mismatch(self):
        validator = ConfigValidation({"port": {"type": "int"}})
        result = validator.validate({"port": "not_int"})
        self.assertIn("port must be int", result.errors)

    def test_range_violation(self):
        validator = ConfigValidation({"timeout": {"type": "int", "min": 1, "max": 100}})
        result = validator.validate({"timeout": 200})
        self.assertIn("timeout above maximum 100", result.errors)


class TestErrorRecovery(unittest.TestCase):
    def test_success_first_try(self):
        recovery = ErrorRecovery(max_retries=2)
        result = recovery.execute("ok", lambda: 42)
        self.assertEqual(result, 42)

    def test_retry_then_success(self):
        recovery = ErrorRecovery(max_retries=2, base_delay=0.0)
        state = {"attempts": 0}

        def fn():
            state["attempts"] += 1
            if state["attempts"] < 3:
                raise RuntimeError("fail")
            return "success"

        result = recovery.execute("flaky", fn, retries=3)
        self.assertEqual(result, "success")
        self.assertEqual(state["attempts"], 3)

    def test_circuit_opens(self):
        recovery = ErrorRecovery(max_retries=1, base_delay=0.0)

        def fail():
            raise RuntimeError("down")

        for _ in range(5):
            try:
                recovery.execute("db", fail, retries=0)
            except RuntimeError:
                pass
        state = recovery.circuit_state("db")
        self.assertEqual(state["state"], "open")


class TestRequestDeduplication(unittest.TestCase):
    def test_duplicate_suppressed(self):
        dedup = RequestDeduplication(default_ttl=1.0)
        call_count = 0

        def compute():
            nonlocal call_count
            call_count += 1
            return {"id": call_count}

        r1 = dedup.process("GET", "/x", "body", compute)
        r2 = dedup.process("GET", "/x", "body", compute)
        self.assertEqual(r1, r2)
        self.assertEqual(call_count, 1)

    def test_different_bodies_computed(self):
        dedup = RequestDeduplication(default_ttl=1.0)
        r1 = dedup.process("GET", "/x", "a", lambda: 1)
        r2 = dedup.process("GET", "/x", "b", lambda: 2)
        self.assertNotEqual(r1, r2)


class TestTracing(unittest.TestCase):
    def test_span_lifecycle(self):
        tracing = Tracing()
        span = tracing.start_span("op")
        tracing.log(span, "event", {"key": "value"})
        tracing.end_span(span)
        trace = tracing.trace()
        self.assertEqual(len(trace["spans"]), 1)
        self.assertIsNotNone(trace["spans"][0]["end_time"])

    def test_duration_calculated(self):
        tracing = Tracing()
        span = tracing.start_span("op")
        time.sleep(0.01)
        tracing.end_span(span)
        duration = span.duration_ms()
        self.assertIsNotNone(duration)
        self.assertGreater(duration, 5)


class TestRateLimiter(unittest.TestCase):
    def test_token_bucket(self):
        rl = RateLimiter()
        bucket = rl.bucket("api", rate=10.0, capacity=10.0)
        self.assertTrue(bucket.consume())
        self.assertFalse(bucket.consume(100.0))

    def test_sliding_window(self):
        rl = RateLimiter()
        window = rl.window("ip", limit=2, window=0.1)
        self.assertTrue(window.allow())
        self.assertTrue(window.allow())
        self.assertFalse(window.allow())


class TestLoadBalancer(unittest.TestCase):
    def test_round_robin(self):
        lb = LoadBalancer(strategy="round_robin")
        lb.add_backend(Backend(name="a", address="1"))
        lb.add_backend(Backend(name="b", address="2"))
        first = lb.select()
        second = lb.select()
        self.assertNotEqual(first.name, second.name)

    def test_unhealthy_excluded(self):
        lb = LoadBalancer()
        lb.add_backend(Backend(name="a", address="1", healthy=False))
        lb.add_backend(Backend(name="b", address="2", healthy=True))
        selected = lb.select()
        self.assertEqual(selected.name, "b")

    def test_remove_backend(self):
        lb = LoadBalancer()
        lb.add_backend(Backend(name="a", address="1"))
        lb.remove_backend("a")
        self.assertIsNone(lb.select())


class TestAlertManager(unittest.TestCase):
    def test_fires_alert(self):
        am = AlertManager(suppression_window=0.0)
        alert = am.evaluate("cpu", value=95.0, threshold=90.0, severity=AlertSeverity.CRITICAL)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "critical")

    def test_suppresses_duplicate(self):
        am = AlertManager(suppression_window=10.0)
        am.evaluate("cpu", value=95.0, threshold=90.0)
        again = am.evaluate("cpu", value=96.0, threshold=90.0)
        self.assertIsNone(again)

    def test_filter_by_severity(self):
        am = AlertManager(suppression_window=0.0)
        am.evaluate("mem", value=85.0, threshold=80.0, severity=AlertSeverity.WARNING)
        am.evaluate("disk", value=99.0, threshold=95.0, severity=AlertSeverity.CRITICAL)
        warnings = am.alerts(severity="warning")
        critical = am.alerts(severity="critical")
        self.assertEqual(len(warnings), 1)
        self.assertEqual(len(critical), 1)


if __name__ == "__main__":
    unittest.main()
