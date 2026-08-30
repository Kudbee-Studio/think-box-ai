# Agent First 15 Minutes

**Last Updated:** 2026-08-30

---

## Purpose

This document tells any coding agent (Kilo, Claude, Codex, etc.) exactly what to do in the first 15 minutes of joining the KUDBEE environment. Follow this procedure. Do not improvise.

---

## FIRST: Read Project Boot/Entrypoint (2 min)

1. Read `AGENTS.md` — architecture rules
2. Read `README.md` — project overview
3. Read `pyproject.toml` — project configuration
4. Note: This is a Python 3.10+ project with stdlib-only dependencies in Phase 0

---

## SECOND: Read Infrastructure Documentation (3 min)

1. Read `docs/infrastructure/README.md` — infrastructure overview
2. Read `docs/infrastructure/ACCESS.md` — how to access everything
3. Read `docs/infrastructure/SERVERS.md` — what servers exist
4. Read `docs/infrastructure/CREDENTIALS.md` — what credentials are available

---

## THIRD: Validate Credential Interfaces (2 min)

Check these environment variables exist:
```bash
echo $THINKBOX_UPCLOUD_API_TOKEN  # UpCloud API
echo $GH_TOKEN                     # GitHub
echo $KILOCODE_TOKEN               # Kilo platform
echo $UPCLOUD_SSH_USER             # SSH username (root)
```

If any are missing, **STOP** and report to user. Do not proceed without credentials.

---

## FOURTH: Validate UpCloud API (2 min)

```bash
curl -s -H "Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN" \
  https://api.upcloud.com/1.3/server | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Servers: {len(data[\"servers\"][\"server\"])}')
for s in data['servers']['server']:
    print(f'  {s[\"title\"]:<40} {s[\"state\"]:<10} {s[\"zone\"]}')
"
```

Expected: List of 10 servers, all "started".

If this fails, **STOP**. Token may be expired.

---

## FIFTH: Inventory Infrastructure (2 min)

```bash
# Get all IPs
curl -s -H "Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN" \
  https://api.upcloud.com/1.3/ip_address | python3 -c "
import sys, json
data = json.load(sys.stdin)
for ip in data['ip_addresses']['ip_address']:
    floating = ' (FLOATING)' if ip.get('floating') == 'yes' else ''
    print(f'{ip[\"address\"]:<18} {ip[\"server\"]}{floating}')
"
```

Compare against `docs/infrastructure/SERVERS.md`. Note any new/changed servers.

---

## SIXTH: Validate SSH (2 min)

```bash
# Check if SSH key exists
ls ~/.ssh/id_* 2>/dev/null

# Try to SSH to foothold (if key available)
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
  -i ~/.ssh/kilocloud root@87.58.149.82 "hostname" 2>&1

# Try other servers (will likely fail with publickey)
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
  root@87.58.149.32 "hostname" 2>&1
```

Expected: Foothold accessible (if key present), others blocked.

If SSH fails, **DO NOT** attempt to:
- Reset the server
- Reinstall the server
- Detach storage
- Modify firewall rules

Instead, use UpCloud web console emergency console for SSH recovery.

---

## SEVENTH: Validate Kubernetes (1 min)

```bash
# Check if kubectl is available
which kubectl 2>/dev/null || echo "kubectl not installed"

# Check if K8s API is responding on known server
nc -zv -w 3 10.6.22.159 6443 2>&1 || echo "K8s API not responding"
```

Expected: kubectl not installed, K8s API not responding.

If K8s IS responding, read `docs/infrastructure/KUBERNETES.md` for next steps.

---

## EIGHTH: Locate Mercury (1 min)

```bash
# Search environment variables
env | grep -i mercury

# Search accessible servers (if SSH available)
ssh -o ConnectTimeout=5 root@87.58.149.82 \
  "find / -maxdepth 3 -name '*mercury*' 2>/dev/null | head -5"
```

Expected: Mercury not found in this environment.

If Mercury IS found, read `docs/infrastructure/MERCURY.md` for integration steps.

---

## NINTH: Locate KUDBEE (1 min)

```bash
# Verify repository
git remote -v
git log --oneline -3

# Run tests
python3 -m unittest discover -s tests/unit -v 2>&1 | tail -5

# Verify bootstrap
python3 -c "from core.foundation.bootstrap import bootstrap; print('KUDBEE core OK')"
```

Expected: Tests pass, bootstrap works.

---

## TENTH: Report VERIFIED / UNKNOWN (1 min)

Produce a summary:

```
INFRASTRUCTURE STATUS
═══════════════════
✅ VERIFIED:
  - UpCloud API access (10 servers visible)
  - Server inventory matches documentation
  - KUDBEE core runtime functional
  - Think Token logic functional

❌ BLOCKED:
  - GPU server SSH (no private key)
  - All production server SSH (publickey-only)

❓ UNKNOWN:
  - Mercury 2 location
  - Kubernetes cluster state (needs SSH to investigate)
  - Mercury 2 source code location
```

---

## CRITICAL RULES

1. **NEVER** delete, stop, or modify production servers without explicit user approval
2. **NEVER** rotate credentials or regenerate tokens
3. **NEVER** expose secret values in output
4. **NEVER** attempt destructive SSH recovery (storage detaching, reinstall)
5. **ALWAYS** use web console emergency console for SSH key recovery
6. **ALWAYS** read infrastructure docs before making API calls
7. **ALWAYS** report VERIFIED vs UNKNOWN vs BLOCKED clearly

---

## When Authentication Fails

If SSH access fails:

1. **DO NOT** try to reset the server
2. **DO NOT** try to reinstall
3. **DO NOT** try to detach storage
4. **DO** report the failure clearly
5. **DO** suggest web console emergency console
6. **DO** provide the KILO public key for adding to authorized_keys

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee
```
