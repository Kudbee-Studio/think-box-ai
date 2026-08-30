# KUDBEE Architecture v2.0

## Hardware Allocation

### 3x NVIDIA L40S (46 GB VRAM each = 138 GB total)
| GPU | Purpose | Model | VRAM Used |
|-----|---------|-------|-----------|
| GPU 0 | Heavy inference | GPT-OSS-120B | 80 GB |
| GPU 1 | Image generation | SDXL / FLUX | 8-24 GB |
| GPU 2 | Video generation | LTX-2.3 / Music | 8-48 GB |

### 20 CPU Cores (AMD EPYC 9575F)
| Core Range | Task |
|------------|------|
| 0-3 | Ollama API + model routing |
| 4-7 | Embedding generation (sentence-transformers) |
| 8-11 | Data processing + SQLite |
| 12-15 | Background workers + monitoring |
| 16-19 | Redis + caching layer |

### 251 GB RAM
| Usage | Amount |
|-------|--------|
| GPT-OSS-120B (GPU offload) | ~8 GB |
| Redis cache | ~2 GB |
| Embedding model | ~1 GB |
| Docker containers | ~6 GB |
| Available for scaling | ~234 GB |

## Service Architecture

```
USER
  ↓
KUDBEE Dashboard (Nginx :80)
  ↓
Think Box Orchestrator (:9090)
  ↓
  ├─→ Director Box (GPT-120B) → GPU 0
  ├─→ Image Box (SDXL) → GPU 1
  ├─→ Video Box (LTX-2.3) → GPU 2
  ├─→ Music Box (ACE-Step) → GPU 0
  └─→ Jury Box (GPT-20B) → GPU 0
  
CPU Workers
  ├─→ Embedding Service (all-MiniLM-L6-v2)
  ├─→ Redis Cache (:6379)
  ├─→ Health Monitor
  └─→ Log Analyzer

Governance (:8081)
  ├─→ Agent state tracking
  ├─→ Heartbeat monitoring
  └─→ Auto-heal

GPU API (:8082)
  └─→ Real-time telemetry
```

## Job Pipeline

```
1. INTAKE → Job created with requirements
2. EXECUTION → Boxes work in parallel
   ├─→ Director writes script
   ├─→ Image Box generates keyframes
   ├─→ Music Box composes score
   └─→ Editor assembles
3. REVIEW → Automated quality gates
   ├─→ Duration check
   ├─→ Audio sync check
   ├─→ Resolution check
   └─→ Content safety check
4. DELIVERY → Only approved work ships
   ├─→ Copy to web root
   ├─→ Update CDN
   └─→ Notify user
```

## Scaling Path

### Current (1 user)
- 1x GPU server (3x L40S)
- 251 GB RAM, 20 CPU cores
- SQLite databases
- Local Redis

### Growth (1K users)
- Add load balancer
- Add Redis cluster
- Add read replicas
- CDN for static assets

### Scale (1M users)
- Kubernetes cluster
- Auto-scaling GPU nodes
- Managed PostgreSQL
- Global CDN
- Multi-region deployment

### Migration to AWS (~2 hours)
1. Export Docker images → ECR
2. Export databases → RDS
3. Deploy to EKS
4. Route53 DNS cutover

## Key Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Image generation | 1.5s | <1s |
| Video generation | 60s/clip | <30s/clip |
| Model inference | 110 tok/s | >200 tok/s |
| Job throughput | 1/min | 10/min |
| Uptime | 99% | 99.9% |

## Security

- All agent communication via capability tokens
- Audit logs append-only
- No secrets in code
- Environment variables injected at runtime
- Network isolation between Think Boxes

---

**Last Updated:** 2026-08-30
**Version:** 2.0
