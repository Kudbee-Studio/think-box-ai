#!/usr/bin/env python3
"""KUDBEE Bootstrap - Creates and configures UpCloud infrastructure.

This script creates:
  1. A foothold server (SSH accessible)
  2. A GPU server (accessible via foothold)
  3. Configures both with Inception API key, Docker, etc.

Usage:
  python3 bootstrap.py          # Create everything
  python3 bootstrap.py --status # Check status
  python3 bootstrap.py --delete # Delete everything
"""

import json
import os
import subprocess
import sys
import time

TOKEN = os.environ.get('THINKBOX_UPCLOUD_API_TOKEN')
if not TOKEN:
    print('ERROR: THINKBOX_UPCLOUD_API_TOKEN not set')
    sys.exit(1)

BASE_URL = 'https://api.upcloud.com/1.3'
HEADERS = [
    '-H', f'Authorization: Bearer {TOKEN}',
    '-H', 'Content-Type: application/json',
]

# KILO public key - add to all servers
KILO_SSH_KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee'

# Inception API key
INCEPTION_API_KEY = 'sk_63c907f6e5c65a4fd03d1bafcd81e895'


def api(method, path, data=None):
    """Make an API call."""
    cmd = ['curl', '-s', '-X', method] + HEADERS
    if data:
        cmd += ['-d', json.dumps(data)]
    cmd.append(f'{BASE_URL}{path}')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except:
        return result.stdout


def create_server(title, hostname, plan, ssh_keys, user_data=None, wait=True):
    """Create a server and optionally wait for it to start."""
    payload = {
        'server': {
            'zone': 'fi-hel2',
            'title': title,
            'hostname': hostname,
            'plan': plan,
            'storage_devices': {
                'storage_device': [{
                    'action': 'create',
                    'size': 5 if '1xCPU' in plan else 300,
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

    resp = api('POST', '/server', payload)
    if 'server' not in resp:
        print(f'  Error creating {title}: {resp}')
        return None

    uuid = resp['server']['uuid']
    print(f'  Created {title}: {uuid}')

    if wait:
        return wait_for_server(uuid)
    return resp['server']


def wait_for_server(uuid, target_state='started', timeout=300):
    """Wait for a server to reach a specific state."""
    start = time.time()
    while time.time() - start < timeout:
        resp = api('GET', f'/server/{uuid}')
        state = resp['server']['state']
        if state == target_state:
            return resp['server']
        time.sleep(5)
    print(f'  Timeout waiting for {uuid} to be {target_state}')
    return None


def stop_server(uuid):
    """Stop a server."""
    return api('POST', f'/server/{uuid}/stop', {
        'stop_server': {'stop_type': 'hard', 'timeout': '60'}
    })


def delete_server(uuid):
    """Delete a server."""
    return api('DELETE', f'/server/{uuid}?storages=true')


def get_servers():
    """Get all servers."""
    return api('GET', '/server')


def bootstrap():
    """Main bootstrap flow."""
    print('=== KUDBEE BOOTSTRAP ===\n')

    # Step 1: Create foothold server FIRST
    print('1. Creating foothold server...')
    foothold = create_server(
        title='kilo-foothold',
        hostname='kilo-foothold',
        plan='1xCPU-1GB',
        ssh_keys=[KILO_SSH_KEY]
    )
    if not foothold:
        print('FAILED: Could not create foothold')
        return

    foothold_ip = foothold['ip_addresses']['ip_address'][0]['address']
    print(f'   Foothold IP: {foothold_ip}')

    # Step 2: Create GPU server
    print('\n2. Creating GPU server...')
    gpu_user_data = f"""#cloud-config
package_update: true
packages:
  - docker.io
  - nvidia-driver-535
  - nvidia-container-toolkit
  - python3
  - python3-pip
  - git
  - curl
  - jq
runcmd:
  - systemctl enable docker
  - systemctl start docker
  - echo 'INCEPTION_API_KEY={INCEPTION_API_KEY}' > /root/.env
  - chmod 600 /root/.env
"""

    gpu = create_server(
        title='kudbee-gpu-primary',
        hostname='kudbee-gpu-primary',
        plan='GPU-SPOT-12xCPU-128GB-2xL40S',
        ssh_keys=[KILO_SSH_KEY],
        user_data=gpu_user_data
    )
    if not gpu:
        print('FAILED: Could not create GPU server')
        return

    gpu_ip = gpu['ip_addresses']['ip_address'][0]['address']
    print(f'   GPU IP: {gpu_ip}')

    # Step 3: Attach floating IPs if available
    print('\n3. Attaching floating IPs...')
    ips = api('GET', '/ip_address')
    floating = [ip for ip in ips['ip_addresses']['ip_address'] if ip.get('floating') == 'yes' and not ip.get('server')]
    if floating:
        api('POST', f'/server/{gpu["uuid"]}/ip_address', {
            'ip_address': {'family': 'IPv4', 'floating': 'yes'}
        })
        print(f'   Attached floating IP to GPU server')

    print('\n=== BOOTSTRAP COMPLETE ===')
    print(f'Foothold: {foothold_ip}')
    print(f'GPU:      {gpu_ip}')
    print(f'\nTo access GPU server via foothold:')
    print(f'  ssh -i ~/.ssh/kilocloud root@{foothold_ip}')
    print(f'  then: ssh root@{gpu_ip}')


def status():
    """Show current infrastructure status."""
    servers = get_servers()
    if 'servers' not in servers:
        print('No servers found')
        return

    print('=== SERVERS ===')
    for s in servers['servers']['server']:
        print(f"  {s['uuid'][:8]}  {s['title']:<35} {s['state']:<12} {s['zone']}")


def delete_all():
    """Delete all servers."""
    servers = get_servers()
    if 'servers' not in servers:
        print('No servers')
        return

    for s in servers['servers']['server']:
        uuid = s['uuid']
        title = s['title']
        print(f'Stopping {title}...', end=' ')
        stop_server(uuid)
        print('done')

    print('Waiting 30s for servers to stop...')
    time.sleep(30)

    for s in servers['servers']['server']:
        uuid = s['uuid']
        title = s['title']
        print(f'Deleting {title}...', end=' ')
        delete_server(uuid)
        print('done')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == '--status':
            status()
        elif cmd == '--delete':
            delete_all()
        else:
            print(f'Unknown command: {cmd}')
            print('Usage: python3 bootstrap.py [--status|--delete]')
    else:
        bootstrap()
