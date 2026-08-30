# Credential Inventory

**Last Updated:** 2026-08-30
**SECURITY:** This document NEVER contains secret values. Only names, sources, and usage patterns.

---

## Credential Registry

### UpCloud API Token

| Field | Value |
|-------|-------|
| Name | THINKBOX_UPCLOUD_API_TOKEN |
| Source | Environment variable (injected at container boot) |
| Location | `os.environ['THINKBOX_UPCLOUD_API_TOKEN']` |
| Type | Bearer token |
| API Endpoint | `https://api.upcloud.com/1.3/*` |
| Auth Header | `Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN` |
| Scope | Account-wide (full infrastructure CRUD) |
| Required For | All UpCloud infrastructure operations |
| Rotation | Manual (generate new token in UpCloud console) |

### UpCloud SSH User

| Field | Value |
|-------|-------|
| Name | UPCLOUD_SSH_USER |
| Value | root |
| Source | Environment variable |
| Usage | SSH login username |

### UpCloud SSH Key Path

| Field | Value |
|-------|-------|
| Name | UPCLOUD_SSH_KEY_PATH |
| Value | `~/.ssh/kilo-upcloud` |
| Source | Environment variable |
| Status | **File does NOT exist** |
| Usage | Would be used as `ssh -i $UPCLOUD_SSH_KEY_PATH root@<ip>` |

### GitHub Token

| Field | Value |
|-------|-------|
| Name | GH_TOKEN |
| Source | Environment variable |
| Type | GitHub personal access token |
| Usage | Git HTTPS authentication |
| Scope | Kudbee-Studio/think-box-ai repository |

### Inception API Key

| Field | Value |
|-------|-------|
| Name | INCEPTION_API_KEY |
| Source | User-provided |
| Location | `~/.env` on target UpCloud servers |
| Format | `sk_63c907f6e5c65a4fd03d1bafcd81e895` |
| Token Balance | ~99,000,000+ tokens |
| Purpose | Model inference for Mercury 2 / Think Box |
| Required On | kudbee-host-v1-mercury, kudbee-gpu-primary |

**To install on a server:**
```bash
# SSH into server, then:
echo 'INCEPTION_API_KEY=sk_63c907f6e5c65a4fd03d1bafcd81e895' > ~/.env
chmod 600 ~/.env
```

---

### Upstash Box API Key

| Field | Value |
|-------|-------|
| Name | UPSTASH_BOX_API_KEY |
| Source | Environment variable |
| Usage | Upstash Box sandbox SDK |
| SDK Status | NOT installed |

### Upstash Box URL

| Field | Value |
|-------|-------|
| Name | UPSTASH_PUBLIC_BOX_URL |
| Value | `https://wanted-tuna-71803-3000.preview.box.upstash.com/` |
| Source | Environment variable |
| Usage | Public URL for the provisioned Box |

### Upstash Vector

| Field | Value |
|-------|-------|
| Name | UPSTASH_VECTOR_REST_TOKEN |
| Source | Environment variable |
| URL | `https://unified-chigger-36053-gcp-usc1-vector.upstash.io/` |
| Usage | Vector database REST API |

### Upstash API Key

| Field | Value |
|-------|-------|
| Name | UPSTASH_API_KEY |
| Source | Environment variable |
| Usage | Upstash general API |

### Kilo Platform Token

| Field | Value |
|-------|-------|
| Name | KILOCODE_TOKEN |
| Source | Environment variable |
| Usage | Kilo platform authentication |

### Kilo API URL

| Field | Value |
|-------|-------|
| Name | KILO_API_URL |
| Value | `https://api.kilo.ai` |
| Source | Environment variable |
| Usage | Kilo platform API endpoint |

### AI Gateway API Key

| Field | Value |
|-------|-------|
| Name | AI_GATEWAY_API_KEY |
| Source | Environment variable |
| Usage | AI model gateway access |

### Cursor API Key

| Field | Value |
|-------|-------|
| Name | CURSOR_API_KEY |
| Source | Environment variable |
| Usage | Cursor IDE API access |

---

## UpCloud Account SSH Keys (Public)

| Key Name | Fingerprint | Source |
|----------|-------------|--------|
| kilo | SHA256:jFq0DPFKU4hGE/ZmQQTPuPOkpFzaLXBn1sR36LI5u2k | UpCloud Console |
| kudbee-deploy-20260830 | SHA256:9kd4c+hiMqjFiTWB9rVPTOXIGb+L+vh/Anq/FO361pQ | UpCloud Console |

**Note:** Private keys are stored ONLY in the UpCloud Control Panel and/or the user's local machine. They are NOT available in this environment.

---

## Credential Dependencies

```
THINKBOX_UPCLOUD_API_TOKEN
    ├─ Server CRUD (create, read, update, delete)
    ├─ Storage CRUD
    ├─ Network CRUD
    ├─ Router CRUD
    ├─ IP address management
    └─ Template cloning

UPCLOUD_SSH_KEY_PATH + UPCLOUD_SSH_USER
    └─ Server SSH access (when key file exists)

GH_TOKEN
    └─ Git repository access

KILOCODE_TOKEN + KILO_API_URL
    └─ Agent platform + model routing

UPSTASH_BOX_API_KEY + UPSTASH_PUBLIC_BOX_URL
    └─ Think Box sandbox environments

UPSTASH_VECTOR_REST_TOKEN + UPSTASH_VECTOR_REST_URL
    └─ Vector database (memory/knowledge)
```

---

## Credential Recovery

If all credentials are lost:

1. **UpCloud API Token:** Generate new token in UpCloud Control Panel → Account → API Credentials
2. **SSH Keys:** Re-upload public keys in UpCloud Control Panel → Account → SSH Keys
3. **GitHub Token:** Generate new PAT in GitHub Settings → Developer Settings
4. **Upstash Keys:** Regenerate in Upstash Console
5. **Kilo Token:** Re-authenticate via Kilo CLI
