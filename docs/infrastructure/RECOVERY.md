# Disaster Recovery

**Last Updated:** 2026-08-30

---

## Scenario: Complete Environment Loss

If the entire KUDBEE development environment disappeared tomorrow, this document explains how to recover.

---

## Recovery Checklist

### Phase 1: Credential Recovery

| # | Credential | Where to Recover | How |
|---|-----------|-----------------|-----|
| 1 | UpCloud API Token | UpCloud Control Panel → Account → API Credentials | Generate new token |
| 2 | UpCloud SSH Keys | UpCloud Control Panel → Account → SSH Keys | Re-upload public keys |
| 3 | UpCloud Password | UpCloud Control Panel → Account → Password | Reset if needed |
| 4 | GitHub Token | GitHub → Settings → Developer Settings → PAT | Generate new token |
| 5 | Upstash Keys | Upstash Console → API Keys | Regenerate |
| 6 | Kilo Token | Kilo CLI → Re-authenticate | `kilo auth login` |

### Phase 2: Infrastructure Discovery

```bash
# 1. Set the recovered token
export UPCLOUD_TOKEN="<new-token>"

# 2. Discover all servers
curl -s -H "Authorization: Bearer $UPCLOUD_TOKEN" \
  https://api.upcloud.com/1.3/server | python3 -m json.tool

# 3. Discover all IPs
curl -s -H "Authorization: Bearer $UPCLOUD_TOKEN" \
  https://api.upcloud.com/1.3/ip_address | python3 -m json.tool

# 4. Discover all networks
curl -s -H "Authorization: Bearer $UPCLOUD_TOKEN" \
  https://api.upcloud.com/1.3/network | python3 -m json.tool

# 5. Discover all routers
curl -s -H "Authorization: Bearer $UPCLOUD_TOKEN" \
  https://api.upcloud.com/1.3/router | python3 -m json.tool

# 6. Discover all storage
curl -s -H "Authorization: Bearer $UPCLOUD_TOKEN" \
  "https://api.upcloud.com/1.3/storage?private=1" | python3 -m json.tool
```

### Phase 3: SSH Recovery

For each server that needs SSH access:

1. **Try existing keys first:**
   ```bash
   ssh -o ConnectTimeout=5 -i ~/.ssh/id_ed25519 root@<public-ip>
   ```

2. **If key fails, use web console:**
   - Go to `https://control.upcloud.com`
   - Navigate to server → Console
   - Add KILO public key:
     ```
     ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee
     ```

3. **If console needs password, reset it:**
   - UpCloud Control Panel → Server → Reset root password
   - Use emergency console with new password
   - Then add SSH key

### Phase 4: Kubernetes Recovery

1. SSH into kudbee-host-v1-mercury
2. Check Kubernetes state:
   ```bash
   systemctl status kubelet
   crictl ps -a
   ls /etc/kubernetes/
   ```
3. If cluster needs re-initialization:
   ```bash
   kubeadm init --pod-network-cidr=10.0.0.0/24
   ```
4. Re-deploy workloads from manifests (if backed up)

### Phase 5: Mercury Recovery

1. Check if Mercury was a Kubernetes workload:
   ```bash
   kubectl get deployments --all-namespaces
   kubectl get services --all-namespaces
   ```
2. If manifests exist, re-deploy:
   ```bash
   kubectl apply -f /path/to/mercury-manifests/
   ```
3. If Mercury source is in the repository, rebuild and deploy

### Phase 6: KUDBEE Recovery

1. Clone the repository:
   ```bash
   git clone https://github.com/Kudbee-Studio/think-box-ai.git
   ```
2. Install dependencies:
   ```bash
   cd think-box-ai
   pip install -e ".[dev]"
   ```
3. Run tests:
   ```bash
   python3 -m unittest discover -s tests
   ```
4. Verify bootstrap:
   ```bash
   python3 -c "from core.foundation.bootstrap import bootstrap; print('OK')"
   ```

### Phase 7: Validation

| Check | Command | Expected |
|-------|---------|----------|
| UpCloud API | `curl -H "Authorization: Bearer $TOKEN" https://api.upcloud.com/1.3/server` | Server list JSON |
| SSH to GPU | `ssh root@87.58.149.32 hostname` | `gpu-ubuntu-12cpu-128gb-fi-hel2` |
| SSH to Mercury | `ssh root@212.147.250.183 hostname` | `kudbee-host-v1` |
| K8s API | `kubectl get nodes` | Node list |
| KUDBEE runtime | `python3 -c "from core.foundation.bootstrap import bootstrap; print('OK')"` | `OK` |
| Think Token | `python3 -c "from think_box_ai.token import ThinkToken; print('OK')"` | `OK` |

---

## Backup Requirements

| What | How | Frequency |
|------|-----|-----------|
| Server configurations | UpCloud API export | On change |
| Storage volumes | UpCloud backup rule | Daily |
| Kubernetes manifests | Git repository | On change |
| Mercury source/config | Git repository | On change |
| KUDBEE code | GitHub | Every commit |
| Credentials | UpCloud Console + Vault | On rotation |

---

## Single Points of Failure

| Component | Risk | Mitigation |
|-----------|------|------------|
| UpCloud API token | HIGH | Store in multiple safe locations |
| SSH private keys | HIGH | Back up encrypted |
| Kubernetes control plane | MEDIUM | Export manifests to git |
| Mercury source | MEDIUM | Ensure in version control |
| GPU server data | LOW | 300 GB maxiops, no backup rule |
