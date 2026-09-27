# Security Policy

## Reporting a Security Vulnerability

If you discover a security vulnerability in Think Box AI, please report it by emailing
the project maintainers. Please do not open a public issue for security vulnerabilities.

## Security Measures

### Authentication
- All API endpoints (except `/health`) require a valid API key
- API keys are passed via the `X-API-Key` header or `api_key` query parameter
- Keys are compared using constant-time comparison to prevent timing attacks

### Rate Limiting
- Default: 100 requests per minute per IP
- Configurable via `THINKBOX_RATE_LIMIT` environment variable
- Returns 429 status with `Retry-After` header when exceeded

### CORS
- Only allowed origins can make cross-origin requests
- Configurable via `THINKBOX_ALLOWED_ORIGINS` environment variable
- Credentials are not allowed with wildcard origins

### Input Validation
- All user inputs are validated and sanitized
- Maximum request body size: 1MB
- Maximum goal length: 10,000 characters
- Maximum iterations: 100
- Path traversal is blocked in all file operations

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy: default-src 'self'`
- `Referrer-Policy: strict-origin-when-cross-origin`

### Audit Logging
- All API requests are logged to SQLite
- Audit log includes: timestamp, action, actor, outcome, metadata
- Audit log is append-only

### Infrastructure Secrets
- No secrets are stored in the repository
- All configuration is via environment variables
- Infrastructure details (IPs, UUIDs) are excluded from version control

### Agent OS Web Runtime

The Agent OS web runtime is a development-oriented surface until authentication
and approval enforcement are added to its WebSocket and plugin routes. Do not
expose port `3000` directly to the internet. In particular:

- `shell_exec` can execute commands and must be sandboxed before production use.
- `file_write` is limited to an approved workspace in production deployments.
- `http_request` and `rss_feed` require network allowlists and egress controls.
- Uploads must retain the 50 MB per-file and 500-file limits, reject traversal,
	and be scanned before agent access.
- Ollama should remain on a private network and must not be publicly exposed.
- Plugin and middleware results are session memory and should be retained only
	according to the deployment's data-retention policy.

## Production Deployment Checklist

- [ ] Change default API key
- [ ] Set strong `THINKBOX_API_KEY` (use `python3 -c "import secrets; print('tb_' + secrets.token_urlsafe(32))"`)
- [ ] Configure `THINKBOX_ALLOWED_ORIGINS` for your domain
- [ ] Set `THINKBOX_RATE_LIMIT` appropriately
- [ ] Use HTTPS (TLS termination via reverse proxy)
- [ ] Run behind a reverse proxy (nginx, Caddy, or traefik)
- [ ] Enable firewall (allow only 80/443)
- [ ] Set up log rotation
- [ ] Configure monitoring and alerting
- [ ] Use Docker with non-root user
- [ ] Keep dependencies updated
