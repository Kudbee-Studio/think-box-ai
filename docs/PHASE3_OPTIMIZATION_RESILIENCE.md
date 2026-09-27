# PHASE 3: Optimization & Resilience

**Status**: CODE COMPLETE / TEST VERIFIED (hermetic)  
**Timestamp**: 2026-09-27  
**Session**: https://claude.ai/code/session_01EAuGaDfcF7uPqVxMZ4eyfp

---

## Overview

Phase 3 adds enterprise-grade observability, advanced rate limiting, and comprehensive load testing to Think Box AI. All systems operate with Phase 0 compliance (stdlib-only, no external HTTP dependencies).

### Key Components

| Component | Python | PHP | Purpose |
|-----------|--------|-----|---------|
| **Distributed Tracing** | `thinkbox/observability.py` | `backend/observability.php` | OpenTelemetry-compatible trace collection |
| **Prometheus Metrics** | `thinkbox/observability.py` | `backend/observability.php` | Time-series metrics export |
| **Rate Limiter** | `thinkbox/rate_limiter.py` | `backend/rate_limiter.php` | Multi-strategy rate limiting |
| **Load Testing** | `scripts/load_test.py` | `scripts/load_test.php` | Enterprise load testing |

---

## 1. Distributed Tracing

### Python Implementation

**File**: `thinkbox/observability.py` (266 lines)

#### Span Model
```python
from thinkbox.observability import Span

span = Span(
    trace_id="abc123",
    span_id="def456",
    parent_span_id=None,
    operation_name="inference",
    start_time=time.time(),
)

span.attributes["model"] = "claude-3"
span.finish()
```

#### Tracer Usage
```python
from thinkbox.observability import get_tracer

tracer = get_tracer()
span = tracer.start_span("model_call", {"model": "claude-3", "tokens": 100})

# ... operation ...

tracer.add_event("model_response_received", {"latency_ms": 250})
tracer.set_attribute("result_length", 500)
tracer.end_span(status="ok")

# Export
trace = tracer.get_trace(span.trace_id)
```

#### Decorators
```python
from thinkbox.observability import traced, timed, get_metrics

@traced(operation_name="inference")
def run_model(prompt):
    return model.generate(prompt)

metrics = get_metrics()

@timed(metrics, operation_name="inference_latency")
def run_model(prompt):
    return model.generate(prompt)
```

### PHP Implementation

**File**: `backend/observability.php` (342 lines)

#### Usage
```php
<?php
require_once 'observability.php';

$tracer = get_tracer();
$metrics = get_metrics();

// Manual tracing
$span = $tracer->start_span('request_processing', ['client_id' => '123']);
$tracer->add_event('validation_complete');
$tracer->set_attribute('validated', true);
$tracer->end_span('ok');

// Helper functions
trace_operation('api_call', function($span) {
    $span->attributes['endpoint'] = '/inference';
    return call_api();
});

timed_operation('database_query', function() {
    return $db->query('SELECT ...');
});

// Export
echo $tracer->export_json();
echo $metrics->to_prometheus_format();
?>
```

### Features

✅ OpenTelemetry-compatible span model  
✅ Parent-child span relationships  
✅ Event tracking within spans  
✅ Automatic RFC 3339 timestamps  
✅ JSON and Prometheus export  
✅ Decorator-based instrumentation  

---

## 2. Prometheus Metrics

### Python Metrics API

```python
from thinkbox.observability import get_metrics

metrics = get_metrics()

# Counters
metrics.increment_counter("requests_total", value=1, labels={"method": "POST"})

# Gauges
metrics.set_gauge("active_requests", value=42, labels={"endpoint": "/inference"})

# Histograms
metrics.record_histogram("payload_size_bytes", value=1024)

# Timings
metrics.record_timing("inference_latency_ms", duration_ms=250)

# Export
prometheus_text = metrics.to_prometheus_format()
# requests_total{method=POST} 1
# active_requests{endpoint=/inference} 42
# payload_size_bytes_count 1
# payload_size_bytes_sum 1024
# inference_latency_ms_count 1
# inference_latency_ms_sum_ms 250
# inference_latency_ms_p50_ms 250.00
# inference_latency_ms_p99_ms 250.00
```

### Percentile Support

```python
metrics.record_timing("latency", 100.0)
metrics.record_timing("latency", 150.0)
metrics.record_timing("latency", 200.0)

p50 = metrics.get_percentile("latency", 50)  # 150.0
p95 = metrics.get_percentile("latency", 95)  # 195.0
p99 = metrics.get_percentile("latency", 99)  # 199.0
```

---

## 3. Rate Limiting

### Three Strategies

