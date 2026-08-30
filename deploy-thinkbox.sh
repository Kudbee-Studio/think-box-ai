#!/bin/bash
# KUDBEE Think Box Setup Script (ACE-Step Music)
# Run on the CPU server or in a Docker container

set -e

echo "=== KUDBEE Think Box Setup ==="

# 1. System setup
apt-get update && apt-get install -y python3 python3-pip python3-venv git curl

# 2. Create app directory
mkdir -p /opt/kudbee/thinkbox
cd /opt/kudbee/thinkbox

# 3. Clone ACE-Step
if [ ! -d "ACE-Step" ]; then
    git clone https://github.com/ACE-Step/ACE-Step.git
fi

cd ACE-Step

# 4. Install dependencies
pip3 install --break-system-packages -r requirements.txt

# 5. Create Think Box wrapper
cat > /opt/kudbee/thinkbox/thinkbox.py << 'PYTHON'
#!/usr/bin/env python3
"""KUDBEE Think Box - Music Generation Agent"""

import os
import json
import subprocess
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

INCEPTION_API_KEY = os.environ.get('INCEPTION_API_KEY', '')
VLLM_URL = os.environ.get('VLLM_URL', 'http://localhost:8000')

class ThinkBoxHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/health':
            self.send_json(200, {"status": "ok", "service": "thinkbox"})
        elif parsed.path == '/generate':
            params = parse_qs(parsed.query)
            prompt = params.get('prompt', [''])[0]
            result = self.generate_music(prompt)
            self.send_json(200, result)
        else:
            self.send_json(404, {"error": "not found"})
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        data = json.loads(body) if body else {}
        
        if self.path == '/music':
            prompt = data.get('prompt', '')
            result = self.generate_music(prompt)
            self.send_json(200, result)
        elif self.path == '/chat':
            message = data.get('message', '')
            result = self.chat(message)
            self.send_json(200, result)
        else:
            self.send_json(404, {"error": "not found"})
    
    def generate_music(self, prompt):
        """Generate music using ACE-Step"""
        # TODO: Integrate ACE-Step pipeline
        return {"status": "generating", "prompt": prompt, "eta": "2-5 minutes"}
    
    def chat(self, message):
        """Chat with the AI using vLLM"""
        try:
            resp = requests.post(f"{VLLM_URL}/v1/chat/completions", json={
                "model": "openai/gpt-oss-120b",
                "messages": [{"role": "user", "content": message}],
                "stream": False
            }, timeout=30)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def send_json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), ThinkBoxHandler)
    print(f"Think Box running on port {port}")
    server.serve_forever()
PYTHON

chmod +x /opt/kudbee/thinkbox/thinkbox.py

# 6. Create systemd service
cat > /etc/systemd/system/kudbee-thinkbox.service << 'SERVICE'
[Unit]
Description=KUDBEE Think Box
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/kudbee/thinkbox
ExecStart=/usr/bin/python3 /opt/kudbee/thinkbox/thinkbox.py
Restart=always
RestartSec=5
Environment=PORT=8080
EnvironmentFile=/root/.env

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable kudbee-thinkbox

echo "=== Think Box setup complete ==="
echo "Start with: systemctl start kudbee-thinkbox"
echo "Access at: http://<server-ip>:8080"
