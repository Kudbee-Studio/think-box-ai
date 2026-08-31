# KU3BEE — AI Film Production Platform

An AI-powered platform for producing full-length films using state-of-the-art video generation models, professional voice synthesis, and automated quality control.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        KU3BEE PLATFORM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Agent Runtime │  │  Video Gen   │  │  Voice Synthesis     │  │
│  │ (Harnessed)   │  │  (Wan2.2)    │  │  (ElevenLabs)        │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│  ┌──────┴─────────────────┴──────────────────────┴───────────┐  │
│  │                    Core Runtime                           │  │
│  │  - Think Box lifecycle    - Tool registry                 │  │
│  │  - Memory architecture    - Governance engine             │  │
│  └────────────────────────────┬──────────────────────────────┘  │
│                               │                                 │
│  ┌────────────────────────────┴──────────────────────────────┐  │
│  │                    Docker Harness                         │  │
│  │  - Isolated tool execution  - Resource limits             │  │
│  │  - Filesystem scoping       - Network isolation           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker + NVIDIA Container Toolkit (for GPU workloads)
- UpCloud account (for GPU server deployment)

### Installation

```bash
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai

# Build harness image
docker build -t ku3bee-harness:dev -f Dockerfile .

# Run tests
python3 -m unittest discover tests/unit -v
```

### Docker Compose (Local Dev)

```bash
docker-compose up -d
```

Starts: Nginx (dashboard), Ollama (LLM), Worker Monitor, Governance API

### GPU Server Setup

```bash
# On a fresh Ubuntu 24.04 server:
sudo bash setup-gpu-server.sh
```

## Phase 1: Foundation (Complete)

- [x] Docker harness for sandboxed tool execution
- [x] Agent runtime with Think Box lifecycle
- [x] Governance engine with state tracking
- [x] Memory architecture (L0-L4 layers)
- [x] Worker monitoring dashboard
- [x] Deployment scripts for GPU server

## Phase 2: Full-Length Film Production (In Progress)

- [ ] Wan2.2-TI2V-5B integration
- [ ] ElevenLabs voice production
- [ ] Scene assembly pipeline
- [ ] Quality assurance automation
- [ ] 90-minute feature production

## Project Structure

```
.
├── core/
│   ├── runtime/          # Agent, Harness, ThinkBox
│   ├── tools/            # Shell exec, filesystem, registry
│   ├── video/            # Script parser, generator, assembler
│   └── foundation/       # Logging, config, rate limiter
├── tests/
│   ├── unit/             # Pure logic tests
│   └── integration/      # Docker-dependent tests
├── docs/
│   ├── guides/           # Setup, tools, server
│   ├── architecture-v1.md
│   └── phase2-full-length-film.md
├── control_tower.html    # Dashboard UI
├── worker_monitor.py     # System metrics agent
├── setup-gpu-server.sh   # Server provisioning
└── Dockerfile            # Harness container image
```

## Configuration

| Env Var | Purpose |
|---------|---------|
| `HARNESS=1` | Enable Docker sandbox |
| `HARNESS_NETWORK=bridge` | Enable network in containers |
| `ELEVENLABS_API_KEY` | Voice generation |
| `THINKBOX_UPCLOUD_API_TOKEN` | Infrastructure API |

## License

Proprietary — Kudbee Studio
