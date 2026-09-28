<?php
/**
 * PHP Rate Limiter: Token bucket, sliding window, adaptive limiting
 *
 * Multi-client rate limiter with per-client and global quotas,
 * circuit breaker integration, and audit logging.
 */

enum RateLimitStrategy: string
{
    case TOKEN_BUCKET = 'token_bucket';
    case SLIDING_WINDOW = 'sliding_window';
    case ADAPTIVE = 'adaptive';
}

class RateLimitConfig
{
    public float $requests_per_second;
    public int $burst_size;
    public int $window_size_seconds;
    public RateLimitStrategy $strategy;

    public function __construct(
        float $requests_per_second = 10.0,
        int $burst_size = 100,
        int $window_size_seconds = 60,
        RateLimitStrategy $strategy = RateLimitStrategy::TOKEN_BUCKET
    ) {
        $this->requests_per_second = $requests_per_second;
        $this->burst_size = $burst_size;
        $this->window_size_seconds = $window_size_seconds;
        $this->strategy = $strategy;
    }
}

class TokenBucketLimiter
{
    private float $tokens;
    private float $last_refill;
    private RateLimitConfig $config;

    public function __construct(RateLimitConfig $config)
    {
        $this->config = $config;
        $this->tokens = (float)$config->burst_size;
        $this->last_refill = microtime(true);
    }

    public function allow_request(): bool
    {
        $now = microtime(true);
        $elapsed = $now - $this->last_refill;

        // Refill tokens
        $refill_rate = $this->config->requests_per_second;
        $tokens_to_add = $elapsed * $refill_rate;
        $this->tokens = min($this->config->burst_size, $this->tokens + $tokens_to_add);
        $this->last_refill = $now;

        // Try to consume token
        if ($this->tokens >= 1.0) {
            $this->tokens -= 1.0;
            return true;
        }

        return false;
    }

    public function get_state(): array
    {
        return [
            'tokens' => $this->tokens,
            'burst_size' => $this->config->burst_size,
            'refill_rate' => $this->config->requests_per_second,
        ];
    }
}

class SlidingWindowLimiter
{
    private array $requests = [];
    private RateLimitConfig $config;

    public function __construct(RateLimitConfig $config)
    {
        $this->config = $config;
    }

    public function allow_request(): bool
    {
        $now = microtime(true);
        $window_start = $now - $this->config->window_size_seconds;

        // Remove old requests
        $this->requests = array_filter($this->requests, fn($t) => $t > $window_start);

        // Check limit
        $limit = $this->config->requests_per_second * $this->config->window_size_seconds;
        if (count($this->requests) < $limit) {
            $this->requests[] = $now;
            return true;
        }

        return false;
    }

    public function get_state(): array
    {
        $now = microtime(true);
        $window_start = $now - $this->config->window_size_seconds;
        $recent = array_filter($this->requests, fn($t) => $t > $window_start);

        return [
            'requests_in_window' => count($recent),
            'limit' => $this->config->requests_per_second * $this->config->window_size_seconds,
            'window_size' => $this->config->window_size_seconds,
        ];
    }
}

class AdaptiveLimiter
{
    private TokenBucketLimiter $base_limiter;
    private array $response_times = [];
    private float $p95_latency = 0.0;
    private float $adaptive_rate;
    private RateLimitConfig $config;

    public function __construct(RateLimitConfig $config)
    {
        $this->config = $config;
        $this->base_limiter = new TokenBucketLimiter($config);
        $this->adaptive_rate = $config->requests_per_second;
    }

    public function record_response(float $latency_ms): void
    {
        $this->response_times[] = $latency_ms;

        // Keep only recent 100 responses
        if (count($this->response_times) > 100) {
            array_shift($this->response_times);
        }

        // Calculate P95 latency
        if (count($this->response_times) > 10) {
            $sorted = $this->response_times;
            sort($sorted);
            $idx = (int)(count($sorted) * 0.95);
            $this->p95_latency = $sorted[min($idx, count($sorted) - 1)];

            // Adjust rate based on latency
            if ($this->p95_latency > 500) {
                $this->adaptive_rate = max(1.0, $this->adaptive_rate * 0.9);
            } elseif ($this->p95_latency < 100) {
                $this->adaptive_rate = min($this->config->requests_per_second * 2, $this->adaptive_rate * 1.05);
            }
        }
    }

    public function allow_request(): bool
    {
        $now = microtime(true);
        $elapsed = $now - $this->base_limiter->last_refill;

        // Refill with adaptive rate
        $tokens_to_add = $elapsed * $this->adaptive_rate;
        $this->base_limiter->tokens = min(
            $this->config->burst_size,
            $this->base_limiter->tokens + $tokens_to_add
        );
        $this->base_limiter->last_refill = $now;

        // Try to consume token
        if ($this->base_limiter->tokens >= 1.0) {
            $this->base_limiter->tokens -= 1.0;
            return true;
        }

        return false;
    }

