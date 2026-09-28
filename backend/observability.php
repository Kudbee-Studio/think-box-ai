<?php
/**
 * PHP Observability: Tracing, Metrics, Profiling
 *
 * Distributed tracing spans, Prometheus metrics, and performance profiling
 * compatible with Python observability layer.
 */

class Span
{
    public string $trace_id;
    public string $span_id;
    public ?string $parent_span_id;
    public string $operation_name;
    public float $start_time;
    public ?float $end_time = null;
    public array $attributes = [];
    public array $events = [];
    public string $status = "ok";
    public ?string $error = null;

    public function __construct(
        string $trace_id,
        string $span_id,
        ?string $parent_span_id,
        string $operation_name,
        float $start_time
    ) {
        $this->trace_id = $trace_id;
        $this->span_id = $span_id;
        $this->parent_span_id = $parent_span_id;
        $this->operation_name = $operation_name;
        $this->start_time = $start_time;
    }

    public function finish(): void
    {
        $this->end_time = microtime(true);
    }

    public function duration_ms(): float
    {
        if ($this->end_time === null) {
            return 0;
        }
        return ($this->end_time - $this->start_time) * 1000;
    }

    public function to_array(): array
    {
        return [
            'trace_id' => $this->trace_id,
            'span_id' => $this->span_id,
            'parent_span_id' => $this->parent_span_id,
            'operation_name' => $this->operation_name,
            'start_time' => date('c', (int)$this->start_time),
            'duration_ms' => $this->duration_ms(),
            'attributes' => $this->attributes,
            'events' => $this->events,
            'status' => $this->status,
            'error' => $this->error,
        ];
    }
}

class PHPTracer
{
    private array $spans = [];
    private ?Span $current_span = null;
    private int $span_counter = 0;

    public function start_span(
        string $operation_name,
        array $attributes = [],
        ?string $trace_id = null
    ): Span {
        if ($trace_id === null) {
            $trace_id = bin2hex(random_bytes(16));
        }

        $this->span_counter++;
        $span_id = dechex($this->span_counter);

        $parent_span_id = $this->current_span?->span_id;

        $span = new Span(
            $trace_id,
            $span_id,
            $parent_span_id,
            $operation_name,
            microtime(true)
        );

        $span->attributes = $attributes;
        $this->spans[] = $span;
        $this->current_span = $span;

        return $span;
    }

    public function add_event(string $name, array $attributes = []): void
    {
        if ($this->current_span) {
            $this->current_span->events[] = [
                'name' => $name,
                'timestamp' => date('c'),
                'attributes' => $attributes,
            ];
        }
    }

    public function set_attribute(string $key, mixed $value): void
    {
        if ($this->current_span) {
            $this->current_span->attributes[$key] = $value;
        }
    }

    public function end_span(string $status = "ok", ?string $error = null): ?Span
    {
        if (!$this->current_span) {
            return null;
        }

        $this->current_span->finish();
        $this->current_span->status = $status;
        $this->current_span->error = $error;

        $closed_span = $this->current_span;

        // Restore parent span
        if ($this->current_span->parent_span_id) {
            foreach (array_reverse($this->spans) as $span) {
                if ($span->span_id === $this->current_span->parent_span_id) {
                    $this->current_span = $span;
                    return $closed_span;
                }
            }
        }

        $this->current_span = null;
        return $closed_span;
    }

    public function get_trace(string $trace_id): array
    {
        $trace = [];
        foreach ($this->spans as $span) {
            if ($span->trace_id === $trace_id) {
                $trace[] = $span->to_array();
            }
        }
        return $trace;
    }

    public function export_json(): string
    {
        return json_encode(array_map(fn($s) => $s->to_array(), $this->spans), JSON_PRETTY_PRINT);
    }
}

class PHPMetrics
{
    private array $counters = [];
    private array $gauges = [];
    private array $histograms = [];
    private array $timings = [];

    public function increment_counter(string $name, int $value = 1, array $labels = []): void
    {
        $key = $this->make_key($name, $labels);
        $this->counters[$key] = ($this->counters[$key] ?? 0) + $value;
    }

    public function set_gauge(string $name, float $value, array $labels = []): void
    {
        $key = $this->make_key($name, $labels);
        $this->gauges[$key] = $value;
    }

    public function record_histogram(string $name, float $value, array $labels = []): void
    {
        $key = $this->make_key($name, $labels);
        $this->histograms[$key][] = $value;
    }

