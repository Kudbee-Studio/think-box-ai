# CRITICAL LESSONS LEARNED — DO NOT FORGET

## UpCloud API Stop Command

**CORRECT:**
```json
{"stop_server": {"stop_type": "hard", "timeout": "60"}}
```

**WRONG:**
```json
{"stop_type": "hard"}
{"server": {"stop_type": "hard"}}
```

The wrapper key MUST be `stop_server`, not `server`. Using wrong key returns `UNKNOWN_ATTRIBUTE`.

## Server Deletion

Servers must be in `stopped` state before deletion. Delete returns `SERVER_STATE_ILLEGAL` if server is running.

## IPv6 Addresses

IPv6 is NOT automatic — it can be toggled on/off when creating servers. Public networks have both IPv4 and IPv6 subnets.

## SSH Access

- Account-level SSH keys are stored in UpCloud, NOT in this container
- New servers need the SSH key added via `login_user.ssh_keys` at creation time
- Foothold servers can be used as jump hosts to reach other servers on private networks
- NEVER delete the foothold server while it's your only access path

## Server Creation Flow

1. Create foothold FIRST
2. Verify SSH access to foothold
3. Create GPU server
4. Use foothold as jump host to reach GPU server private IP
5. Set up services (Docker, Inception API key, etc.)

## Emergency Access

If SSH is blocked:
1. Use UpCloud web console → Server → Emergency Console (VNC/serial)
2. Add KILO public key to `/root/.ssh/authorized_keys`
3. KILO public key: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee`

## Floating IPs

Floating IPs require OS-level configuration to route properly after attachment. They don't work immediately.

## Inception API Key

```
sk_63c907f6e5c65a4fd03d1bafcd81e895
```

Must be placed in `~/.env` on target servers with `chmod 600 ~/.env`.
