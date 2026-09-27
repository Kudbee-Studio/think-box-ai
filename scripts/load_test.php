#!/usr/bin/env php
<?php
/**
 * PHP Load Testing Script
 *
 * Comprehensive load testing with configurable patterns and metrics collection.
 */

require_once __DIR__ . '/../backend/rate_limiter.php';
require_once __DIR__ . '/../backend/observability.php';

class LoadTestConfig
{
    public string $target_url;
    public string $pattern = 'constant';
    public int $duration_seconds = 60;
    public float $requests_per_second = 10.0;
    public int $max_concurrent = 50;
    public int $ramp_up_seconds = 10;
    public float $spike_multiplier = 5.0;
    public int $spike_duration_seconds = 5;
    public ?string $auth_token = null;
}

class LoadTestMetrics
{
    public int $total_requests = 0;
    public int $successful_requests = 0;
    public int $failed_requests = 0;
    public float $min_latency_ms = PHP_FLOAT_MAX;
    public float $max_latency_ms = 0;
    public float $mean_latency_ms = 0;
    public float $p95_latency_ms = 0;
    public float $p99_latency_ms = 0;
    public float $throughput_rps = 0;
    public array $errors_by_code = [];
    public float $test_duration_seconds = 0;
    public string $timestamp;

    public function __construct()
    {
        $this->timestamp = date('c');
    }
}

class PHPLoadTester
{
    private LoadTestConfig $config;
    private array $latencies = [];
    private int $request_counter = 0;
    private float $start_time = 0;
    private LoadTestMetrics $metrics;

    public function __construct(LoadTestConfig $config)
    {
        $this->config = $config;
        $this->metrics = new LoadTestMetrics();
    }

    public function run(): LoadTestMetrics
    {
        $this->start_time = microtime(true);

        echo "🚀 Starting PHP load test: {$this->config->pattern} pattern\n";
        echo "   Target: {$this->config->target_url}\n";
        echo "   Duration: {$this->config->duration_seconds}s\n";
        echo "   Requests/sec: {$this->config->requests_per_second}\n";
        echo "   Max concurrent: {$this->config->max_concurrent}\n\n";

        match ($this->config->pattern) {
            'constant' => $this->run_constant_load(),
            'ramp' => $this->run_ramp_load(),
            'spike' => $this->run_spike_load(),
            'wave' => $this->run_wave_load(),
        };

        return $this->calculate_results();
    }

    private function run_constant_load(): void
    {
        $end_time = $this->start_time + $this->config->duration_seconds;
        $interval = 1.0 / $this->config->requests_per_second;

        while (microtime(true) < $end_time) {
            $this->send_request();
            usleep($interval * 1_000_000);
        }
    }

    private function run_ramp_load(): void
    {
        $end_time = $this->start_time + $this->config->duration_seconds;
        $ramp_step = $this->config->requests_per_second / $this->config->ramp_up_seconds;
        $current_rps = 1.0;

        while (microtime(true) < $end_time) {
            $elapsed = microtime(true) - $this->start_time;
            if ($elapsed < $this->config->ramp_up_seconds) {
                $current_rps = min($this->config->requests_per_second, $current_rps + $ramp_step);
            }

            $this->send_request();
            usleep((1.0 / $current_rps) * 1_000_000);
        }
    }

    private function run_spike_load(): void
    {
        $end_time = $this->start_time + $this->config->duration_seconds;
        $spike_start = $this->start_time + ($this->config->duration_seconds / 2);
        $spike_end = $spike_start + $this->config->spike_duration_seconds;

        while (microtime(true) < $end_time) {
            $now = microtime(true);
            $current_rps = $this->config->requests_per_second;

            if ($now >= $spike_start && $now < $spike_end) {
                $current_rps *= $this->config->spike_multiplier;
            }

            $this->send_request();
            usleep((1.0 / $current_rps) * 1_000_000);
        }
    }

    private function run_wave_load(): void
    {
        $end_time = $this->start_time + $this->config->duration_seconds;
        $wave_period = 10.0;

        while (microtime(true) < $end_time) {
            $elapsed = microtime(true) - $this->start_time;
            $wave_phase = fmod($elapsed, $wave_period) / $wave_period;
            $multiplier = 1.0 + 0.5 * (2.0 * ($wave_phase - 0.5));
            $current_rps = $this->config->requests_per_second * $multiplier;

            $this->send_request();
            usleep((1.0 / $current_rps) * 1_000_000);
        }
    }