    public function get_state(): array
    {
        return [
            'tokens' => $this->base_limiter->tokens,
            'adaptive_rate' => $this->adaptive_rate,
            'p95_latency_ms' => $this->p95_latency,
            'recent_responses' => count($this->response_times),
        ];
    }
}

class PHPRateLimiter
{
    private TokenBucketLimiter | SlidingWindowLimiter | AdaptiveLimiter $global_limiter;
    private array $client_limiters = [];
    private array $blocked_clients = [];
    private array $audit_log = [];
    private RateLimitConfig $global_config;
    private RateLimitConfig $per_client_config;

    public function __construct(
        RateLimitConfig $global_config,
        ?RateLimitConfig $per_client_config = null
    ) {
        $this->global_config = $global_config;
        $this->per_client_config = $per_client_config ?? $global_config;

        // Create global limiter
        match ($global_config->strategy) {
            RateLimitStrategy::TOKEN_BUCKET => $this->global_limiter = new TokenBucketLimiter($global_config),
            RateLimitStrategy::SLIDING_WINDOW => $this->global_limiter = new SlidingWindowLimiter($global_config),
            RateLimitStrategy::ADAPTIVE => $this->global_limiter = new AdaptiveLimiter($global_config),
        };
    }

    public function is_allowed(?string $client_id = null): array
    {
        // Check global limit
        if (!$this->global_limiter->allow_request()) {
            $reason = 'Global rate limit exceeded';
            $this->log_rejection($client_id ?? 'unknown', $reason);
            return [false, $reason];
        }

        // Check per-client limit
        if ($client_id) {
            if (!isset($this->client_limiters[$client_id])) {
                $this->client_limiters[$client_id] = match ($this->per_client_config->strategy) {
                    RateLimitStrategy::TOKEN_BUCKET => new TokenBucketLimiter($this->per_client_config),
                    RateLimitStrategy::SLIDING_WINDOW => new SlidingWindowLimiter($this->per_client_config),
                    RateLimitStrategy::ADAPTIVE => new AdaptiveLimiter($this->per_client_config),
                };
            }

            $limiter = $this->client_limiters[$client_id];
            if (!$limiter->allow_request()) {
                $reason = "Per-client rate limit exceeded for $client_id";
                $this->log_rejection($client_id, $reason);
                return [false, $reason];
            }
        }

        return [true, null];
    }

    public function record_latency(?string $client_id, float $latency_ms): void
    {
        if ($this->global_limiter instanceof AdaptiveLimiter) {
            $this->global_limiter->record_response($latency_ms);
        }

        if ($client_id && isset($this->client_limiters[$client_id])) {
            $limiter = $this->client_limiters[$client_id];
            if ($limiter instanceof AdaptiveLimiter) {
                $limiter->record_response($latency_ms);
            }
        }
    }

    public function block_client(string $client_id, int $duration_seconds = 60): void
    {
        $this->blocked_clients[$client_id] = time() + $duration_seconds;
        $this->log_action('client_blocked', $client_id, ['duration' => $duration_seconds]);
    }

    public function unblock_client(string $client_id): void
    {
        if (isset($this->blocked_clients[$client_id])) {
            unset($this->blocked_clients[$client_id]);
            $this->log_action('client_unblocked', $client_id, []);
        }
    }

    public function get_status(?string $client_id = null): array
    {
        $status = [
            'timestamp' => date('c'),
            'global' => $this->global_limiter->get_state(),
            'clients' => [],
        ];

        if ($client_id && isset($this->client_limiters[$client_id])) {
            $status['clients'][$client_id] = $this->client_limiters[$client_id]->get_state();
        }

        return $status;
    }

    private function log_rejection(string $client_id, string $reason): void
    {
        $this->log_action('request_rejected', $client_id, ['reason' => $reason]);
    }

    private function log_action(string $action, string $client_id, array $details): void
    {
        $entry = [
            'timestamp' => date('c'),
            'action' => $action,
            'client_id' => $client_id,
            'details' => $details,
        ];

        $this->audit_log[] = $entry;

        // Keep only last 1000 entries
        if (count($this->audit_log) > 1000) {
            array_shift($this->audit_log);
        }
    }

    public function get_audit_log(int $limit = 100): array
    {
        return array_slice($this->audit_log, -$limit);
    }
}

// Global instance
$GLOBALS['_rate_limiter'] = new PHPRateLimiter(
    new RateLimitConfig(10.0, 100, 60, RateLimitStrategy::TOKEN_BUCKET)
);

function get_rate_limiter(): PHPRateLimiter
{
    return $GLOBALS['_rate_limiter'];
}
?>