#### Token Bucket
```python
from thinkbox.rate_limiter import RateLimiter, RateLimit, RateLimitStrategy

config = RateLimit(
    requests_per_second=10.0,
    burst_size=100,
    strategy=RateLimitStrategy.TOKEN_BUCKET,
)
limiter = RateLimiter(config)

allowed, reason = limiter.is_allowed(client_id="user-123")
if not allowed:
    raise RateLimitError(reason)
```

#### Sliding Window
```python
config = RateLimit(
    requests_per_second=100.0,
    window_size_seconds=60,
    strategy=RateLimitStrategy.SLIDING_WINDOW,
)
```

#### Adaptive
Adjusts rate based on observed latency:
- P95 latency > 500ms → reduce rate by 10%
- P95 latency < 100ms → increase rate by 5%

```python
config = RateLimit(
    requests_per_second=50.0,
    strategy=RateLimitStrategy.ADAPTIVE,
)

limiter.record_latency(client_id="user-123", latency_ms=450)
# Limiter reduces rate automatically
```

### Per-Client Limits

```python
global_config = RateLimit(requests_per_second=1000.0)  # Global: 1000 req/s
per_client_config = RateLimit(requests_per_second=10.0)  # Per-client: 10 req/s

limiter = RateLimiter(global_config, per_client_config)

# Both global and per-client limits enforced
allowed, reason = limiter.is_allowed(client_id="user-123")
```

### Status Tracking

```python
status = limiter.get_status(client_id="user-123")
# {
#   "timestamp": "2026-09-27T...",
#   "global": {"tokens": 95.5, "burst_size": 100, "refill_rate": 10.0},
#   "clients": {
#     "user-123": {"tokens": 8.2, "burst_size": 100, "refill_rate": 10.0}
#   }
# }

# Decorator support
@rate_limit(limiter, lambda r: r.headers.get("X-Client-ID"))
def inference_endpoint(request):
    return run_model(request.body)
```

### Audit Log

```python
limiter._log_rejection("user-123", "Per-client limit exceeded")

# Retrieve
log = limiter.get_audit_log(limit=100)
# [
#   {
#     "timestamp": "2026-09-27T...",
#     "action": "request_rejected",
#     "client_id": "user-123",
#     "details": {"reason": "Per-client limit exceeded"}
#   }
# ]
```

---

## 4. Enterprise Load Testing

### Python Load Tester

**File**: `scripts/load_test.py` (360+ lines)

#### Basic Usage
```bash
python3 scripts/load_test.py \
  --url http://localhost:8000/api/v1/inference \
  --duration 60 \
  --rps 100 \
  --max-concurrent 50
```

#### Load Patterns

**Constant**: Steady throughput
```bash
python3 scripts/load_test.py --url http://localhost:8000 --pattern constant --rps 100
```

**Ramp**: Linear increase from 1 to target RPS
```bash
python3 scripts/load_test.py --url http://localhost:8000 --pattern ramp --rps 100
```

**Spike**: Sudden 5x increase mid-test
```bash
python3 scripts/load_test.py --url http://localhost:8000 --pattern spike --rps 50
```

**Wave**: Sinusoidal variation (0.5x to 1.5x)
```bash
python3 scripts/load_test.py --url http://localhost:8000 --pattern wave --rps 50
```

#### Output Example
```
🚀 Starting load test: constant pattern
   Target: http://localhost:8000/api/v1/inference
   Duration: 60s
   Requests/sec: 100.0
   Max concurrent: 50

  ✓ Sent 100 requests (98.0% success)
  ✓ Sent 200 requests (99.5% success)

📊 Load Test Results
============================================================
Total Requests:     6000
Successful:         5970 (99.5%)
Failed:             30
Throughput:         99.84 req/s
Test Duration:      60.08s

⏱️  Latency Metrics
============================================================
Min:                45.23ms
Max:                2850.12ms
Mean:               250.45ms
Median:             210.33ms
P95:                580.22ms
P99:                1240.55ms

⚠️  Errors by Status Code
============================================================
503: 25
500: 5
```

#### Save Results
```bash
python3 scripts/load_test.py --url ... --output results.json
```

```json
{
  "total_requests": 6000,
  "successful_requests": 5970,
  "failed_requests": 30,
  "min_latency_ms": 45.23,
  "mean_latency_ms": 250.45,
  "p95_latency_ms": 580.22,
  "p99_latency_ms": 1240.55,
  "throughput_rps": 99.84,
  "errors_by_code": {"503": 25, "500": 5},
  "test_duration_seconds": 60.08,
  "timestamp": "2026-09-27T..."
}
```

### PHP Load Tester

**File**: `scripts/load_test.php` (310+ lines)

```bash
php scripts/load_test.php \
  --url http://localhost:8000/api/v1/inference \
  --duration 60 \
  --rps 100 \
  --output results.json
```

---

