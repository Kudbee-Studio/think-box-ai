#!/usr/bin/env bash
# KU3BEE Storage Disk Attachment Script
# Attaches existing UpCloud storage disks to the GPU server
#
# Usage: UPCLOUD_API_TOKEN=<token> bash attach-storage.sh <server_uuid>

set -euo pipefail

TOKEN="${THINKBOX_UPCLOUD_API_TOKEN:-}"
SERVER_UUID="${1:-00d832ec-8565-447b-86ac-74bf9bd41e57}"

if [[ -z "$TOKEN" ]]; then
    echo "ERROR: Set THINKBOX_UPCLOUD_API_TOKEN env var"
    exit 1
fi

API_URL="https://api.upcloud.com/1.3"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# Storage disks to attach (from available storage list)
declare -A DISKS=(
    ["models-disk-500gb"]="01f540e7-8e39-4674-a44d-bb4aafe5854a"
    ["video-models-disk-1"]="01eeb13d-5f08-44a8-8a0a-f2c9de95a00c"
    ["video-models-disk-2"]="01c67400-b395-4a66-810e-0d880cfa1abe"
    ["main-hd-v1"]="016d4a87-5911-41ec-9805-622f1d1a2661"
)

# Check server state
check_server() {
    log "Checking server state..."
    STATE=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "$API_URL/server/$SERVER_UUID" | python3 -c "import sys,json; print(json.load(sys.stdin)['server']['state'])")
    log "Server state: $STATE"
    
    if [[ "$STATE" != "stopped" && "$STATE" != "started" ]]; then
        log "ERROR: Server must be stopped or started (current: $STATE)"
        exit 1
    fi
    echo "$STATE"
}

# Get current storage devices
get_current_devices() {
    curl -s -H "Authorization: Bearer $TOKEN" \
        "$API_URL/server/$SERVER_UUID" | python3 -c "
import sys, json
data = json.load(sys.stdin)
devices = data['server'].get('storage_devices', {}).get('storage_device', [])
for d in devices:
    print(f\"{d['address']} {d.get('storage', 'N/A')}\")
"
}

# Attach a disk
attach_disk() {
    local name="$1"
    local uuid="$2"
    local address="virtio:$uuid"
    
    log "Attaching $name ($uuid)..."
    
    # Check if already attached
    if get_current_devices | grep -q "$uuid"; then
        log "  Already attached, skipping"
        return 0
    fi
    
    # Modify server to add storage device
    MOD=$(cat <<JSON
{
    "server": {
        "storage_devices": {
            "storage_device": [
                {
                    "action": "attach",
                    "storage": "$uuid",
                    "address": "virtio"
                }
            ]
        }
    }
}
JSON
)
    
    RESULT=$(curl -s -X PUT \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$MOD" \
        "$API_URL/server/$SERVER_UUID")
    
    if echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'server' in d" 2>/dev/null; then
        log "  Attached successfully"
    else
        log "  ERROR: $(echo "$RESULT" | head -c 200)"
        return 1
    fi
}

# Mount disks inside server
generate_mount_script() {
    cat <<'MOUNT'
#!/bin/bash
# Run this INSIDE the server after disks are attached

# Format disks (only if not already formatted)
for dev in /dev/vdb /dev/vdc /dev/vdd /dev/vde; do
    if [[ -b "$dev" ]]; then
        # Check if already has filesystem
        if ! blkid "$dev" > /dev/null 2>&1; then
            mkfs.ext4 -F "$dev"
        fi
    fi
done

# Create mount points
mkdir -p /mnt/models /mnt/video-models /mnt/video-models-2 /mnt/main-hd

# Mount disks (add to /etc/fstab for persistence)
cat >> /etc/fstab <<FSTAB
/dev/vdb /mnt/models ext4 defaults,noatime 0 2
/dev/vdc /mnt/video-models ext4 defaults,noatime 0 2
/dev/vdd /mnt/video-models-2 ext4 defaults,noatime 0 2
/dev/vde /mnt/main-hd ext4 defaults,noatime 0 2
FSTAB

mount -a
echo "Disks mounted:"
df -h /mnt/models /mnt/video-models /mnt/video-models-2 /mnt/main-hd
MOUNT
}

# Main
main() {
    log "=== KU3BEE Storage Attachment ==="
    log "Server: $SERVER_UUID"
    
    STATE=$(check_server)
    
    # Attach each disk
    for name in "${!DISKS[@]}"; do
        attach_disk "$name" "${DISKS[$name]}"
    done
    
    log ""
    log "=== Current Storage Devices ==="
    get_current_devices
    
    log ""
    log "=== Next Steps ==="
    log "1. Start server: curl -X POST -H 'Authorization: Bearer $TOKEN' $API_URL/server/$SERVER_UUID/start"
    log "2. Wait 60 seconds for SSH"
    log "3. Run mount script inside server (see below)"
    log ""
    log "=== Mount Script (run inside server) ==="
    generate_mount_script
}

main "$@"
