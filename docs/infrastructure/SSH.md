# SSH Access

**Last Updated:** 2026-08-30

---

## Current State

All production servers use **publickey-only** SSH authentication. Password authentication is disabled.

| Server | SSH Access | Method |
|--------|-----------|--------|
| kilo-foothold | ✅ | kilocloud key |
| kudbee-gpu-primary | ❌ | No key available |
| kudbee-host-v1-mercury | ❌ | No key available |
| kudbee-command | ❌ | No key available |
| kudbee-access | ❌ | No key available |
| kudbee-debian | ❌ | No key available |
| kudbee-chicago-8cpu | ❌ | No key available |

---

## Available Keys

### kilocloud (foothold only)

| Field | Value |
|-------|-------|
| Type | ED25519 |
| Private Key | `~/.ssh/kilocloud` |
| Public Key | `~/.ssh/kilocloud.pub` |
| Fingerprint | `SHA256:6WYtk3LiYSNQtUf/Pmz/kZ9rvK1o29PFbkfB5YnzB9s` |
| Authorized on | kilo-foothold only |

### KILO Public Key (for adding to servers)

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee
```

### UpCloud Account SSH Keys

| Key Name | Fingerprint |
|----------|-------------|
| kilo | SHA256:jFq0DPFKU4hGE/ZmQQTPuPOkpFzaLXBn1sR36LI5u2k |
| kudbee-deploy-20260830 | SHA256:9kd4c+hiMqjFiTWB9rVPTOXIGb+L+vh/Anq/FO361pQ |

**Note:** The private keys for these are NOT available in this environment.

---

## SSH Configuration

### sshd_config.d pattern (Ubuntu 24.04)

Ubuntu 24.04 uses `Include /etc/ssh/sshd_config.d/*.conf` which overrides the main config. To enable password auth:

```bash
echo 'PasswordAuthentication yes' > /etc/ssh/sshd_config.d/50-password-auth.conf
systemctl restart sshd
```

### Foothold SSH config

The foothold server has:
- `PasswordAuthentication yes` in `/etc/ssh/sshd_config.d/50-cloud-init.conf`
- `ssh_pwauth: true` in cloud-init
- Root password: `kudbee-temp-password`

---

## Emergency Access Procedure

When SSH key is not available:

### Option 1: Add KILO public key via web console

1. Go to `https://control.upcloud.com`
2. Navigate to target server → Console
3. Log in with root credentials
4. Run:
   ```bash
   mkdir -p ~/.ssh
   echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee' >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

### Option 2: Enable password auth via web console

1. Go to `https://control.upcloud.com`
2. Navigate to target server → Console
3. Run:
   ```bash
   echo 'PasswordAuthentication yes' > /etc/ssh/sshd_config.d/50-password-auth.conf
   systemctl restart sshd
   ```
4. SSH with password

### Option 3: Mount storage on another host

1. Stop the target server
2. Detach its storage via API
3. Attach storage to a host with known SSH access
4. Mount the filesystem
5. Edit `root/.ssh/authorized_keys`
6. Detach and reattach to original server
7. Start the server

---

## SSH Jump Host Pattern

From the foothold, you can reach all servers on the utility network:

```bash
ssh -o ProxyJump=root@87.58.149.82 root@10.6.13.220
```

This works for connectivity but still requires authentication on the target.
