#!/usr/bin/env python3
"""
Worker Monitor - System resource and task progress dashboard
"""
import json
import os
import subprocess
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

PORT = 8765
STATE_FILE = "/opt/kudbee/worker_state.json"

class SystemMonitor:
    """Collect system metrics"""
    
    @staticmethod
    def get_gpu_info():
        """Get GPU utilization and memory"""
        try:
            result = subprocess.run([
                'nvidia-smi', 
                '--query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, timeout=5)
            
            gpus = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    gpus.append({
                        'index': int(parts[0]),
                        'name': parts[1],
                        'gpu_util': float(parts[2]),
                        'mem_util': float(parts[3]),
                        'mem_used': float(parts[4]),
                        'mem_total': float(parts[5]),
                        'temp': float(parts[6])
                    })
            return gpus
        except Exception as e:
            return [{'error': str(e)}]
    
    @staticmethod
    def get_cpu_info():
        """Get CPU usage"""
        try:
            result = subprocess.run(
                "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'",
                shell=True, capture_output=True, text=True, timeout=5
            )
            return float(result.stdout.strip() or 0)
        except:
            return 0.0
    
    @staticmethod
    def get_memory_info():
        """Get system memory usage"""
        try:
            result = subprocess.run(
                "free -m | awk 'NR==2{printf \"%.1f,%d,%d\", $3*100/$2, $3, $2}'",
                shell=True, capture_output=True, text=True, timeout=5
            )
            parts = result.stdout.strip().split(',')
            return {
                'percent': float(parts[0]),
                'used_mb': int(parts[1]),
                'total_mb': int(parts[2])
            }
        except:
            return {'percent': 0, 'used_mb': 0, 'total_mb': 0}
    
    @staticmethod
    def get_disk_info():
        """Get disk usage"""
        try:
            result = subprocess.run(
                "df -h / /mnt/video-models 2>/dev/null | awk 'NR>1{print $5\",\"$3\",\"$2\",\"$6}'",
                shell=True, capture_output=True, text=True, timeout=5
            )
            disks = {}
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split(',')
                    mount = parts[3] if len(parts) > 3 else 'unknown'
                    disks[mount] = {
                        'percent': int(parts[0].replace('%', '')),
                        'used': parts[1],
                        'total': parts[2]
                    }
            return disks
        except:
            return {}
    
    @staticmethod
    def get_ollama_status():
        """Check Ollama and loaded models"""
        try:
            result = subprocess.run(
                ['curl', '-s', 'http://localhost:11434/api/tags'],
                capture_output=True, text=True, timeout=5
            )
            data = json.loads(result.stdout)
            models = data.get('models', [])
            return {
                'running': True,
                'models': [{'name': m['name'], 'size': m.get('size', 0)} for m in models]
            }
        except:
            return {'running': False, 'models': []}
    
    @staticmethod
    def get_network_info():
        """Get network interfaces"""
        try:
            result = subprocess.run(
                "ip -4 addr show | grep 'inet ' | awk '{print $2,$NF}'",
                shell=True, capture_output=True, text=True, timeout=5
            )
            ips = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    ips.append({'ip': parts[0], 'iface': parts[1]})
            return ips
        except:
            return []
    
    @staticmethod
    def get_running_tasks():
        """Get running background tasks"""
        tasks = []
        try:
            result = subprocess.run(
                "ps aux | grep -E '(ollama|acestep|python|ffmpeg|docker)' | grep -v grep | awk '{print $11,$12,$13,$14}'",
                shell=True, capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 1:
                        cmd = ' '.join(parts)
                        if len(cmd) > 60:
                            cmd = cmd[:60] + '...'
                        tasks.append({'command': cmd})
        except:
            pass
        return tasks


def collect_state():
    """Collect all system state"""
    monitor = SystemMonitor()
    state = {
        'timestamp': datetime.now().isoformat(),
        'hostname': os.uname().nodename,
        'uptime': get_uptime(),
        'gpu': monitor.get_gpu_info(),
        'cpu': monitor.get_cpu_info(),
        'memory': monitor.get_memory_info(),
        'disk': monitor.get_disk_info(),
        'ollama': monitor.get_ollama_status(),
        'network': monitor.get_network_info(),
        'tasks': monitor.get_running_tasks(),
        'worker_status': read_worker_state()
    }
    return state


def get_uptime():
    """Get system uptime"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
    except:
        return "unknown"


def read_worker_state():
    """Read worker state file"""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            'status': 'idle',
            'current_task': 'Waiting for work',
            'progress': 0,
            'progress_label': 'Idle',
            'started_at': None
        }


def write_worker_state(status, current_task, progress, progress_label, started_at=None):
    """Write worker state"""
    state = {
        'status': status,
        'current_task': current_task,
        'progress': progress,
        'progress_label': progress_label,
        'started_at': started_at or datetime.now().isoformat()
    }
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except:
        pass


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ku3Bee Worker Monitor</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e0e0e0; min-height: 100vh; }
.header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px 30px; border-bottom: 1px solid #2a2a3e; display: flex; justify-content: space-between; align-items: center; }
.header h1 { font-size: 1.5rem; color: #00d4ff; }
.header .status { display: flex; align-items: center; gap: 10px; }
.status-dot { width: 12px; height: 12px; border-radius: 50%; background: #00ff88; animation: pulse 2s infinite; }
.status-dot.warning { background: #ffaa00; }
.status-dot.error { background: #ff4444; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 20px; }
.card { background: #12121a; border: 1px solid #2a2a3e; border-radius: 12px; padding: 20px; }
.card h3 { color: #00d4ff; margin-bottom: 15px; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; }
.metric { display: flex; justify-content: space-between; margin: 8px 0; padding: 8px 0; border-bottom: 1px solid #1a1a2e; }
.metric:last-child { border-bottom: none; }
.metric-label { color: #888; }
.metric-value { color: #fff; font-weight: 600; }
.progress-bar { width: 100%; height: 24px; background: #1a1a2e; border-radius: 12px; overflow: hidden; margin: 10px 0; position: relative; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #00d4ff, #00ff88); border-radius: 12px; transition: width 0.5s ease; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 600; color: #000; }
.progress-fill.idle { background: #333; color: #888; }
.progress-fill.working { background: linear-gradient(90deg, #00d4ff, #00ff88); }
.progress-fill.warning { background: linear-gradient(90deg, #ffaa00, #ff6600); }
.gpu-card { background: linear-gradient(135deg, #1a1a2e 0%, #1a2a1a 100%); }
.gpu-metric { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.temp { color: #00ff88; }
.temp.hot { color: #ffaa00; }
.temp.danger { color: #ff4444; }
.ollama-model { background: #1a1a2e; padding: 10px; border-radius: 8px; margin: 8px 0; font-family: monospace; font-size: 0.85rem; }
.working-task { background: linear-gradient(90deg, rgba(0,212,255,0.1), transparent); border-left: 3px solid #00d4ff; padding: 15px; margin: 10px 0; border-radius: 0 8px 8px 0; }
.refresh-btn { background: #00d4ff; color: #000; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; }
.refresh-btn:hover { background: #00b8e6; }
.timestamp { color: #666; font-size: 0.8rem; }
.full-width { grid-column: 1 / -1; }
.task-item { padding: 6px 12px; background: #1a1a2e; border-radius: 4px; margin: 4px 0; font-family: monospace; font-size: 0.8rem; color: #aaa; }
</style>
</head>
<body>
<div class="header">
    <h1>Ku3Bee Worker Monitor</h1>
    <div class="status">
        <span class="hostname">{hostname}</span>
        <span class="status-dot {status_class}"></span>
        <span>{status_text}</span>
        <button class="refresh-btn" onclick="location.reload()">Refresh</button>
    </div>
</div>
<div class="container">

<!-- Worker Progress -->
<div class="grid">
<div class="card full-width">
    <h3>Current Task</h3>
    <div class="working-task">
        <strong style="color:#00d4ff">{worker_task}</strong>
        <div class="timestamp">Status: {worker_status} | Started: {worker_started}</div>
    </div>
    <div class="progress-bar">
        <div class="progress-fill {progress_class}" style="width: {worker_progress}%">{worker_progress}% - {progress_label}</div>
    </div>
</div>
</div>

<!-- GPU Cards -->
<div class="grid">
{gpu_cards}
</div>

<!-- System Resources -->
<div class="grid">
<div class="card">
    <h3>CPU Usage</h3>
    <div class="progress-bar"><div class="progress-fill {cpu_class}" style="width: {cpu}%">{cpu}%</div></div>
</div>
<div class="card">
    <h3>Memory</h3>
    <div class="progress-bar"><div class="progress-fill {mem_class}" style="width: {mem_percent}%">{mem_percent}%</div></div>
    <div class="metric"><span class="metric-label">Used</span><span class="metric-value">{mem_used} MB</span></div>
    <div class="metric"><span class="metric-label">Total</span><span class="metric-value">{mem_total} MB</span></div>
</div>
<div class="card">
    <h3>Uptime</h3>
    <div class="metric"><span class="metric-value" style="font-size:1.5rem;color:#00ff88">{uptime}</span></div>
</div>
</div>

<!-- Disk & Ollama -->
<div class="grid">
<div class="card">
    <h3>Disk Usage</h3>
{disk_info}
</div>
<div class="card">
    <h3>Ollama Server</h3>
    <div class="metric"><span class="metric-label">Status</span><span class="metric-value" style="color:{ollama_color}">{ollama_status}</span></div>
{ollama_models}
</div>
</div>

<!-- Running Tasks -->
<div class="grid">
<div class="card full-width">
    <h3>Running Processes</h3>
{running_tasks}
</div>
</div>

<!-- Network -->
<div class="grid">
<div class="card">
    <h3>Network</h3>
{network_info}
</div>
<div class="card">
    <h3>System Info</h3>
    <div class="metric"><span class="metric-label">Hostname</span><span class="metric-value">{hostname}</span></div>
    <div class="metric"><span class="metric-label">Last Updated</span><span class="metric-value">{timestamp}</span></div>
</div>
</div>

</div>
<script>
// Auto-refresh every 10 seconds
setTimeout(function() {{ location.reload(); }}, 10000);
</script>
</body>
</html>"""


def generate_html(state):
    """Generate HTML from state"""
    worker = state.get('worker_status', {})
    progress = worker.get('progress', 0)
    progress_label = worker.get('progress_label', 'Idle')
    worker_status = worker.get('status', 'idle')
    
    if worker_status == 'working':
        progress_class = 'working'
    elif worker_status == 'error':
        progress_class = 'warning'
    else:
        progress_class = 'idle'
    
    # GPU cards
    gpu_cards = ''
    for gpu in state.get('gpu', []):
        if 'error' in gpu:
            gpu_cards += f'<div class="card gpu-card"><h3>GPU {gpu.get("index", "?")}</h3><div class="metric"><span class="metric-value" style="color:#ff4444">{gpu["error"]}</span></div></div>'
        else:
            temp_class = 'temp'
            if gpu['temp'] > 80:
                temp_class = 'temp danger'
            elif gpu['temp'] > 70:
                temp_class = 'temp hot'
            
            gpu_cards += f'''<div class="card gpu-card">
                <h3>GPU {gpu['index']} - {gpu['name']}</h3>
                <div class="gpu-metric">
                    <div><div class="progress-bar"><div class="progress-fill working" style="width:{gpu['gpu_util']}%">{gpu['gpu_util']:.0f}% GPU</div></div></div>
                    <div><div class="progress-bar"><div class="progress-fill" style="width:{gpu['mem_util']}%">{gpu['mem_util']:.0f}% VRAM</div></div></div>
                </div>
                <div class="metric"><span class="metric-label">VRAM</span><span class="metric-value">{gpu['mem_used']:.0f} / {gpu['mem_total']:.0f} MB</span></div>
                <div class="metric"><span class="metric-label">Temperature</span><span class="metric-value {temp_class}">{gpu['temp']:.0f}°C</span></div>
            </div>'''
    
    # Disk info
    disk_info = ''
    for mount, info in state.get('disk', {}).items():
        disk_info += f'<div class="progress-bar"><div class="progress-fill" style="width:{info["percent"]}%">{mount}: {info["percent"]}% ({info["used"]}/{info["total"]})</div></div>'
    
    # Ollama
    ollama = state.get('ollama', {})
    ollama_status = 'Running' if ollama['running'] else 'Stopped'
    ollama_color = '#00ff88' if ollama['running'] else '#ff4444'
    ollama_models = ''
    for model in ollama.get('models', []):
        size_gb = model['size'] / (1024**3)
        ollama_models += f'<div class="ollama-model">{model["name"]} ({size_gb:.1f} GB)</div>'
    
    # Running tasks
    running_tasks = ''
    for task in state.get('tasks', [])[:20]:
        running_tasks += f'<div class="task-item">{task["command"]}</div>'
    
    # Network
    network_info = ''
    for iface in state.get('network', []):
        network_info += f'<div class="metric"><span class="metric-label">{iface["iface"]}</span><span class="metric-value">{iface["ip"]}</span></div>'
    
    cpu = state.get('cpu', 0)
    mem = state.get('memory', {})
    
    return HTML_TEMPLATE.format(
        hostname=state.get('hostname', 'unknown'),
        status_class='' if worker_status == 'working' else 'warning' if worker_status == 'idle' else 'error',
        status_text=worker_status.upper(),
        worker_task=worker.get('current_task', 'Waiting for work'),
        worker_status=worker_status,
        worker_started=worker.get('started_at', 'N/A')[:19] if worker.get('started_at') else 'N/A',
        worker_progress=progress,
        progress_label=progress_label,
        progress_class=progress_class,
        gpu_cards=gpu_cards or '<div class="card"><h3>GPUs</h3><div class="metric"><span class="metric-value">No GPUs detected</span></div></div>',
        cpu=cpu,
        cpu_class='working' if cpu < 80 else 'warning',
        mem_percent=mem.get('percent', 0),
        mem_class='working' if mem.get('percent', 0) < 80 else 'warning',
        mem_used=mem.get('used_mb', 0),
        mem_total=mem.get('total_mb', 0),
        uptime=state.get('uptime', 'unknown'),
        disk_info=disk_info or '<div class="metric"><span class="metric-value">No disk info</span></div>',
        ollama_status=ollama_status,
        ollama_color=ollama_color,
        ollama_models=ollama_models or '<div class="metric"><span class="metric-value">No models loaded</span></div>',
        running_tasks=running_tasks or '<div class="task-item">No relevant processes running</div>',
        network_info=network_info,
        timestamp=state.get('timestamp', '')[:19]
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            # Return JSON for dashboard
            state = collect_state()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(state).encode())
        elif self.path == '/status':
            # Simple status check
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'timestamp': datetime.now().isoformat()}).encode())
        elif self.path == '/update':
            # Update worker state via query params
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            status = params.get('status', ['idle'])[0]
            task = params.get('task', [''])[0]
            progress = int(params.get('progress', ['0'])[0])
            label = params.get('label', [''])[0]
            write_worker_state(status, task, progress, label)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'updated'}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress log output


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'update':
        # CLI: python3 worker_monitor.py update <status> <task> <progress> <label>
        status = sys.argv[2] if len(sys.argv) > 2 else 'idle'
        task = sys.argv[3] if len(sys.argv) > 3 else 'Waiting for work'
        progress = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        label = sys.argv[5] if len(sys.argv) > 5 else ''
        write_worker_state(status, task, progress, label)
        print(f"Worker state: {status} - {task} ({progress}%)")
    else:
        server = HTTPServer(('0.0.0.0', PORT), Handler)
        print(f"Worker Monitor running on port {PORT}")
        server.serve_forever()
