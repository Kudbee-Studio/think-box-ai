# UPC-001: Stop Server API Format

**Status:** VERIFIED via official docs + testing
**Source:** https://developers.upcloud.com/1.3/8-servers/#stop-server

## Correct Format

```bash
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.upcloud.com/1.3/server/{uuid}/stop" \
  -d '{"stop_server": {"stop_type": "hard", "timeout": "60"}}'
```

## Wrong Formats (NEVER USE)

```bash
# WRONG - returns UNKNOWN_ATTRIBUTE
-d '{"stop_type": "hard"}'

# WRONG - returns UNKNOWN_ATTRIBUTE  
-d '{"server": {"stop_type": "hard"}}'

# WRONG - returns UNKNOWN_ATTRIBUTE
-d '{"stop_type": "hard", "timeout": "60"}'
```

## Key Insight

The JSON wrapper key MUST be `stop_server`, NOT `server`. Using the wrong key returns `UNKNOWN_ATTRIBUTE` error.

## Stop Types

| Type | Description |
|------|-------------|
| `hard` | Immediate power off |
| `soft` | Graceful shutdown |

## Python Helper

```python
def stop_server(uuid, hard=True):
    return api('POST', f'/server/{uuid}/stop', {
        'stop_server': {
            'stop_type': 'hard' if hard else 'soft',
            'timeout': '60'
        }
    })
```
