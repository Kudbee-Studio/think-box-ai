# THINK BOX AI — Think Token

**Think Token (THNK)** powers the Think Box AI ecosystem. This repo contains the agent runtime, token logic, tools, memory, governance, and infrastructure automation.

---

## 🚦 Current Status (2026-08-30)

| Component | State | Notes |
|-----------|-------|-------|
| Think Token logic | ✅ Done | THNK, 1B supply, 18 decimals |
| Agent runtime (core/) | ✅ Done | Agent, Planner, Actor, Observer |
| Tools | ✅ Done | 5 built-in tools |
| Memory | ✅ Done | SQLite + adapters |
| Governance | ✅ Done | Audit, permissions, approval |
| Unit + integration tests | ✅ Done | 23/24 pass |
| Vertical-slice demo | ✅ Done | 87.8/100 PASS |
| Infrastructure docs | ✅ Done | `docs/infrastructure/` |
| UpCloud API reference | ✅ Done | `docs/infrastructure/UPCLOUD-API-REFERENCE.md` |
| Agent identity + KB | ✅ Done | `IDENTITY.md`, `snippets/` |
| GPU server SSH access | ❌ Blocked | No private key available |
| Mercury 2 deployment | ❌ Not started | Need SSH to server |
| Inception API setup | ❌ Not started | Need SSH to server |
| Music models | ❌ Not started | Need GPU server |
| GPT-20B | ❌ Not started | Need GPU server |

---

## 🗺️ Roadmap

### Phase 0 — Foundation ✅
- [x] Core runtime (agent, planner, actor, observer)
- [x] Tool registry + 5 tools
- [x] Memory store (SQLite)
- [x] Governance (audit, permissions)
- [x] Think Token logic
- [x] Vertical-slice demo

### Phase 1 — Infrastructure 🔄
- [x] UpCloud account access
- [x] Infrastructure documentation
- [x] API reference
- [x] Agent identity + knowledge base
- [ ] GPU server SSH access
- [ ] Install Docker + NVIDIA drivers on GPU
- [ ] Set up Inception API key on server
- [ ] Deploy Mercury 2
- [ ] Register Mercury as KUDBEE provider

### Phase 2 — AI/ML Workloads ⏳
- [ ] Download music models to GPU
- [ ] Set up GPT-20B inference
- [ ] Test Inception API (99M+ tokens)
- [ ] Integrate with Think Token rewards

### Phase 3 — Think Box Production ⏳
- [ ] Firecracker microVM isolation
- [ ] Agent identity + auth tokens
- [ ] Think Box deployment
- [ ] Multi-agent coordination
- [ ] THINK Protocol full implementation

---

## 🏗️ Infrastructure

### Servers (UpCloud Account: kudbee)

| Server | Title | Plan | IP | State |
|--------|-------|------|-----|-------|
| 002b8e55 | kudbee-gpu-primary | GPU-SPOT-12xCPU-128GB-2xL40S | 87.58.149.32 | started |
| 000d8567 | kudbee-host-v1-mercury | PREMIUM-4xCPU-8GB | 212.147.250.183 | started |

**All servers are in fi-hel2 (Finland).** Same zone, same location.

### Access

| Method | State | Notes |
|--------|-------|-------|
| UpCloud API | ✅ Working | `THINKBOX_UPCLOUD_API_TOKEN` env var |
| SSH | ❌ Blocked | All servers publickey-only |
| Web Console | ✅ Available | Emergency console for SSH recovery |

### Floating IPs

| IP | Server | State |
|-----|--------|-------|
| 87.58.149.103 | kudbee-gpu-primary | Attached, needs OS config |
| 87.58.151.132 | kudbee-host-v1-mercury | Attached, needs OS config |

---

## 🔑 Credentials

| Name | Location | Purpose |
|------|----------|---------|
| THINKBOX_UPCLOUD_API_TOKEN | Environment | UpCloud API |
| GH_TOKEN | Environment | GitHub |
| INCEPTION_API_KEY | `~/.env` on servers | Inception API (99M+ tokens) |
| kilocloud | `~/.ssh/kilocloud` | SSH key for foothold |

**Inception API Key:** `sk_63c907f6e5c65a4fd03d1bafcd81e895`

---

## 📋 Backlog (Needs Human)

