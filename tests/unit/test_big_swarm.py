"""Unit tests for big_swarm instrumentation (stdlib unittest).

Tests the Instruments collector, HTTP 429/rate-limit tracking,
concurrency monitoring, latency bucketing, and throughput measurement.
"""

from __future__ import annotations

import unittest

from experiments.big_swarm import (
    Compartment,
    Instruments,
)


def _make_compartment(role: str, ok: bool, http_status: int = 200,
                       latency: float = 0.5, queue: float = 0.1,
                       error: str = "") -> Compartment:
    return Compartment(
        slot=1, worker_id=f"SWARM-{role}-0001", role=role,
        capability="research:primary", claim_id="CLM-0001", claim="test",
        ok=ok, http_status=http_status, latency_s=latency,
        queue_s=queue, error=error, tier="EVIDENCE" if ok else "ERROR",
    )


class TestInstrumentsStructure(unittest.TestCase):
    """Instruments dataclass fields and to_dict() structure."""

    def test_defaults(self) -> None:
        i = Instruments()
        self.assertEqual(i.total_calls, 0)
        self.assertEqual(i.http_200, 0)
        self.assertEqual(i.http_429, 0)
        self.assertEqual(i.http_5xx, 0)
        self.assertEqual(i.http_4xx_other, 0)
        self.assertEqual(i.http_other, 0)
        self.assertEqual(i.max_active_concurrency, 0)
        self.assertEqual(i.p50_latency_s, 0.0)
        self.assertEqual(i.p95_latency_s, 0.0)
        self.assertEqual(i.max_latency_s, 0.0)
        self.assertGreaterEqual(len(i.rate_limit_headers), 0)
        self.assertGreaterEqual(len(i.error_types), 0)

    def test_to_dict_structure(self) -> None:
        i = Instruments(total_calls=10)
        d = i.to_dict()
        self.assertIn("total_calls", d)
        self.assertIn("http_status_distribution", d)
        self.assertIn("rate_limit_headers_observed", d)
        self.assertIn("rate_limit_header_samples", d)
        self.assertIn("error_types", d)
        self.assertIn("timing", d)
        self.assertIn("latency_buckets", d)
        self.assertIn("concurrency", d)
        self.assertIn("throughput_per_second", d)
        self.assertIn("role_distribution", d)

    def test_to_dict_http_distribution(self) -> None:
        i = Instruments(
            total_calls=10, http_200=7, http_429=1, http_5xx=1,
            http_4xx_other=1,
        )
        d = i.to_dict()
        dist = d["http_status_distribution"]
        self.assertEqual(dist["200"], 7)
        self.assertEqual(dist["429"], 1)
        self.assertEqual(dist["5xx"], 1)
        self.assertEqual(dist["4xx_other"], 1)
        self.assertEqual(dist["other"], 0)

    def test_to_dict_role_distribution(self) -> None:
        i = Instruments(primary_ok=5, primary_failed=2, validator_ok=2,
                        validator_failed=1)
        d = i.to_dict()
        self.assertEqual(d["role_distribution"]["primary"]["ok"], 5)
        self.assertEqual(d["role_distribution"]["primary"]["failed"], 2)
        self.assertEqual(d["role_distribution"]["validator"]["ok"], 2)
        self.assertEqual(d["role_distribution"]["validator"]["failed"], 1)


