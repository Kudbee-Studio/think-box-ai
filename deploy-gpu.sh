#!/bin/bash
# KUDBEE GPU Server Setup Script
# Run this on the GPU server after SSH access is available

set -e

echo "=== KUDBEE GPU Server Setup ==="

# 1. System updates
apt-get update && apt-get upgrade -y

# 2. Install essential packages
apt-get install -y \
    docker.io \
    nvidia-container-toolkit \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    jq \
    htop \
    tmux \
    nginx

# 3. Start Docker
systemctl enable docker
systemctl start docker

# 4. Install vLLM (high-performance LLM serving)
pip3 install --break-system-packages vllm openai

# 5. Set Inception API key
echo 'INCEPTION_API_KEY=sk_63c907f6e5c65a4fd03d1bafcd81e895' > /root/.env
chmod 600 /root/.env

# 6. Create application directory
mkdir -p /opt/kudbee

# 7. Start vLLM with GPT-OSS-120B
cat > /opt/kudbee/start-vllm.sh << 'SCRIPT'
#!/bin/bash
source /root/.env

# Start vLLM server with GPT-OSS-120B
python3 -m vllm.entrypoints.openai.api_server \
    --model openai/gpt-oss-120b \
    --tensor-parallel-size 3 \
    --gpu-memory-utilization 0.9 \
    --max-model-len 32768 \
    --port 8000 \
    --host 0.0.0.0
SCRIPT
chmod +x /opt/kudbee/start-vllm.sh

# 8. Create systemd service for vLLM
cat > /etc/systemd/system/kudbee-vllm.service << 'SERVICE'
[Unit]
Description=KUDBEE vLLM Server
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/kudbee
ExecStart=/opt/kudbee/start-vllm.sh
Restart=always
RestartSec=10
EnvironmentFile=/root/.env

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable kudbee-vllm

echo "=== Setup complete. Start vLLM with: systemctl start kudbee-vllm ==="
