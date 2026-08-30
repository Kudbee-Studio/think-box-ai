# KUDBEE Troubleshooting Log

**Date:** 2026-08-30
**Session:** agent_7af7e70e

---

## Issue #1: ACE-Step Import Failure

**Error:**
```
Failed to import transformers.models.clip.modeling_clip
module 'lib' has no attribute 'GEN_EMAIL'
```

**Status:** ❌ NOT FIXED

**What we tried:**
1. Installed ACE-Step from source → Failed with same error
2. Upgraded transformers to 4.51.3 → Failed with same error
3. Installed requirements.txt → Failed with same error

**Root Cause:** The `lib` Python module (system library) is conflicting with transformers' internal `lib` reference. This is a known issue with certain versions of transformers + system Python.

**Next fixes to try:**
- [ ] Use a virtual environment to isolate from system Python
- [ ] Use Docker with clean Ubuntu 22.04 image (no system conflicts)
- [ ] Downgrade transformers to 4.40.x (before the lib conflict)
- [ ] Use `infer-api.py` directly instead of pipeline import

---

## Issue #2: vLLM Docker GPT-OSS-120B Failure

**Error:**
```
ValueError: The checkpoint you are trying to load has model type `gpt_oss` 
but Transformers does not recognize this architecture.
```

**Status:** ❌ NOT FIXED

**What we tried:**
1. vllm/vllm-openai:v0.7.3 → Transformers too old
2. vllm/vllm-openai:latest → Same issue + tensor parallel error
3. tensor-parallel-size=2 → Still failed

**Root Cause:** GPT-OSS requires newer Transformers than what vLLM bundles.

**Next fixes to try:**
- [ ] Build custom vLLM image with latest transformers
- [ ] Use Ollama instead (already working with GPT-20B)
- [ ] Use Inception API for 120B, local Ollama for 20B

---

## Issue #3: Ollama GPT-120B Pull

**Error:** SSH connection closed during pull (65GB model)

**Status:** ⏳ IN PROGRESS

**What happened:**
- Started `ollama pull gpt-oss:120b` in background
- SSH connection timed out after 2 minutes
- Pull needs ~2 hours for 65GB

**Solution:** Use `nohup` or `tmux` to keep pull alive after SSH disconnect.

---

## What's Working ✅

| Component | Status | Notes |
|-----------|--------|-------|
| GPU Server (3x L40S) | ✅ | 251GB RAM, CUDA 13.2 |
| Ollama | ✅ | Running |
| GPT-oss:20B | ✅ | 13GB, loaded, responding |
| Memory Architecture | ✅ | Deployed to server |
| Web UI | ✅ | http://87.58.149.157 |
| Think Box CLI | ✅ | `thinkbox <cmd>` |
| ACE-Step download | ✅ | 19GB model downloaded |
| Queue system | ✅ | Autonomous processing |

## What's Broken ❌

| Component | Error | Next Step |
|-----------|-------|-----------|
| ACE-Step pipeline | `lib.GEN_EMAIL` conflict | Use Docker or venv |
| GPT-120B local | Transformers too old | Use Inception API |
| vLLM | Transformers conflict | Use Ollama instead |

---

## Action Items

1. **Fix ACE-Step:** Try Docker with clean Ubuntu 22.04 image
2. **Get music generation working:** Use infer-api.py with model path
3. **Document everything:** Every fix, every failure, every workaround
