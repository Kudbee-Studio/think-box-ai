"""Unit tests for thinkbox/agent/telemetry — Agent Telemetry & Observability."""

import logging
import unittest

from thinkbox.agent.telemetry import (
    LogEntry,
    MetricRecord,
    Span,
    TelemetryEmitter,
    TelemetryLevel,
)


class TestTelemetryLevel(unittest.TestCase):
    def test_values(self):
        self.assertEqual(TelemetryLevel.DEBUG.value, "DEBUG")
        self.assertEqual(TelemetryLevel.INFO.value, "INFO")
        self.assertEqual(TelemetryLevel.WARNING.value, "WARNING")
        self.assertEqual(TelemetryLevel.ERROR.value, "ERROR")
        self.assertEqual(TelemetryLevel.CRITICAL.value, "CRITICAL")


class TestMetricRecord(unittest.TestCase):
    def test_creation(self):
        m = MetricRecord(name="test", value=42.0, labels={"a": "b"})
        self.assertEqual(m.name, "test")
        self.assertEqual(m.value, 42.0)
        self.assertEqual(m.labels, {"a": "b"})
        self.assertGreater(m.timestamp, 0)

    def test_default_labels(self):
        m = MetricRecord(name="test", value=1.0)
        self.assertEqual(m.labels, {})


class TestSpan(unittest.TestCase):
    def test_creation(self):
        now = 1000.0
        s = Span(
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            operation_name="test",
            start_time=now,
        )
        self.assertEqual(s.duration_ms, None)

    def test_duration(self):
        s = Span(
            trace_id="t1",
            span_id="s1",
            parent_span_id="p1",
            operation_name="test",
            start_time=1000.0,
            end_time=1001.0,
        )
        self.assertEqual(s.duration_ms, 1000.0)


class TestLogEntry(unittest.TestCase):
    def test_creation(self):
        e = LogEntry(
            level=TelemetryLevel.INFO,
            message="test",
            agent_id="agent_1",
        )
        self.assertEqual(e.level, TelemetryLevel.INFO)
        self.assertEqual(e.message, "test")
        self.assertEqual(e.agent_id, "agent_1")
        self.assertGreater(e.timestamp, 0)
        self.assertEqual(e.data, {})


