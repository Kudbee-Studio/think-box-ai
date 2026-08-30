# KUDBEE Infrastructure Skill — UpCloud Operations

**CRITICAL:** This document contains VERIFIED, TESTED patterns.
Never guess. Always reference this document.

---

## Rate Limiter

ALWAYS use the rate limiter for API calls:

```python
from rate_limiter import UpCloudAPI
api = UpCloudAPI()
```

The rate limiter enforces:
- 2-second minimum delay between API calls
- 1 concurrent request max
- Exponential backoff on retries

---

## Server Lifecycle

### Create Server (VERIFIED)
```python
api.create_server(
    title='my-server',
    hostname='my-server',
    plan='1xCPU-1GB',
    ssh_keys=['ssh-ed25519 AAAA...']
)
```

### Stop Server (VERIFIED)
```python
api.stop_server(uuid, hard=True)
api.wait_for_stopped(uuid)
```

**JSON format:** `{"stop_server": {"stop_type": "hard", "timeout": "60"}}`

### Delete Server (VERIFIED)
```python
api.delete_server(uuid)
# OR
api.delete_server_full(uuid)  # stop + wait + delete
```

### Start Server (VERIFIED)
```python
api.start_server(uuid)
api.wait_for_started(uuid)
```

---

## SSH Access

### Current Working Key
- Private key: `~/.ssh/kilocloud`
- Public key: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee`

### SSH Command
```bash
ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no -i ~/.ssh/kilocloud root@<ip>
```

### Jump Host Pattern
```bash
ssh -o ProxyJump=root@<foothold-ip> root@<target-private-ip>
```

---

## Common Mistakes (NEVER DO THESE)

1. **Wrong stop JSON:** `{"server": {...}}` → Use `{"stop_server": {...}}`
2. **Delete while running:** Always stop first, wait for `stopped`, then delete
3. **Multiple concurrent servers:** Create ONE at a time, verify SSH works, then create next
4. **Not waiting long enough:** Cloud-init takes 2-5 minutes. Wait for `started` state.
5. **Forgetting to wait after stop:** Stop is async. Poll until `stopped`.

---

## Server Configurations

### Foothold Server
- Plan: `1xCPU-1GB`
- Storage: 10 GB maxiops
- SSH: KILO key
- Purpose: Jump host to reach other servers

### GPU Server
- Plan: `GPU-SPOT-12xCPU-128GB-2xL40S`
- Storage: 300 GB maxiops
- SSH: KILO key
- User-data: Installs Docker, NVIDIA drivers, Inception API key

---

## Inception API Key

```
INCEPTION_API_KEY=sk_63c907f6e5c65a4fd03d1bafcd81e895
```

Install on server:
```bash
echo 'INCEPTION_API_KEY=sk_63c907f6e5c65a4fd03d1bafcd81e895' > /root/.env
chmod 600 /root/.env
```

---

## IPv6

IPv6 is toggleable at server creation. Public networks have both IPv4 and IPv6.
To disable IPv6, do not assign an IPv6 address at creation time.

---

## Emergency Access

If SSH is blocked:
1. UpCloud Control Panel → Server → Console (emergency VNC)
2. Add KILO public key to `/root/.ssh/authorized_keys`
3. Or enable password auth via cloud-init

---

## Reference

- UpCloud API docs: https://developers.upcloud.com/1.3/
- UpCloud server ops: https://developers.upcloud.com/1.3/8-servers/
- Rate limiter: `rate_limiter.py`
- Bootstrap: `bootstrap.py`
