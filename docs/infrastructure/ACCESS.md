# Infrastructure Access Guide

**Last Updated:** 2026-08-30

---

## Access Methods

### 1. UpCloud API (Primary)

| Item | Value |
|------|-------|
| Endpoint | `https://api.upcloud.com/1.3/` |
| Auth | Bearer token |
| Token Name | `THINKBOX_UPCLOUD_API_TOKEN` |
| Token Source | Environment variable |
| Python Access | `os.environ['THINKBOX_UPCLOUD_API_TOKEN']` |
| Required Permission | Account-wide read/write |

**Basic pattern:**
```bash
curl -s -H "Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN" \
  https://api.upcloud.com/1.3/server | python3 -m json.tool
```

### 2. SSH (Server Access)

| Item | Value |
|------|-------|
| User | `root` |
| Auth Method | Public key only (on all production servers) |
| Key Path | `~/.ssh/kilo-upcloud` (NOT provisioned) |
| Available Key | `~/.ssh/kilocloud` (foothold only) |

**Current state:** Only `kilo-foothold` (87.58.149.82) is accessible via SSH. All other servers reject the available key.

### 3. UpCloud Web Console

| Item | Value |
|------|-------|
| URL | `https://control.upcloud.com` |
| Emergency Console | Available per-server (VNC/serial) |
| Password Reset | Available per-server |

---

## Access Sequence

```
1. Environment boots with injected env vars
   └─ THINKBOX_UPCLOUD_API_TOKEN available

2. Validate API access
   └─ curl https://api.upcloud.com/1.3/server

3. Inventory infrastructure
   └─ Parse server list, IPs, networks

4. Attempt SSH to target server
   ├─ Success → proceed with work
   └─ Failure → use web console emergency console
       ├─ Add SSH key to authorized_keys
       └─ OR enable password auth temporarily

5. For GPU server specifically:
   └─ SSH is blocked (publickey-only, no key available)
   └─ Use web console → emergency console
   └─ OR mount storage on another host
```

---

## Server Access Matrix

| Server | SSH | API | Web Console | Emergency |
|--------|-----|-----|-------------|-----------|
| kudbee-gpu-primary | ❌ No key | ✅ | ✅ | ✅ |
| kudbee-host-v1-mercury | ❌ No key | ✅ | ✅ | ✅ |
| kudbee-command | ❌ No key | ✅ | ✅ | ✅ |
| kudbee-access | ❌ No key | ✅ | ✅ | ✅ |
| kudbee-debian | ❌ No key | ✅ | ✅ | ✅ |
| kilo-foothold | ✅ kilocloud | ✅ | ✅ | ✅ |

---

## Emergency Access Procedure

When SSH key is not available:

1. Go to `https://control.upcloud.com`
2. Navigate to the target server
3. Click "Console" or "Serial Console"
4. Log in with root credentials
5. Add SSH public key:
   ```bash
   mkdir -p ~/.ssh
   echo '<PUBLIC_KEY>' >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```
6. OR enable password auth:
   ```bash
   echo 'PasswordAuthentication yes' > /etc/ssh/sshd_config.d/50-password-auth.conf
   systemctl restart sshd
   ```

---

## KILO Public Key (for emergency console)

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee
```

Add this to any server's `~/.ssh/authorized_keys` to grant Kilo SSH access.