class TestTelemetryEmitter(unittest.TestCase):
    def setUp(self):
        self.emitter = TelemetryEmitter(
            agent_id="agent_1",
            agent_type="TASK_AGENT",
            tenant_id="tenant_1",
            endpoint="localhost:4317",
        )

    def test_initial_state(self):
        self.assertEqual(self.emitter.agent_id, "agent_1")
        self.assertEqual(self.emitter.agent_type, "TASK_AGENT")
        self.assertEqual(self.emitter.tenant_id, "tenant_1")
        self.assertFalse(self.emitter.is_running())
        self.assertEqual(len(self.emitter.get_metrics()), 0)
        self.assertEqual(len(self.emitter.get_spans()), 0)
        self.assertEqual(len(self.emitter.get_logs()), 0)

    def test_counter(self):
        self.emitter.counter("test.counter")
        self.assertEqual(self.emitter.get_counter("test.counter"), 1.0)

    def test_counter_multiple(self):
        self.emitter.counter("test.counter")
        self.emitter.counter("test.counter")
        self.emitter.counter("test.counter", 2.0)
        self.assertEqual(self.emitter.get_counter("test.counter"), 4.0)

    def test_counter_with_labels(self):
        self.emitter.counter("test.counter", labels={"a": "x"})
        self.emitter.counter("test.counter", labels={"a": "y"})
        self.assertEqual(self.emitter.get_counter("test.counter", {"a": "x"}), 1.0)
        self.assertEqual(self.emitter.get_counter("test.counter", {"a": "y"}), 1.0)
        self.assertEqual(self.emitter.get_counter("test.counter", {"a": "z"}), 0.0)

    def test_gauge(self):
        self.emitter.gauge("test.gauge", 42.0)
        self.assertEqual(self.emitter.get_gauge("test.gauge"), 42.0)

    def test_gauge_update(self):
        self.emitter.gauge("test.gauge", 10.0)
        self.emitter.gauge("test.gauge", 20.0)
        self.assertEqual(self.emitter.get_gauge("test.gauge"), 20.0)

    def test_histogram(self):
        self.emitter.histogram("test.hist", 1.0)
        self.emitter.histogram("test.hist", 2.0)
        self.emitter.histogram("test.hist", 3.0)
        metrics = self.emitter.get_metrics()
        self.assertEqual(len(metrics), 3)
        summary = self.emitter.get_telemetry_summary()
        self.assertEqual(summary["histogram_keys"], 1)

    def test_start_stop(self):
        self.assertFalse(self.emitter.is_running())
        self.emitter.start()
        self.assertTrue(self.emitter.is_running())
        self.emitter.stop()
        self.assertFalse(self.emitter.is_running())

    def test_flush(self):
        self.emitter.start()
        self.emitter.counter("a")
        self.emitter.counter("b")
        count = self.emitter.flush()
        self.assertEqual(count, 2)
        self.assertFalse(self.emitter.is_running())

    def test_health_check(self):
        self.emitter.start()
        health = self.emitter.health_check()
        self.assertEqual(health["agent_id"], "agent_1")
        self.assertEqual(health["agent_type"], "TASK_AGENT")
        self.assertTrue(health["running"])
        self.assertGreater(health["uptime_seconds"], 0)
        self.emitter.stop()

    def test_telemetry_summary(self):
        self.emitter.start()
        self.emitter.counter("test")
        self.emitter.gauge("gauge", 1.0)
        summary = self.emitter.get_telemetry_summary()
        self.assertEqual(summary["agent_id"], "agent_1")
        self.assertEqual(summary["metrics_total"], 2)
        self.assertEqual(summary["counter_keys"], 1)
        self.assertEqual(summary["gauge_keys"], 1)
        self.assertEqual(summary["histogram_keys"], 0)
        self.emitter.stop()

    def test_emit_lifecycle_event(self):
        self.emitter.emit_lifecycle_event("SPAWNED", "INITIALIZED")
        summary = self.emitter.get_telemetry_summary()
        self.assertEqual(summary["metrics_total"], 1)
        logs = self.emitter.get_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].message, "Agent lifecycle: SPAWNED -> INITIALIZED")

    def test_log_levels(self):
        for level in TelemetryLevel:
            with self.subTest(level=level):
                self.emitter.log(level, f"test {level.value}")
        logs = self.emitter.get_logs()
        self.assertEqual(len(logs), 5)
        self.assertEqual(logs[0].level, TelemetryLevel.DEBUG)
        self.assertEqual(logs[4].level, TelemetryLevel.CRITICAL)

    def test_log_with_data(self):
        self.emitter.log(
            TelemetryLevel.INFO,
            "test",
            data={"key": "value"},
        )
        logs = self.emitter.get_logs()
        self.assertEqual(logs[0].data, {"key": "value"})

    def test_get_logs_filtered_by_level(self):
        self.emitter.log(TelemetryLevel.DEBUG, "debug")
        self.emitter.log(TelemetryLevel.ERROR, "error")
        self.emitter.log(TelemetryLevel.DEBUG, "debug2")
        errors = self.emitter.get_logs(level=TelemetryLevel.ERROR)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].level, TelemetryLevel.ERROR)
        debugs = self.emitter.get_logs(level=TelemetryLevel.DEBUG)
        self.assertEqual(len(debugs), 2)

    def test_get_logs_limit(self):
        for i in range(5):
            self.emitter.log(TelemetryLevel.INFO, f"msg {i}")
        logs = self.emitter.get_logs(limit=2)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0].message, "msg 3")

    def test_start_trace(self):
        span = self.emitter.start_trace("op1")
        self.assertEqual(span.operation_name, "op1")
        self.assertIsNone(span.parent_span_id)
        self.assertIsNone(span.end_time)
        self.assertGreater(len(span.span_id), 0)

    def test_start_trace_with_parent(self):
        span = self.emitter.start_trace("op1", parent_span_id="parent_1")
        self.assertEqual(span.parent_span_id, "parent_1")

    def test_end_trace(self):
        span = self.emitter.start_trace("op1")
        ended = self.emitter.end_trace(span.span_id, tags={"result": "ok"})
        self.assertIsNotNone(ended)
        self.assertIsNotNone(ended.end_time)
        self.assertGreater(ended.duration_ms, 0)
        self.assertEqual(ended.tags.get("result"), "ok")

    def test_end_trace_not_found(self):
        ended = self.emitter.end_trace("nonexistent")
        self.assertIsNone(ended)

    def test_trace_flow(self):
        span = self.emitter.start_trace("op1", tags={"a": "1"})
        self.emitter.add_span_log(
            span.span_id,
            TelemetryLevel.INFO,
            "processing",
            {"step": 1},
        )
        ended = self.emitter.end_trace(span.span_id, tags={"b": "2"})
        self.assertEqual(ended.tags.get("a"), "1")
        self.assertEqual(ended.tags.get("b"), "2")
        self.assertGreater(len(ended.logs), 0)
        self.assertEqual(ended.logs[0]["message"], "processing")

    def test_add_span_log_not_found(self):
        result = self.emitter.add_span_log("nonexistent", TelemetryLevel.INFO, "test")
        self.assertFalse(result)

    def test_get_spans(self):
        self.emitter.start_trace("op1")
        self.emitter.start_trace("op2")
        spans = self.emitter.get_spans()
        self.assertEqual(len(spans), 2)

    def test_get_metrics(self):
        self.emitter.counter("a")
        self.emitter.gauge("b", 1.0)
        metrics = self.emitter.get_metrics()
        self.assertEqual(len(metrics), 2)


class TestTelemetryEmitterFlush(unittest.TestCase):
    def setUp(self):
        self.emitter = TelemetryEmitter("a", "T", "t")

    def test_flush_without_start(self):
        self.emitter.counter("test")
        count = self.emitter.flush()
        self.assertEqual(count, 1)

    def test_multiple_flushes(self):
        self.emitter.start()
        self.emitter.counter("a")
        self.assertEqual(self.emitter.flush(), 1)
        self.emitter.counter("b")
        self.assertEqual(self.emitter.flush(), 2)
        self.emitter.counter("c")
        self.assertEqual(self.emitter.flush(), 3)
        self.assertEqual(self.emitter.flush(), 3)
        summary = self.emitter.get_telemetry_summary()
        self.assertEqual(summary["flush_count"], 4)
