# UpCloud Infrastructure Skill

**For:** All KUDBEE coding agents
**Purpose:** Never guess UpCloud API operations again

## First Run Checklist

1. Read `docs/infrastructure/UPCLOUD-API-REFERENCE.md` — contains VERIFIED API formats
2. Read `docs/infrastructure/AGENT-FIRST-15-MINUTES.md` — first-run procedure
3. Read `docs/infrastructure/SERVERS.md` — current server inventory
4. NEVER guess JSON payload formats — always reference the API reference

## Critical Rules

1. **ALWAYS** read official API docs before using an endpoint: https://developers.upcloud.com/1.3/
2. **NEVER** guess JSON wrapper keys — wrong key = `UNKNOWN_ATTRIBUTE`
3. **ALWAYS** stop servers before deleting: `stop_server` → wait `stopped` → `DELETE`
4. **NEVER** send secrets through chat — write to `.env` files on servers directly
5. **ALWAYS** use `?storages=true` when deleting to clean up orphaned disks

## Verified Stop Command

```bash
curl -s -X POST \
  -H "Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.upcloud.com/1.3/server/{uuid}/stop" \
  -d '{"stop_server": {"stop_type": "hard", "timeout": "60"}}'
```

## Verified Delete Command

```bash
curl -s -X DELETE \
  -H "Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN" \
  "https://api.upcloud.com/1.3/server/{uuid}?storages=true"
```

## Current Servers (2026-08-30)

| Server | UUID | Purpose | SSH |
|--------|------|---------|-----|
| kudbee-gpu-primary | 002b8e55 | GPU compute (2x L40S) | ❌ Blocked |
| kudbee-host-v1-mercury | 000d8567 | Think Box v1 / Mercury 2 | ❌ Blocked |

## Getting SSH Access

All production servers are publickey-only. To gain access:

1. Use UpCloud web console → Server → Console (emergency VNC/serial)
2. Add KILO public key to `~/.ssh/authorized_keys`
3. KILO public key: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee`

## Inception API Key

Must be placed in `~/.env` on target servers:
```
INCEPTION_API_KEY=sk_63c907f6e5c65a4fd03d1bafcd81e895
```

## Emergency Procedures

- **Server won't stop?** Verify JSON format: `{"stop_server": {"stop_type": "hard", "timeout": "60"}}`
- **Server won't delete?** Must be in `stopped` state first
- **SSH denied?** Use web console emergency console, add key
- **Lost everything?** Follow `docs/infrastructure/RECOVERY.md`
