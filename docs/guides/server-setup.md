# KU3BEE Server Setup Guide

**For:** GPU server `00d832ec` (GPU-SPOT-20xCPU-256GB-3xL40S)
**OS:** Ubuntu 24.04 LTS
**Public IP:** 87.58.148.168

---

## Quick Start (when server is running)

```bash
# SSH into server
ssh -i ~/.ssh/kilo-upcloud root@87.58.148.168

# Clone repo
git clone <repo-url> /opt/kudbee/repo
cd /opt/kudbee/repo

# Run setup
sudo bash setup-gpu-server.sh
```

---

## Manual Steps

### 1. Attach Storage Disks

```bash
export THINKBOX_UPCLOUD_API_TOKEN=<token>
bash attach-storage.sh 00d832ec-8565-447b-86ac-74bf9bd41e57
```

Disks to attach:
| Name | UUID | Size | Mount |
|------|------|------|-------|
| models-disk-500gb | 01f540e7 | 500GB | /mnt/models |
| video-models-disk-1 | 01eeb13d | 400GB | /mnt/video-models |
| video-models-disk-2 | 01c67400 | 400GB | /mnt/video-models-2 |
| main-hd-v1 | 016d4a87 | 400GB | /mnt/main-hd |

### 2. Start Server

```bash
curl -X POST \
  -H "Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN" \
  https://api.upcloud.com/1.3/server/00d832ec-8565-447b-86ac-74bf9bd41e57/start
```

**Wait 60 seconds for SSH after state=started.**

### 3. Deploy Services

```bash
# On server:
sudo bash /opt/kudbee/repo/setup-gpu-server.sh
```

### 4. Load Models

```bash
# Load Ollama model
ollama pull gpt-oss:20b

# Or for 120B (if GPU memory allows)
ollama pull gpt-oss:120b
```

### 5. Verify

```bash
kudbee-status
```

Access dashboard at `http://87.58.148.168`

---

## Services

| Service | Port | Description |
|---------|------|-------------|
| Nginx | 80 | Dashboard + API proxy |
| Worker Monitor | 8765 | System metrics |
| Governance | 8081 | Agent state tracking |
| Ollama | 11434 | LLM inference |

---

## Troubleshooting

### Server won't start (resources unavailable)
- UpCloud GPU capacity issue
- Wait and retry, or try different zone

### SSH connection refused
- Wait 60 seconds after state=started
- Check SSH key: `ssh -i ~/.ssh/kilo-upcloud root@87.58.148.168`

### Docker not running
```bash
sudo systemctl start docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### GPU not visible
```bash
nvidia-smi  # Check driver
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi  # Check container GPU
```
