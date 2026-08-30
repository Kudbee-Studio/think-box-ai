# KUDBEE Recovery & Continuity Guide

**Last Updated:** 2026-08-30T18:00:00Z
**Session:** agent_7af7e70e-85ae-498e-a2cc-54314eddfe5a

---

## Critical Environment Variables

These are injected at container boot. If session resets, they come back automatically.

| Variable | Purpose |
|----------|---------|
| THINKBOX_UPCLOUD_API_TOKEN | UpCloud infrastructure API |
| GH_TOKEN | GitHub repository access |
| UPSTASH_BOX_API_KEY | Think Box sandbox |
| UPCLOUD_SSH_KEY_PATH | SSH key location |

---

## Servers

### GPU Server (Primary)
- **UUID:** 00bd760e-c1f6-4f18-a4fa-aad5b2eb95d8
- **Public IP:** 87.58.149.157
- **Plan:** GPU-SPOT-12xCPU-128GB-2xL40S (actually 3x L40S)
- **SSH Key:** kilocloud (ed25519)
- **Services:** Ollama, Think Boxes, Governance, GPU API, Nginx

### kudbee-os (Secondary)
- **UUID:** 0011544f-fada-4edd-ae91-c5d872e35114
- **Public IP:** 87.58.149.167
- **Plan:** PREMIUM-4xCPU-32GB
- **SSH Key:** Not provisioned (needs manual setup)

---

## Running Services

| Service | Port | Start Command |
|---------|------|---------------|
| Ollama | 11434 | `systemctl start ollama` |
| Think Boxes | 9090 | `systemctl start kudbee-boxes` |
| Governance | 8081 | `python3 /opt/kudbee/agent_governance.py &` |
| GPU API | 8082 | `python3 /opt/kudbee/api_gpu.py &` |
| Diffusion API | 8083 | `python3 /opt/kudbee/diffusion_api.py &` |
| Nginx | 80 | `systemctl start nginx` |

---

## Models Installed

| Model | Size | Location | VRAM |
|-------|------|----------|------|
| GPT-OSS-120B | 65.4 GB | Ollama | ~80GB |
| GPT-OSS-20B | 13.8 GB | Ollama | ~16GB |
| SDXL 1.0 | ~7GB | venv-diffusion | ~8GB |
| ACE-Step 1.5 XL | ~19GB | /opt/kudbee/models/acestep | ~8GB |
| LTX-2.3 | ~146GB | /mnt/models/ltx | ~48GB |

---

## Recovery Commands (If Session Resets)

```bash
# 1. Connect to GPU server
ssh -i ~/.ssh/kilocloud root@87.58.149.157

# 2. Verify services
systemctl status ollama nginx kudbee-boxes
curl -s http://localhost:11434/api/tags
curl -s http://localhost:8081/api/health

# 3. Restart if needed
systemctl restart ollama nginx kudbee-boxes

# 4. Restart governance
nohup python3 /opt/kudbee/agent_governance.py > /var/log/governance.log 2>&1 &

# 5. Restart GPU API
nohup python3 /opt/kudbee/api_gpu.py > /var/log/gpu_api.log 2>&1 &

# 6. Verify dashboard
curl -sI http://localhost/ | head -3
curl -sI http://localhost/ku3bee-trailer-latest.mp4 | head -3
```

---

## Key Files on Server

```
/opt/kudbee/
├── agent_governance.py    # Agent state tracking
├── api_gpu.py             # GPU telemetry API
├── thinkbox_server.py     # Think Box API (port 9090)
├── mercury2.py            # Mercury 2 AI gateway
├── inception_config.json  # Inception API config
├── production.py          # Production management
├── pipeline.py            # Master production pipeline
├── produce_v3.py          # Trailer production
├── memory/                # SQLite databases
│   ├── kudbee.db          # Memory + tokens
│   ├── think_tokens.db    # Token system
│   ├── quality.db         # Quality metrics
│   └── agent_governance.db # Agent states
├── outputs/               # Generated content
│   ├── images/            # AI-generated images
│   ├── PROD-FINAL/        # Final production output
│   └── ku3bee-trailer-latest.mp4
├── models/
│   └── acestep/           # ACE-Step music model
└── venv-diffusion/        # Python venv for SDXL

/var/www/html/
├── index.html             # Dashboard
├── ku3bee-trailer-latest.mp4
└── images/                # Generated keyframes
```

---

## GitHub Repository

**URL:** https://github.com/Kudbee-Studio/think-box-ai.git
**Branch:** session/agent_7af7e70e-85ae-498e-a2cc-54314eddfe5a

### Recent Commits
```
fdcbc4a pipeline: job queue + reviewer
70f5786 diffusion: SDXL working, keyframes
251c863 governance: agent states + dashboard
14607b9 audio: Google TTS fixed
7929afa execution: provider abstraction
4877201 isolation: docker + cloud research
1644137 think: token engine v2
```

---

## Architecture Vision

```
USER → Dashboard (80)
         ↓
    Job Queue (pipeline.py)
         ↓
    ┌────┴────┐
    ↓         ↓
Think Boxes  Media Packs
(9090)       (FLUX/SDXL/LTX)
    ↓         ↓
    └────┬────┘
         ↓
    Reviewer (quality gates)
         ↓
    Delivery (web/CDN)
```

---

## Scaling Path

**Current:** 1 GPU server (3x L40S)
**Scale to 1M users:**
1. Add load balancer (UpCloud)
2. Add GPU workers (auto-scale)
3. Add Redis queue (replace SQLite)
4. Add CDN for media (Cloudflare)
5. Add PostgreSQL (replace SQLite)

**Migration time to AWS: ~2 hours**

---

**END OF RECOVERY GUIDE**
