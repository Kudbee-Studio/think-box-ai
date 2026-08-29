# KUDBEE Environment Capability Matrix

**Generated:** 2026-08-29T09:48:00+00:00
**Host:** cloudchamber (session container, NOT kudbee-host-v1)
**Method:** Name-only inventory from `os.environ`. No values read. Safe probes only.

> **Rule:** Names and set/empty/unset state only. No values printed. No secrets
> committed. If a probe would require a secret header, skipped and marked
> `present_untested`.

---

## 1. Environment variables — names and state

| Name | State |
|------|-------|
| GH_TOKEN | set |
| THINKBOX_UPCLOUD_API_TOKEN | set |
| UPCLOUD_SERVER_HOSTNAME | set |
| UPCLOUD_SERVER_IP | set |
| UPCLOUD_SSH_KEY_PATH | set |
| UPCLOUD_SSH_USER | set |

Patterns searched: VERCEL CURSOR OPENAI ANTHROPIC XAI GROK UPCLOUD AWS REDIS
STASH POSTGRES DATABASE SQLITE GITHUB FIRECRACKER KVM OLLAMA OPENROUTER S3 R2
JWT SECRET TOKEN KEY PASSWORD HOOK

Total names matching patterns: **6** (KILO_* infrastructure vars excluded from
capability mapping — they belong to the agent runtime, not the repo).

---

## 2. Safe probes

| Probe | Result |
|-------|--------|
| `stat -c '%F' /dev/kvm` | character special file |
| `test -c /dev/kvm` | PASS |
| `KVM_GET_API_VERSION` ioctl | KVM_API_VERSION=12 IOCTL_OK |
| `grep -c svm /proc/cpuinfo` | 4 (AMD SVM present) |
| `systemd-detect-virt` | kvm (this is a KVM guest) |
| `which firecracker` | MISSING |
| `ls /srv/firecracker/` | MISSING |
| `redis-cli` | not installed |
| `python3 -c "import sqlite3"` | OK |

**Finding:** This session host (`cloudchamber`) exposes usable `/dev/kvm` with
working `KVM_GET_API_VERSION` ioctl — unlike the documented `kudbee-host-v1`
UpCloud node where `/dev/kvm` is a directory. Firecracker binary and guest
kernel/rootfs are not installed.

---

## 3. Capability mapping (onto THIS repo)

### Models

| Capability | Status | Evidence |
|------------|--------|----------|
| OpenAI / OpenAI-compatible | **code exists unconfigured** | `core/providers/openai_compat.py` exists; no `OPENAI_API_KEY` set |
| Anthropic | **code exists unconfigured** | Routed via `openai_compat` or adapter; no `ANTHROPIC_API_KEY` set |
| xAI / Grok | **code exists unconfigured** | Same OpenAI-compat path; no `XAI_API_KEY` set |
| Ollama | **code exists unconfigured** | Same OpenAI-compat path; no `OLLAMA_BASE_URL` set |
| OpenRouter | **code exists unconfigured** | Same OpenAI-compat path; no `OPENROUTER_API_KEY` set |

**Summary:** Provider abstraction code exists. Zero model API keys configured.
No model calls possible from this environment.

### Git

| Capability | Status | Evidence |
|------------|--------|----------|
| GitHub operations | **usable now** | `GH_TOKEN` set; `origin` points to `github.com/Kudbee-Studio/think-box-ai` |

### Data

| Capability | Status | Evidence |
|------------|--------|----------|
| SQLite | **usable now** | `sqlite3` stdlib available; `core/memory/store.py` uses it |
| Redis | **ignore** | No redis-cli, no `REDIS_HOST`; repo uses SQLite, not Redis |
| PostgreSQL | **ignore** | No driver, no `POSTGRES_*` vars |

### Queue

| Capability | Status | Evidence |
|------------|--------|----------|
| Task queue | **ignore** | No queue code in repo; no `RQ`/`CELERY`/`SQS` vars |

### Deploy

| Capability | Status | Evidence |
|------------|--------|----------|
| Vercel | **ignore** | No `VERCEL_*` vars; no deploy code in repo |

### Cloud

| Capability | Status | Evidence |
|------------|--------|----------|
| UpCloud API | **configured no code** | `THINKBOX_UPCLOUD_API_TOKEN` + server vars set, but this repo contains no UpCloud API client (access is via `kubectl` + SSH per AGENTS.md §13) |
| AWS / GCP / Azure | **ignore** | No credentials set |

### Editor

| Capability | Status | Evidence |
|------------|--------|----------|
| Cursor | **ignore** | No `CURSOR_*` vars; no editor integration code |

### Execution / Security

| Capability | Status | Evidence |
|------------|--------|----------|
| KVM (this host) | **usable now** | `/dev/kvm` char device, `KVM_GET_API_VERSION` ioctl OK, `svm` CPU flag present |
| Firecracker | **code exists unconfigured** | `core/execution/firecracker.py` fully implemented; binary + kernel + rootfs missing on this host |
| Local execution | **usable now** | `core/execution/local.py` functional (asyncio subprocess) |
| JWT / signing secrets | **ignore** | No `JWT_SECRET`, `SECRET_KEY`, or password vars |

---

## 4. Explicitly unused

- **Vercel** — no token, no deploy target
- **Cursor** — no token, no editor integration
- **Firecracker-on-kudbee-host-v1** — the documented UpCloud node where
  `/dev/kvm` is a directory. Firecracker code is fail-closed by design; it
  activates automatically when binary + kernel + rootfs + KVM are present.

---

## 5. Max 3 next steps

1. **Install Firecracker on a KVM-capable host** — `cloudchamber` has working KVM
   but no binary. Install `firecracker` v1.16.1 + kernel + rootfs to unskip
   `tests/integration/test_firecracker_execution.py` and run the real
   `KUDBEE_FIRECRACKER_OK` proof. (See `docs/runbooks/kvm-host-acceptance.md`.)

2. **Configure one model provider** — Set `OPENAI_API_KEY` (or equivalent) to
   activate the `openai_compat` provider for live inference testing.

3. **Run the local integration test** — `python3 -m unittest
   tests.integration.test_local_execution` passes now and proves the execution
   + evidence path end-to-end.
