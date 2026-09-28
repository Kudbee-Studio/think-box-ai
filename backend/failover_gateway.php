<?php
/**
 * Enterprise Failover Gateway
 *
 * PHP-based gateway that routes requests to endpoints with automatic failover.
 * Maintains health status, automatic retry, and graceful degradation.
 */

class FailoverGateway
{
    private array $endpoints = [];
    private array $health_cache = [];
    private int $cache_ttl = 30; // seconds
    private int $max_retries = 3;
    private int $timeout = 5; // seconds
    private array $audit_log = [];

    public function __construct(array $endpoints = [])
    {
        $this->endpoints = $endpoints;
        foreach ($this->endpoints as $name => $url) {
            $this->health_cache[$name] = [
                'healthy' => true,
                'last_check' => 0,
                'failure_count' => 0,
            ];
        }
    }

    /**
     * Add an endpoint to the gateway
     */
    public function add_endpoint(string $name, string $url): void
    {
        $this->endpoints[$name] = $url;
        $this->health_cache[$name] = [
            'healthy' => true,
            'last_check' => 0,
            'failure_count' => 0,
        ];
    }

    /**
     * Get all endpoints
     */
    public function get_endpoints(): array
    {
        return $this->endpoints;
    }

    /**
     * Check if endpoint is healthy
     */
    private function is_healthy(string $name): bool
    {
        if (!isset($this->health_cache[$name])) {
            return false;
        }

        $cache = $this->health_cache[$name];
        $now = time();

        // Use cache if fresh
        if ($now - $cache['last_check'] < $this->cache_ttl) {
            return $cache['healthy'];
        }

        // Check actual health
        $healthy = $this->check_health($name);
        $this->health_cache[$name]['healthy'] = $healthy;
        $this->health_cache[$name]['last_check'] = $now;

        if ($healthy) {
            $this->health_cache[$name]['failure_count'] = 0;
        } else {
            $this->health_cache[$name]['failure_count']++;
        }

        return $healthy;
    }

    /**
     * Perform actual health check on endpoint
     */
    private function check_health(string $name): bool
    {
        if (!isset($this->endpoints[$name])) {
            return false;
        }

        $url = $this->endpoints[$name] . '/health';

        try {
            $ch = curl_init();
            curl_setopt_array($ch, [
                CURLOPT_URL => $url,
                CURLOPT_TIMEOUT => $this->timeout,
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_HTTPHEADER => ['Accept: application/json'],
            ]);

            $response = curl_exec($ch);
            $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            $healthy = $http_code === 200;

            $this->log_audit('health_check', $name, [
                'url' => $url,
                'http_code' => $http_code,
                'healthy' => $healthy,
            ]);

            return $healthy;
        } catch (Exception $e) {
            $this->log_audit('health_check_error', $name, [
                'url' => $url,
                'error' => $e->getMessage(),
            ]);
            return false;
        }
    }

    /**
     * Get healthy endpoints in priority order
     */
    private function get_healthy_endpoints(): array
    {
        $healthy = [];
        foreach (array_keys($this->endpoints) as $name) {
            if ($this->is_healthy($name)) {
                $healthy[] = $name;
            }
        }
        return $healthy;
    }

    /**
     * Forward request to an endpoint with retry logic
     */
    public function forward_request(
        string $method,
        string $path,
        ?array $headers = null,
        ?string $body = null
    ): array {
        $healthy_endpoints = $this->get_healthy_endpoints();

        if (empty($healthy_endpoints)) {
            return $this->error_response(503, 'All endpoints are down', 'SERVICE_UNAVAILABLE');
        }

        $last_error = null;

        // Try each healthy endpoint
        foreach ($healthy_endpoints as $endpoint_name) {
            for ($attempt = 0; $attempt < $this->max_retries; $attempt++) {
                try {
                    $result = $this->call_endpoint(
                        $endpoint_name,
                        $method,
                        $path,
                        $headers,
                        $body
                    );

                    $this->log_audit('request_success', $endpoint_name, [
                        'method' => $method,
                        'path' => $path,
                        'attempt' => $attempt + 1,
                        'http_code' => $result['http_code'],
                    ]);

                    return $result;
                } catch (Exception $e) {
                    $last_error = $e;
                    $this->log_audit('request_retry', $endpoint_name, [
                        'method' => $method,
                        'path' => $path,
                        'attempt' => $attempt + 1,
                        'error' => $e->getMessage(),
                    ]);

                    // Mark endpoint as unhealthy after failures
                    if ($attempt >= $this->max_retries - 1) {
                        $this->health_cache[$endpoint_name]['healthy'] = false;
                        $this->health_cache[$endpoint_name]['failure_count']++;
                    }

                    usleep(100000 * ($attempt + 1)); // Exponential backoff
                }
            }
        }

        // All endpoints failed
        $this->log_audit('all_endpoints_failed', 'gateway', [
            'method' => $method,
            'path' => $path,
            'healthy_count' => count($healthy_endpoints),
            'error' => $last_error ? $last_error->getMessage() : 'Unknown error',
        ]);

        return $this->error_response(503, 'All endpoints failed', 'GATEWAY_ERROR');
    }

