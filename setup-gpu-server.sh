#!/usr/bin/env bash
# KUDBEE GPU Server Setup Script
# Run this on a fresh Ubuntu 24.04 GPU server
# Usage: sudo bash setup-gpu-server.sh

set -euo pipefail

KUDBEE_DIR="/opt/kudbee"
LOG_FILE="/var/log/kudbee-setup.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[ERROR] $*" | tee -a "$LOG_FILE"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if running as root
    [[ $EUID -eq 0 ]] || error "This script must be run as root"
    
    # Check Ubuntu version
    if ! grep -q "24.04" /etc/os-release; then
        log "WARNING: This script is designed for Ubuntu 24.04"
    fi
    
    # Check internet connectivity
    if ! curl -s --connect-timeout 5 https://registry-1.docker.io/v2/ > /dev/null; then
        log "WARNING: Docker registry not reachable - Docker install may fail"
    fi
    
    log "Prerequisites OK"
}

# Install system dependencies
install_dependencies() {
    log "Installing system dependencies..."
    
    apt-get update -y >> "$LOG_FILE" 2>&1
    
    apt-get install -y \
        docker.io \
        nvidia-container-toolkit \
        nginx \
        ffmpeg \
        espeak \
        imagemagick \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        wget \
        git \
        htop \
        jq >> "$LOG_FILE" 2>&1
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    # Configure Docker for NVIDIA
    nvidia-ctk runtime configure --runtime=docker >> "$LOG_FILE" 2>&1
    systemctl restart docker
    
    log "System dependencies installed"
}

# Create directory structure
create_directories() {
    log "Creating directory structure..."
    
    mkdir -p "$KUDBEE_DIR"/{memory,outputs,logs,config,tokens}
    mkdir -p /var/log/kudbee
    mkdir -p /mnt/video-models
    
    # Set permissions
    chmod 755 "$KUDBEE_DIR"
    chmod 777 "$KUDBEE_DIR/outputs"
    chmod 777 "$KUDBEE_DIR/logs"
    
    log "Directory structure created"
}

# Deploy KUDBEE code
deploy_code() {
    log "Deploying KUDBEE code..."
    
    # Clone or copy code
    if [[ -d "$KUDBEE_DIR/repo" ]]; then
        cd "$KUDBEE_DIR/repo"
        git pull >> "$LOG_FILE" 2>&1 || log "Git pull failed - using existing code"
    else
        log "NOTE: Copy repo to $KUDBEE_DIR/repo manually or use: git clone <url> $KUDBEE_DIR/repo"
    fi
    
    # Set up Python virtual environment
    if [[ ! -d "$KUDBEE_DIR/venv" ]]; then
        python3 -m venv "$KUDBEE_DIR/venv"
    fi
    
    # Install Python dependencies
    source "$KUDBEE_DIR/venv/bin/activate"
    pip install --upgrade pip >> "$LOG_FILE" 2>&1
    pip install -r "$KUDBEE_DIR/repo/requirements.txt" 2>/dev/null || log "No requirements.txt found"
    
    log "Code deployed"
}

# Build harness Docker image
build_harness_image() {
    log "Building ku3bee-harness Docker image..."
    
    if [[ -f "$KUDBEE_DIR/repo/Dockerfile" ]]; then
        cd "$KUDBEE_DIR/repo"
        docker build -t ku3bee-harness:dev -f Dockerfile . >> "$LOG_FILE" 2>&1
        log "Harness image built"
    else
        log "WARNING: No Dockerfile found - skipping harness build"
    fi
}

# Set up Ollama
setup_ollama() {
    log "Setting up Ollama..."
    
    if ! command -v ollama &> /dev/null; then
        curl -fsSL https://ollama.com/install.sh | sh >> "$LOG_FILE" 2>&1
    fi
    
    # Start Ollama
    systemctl start ollama 2>/dev/null || ollama serve &
    
    log "Ollama installed"
}