class TestInstrumentsFromResults(unittest.TestCase):
    """_build_instruments() produces correct counts from Compartment results."""

    def setUp(self) -> None:
        from experiments.big_swarm import BigSwarm
        self.swarm = BigSwarm(primary=2, validators=1, concurrency=2)

    def test_counts_from_ok_results(self) -> None:
        self.swarm.results = [
            _make_compartment("PRIMARY", True, http_status=200, latency=0.5),
            _make_compartment("PRIMARY", True, http_status=200, latency=0.8),
            _make_compartment("VALIDATOR", True, http_status=200, latency=0.6),
        ]
        instr = self.swarm._build_instruments(wave1=0.8, wave2=0.6)
        self.assertEqual(instr.total_calls, 3)
        self.assertEqual(instr.http_200, 3)
        self.assertEqual(instr.http_429, 0)
        self.assertEqual(instr.primary_ok, 2)
        self.assertEqual(instr.primary_failed, 0)
        self.assertEqual(instr.validator_ok, 1)
        self.assertEqual(instr.validator_failed, 0)

    def test_counts_mixed_http_status(self) -> None:
        self.swarm.results = [
            _make_compartment("PRIMARY", True, http_status=200, latency=0.5),
            _make_compartment("PRIMARY", False, http_status=429, latency=1.0,
                              error="HTTP 429: rate limited"),
            _make_compartment("PRIMARY", False, http_status=500, latency=2.0,
                              error="HTTP 500: server error"),
            _make_compartment("PRIMARY", False, http_status=400, latency=0.5,
                              error="HTTP 400: bad request"),
            _make_compartment("PRIMARY", False, http_status=0, latency=0.5,
                              error="TimeoutError: timed out"),
        ]
        instr = self.swarm._build_instruments(wave1=2.0, wave2=0.0)
        self.assertEqual(instr.http_200, 1)
        self.assertEqual(instr.http_429, 1)
        self.assertEqual(instr.http_5xx, 1)
        self.assertEqual(instr.http_4xx_other, 1)
        self.assertEqual(instr.http_other, 1)
        self.assertEqual(instr.primary_ok, 1)
        self.assertEqual(instr.primary_failed, 4)

    def test_latency_buckets(self) -> None:
        self.swarm.results = [
            _make_compartment("PRIMARY", True, http_status=200, latency=0.5,
                              queue=0.2),
            _make_compartment("PRIMARY", True, http_status=200, latency=2.0,
                              queue=0.3),
            _make_compartment("PRIMARY", True, http_status=200, latency=10.0,
                              queue=0.5),
            _make_compartment("PRIMARY", True, http_status=200, latency=35.0,
                              queue=1.0),
        ]
        instr = self.swarm._build_instruments(wave1=15.0, wave2=0.0)
        self.assertEqual(instr.latency_under_1s, 1)
        self.assertEqual(instr.latency_1_to_5s, 1)
        self.assertEqual(instr.latency_5_to_30s, 1)
        self.assertEqual(instr.latency_over_30s, 1)

    def test_p50_p95_max_latency(self) -> None:
        self.swarm.results = [
            _make_compartment("PRIMARY", True, http_status=200, latency=1.0,
                              queue=0.0),
            _make_compartment("PRIMARY", True, http_status=200, latency=2.0,
                              queue=0.0),
            _make_compartment("PRIMARY", True, http_status=200, latency=3.0,
                              queue=0.0),
        ]
        instr = self.swarm._build_instruments(wave1=3.0, wave2=0.0)
        self.assertAlmostEqual(instr.p50_latency_s, 2.0, delta=0.1)
        self.assertAlmostEqual(instr.p95_latency_s, 3.0, delta=0.1)
        self.assertAlmostEqual(instr.max_latency_s, 3.0, delta=0.1)

    def test_concurrency_peaks(self) -> None:
        self.swarm._max_active_concurrency = 8
        self.swarm._peak_primary_active = 5
        self.swarm._peak_validator_active = 3
        instr = self.swarm._build_instruments(wave1=1.0, wave2=1.0)
        self.assertEqual(instr.max_active_concurrency, 8)
        self.assertEqual(instr.peak_primary_active, 5)
        self.assertEqual(instr.peak_validator_active, 3)

    def test_error_categorization(self) -> None:
        self.swarm.results = [
            _make_compartment("PRIMARY", False, http_status=429, latency=1.0,
                              error="HTTP 429: rate limited"),
            _make_compartment("PRIMARY", False, http_status=429, latency=1.0,
                              error="HTTP 429: rate limited"),
            _make_compartment("PRIMARY", False, http_status=500, latency=2.0,
                              error="HTTP 500: server error"),
            _make_compartment("PRIMARY", True, http_status=200, latency=0.5,
                              error=""),
        ]
        instr = self.swarm._build_instruments(wave1=2.0, wave2=0.0)
        self.assertIn("HTTP 429", instr.error_types)
        self.assertEqual(instr.error_types["HTTP 429"], 2)
        self.assertIn("HTTP 500", instr.error_types)
        self.assertEqual(instr.error_types["HTTP 500"], 1)

    def test_per_second_throughput(self) -> None:
        import time
        now = int(time.monotonic())
        self.swarm._call_timestamps = [
            float(now), float(now), float(now + 1), float(now + 1),
            float(now + 1), float(now + 2),
        ]
        instr = self.swarm._build_instruments(wave1=1.0, wave2=0.0)
        cps = instr.calls_per_second
        self.assertEqual(cps.get(now, 0), 2)
        self.assertEqual(cps.get(now + 1, 0), 3)
        self.assertEqual(cps.get(now + 2, 0), 1)