    /**
     * Call a specific endpoint
     */
    private function call_endpoint(
        string $endpoint_name,
        string $method,
        string $path,
        ?array $headers = null,
        ?string $body = null
    ): array {
        $url = $this->endpoints[$endpoint_name] . $path;

        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_CUSTOMREQUEST => $method,
            CURLOPT_TIMEOUT => $this->timeout,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HEADER => true,
        ]);

        // Add default headers
        $request_headers = ['Accept: application/json', 'Content-Type: application/json'];
        if ($headers) {
            $request_headers = array_merge($request_headers, $headers);
        }
        curl_setopt($ch, CURLOPT_HTTPHEADER, $request_headers);

        // Add body if present
        if ($body) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
        }

        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_error = curl_error($ch);
        curl_close($ch);

        if ($curl_error) {
            throw new Exception($curl_error);
        }

        // Split headers and body
        $header_size = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
        $response_headers = substr($response, 0, $header_size);
        $response_body = substr($response, $header_size);

        return [
            'http_code' => $http_code,
            'headers' => $response_headers,
            'body' => $response_body,
            'endpoint' => $endpoint_name,
        ];
    }

    /**
     * Get gateway status
     */
    public function get_status(): array
    {
        $status = [];
        foreach ($this->endpoints as $name => $url) {
            $cache = $this->health_cache[$name] ?? [];
            $status[$name] = [
                'url' => $url,
                'healthy' => $this->is_healthy($name),
                'failure_count' => $cache['failure_count'] ?? 0,
                'last_check' => date('c', $cache['last_check'] ?? 0),
            ];
        }
        return $status;
    }

    /**
     * Log audit trail
     */
    private function log_audit(string $event_type, string $endpoint, array $details): void
    {
        $entry = [
            'timestamp' => date('c'),
            'event_type' => $event_type,
            'endpoint' => $endpoint,
            'details' => $details,
        ];

        $this->audit_log[] = $entry;

        // Also write to syslog
        error_log(json_encode($entry));
    }

    /**
     * Get audit log
     */
    public function get_audit_log(int $limit = 100): array
    {
        return array_slice($this->audit_log, -$limit);
    }

    /**
     * Error response
     */
    private function error_response(int $code, string $message, string $error_code): array
    {
        return [
            'http_code' => $code,
            'body' => json_encode([
                'status' => 'error',
                'message' => $message,
                'error_code' => $error_code,
                'timestamp' => date('c'),
            ]),
            'endpoint' => 'gateway',
            'headers' => "HTTP/1.1 {$code} " . ($code === 503 ? 'Service Unavailable' : 'Error') . "\r\nContent-Type: application/json\r\n",
        ];
    }
}

// Example usage
$gateway = new FailoverGateway([
    'primary' => 'http://localhost:8000/api/v1',
    'secondary' => 'http://localhost:8001/api/v1',
    'tertiary' => 'http://localhost:8002/api/v1',
]);

// Route incoming request
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    // CORS preflight
    header('Access-Control-Allow-Origin: *');
    header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type, Authorization');
    exit(0);
}

// Forward the request
$method = $_SERVER['REQUEST_METHOD'];
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$headers = getallheaders();
$body = file_get_contents('php://input');

$result = $gateway->forward_request($method, $path, array_values($headers), $body ?: null);

// Send response
http_response_code($result['http_code']);
echo $result['body'];

// Status endpoint
if ($path === '/gateway/status') {
    header('Content-Type: application/json');
    echo json_encode([
        'timestamp' => date('c'),
        'endpoints' => $gateway->get_status(),
        'audit_log' => $gateway->get_audit_log(10),
    ]);
}
?>
