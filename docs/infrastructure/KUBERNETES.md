# Kubernetes / CAPU

**Last Updated:** 2026-08-30

---

## Current State

| Item | Status |
|------|--------|
| Kubernetes API (port 6443) | ❌ Not responding on any server |
| kubectl | ❌ Not installed on any accessible server |
| Cluster control plane | UNKNOWN |
| Running workloads | UNKNOWN |

---

## Cluster Information

### Cluster: think-box-test

| Field | Value |
|-------|-------|
| Cluster ID | 0db2a391-1402-4e66-bde6-18cded72ed6d |
| Cluster Name | think-box-test |
| Provisioner | Cluster API for UpCloud (CAPU) |
| Node | kid-bee-mlw5f-6wmt7 (kudbee-host-v1-mercury) |
| Server Group | 0ba04fd7-8f9a-4410-b3a5-d4f6eccb2dcb |
| K8s Version | 1.35 (from template) |
| Template | UpCloud K8s 1.35 (01000000-0000-4000-8000-000160150100) |

### Evidence of Kubernetes

The kudbee-host-v1-mercury server has CAPU labels:
- `capu_cluster_id: 0db2a391-1402-4e66-bde6-18cded72ed6d`
- `capu_cluster_name: think-box-test`
- `capu_generated_name: kid-bee-mlw5f-6wmt7`

The storage was cloned from the **UpCloud K8s 1.35** template.

### Network

The server has a private network interface on `My Network` (10.0.2.0/24) routed via `think-box-test-data-plane` router. This is likely the Kubernetes pod/service network.

---

## Investigation Results

### Port Scan (from kilo-foothold)

| Port | Status | K8s Component |
|------|--------|---------------|
| 6443 | ❌ Closed | Kubernetes API |
| 10250 | ❌ Closed | Kubelet |
| 10255 | ❌ Closed | Kubelet read-only |
| 10257 | ❌ Closed | Controller manager |
| 10259 | ❌ Closed | Scheduler |
| 2379 | ❌ Closed | etcd |
| 2380 | ❌ Closed | etcd peer |
| 179 | ❌ Closed | BGP (Calico) |
| 4789 | ❌ Closed | VXLAN (Flannel/Calico) |
| 8472 | ❌ Closed | VXLAN (Flannel) |
| 53 | ❌ Closed | CoreDNS |
| 5473 | ❌ Closed | Calico Typha |

**Conclusion:** No Kubernetes components are currently running on this server.

---

## Possible Explanations

1. **Cluster was decommissioned** — Mercury 2 and Think Box workloads were removed
2. **Cluster needs manual start** — kubeadm/cluster-api needs to be initialized
3. **Control plane is elsewhere** — a separate control plane server may have been deleted
4. **Cluster never fully initialized** — server was provisioned but cluster was never bootstrapped

---

## Recovery Path

To investigate further:

1. Gain SSH access to kudbee-host-v1-mercury (via web console)
2. Check for Kubernetes configuration:
   ```bash
   ls /etc/kubernetes/
   cat /etc/kubernetes/admin.conf
   crictl ps -a
   systemctl status kubelet
   ```
3. Check for cluster-api state:
   ```bash
   ls /var/lib/cluster-api/
   kubectl get nodes  # if kubectl configured
   ```
4. Check for Mercury/Think Box deployments:
   ```bash
   kubectl get pods --all-namespaces
   kubectl get services --all-namespaces
   ```