# Deploy dashboard to Nginx
deploy_dashboard() {
    log "Deploying dashboard to Nginx..."
    
    # Copy control tower to nginx
    if [[ -f "$KUDBEE_DIR/repo/control_tower.html" ]]; then
        cp "$KUDBEE_DIR/repo/control_tower.html" /var/www/html/index.html
    fi
    
    # Configure nginx
    cat > /etc/nginx/sites-available/kudbee <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    root /var/www/html;
    index index.html;
    
    server_name _;
    
    location / {
        try_files $uri $uri/ =404;
    }
    
    # Proxy for worker monitor
    location /api/worker/ {
        proxy_pass http://127.0.0.1:8765/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Proxy for governance
    location /api/gov/ {
        proxy_pass http://127.0.0.1:8081/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
    
    # Video files
    location /videos/ {
        alias /opt/kudbee/outputs/;
        autoindex on;
    }
}
NGINX
    
    ln -sf /etc/nginx/sites-available/kudbee /etc/nginx/sites-enabled/kudbee
    rm -f /etc/nginx/sites-enabled/default
    
    nginx -t >> "$LOG_FILE" 2>&1
    systemctl restart nginx
    
    log "Dashboard deployed"
}

# Set up worker monitor service
setup_worker_monitor() {
    log "Setting up worker monitor service..."
    
    cat > /etc/systemd/system/kudbee-worker-monitor.service <<SERVICE
[Unit]
Description=KUDBEE Worker Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/kudbee/repo
Environment=PATH=/opt/kudbee/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
ExecStart=/opt/kudbee/venv/bin/python3 /opt/kudbee/repo/worker_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE
    
    systemctl daemon-reload
    systemctl enable kudbee-worker-monitor
    systemctl start kudbee-worker-monitor
    
    log "Worker monitor service created"
}

# Set up governance service
setup_governance_service() {
    log "Setting up governance service..."
    
    cat > /etc/systemd/system/kudbee-governance.service <<SERVICE
[Unit]
Description=KUDBEE Governance Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/kudbee/repo
Environment=PATH=/opt/kudbee/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
ExecStart=/opt/kudbee/venv/bin/python3 /opt/kudbee/repo/agent_governance.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE
    
    systemctl daemon-reload
    systemctl enable kudbee-governance
    systemctl start kudbee-governance
    
    log "Governance service created"
}

# Create status check script
create_status_script() {
    log "Creating status check script..."
    
    cat > /usr/local/bin/kudbee-status <<'STATUS'
#!/bin/bash
echo "=== KUDBEE System Status ==="
echo ""

# System info
echo "Hostname: $(hostname)"
echo "Uptime: $(uptime -p)"
echo ""

# GPU info
if command -v nvidia-smi &> /dev/null; then
    echo "--- GPU Status ---"
    nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>/dev/null || echo "No GPUs"
    echo ""
fi

# Docker
echo "--- Docker ---"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker not running"
echo ""

# Services
echo "--- Services ---"
for svc in nginx ollama kudbee-worker-monitor kudbee-governance; do
    status=$(systemctl is-active "$svc" 2>/dev/null || echo "not installed")
    echo "  $svc: $status"
done
echo ""

# Disk
echo "--- Disk Usage ---"
df -h / /mnt/video-models 2>/dev/null | head -5
echo ""

# Memory
echo "--- Memory ---"
free -h
STATUS
    
    chmod +x /usr/local/bin/kudbee-status
    
    log "Status script created"
}

# Main execution
main() {
    log "=== KUDBEE GPU Server Setup Started ==="
    
    check_prerequisites
    install_dependencies
    create_directories
    deploy_code
    build_harness_image
    setup_ollama
    deploy_dashboard
    setup_worker_monitor
    setup_governance_service
    create_status_script
    
    log "=== KUDBEE GPU Server Setup Complete ==="
    log "Dashboard: http://$(hostname -I | awk '{print $1}')"
    log "Run 'kudbee-status' to check system status"
}

main "$@"
