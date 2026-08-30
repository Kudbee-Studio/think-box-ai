# UPC-005: Server Creation

**Status:** VERIFIED via official docs
**Source:** https://developers.upcloud.com/1.3/8-servers/#create-server

## Create Server from Scratch (No Clone)

```json
{
  "server": {
    "zone": "fi-hel2",
    "title": "my-server",
    "hostname": "my-server",
    "plan": "1xCPU-1GB",
    "metadata": "yes",
    "storage_devices": {
      "storage_device": [{
        "action": "create",
        "size": 10,
        "tier": "maxiops",
        "title": "root-disk"
      }]
    },
    "networking": {
      "interfaces": {
        "interface": [
          {
            "ip_addresses": {"ip_address": [{"family": "IPv4"}]},
            "type": "public"
          },
          {
            "ip_addresses": {"ip_address": [{"family": "IPv4"}]},
            "type": "utility"
          }
        ]
      }
    },
    "login_user": {
      "username": "root",
      "ssh_keys": {
        "ssh_key": ["ssh-ed25519 AAA... user@host"]
      }
    }
  }
}
```

## Create Server from Template

```json
{
  "server": {
    "zone": "fi-hel2",
    "title": "my-server",
    "hostname": "my-server",
    "plan": "1xCPU-1GB",
    "metadata": "yes",
    "storage_devices": {
      "storage_device": [{
        "action": "clone",
        "storage": "01000000-0000-4000-8000-000030240200",
        "title": "ubuntu-24.04",
        "size": 10,
        "tier": "maxiops"
      }]
    }
  }
}
```

## Create Server from Backup

```json
{
  "server": {
    "zone": "fi-hel2",
    "title": "my-server",
    "hostname": "my-server",
    "plan": "1xCPU-1GB",
    "storage_devices": {
      "storage_device": [{
        "action": "attach",
        "storage": "backup-uuid",
        "title": "restored-disk"
      }]
    }
  }
}
```

## After Creation

1. Wait for `started` state
2. Wait **60 seconds** for SSH to start
3. SSH with `StrictHostKeyChecking=accept-new`
