# Bootstrap Specification

**Last Updated:** 2026-08-30

---

## Purpose

Define the minimum prerequisites for a KUDBEE coding agent to begin work in this environment.

---

## Bootstrap Inputs

### Required Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `THINKBOX_UPCLOUD_API_TOKEN` | UpCloud infrastructure API | `ucat_01...` |
| `UPCLOUD_SSH_USER` | SSH login username | `root` |
| `GH_TOKEN` | GitHub repository access | `ghp_...` |
| `KILOCODE_TOKEN` | Kilo platform auth | `kka1...` |

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| python3 | 3.10+ | Runtime |
| curl | any | API calls |
| ssh | any | Server access |
| ssh-keygen | any | Key generation |
| git | any | Repository access |

### Required Files

| File | Purpose |
|------|---------|
| `~/.ssh/id_ed25519` or similar | SSH private key |
| `AGENTS.md` | Architecture rules |
| `pyproject.toml` | Project configuration |

---

## Bootstrap Sequence

```
STEP 1: ENVIRONMENT PREPARATION
    ├─ Verify Python 3.10+
    ├─ Verify curl available
    ├─ Verify SSH client available
    └─ Verify git available

STEP 2: CREDENTIAL VALIDATION
    ├─ Check THINKBOX_UPCLOUD_API_TOKEN present
    ├─ Check GH_TOKEN present
    └─ Check KILOCODE_TOKEN present

STEP 3: UPCLOUD API VALIDATION
    ├─ GET /1.3/server → verify JSON response
    ├─ GET /1.3/ip_address → verify IP list
    └─ GET /1.3/network → verify network list

STEP 4: INFRASTRUCTORY INVENTORY
    ├─ Parse all servers (UUID, title, IP, state)
    ├─ Parse all IPs (public, private, floating)
    ├─ Parse all networks (public, utility, private)
    └─ Parse all routers

STEP 5: SSH VALIDATION
    ├─ Check SSH key exists
    ├─ Attempt SSH to known accessible servers
    └─ Report which servers are accessible

STEP 6: KUBERNETES VALIDATION
    ├─ Check if kubectl available
    ├─ Check if K8s API responding on any server
    └─ Report cluster status

STEP 7: MERCURY DISCOVERY
    ├─ Search environment variables
    ├─ Search accessible servers
    └─ Report Mercury location/status

STEP 8: KUDBEE DISCOVERY
    ├─ Verify repository cloned
    ├─ Run tests
    └─ Verify bootstrap works

STEP 9: REPORT
    ├─ VERIFIED items
    ├─ UNKNOWN items
    └─ BLOCKED items
```

---

## Validation Tests

| Test | Command | Expected |
|------|---------|----------|
| Python | `python3 --version` | 3.10+ |
| curl | `curl --version` | Any version |
| UpCloud API | `curl -s -H "Authorization: Bearer $TOKEN" https://api.upcloud.com/1.3/server \| python3 -c "import sys,json; print(len(json.load(sys.stdin)['servers']['server']))"` | Number > 0 |
| Git | `git remote -v` | origin → Kudbee-Studio |
| SSH key | `ls ~/.ssh/id_*` | At least one key |
| KUDBEE core | `python3 -c "from core.foundation.bootstrap import bootstrap; print('OK')"` | OK |
| Think Token | `python3 -c "from think_box_ai.token import ThinkToken; print('OK')"` | OK |

---

## Failure Modes

| Failure | Response |
|---------|----------|
| Missing env var | Report which var, STOP |
| API token invalid | Report auth failure, STOP |
| No SSH key | Generate new key, instruct user to add to UpCloud |
| SSH access denied | Report server, instruct emergency console |
| K8s not running | Report status, continue without K8s |
| Mercury not found | Report UNKNOWN, continue |
| Tests fail | Report failures, continue with caution |

---

## Bootstrap Output

After successful bootstrap, the agent should produce:

1. Server inventory (all servers with UUIDs, IPs, states)
2. IP inventory (all public/private/floating IPs)
3. Network inventory (all networks with routers)
4. Access matrix (which servers are accessible)
5. Service discovery (what's running where)
6. VERIFIED / UNKNOWN / BLOCKED classification