    private function send_request(): void
    {
        $this->request_counter++;
        $start = microtime(true);

        try {
            $ch = curl_init();
            curl_setopt_array($ch, [
                CURLOPT_URL => $this->config->target_url,
                CURLOPT_POST => true,
                CURLOPT_TIMEOUT => 30,
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
                CURLOPT_POSTFIELDS => json_encode(['test' => 'load_test', 'request_id' => $this->request_counter]),
            ]);

            if ($this->config->auth_token) {
                curl_setopt($ch, CURLOPT_HTTPHEADER, [
                    'Content-Type: application/json',
                    'Authorization: Bearer ' . $this->config->auth_token,
                ]);
            }

            $response = curl_exec($ch);
            $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            $latency_ms = (microtime(true) - $start) * 1000;
            $this->latencies[] = $latency_ms;

            if ($http_code >= 200 && $http_code < 300) {
                $this->metrics->successful_requests++;
            } else {
                $this->metrics->failed_requests++;
                $this->metrics->errors_by_code[$http_code] = ($this->metrics->errors_by_code[$http_code] ?? 0) + 1;
            }
        } catch (Exception $e) {
            $latency_ms = (microtime(true) - $start) * 1000;
            $this->latencies[] = $latency_ms;
            $this->metrics->failed_requests++;
            $this->metrics->errors_by_code['error'] = ($this->metrics->errors_by_code['error'] ?? 0) + 1;
        }

        if ($this->request_counter % 100 === 0) {
            $success_rate = $this->metrics->successful_requests / $this->request_counter * 100;
            echo "  ✓ Sent {$this->request_counter} requests ({$success_rate:.1f}% success)\n";
        }
    }

    private function calculate_results(): LoadTestMetrics
    {
        $this->metrics->total_requests = $this->request_counter;
        $this->metrics->test_duration_seconds = microtime(true) - $this->start_time;

        if (!empty($this->latencies)) {
            sort($this->latencies);

            $this->metrics->min_latency_ms = min($this->latencies);
            $this->metrics->max_latency_ms = max($this->latencies);
            $this->metrics->mean_latency_ms = array_sum($this->latencies) / count($this->latencies);

            $this->metrics->p95_latency_ms = $this->get_percentile(95);
            $this->metrics->p99_latency_ms = $this->get_percentile(99);
        }

        $this->metrics->throughput_rps = $this->metrics->total_requests / $this->metrics->test_duration_seconds;

        return $this->metrics;
    }

    private function get_percentile(float $p): float
    {
        if (empty($this->latencies)) {
            return 0;
        }
        $idx = (int)(count($this->latencies) * ($p / 100));
        return $this->latencies[min($idx, count($this->latencies) - 1)];
    }
}

function main(): void
{
    $options = getopt('u:p:d:r:c:t:o:', ['url:', 'pattern:', 'duration:', 'rps:', 'max-concurrent:', 'token:', 'output:']);

    $config = new LoadTestConfig();
    $config->target_url = $options['u'] ?? $options['url'] ?? 'http://localhost:8000/api/v1/inference';
    $config->pattern = $options['p'] ?? $options['pattern'] ?? 'constant';
    $config->duration_seconds = (int)($options['d'] ?? $options['duration'] ?? 60);
    $config->requests_per_second = (float)($options['r'] ?? $options['rps'] ?? 10.0);
    $config->max_concurrent = (int)($options['c'] ?? $options['max-concurrent'] ?? 50);
    $config->auth_token = $options['t'] ?? $options['token'] ?? null;

    $tester = new PHPLoadTester($config);
    $result = $tester->run();

    // Print results
    echo "\n📊 Load Test Results\n";
    echo str_repeat('=', 60) . "\n";
    echo sprintf("Total Requests:     %d\n", $result->total_requests);
    echo sprintf("Successful:         %d (%.1f%%)\n", $result->successful_requests, $result->successful_requests / $result->total_requests * 100);
    echo sprintf("Failed:             %d\n", $result->failed_requests);
    echo sprintf("Throughput:         %.2f req/s\n", $result->throughput_rps);
    echo sprintf("Test Duration:      %.2f s\n", $result->test_duration_seconds);

    echo "\n⏱️  Latency Metrics\n";
    echo str_repeat('=', 60) . "\n";
    echo sprintf("Min:                %.2f ms\n", $result->min_latency_ms);
    echo sprintf("Max:                %.2f ms\n", $result->max_latency_ms);
    echo sprintf("Mean:               %.2f ms\n", $result->mean_latency_ms);
    echo sprintf("P95:                %.2f ms\n", $result->p95_latency_ms);
    echo sprintf("P99:                %.2f ms\n", $result->p99_latency_ms);

    if (!empty($result->errors_by_code)) {
        echo "\n⚠️  Errors by Status Code\n";
        echo str_repeat('=', 60) . "\n";
        foreach ($result->errors_by_code as $code => $count) {
            echo "$code: $count\n";
        }
    }

    // Save results
    if (isset($options['o']) || isset($options['output'])) {
        $output_file = $options['o'] ?? $options['output'];
        file_put_contents($output_file, json_encode($result, JSON_PRETTY_PRINT));
        echo "\n✅ Results saved to $output_file\n";
    }
}

main();
?>