    public function record_timing(string $name, float $duration_ms, array $labels = []): void
    {
        $key = $this->make_key($name, $labels);
        $this->timings[$key][] = $duration_ms;
    }

    private function make_key(string $name, array $labels): string
    {
        if (empty($labels)) {
            return $name;
        }
        ksort($labels);
        $label_str = implode(',', array_map(fn($k, $v) => "$k=$v", array_keys($labels), $labels));
        return "$name{$label_str}";
    }

    public function get_percentile(string $name, float $percentile = 50.0): ?float
    {
        $key = null;
        foreach ($this->timings as $k => $v) {
            if (strpos($k, $name) === 0) {
                $key = $k;
                break;
            }
        }

        if (!$key || empty($this->timings[$key])) {
            return null;
        }

        $sorted = $this->timings[$key];
        sort($sorted);
        $index = (int)(count($sorted) * ($percentile / 100));
        return $sorted[min($index, count($sorted) - 1)];
    }

    public function to_prometheus_format(): string
    {
        $lines = [];

        // Counters
        foreach ($this->counters as $name => $value) {
            $lines[] = "$name $value";
        }

        // Gauges
        foreach ($this->gauges as $name => $value) {
            $lines[] = "$name $value";
        }

        // Histograms
        foreach ($this->histograms as $name => $values) {
            if (!empty($values)) {
                $lines[] = "{$name}_count " . count($values);
                $lines[] = "{$name}_sum " . array_sum($values);
                $lines[] = sprintf("{$name}_avg %.2f", array_sum($values) / count($values));
            }
        }

        // Timings
        foreach ($this->timings as $name => $values) {
            if (!empty($values)) {
                $lines[] = "{$name}_count " . count($values);
                $lines[] = sprintf("{$name}_sum_ms %.2f", array_sum($values));
                $lines[] = sprintf("{$name}_avg_ms %.2f", array_sum($values) / count($values));
                $lines[] = sprintf("{$name}_p50_ms %.2f", $this->get_percentile($name, 50) ?? 0);
                $lines[] = sprintf("{$name}_p99_ms %.2f", $this->get_percentile($name, 99) ?? 0);
            }
        }

        return implode("\n", $lines);
    }

    public function export_json(): string
    {
        return json_encode([
            'counters' => $this->counters,
            'gauges' => $this->gauges,
            'histograms' => $this->histograms,
            'timings' => $this->timings,
        ], JSON_PRETTY_PRINT);
    }
}

// Global instances
$GLOBALS['_php_tracer'] = new PHPTracer();
$GLOBALS['_php_metrics'] = new PHPMetrics();

function get_tracer(): PHPTracer
{
    return $GLOBALS['_php_tracer'];
}

function get_metrics(): PHPMetrics
{
    return $GLOBALS['_php_metrics'];
}

function trace_operation(string $name, callable $callback, array $attributes = []): mixed
{
    $tracer = get_tracer();
    $span = $tracer->start_span($name, $attributes);

    try {
        $result = $callback($span);
        $tracer->end_span('ok');
        return $result;
    } catch (Exception $e) {
        $tracer->end_span('error', $e->getMessage());
        throw $e;
    }
}

function timed_operation(string $name, callable $callback): mixed
{
    $metrics = get_metrics();
    $start = microtime(true);

    try {
        $result = $callback();
        $duration_ms = (microtime(true) - $start) * 1000;
        $metrics->record_timing($name, $duration_ms);
        return $result;
    } catch (Exception $e) {
        $duration_ms = (microtime(true) - $start) * 1000;
        $metrics->record_timing("{$name}_error", $duration_ms);
        throw $e;
    }
}

// Example usage
if (php_sapi_name() === 'cli') {
    $tracer = get_tracer();
    $metrics = get_metrics();

    // Start a trace
    $span = $tracer->start_span('example_operation', ['user_id' => '123']);
    $tracer->add_event('operation_started');

    // Simulate work
    usleep(100000);

    // End span
    $tracer->end_span('ok');

    // Record metrics
    $metrics->increment_counter('requests_total', 1, ['method' => 'GET']);
    $metrics->record_timing('request_duration_ms', 150.5);

    // Export
    echo "Trace:\n";
    echo $tracer->export_json() . "\n\n";
    echo "Metrics:\n";
    echo $metrics->to_prometheus_format() . "\n";
}
?>