class TestRateLimitHeaders(unittest.TestCase):
    """_rate_limit_headers() extracts rate-limit headers from HTTPError."""

    def setUp(self) -> None:
        from experiments.big_swarm import BigSwarm
        self.swarm = BigSwarm(primary=2, validators=1, concurrency=2)

    def test_retry_after_extracted(self) -> None:
        import urllib.error
        mock_resp = type("MockHeaders", (), {
            "get": lambda self, key: "60" if key == "Retry-After" else None,
        })()
        e = urllib.error.HTTPError(url="http://test", code=429, msg="Rate limit",
                                       hdrs=mock_resp, fp=None)
        headers = self.swarm._rate_limit_headers(e)
        self.assertEqual(headers.get("Retry-After"), "60")

    def test_x_rate_limit_headers_extracted(self) -> None:
        import urllib.error

        def _mock_get(self, key):
            mapping = {
                "Retry-After": "30",
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "5",
                "X-RateLimit-Reset": "1625000000",
            }
            return mapping.get(key)
        mock_resp = type("MockHeaders", (), {"get": _mock_get})()
        e = urllib.error.HTTPError(url="http://test", code=429, msg="Rate limit",
                                       hdrs=mock_resp, fp=None)
        headers = self.swarm._rate_limit_headers(e)
        self.assertEqual(headers["Retry-After"], "30")
        self.assertEqual(headers["X-RateLimit-Limit"], "100")
        self.assertEqual(headers["X-RateLimit-Remaining"], "5")
        self.assertEqual(headers["X-RateLimit-Reset"], "1625000000")

    def test_no_headers_returns_empty(self) -> None:
        import urllib.error
        mock_resp = type("MockHeaders", (), {
            "get": lambda self, key: None,
        })()
        e = urllib.error.HTTPError(url="http://test", code=429, msg="Rate limit",
                                       hdrs=mock_resp, fp=None)
        headers = self.swarm._rate_limit_headers(e)
        self.assertEqual(headers, {})

    def test_none_headers_returns_empty(self) -> None:
        import urllib.error
        e = urllib.error.HTTPError(url="http://test", code=429, msg="Rate limit",
                                       hdrs=None, fp=None)
        headers = self.swarm._rate_limit_headers(e)
        self.assertEqual(headers, {})


class TestCompartmentInstrumentFields(unittest.TestCase):
    """Compartment has http_status and queue_s fields."""

    def test_compartment_defaults(self) -> None:
        c = Compartment(slot=1, worker_id="W1", role="PRIMARY",
                        capability="test")
        self.assertEqual(c.http_status, 0)
        self.assertEqual(c.queue_s, 0.0)
        self.assertEqual(c.status, "idle")

    def test_compartment_with_values(self) -> None:
        c = Compartment(slot=1, worker_id="W1", role="PRIMARY",
                        capability="test", http_status=429, queue_s=0.5)
        self.assertEqual(c.http_status, 429)
        self.assertEqual(c.queue_s, 0.5)


if __name__ == "__main__":
    unittest.main()