## 5. Integration Guide

### Enable Tracing

```python
from thinkbox.observability import get_tracer, get_metrics
from thinkbox.model_client import AsyncModelClient

client = AsyncModelClient(provider="openai", model="gpt-4")
tracer = get_tracer()

# Start span for inference
span = tracer.start_span("inference", {"model": "gpt-4"})

try:
    response = await client.call(prompt="Hello", temperature=0.7)
    tracer.set_attribute("response_length", len(response))
    tracer.end_span(status="ok")
except Exception as e:
    tracer.end_span(status="error", error=str(e))
    raise
```

### Enable Rate Limiting

```python
from thinkbox.rate_limiter import RateLimiter, RateLimit, RateLimitStrategy

# In your API handler
rate_limiter = RateLimiter(
    global_config=RateLimit(
        requests_per_second=1000.0,
        strategy=RateLimitStrategy.ADAPTIVE,
    ),
    per_client_config=RateLimit(
        requests_per_second=50.0,
    ),
)

@app.post("/inference")
async def inference_handler(request):
    client_id = request.headers.get("X-Client-ID")
    
    allowed, reason = rate_limiter.is_allowed(client_id)
    if not allowed:
        return APIError(reason, status_code=429)
    
    start = time.time()
    result = await run_inference(request)
    latency = (time.time() - start) * 1000
    
    rate_limiter.record_latency(client_id, latency)
    return result
```

### Run Load Tests

```bash
# Test constant load at 100 RPS for 2 minutes
python3 scripts/load_test.py \
  --url http://localhost:8000/api/v1/inference \
  --pattern constant \
  --rps 100 \
  --duration 120 \
  --output load_test_100rps.json

# Test spike scenarios
python3 scripts/load_test.py \
  --url http://localhost:8000/api/v1/inference \
  --pattern spike \
  --rps 50 \
  --spike-multiplier 10 \
  --output load_test_spike.json

# Test ramp-up to find breaking point
python3 scripts/load_test.py \
  --url http://localhost:8000/api/v1/inference \
  --pattern ramp \
  --rps 500 \
  --ramp-up-seconds 30 \
  --output load_test_ramp.json
```

---

## 6. Testing

All components are tested hermetically (no external dependencies):

```bash
# Run unit tests
python3 -m unittest tests.unit.test_observability -v
python3 -m unittest tests.unit.test_rate_limiter -v
python3 -m unittest tests.unit.test_load_test -v

# Full test suite
python3 -m unittest discover tests/unit/ -v
```

### Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| `thinkbox/observability.py` | 15 | ✅ PASS |
| `thinkbox/rate_limiter.py` | 20 | ✅ PASS |
| `scripts/load_test.py` | 12 | ✅ PASS |
| **Total** | **47** | **✅ PASS** |

---

## 7. Monitoring

### Prometheus Scrape Config

```yaml
scrape_configs:
  - job_name: "think-box-ai"
    static_configs:
      - targets: ["localhost:8000"]
    metrics_path: "/metrics"
    scrape_interval: 15s
```

### Key Metrics to Watch

| Metric | Threshold | Action |
|--------|-----------|--------|
| `inference_latency_ms_p95` | > 500ms | Investigate backend |
| `requests_rejected` | > 1% | Review rate limit config |
| `request_errors_total` | > 5% | Check service health |
| `active_requests` | > `max_concurrent` | Increase capacity |

---

## 8. Next Steps (Phase 4)

- [ ] Integration with existing model clients
- [ ] Dashboard widgets for observability
- [ ] Automated alerting on metrics
- [ ] Cost tracking per provider/model
- [ ] Performance benchmarking suite
- [ ] Chaos engineering tests

---

## Files Summary

| File | Lines | Purpose |
|------|-------|---------|
| `thinkbox/observability.py` | 266 | Python tracing & metrics |
| `backend/observability.php` | 342 | PHP tracing & metrics |
| `thinkbox/rate_limiter.py` | 360+ | Python rate limiting |
| `backend/rate_limiter.php` | 260+ | PHP rate limiting |
| `scripts/load_test.py` | 360+ | Python load testing |
| `scripts/load_test.php` | 310+ | PHP load testing |

**Total**: 1,900+ lines of enterprise-grade code

---

## Compliance

✅ **Phase 0**: Stdlib-only (no external HTTP deps)  
✅ **RFC 3339**: All timestamps ISO 8601 compliant  
✅ **Error Handling**: Fail-closed on all errors  
✅ **Audit Logging**: All actions logged  
✅ **Testing**: 100% hermetic tests  

---

**Four-State Classification**: **CODE COMPLETE / TEST VERIFIED**

Not claimed as LIVE VERIFIED (hermetic suite only). Use in production after your own integration tests verify behavior with real endpoints.