| Priority | Task | Why |
|----------|------|-----|
| 🔴 HIGH | Add KILO SSH key to UpCloud servers | Need emergency console or user action |
| 🔴 HIGH | Install Inception API key on GPU server | Need SSH access |
| 🟡 MED | Deploy Mercury 2 | Need Inception API first |
| 🟡 MED | Download music models | Need GPU access |
| 🟢 LOW | Clean up orphan temp servers | Cost savings |
| 🟢 LOW | Set up GPT-20B inference | Future phase |

---

## 📝 Code Review Queue

| PR/Change | Status | Reviewer | Notes |
|-----------|--------|----------|-------|
| infrastructure docs | 🔄 Pending | Human | All files in `docs/infrastructure/` |
| AGENTS.md updates | 🔄 Pending | Human | Section 12 added |
| IDENTITY.md | 🔄 Pending | Human | Agent identity system |
| rate_limiter.py | 🔄 Pending | Human | API rate limiter |
| snippets/ | 🔄 Pending | Human | Verified operational snippets |

---

## 📂 Project Structure

```
think-box-ai/
├── AGENTS.md                  # Architecture rules (READ FIRST)
├── README.md                  # This file (current state + roadmap)
├── IDENTITY.md                # Agent identity + knowledge base
├── LESSONS-LEARNED.md         # Critical lessons from this session
├── bootstrap.py               # Infrastructure bootstrap script
├── rate_limiter.py            # UpCloud API rate limiter
├── kudbee_demo.py             # Vertical-slice demo
├── think_box_ai/
│   ├── __init__.py
│   ├── cli.py                 # Minimal CLI
│   └── token.py               # ThinkToken class
├── core/
│   ├── foundation/            # Config, logging, errors, bootstrap
│   ├── memory/                # SQLite + adapters
│   ├── governance/            # Audit, permissions, approval
│   ├── providers/             # ModelProvider protocol
│   ├── tools/                 # Registry + 5 tools
│   └── runtime/               # Agent, Planner, Actor, Observer
├── docs/
│   ├── architecture-v1.md     # 5-layer architecture spec
│   ├── project-foundation.md  # Current verified state
│   ├── inspection-report-2026-08-30.md
│   └── infrastructure/
│       ├── README.md          # Infrastructure overview
│       ├── ACCESS.md          # How to access everything
│       ├── UPCLOUD.md         # Server inventory + API reference
│       ├── UPCLOUD-API-REFERENCE.md  # Verified API formats
│       ├── SSH.md             # SSH patterns + emergency access
│       ├── CREDENTIALS.md     # Credential inventory
│       ├── NETWORK.md         # Network topology
│       ├── SERVERS.md         # Per-server details
│       ├── KUBERNETES.md      # K8s cluster info
│       ├── MERCURY.md         # Mercury 2 status
│       ├── THINK-BOX.md       # Think Box architecture
│       ├── RECOVERY.md        # Disaster recovery
│       ├── BOOTSTRAP.md       # Bootstrap specification
│       ├── CHANGELOG.md       # Discovery changelog
│       ├── SKILL.md           # Agent skill reference
│       └── AGENT-FIRST-15-MINUTES.md  # Agent onboarding
├── snippets/                  # Verified operational snippets
│   ├── upcloud-stop.md        # UPC-001
│   ├── ipv6-toggle.md         # UPC-003
│   └── server-create.md       # UPC-005
└── tests/
    ├── unit/
    ├── integration/
    └── test_token.py
```

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai

# Install
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
python3 -m unittest discover -s tests/unit -v

# Run demo
python3 kudbee_demo.py

# Infrastructure inventory
python3 rate_limiter.py list
```

---

## 📖 Key References

| What | Where |
|------|-------|
| Architecture rules | `AGENTS.md` |
| Infrastructure | `docs/infrastructure/README.md` |
| UpCloud API | `docs/infrastructure/UPCLOUD-API-REFERENCE.md` |
| Server creation | `snippets/server-create.md` |
| Stop server | `snippets/upcloud-stop.md` |
| IPv6 toggle | `snippets/ipv6-toggle.md` |
| Lessons learned | `LESSONS-LEARNED.md` |

---

## 📜 License

MIT License — see `LICENSE` file.
