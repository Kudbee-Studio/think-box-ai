#!/bin/bash
# KUDBEE Server Setup Script
# Run this on a fresh Ubuntu 24.04/26.04 server with SSH access
# wget https://raw.githubusercontent.com/Kudbee-Studio/think-box-ai/main/scripts/setup-server.sh
# chmod +x setup-server.sh && sudo ./setup-server.sh

set -euo pipefail

echo "=== KUDBEE Server Setup ==="

# ── 1. System Update ──────────────────────────────────────────
echo "[1/6] Updating system..."
apt-get update && apt-get upgrade -y

# ── 2. Install Docker ─────────────────────────────────────────
echo "[2/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker root
    systemctl enable docker
    systemctl start docker
    echo "Docker installed: $(docker --version)"
else
    echo "Docker already installed: $(docker --version)"
fi

# ── 3. Install Docker Compose ─────────────────────────────────
echo "[3/6] Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    apt-get install -y docker-compose-plugin
    echo "Docker Compose installed: $(docker-compose version)"
else
    echo "Docker Compose already installed"
fi

# ── 4. Check for NVIDIA GPU ──────────────────────────────────
echo "[4/6] Checking for NVIDIA GPU..."
if command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    
    # Install NVIDIA Container Toolkit if not present
    if ! dpkg -l | grep -q nvidia-container-toolkit; then
        echo "Installing NVIDIA Container Toolkit..."
        curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
        distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
        curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list > /etc/apt/sources.list.d/nvidia-docker.list
        apt-get update && apt-get install -y nvidia-container-toolkit
        nvidia-ctk runtime configure --runtime=docker
        systemctl restart docker
        echo "NVIDIA Container Toolkit installed"
    fi
else
    echo "No NVIDIA GPU detected - skipping GPU setup"
fi

# ── 5. Check existing services ───────────────────────────────
echo "[5/6] Checking existing services..."
echo "Running containers:"
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" 2>/dev/null || echo "  No containers running"

echo ""
echo "Listening ports:"
ss -tlnp 2>/dev/null | grep -E ":(80|443|8000|5432|6379|11434)" || echo "  No relevant ports in use"

# ── 6. System info ───────────────────────────────────────────
echo "[6/6] System information:"
echo "Hostname: $(hostname)"
echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
echo "CPU: $(nproc) cores"
echo "RAM: $(free -h | awk '/^Mem:/{print $2}')"
echo "Disk: $(df -h / | awk 'NR==2{print $2}') total, $(df -h / | awk 'NR==2{print $4}') free"
echo "IP: $(hostname -I | awk '{print $1}')"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Clone the repo: git clone https://github.com/Kudbee-Studio/think-box-ai.git"
echo "  2. Copy .env: cp .env.example .env"
echo "  3. Start stack: docker-compose up -d"
echo "  4. Check health: curl http://localhost:8000/health"
