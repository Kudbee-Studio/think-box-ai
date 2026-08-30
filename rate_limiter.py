#!/usr/bin/env python3
"""KUDBEE UpCloud API Rate Limiter

Prevents API rate limiting by:
1. Enforcing minimum delays between API calls
2. Queuing concurrent requests
3. Retrying with exponential backoff
4. Logging all API activity

Usage:
  from rate_limiter import UpCloudAPI
  api = UpCloudAPI()
  servers = api.list_servers()
"""

import json
import os
import subprocess
import time
import threading
from collections import deque
from datetime import datetime


class RateLimiter:
    """Thread-safe rate limiter with minimum delay between calls."""
    
    def __init__(self, min_delay=2.0, max_concurrent=1):
        self.min_delay = min_delay
        self.max_concurrent = max_concurrent
        self._last_call = 0
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_concurrent)
        self._call_log = deque(maxlen=100)
    
    def wait(self):
        """Wait until it's safe to make the next call."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
            self._last_call = time.time()
            self._call_log.append(datetime.now().isoformat())
    
    def acquire(self):
        """Acquire the semaphore for concurrent limiting."""
        self._semaphore.acquire()
    
    def release(self):
        """Release the semaphore."""
        self._semaphore.release()


class UpCloudAPI:
    """UpCloud API client with rate limiting and retry logic."""
    
    def __init__(self, token=None, max_retries=3, base_delay=2.0):
        self.token = token or os.environ.get('THINKBOX_UPCLOUD_API_TOKEN')
        if not self.token:
            raise ValueError('THINKBOX_UPCLOUD_API_TOKEN not set')
        self.base_url = 'https://api.upcloud.com/1.3'
        self.max_retries = max_retries
        self.rate_limiter = RateLimiter(min_delay=base_delay)
        self._log = []
    
    def _call(self, method, path, data=None):
        """Make a rate-limited API call with retry logic."""
        self.rate_limiter.acquire()
        try:
            for attempt in range(self.max_retries):
                self.rate_limiter.wait()
                
                cmd = ['curl', '-s', '-X', method,
                       '-H', f'Authorization: Bearer {self.token}',
                       '-H', 'Content-Type: application/json']
                if data:
                    cmd += ['-d', json.dumps(data)]
                cmd.append(f'{self.base_url}{path}')
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                # Log the call
                self._log.append({
                    'time': datetime.now().isoformat(),
                    'method': method,
                    'path': path,
                    'attempt': attempt + 1,
                    'status': result.returncode
                })
                
                try:
                    resp = json.loads(result.stdout)
                    # Check for rate limit errors
                    if isinstance(resp, dict) and resp.get('error', {}).get('error_code') == 'RATE_LIMITED':
                        wait_time = (2 ** attempt) * self.rate_limiter.min_delay
                        time.sleep(wait_time)
                        continue
                    return resp
                except json.JSONDecodeError:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.rate_limiter.min_delay * (attempt + 1))
                        continue
                    return result.stdout
            
            return {'error': {'error_code': 'MAX_RETRIES_EXCEEDED'}}
        finally:
            self.rate_limiter.release()
    
    def get(self, path):
        return self._call('GET', path)
    
    def post(self, path, data=None):
        return self._call('POST', path, data)
    
    def put(self, path, data=None):
        return self._call('PUT', path, data)
    
    def delete(self, path):
        return self._call('DELETE', path)
    
    def list_servers(self):
        return self.get('/server')
    
    def get_server(self, uuid):
        return self.get(f'/server/{uuid}')
    
    def create_server(self, title, hostname, plan, ssh_keys, 
                      size=10, user_data=None, zone='fi-hel2'):
        payload = {
            'server': {
                'zone': zone,
                'title': title,
                'hostname': hostname,
                'plan': plan,
                'storage_devices': {
                    'storage_device': [{
                        'action': 'create',
                        'size': size,
                        'tier': 'maxiops',
                        'title': f'{hostname}-os'
                    }]
                },
                'login_user': {
                    'username': 'root',
                    'ssh_keys': {'ssh_key': ssh_keys}
                }
            }
        }
        if user_data:
            payload['server']['user_data'] = user_data
        return self.post('/server', payload)
    
    def stop_server(self, uuid, hard=True):
        return self.post(f'/server/{uuid}/stop', {
            'stop_server': {
                'stop_type': 'hard' if hard else 'soft',
                'timeout': '60'
            }
        })
    
    def start_server(self, uuid):
        return self.post(f'/server/{uuid}/start')
    
    def delete_server(self, uuid, delete_storage=True):
        return self.delete(f'/server/{uuid}?storages={"true" if delete_storage else "false"}')
    
    def wait_for_state(self, uuid, target_state='started', timeout=300, poll_interval=5):
        """Wait for a server to reach target state."""
        start = time.time()
        while time.time() - start < timeout:
            resp = self.get_server(uuid)
            state = resp['server']['state']
            if state == target_state:
                return resp['server']
            time.sleep(poll_interval)
        return None
    
    def wait_for_stopped(self, uuid, timeout=120):
        """Wait for a server to stop."""
        return self.wait_for_state(uuid, 'stopped', timeout)
    
    def wait_for_started(self, uuid, timeout=300):
        """Wait for a server to start."""
        return self.wait_for_state(uuid, 'started', timeout)
    
    def delete_server_full(self, uuid, delete_storage=True):
        """Stop, wait, then delete a server."""
        self.stop_server(uuid)
        self.wait_for_stopped(uuid)
        return self.delete_server(uuid, delete_storage)
    
    def get_public_ip(self, server):
        """Get the public IPv4 address of a server."""
        for ip in server.get('ip_addresses', {}).get('ip_address', []):
            if ip.get('access') == 'public' and ip.get('family') == 'IPv4':
                return ip['address']
        return None


# CLI usage
if __name__ == '__main__':
    import sys
    api = UpCloudAPI()
    
    if len(sys.argv) < 2:
        print('Usage: python3 rate_limiter.py <command> [args]')
        print('Commands: list, status, create, delete, stop, start')
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == 'list':
        data = api.list_servers()
        for s in data['servers']['server']:
            ip = api.get_public_ip(s)
            print(f"{s['uuid'][:8]}  {s['title']:<30} {s['state']:<10} {ip or 'no-ip'}")
    elif cmd == 'status':
        for s in api.list_servers()['servers']['server']:
            print(f"\n{s['title']}:")
            print(f"  UUID: {s['uuid']}")
            print(f"  State: {s['state']}")
            print(f"  Plan: {s['plan']}")
            print(f"  Zone: {s['zone']}")
    elif cmd == 'stop' and len(sys.argv) > 2:
        api.stop_server(sys.argv[2])
        api.wait_for_stopped(sys.argv[2])
        print('Stopped')
    elif cmd == 'start' and len(sys.argv) > 2:
        api.start_server(sys.argv[2])
        api.wait_for_started(sys.argv[2])
        print('Started')
    elif cmd == 'delete' and len(sys.argv) > 2:
        api.delete_server_full(sys.argv[2])
        print('Deleted')
    else:
        print(f'Unknown command: {cmd}')
