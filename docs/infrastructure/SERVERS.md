# Server Details

**Last Updated:** 2026-08-30

---

## kudbee-gpu-primary

| Field | Value |
|-------|-------|
| UUID | 002b8e55-1d81-4b3a-aff5-c15b2df0e66f |
| Hostname | gpu-ubuntu-12cpu-128gb-fi-hel2 |
| Plan | GPU-SPOT-12xCPU-128GB-2xL40S |
| Zone | fi-hel2 |
| State | started |
| Created | 2026-08-30 |
| CPU | 12 cores |
| RAM | 128 GB |
| GPUs | 2x NVIDIA L40S (48 GB VRAM each, 18,176 CUDA cores) |
| Storage | 300 GB maxiops |
| OS Template | Ubuntu 24.04 with NVIDIA drivers & CUDA (01000000-0000-4000-8000-000030700200) |
| Public IP | 87.58.149.32 |
| Floating IP | 87.58.149.103 |
| Private IP | 10.6.13.220 |
| Metadata | no |
| Firewall | off |
| SSH | publickey-only, no available key |

**Purpose:** GPU compute for model inference, training, music models, GPT-20B.

---

## kudbee-host-v1-mercury

| Field | Value |
|-------|-------|
| UUID | 000d8567-72c8-46b8-99b6-89d260944d0b |
| Hostname | kudbee-host-v1 |
| Plan | PREMIUM-4xCPU-8GB |
| Zone | fi-hel2 |
| State | started |
| Created | 2026-08-20 |
| CPU | 4 cores |
| RAM | 8 GB |
| Storage | 100 GB maxiops |
| OS Template | UpCloud K8s 1.35 (01000000-0000-4000-8000-000160150100) |
| Public IP | 212.147.250.183 |
| Floating IP | 87.58.151.132 |
| Private IPs | 10.0.2.2 (My Network), 10.6.22.159 (Utility) |
| Metadata | yes |
| Firewall | off |
| SSH | publickey-only, no available key |
| Server Group | 0ba04fd7-8f9a-4410-b3a5-d4f6eccb2dcb |

**Labels:**

| Key | Value |
|-----|-------|
| capu_cluster_id | 0db2a391-1402-4e66-bde6-18cded72ed6d |
| capu_cluster_name | think-box-test |
| capu_generated_name | kid-bee-mlw5f-6wmt7 |

**Purpose:** Original Think Box host. Deployed as Kubernetes node via Cluster API for UpCloud (CAPU). Mercury 2 was likely a Kubernetes workload on this server.

**Current State:** Kubernetes API (port 6443) is NOT responding. The cluster may have been decommissioned or is not running.

---

## kudbee-command

| Field | Value |
|-------|-------|
| UUID | 00ddc075-7f51-4e2c-ad5f-601205c6cbda |
| Hostname | kudbee-cmd |
| Plan | PREMIUM-2xCPU-4GB |
| Zone | fi-hel2 |
| State | started |
| Public IP | 87.58.149.70 |
| Private IP | 10.6.23.9 |
| SSH | publickey-only, no available key |

---

## kudbee-access

| Field | Value |
|-------|-------|
| UUID | 007691c9-772b-4e5b-b196-8137017b9db1 |
| Hostname | kudbee-access |
| Plan | PREMIUM-2xCPU-4GB |
| Zone | fi-hel2 |
| State | started |
| Public IP | 87.58.149.45 |
| Private IP | 10.6.23.4 |
| SSH | publickey-only, no available key |

---

## kudbee-debian

| Field | Value |
|-------|-------|
| UUID | 00331bb2-53d6-4b72-a4cf-fd590f3c489f |
| Hostname | kudbee-debian |
| Plan | PREMIUM-2xCPU-4GB |
| Zone | fi-hel2 |
| State | started |
| Public IP | 87.58.149.93 |
| Private IP | 10.6.23.10 |
| SSH | publickey-only, no available key |
| OS | Debian |

---

## kudbee-chicago-8cpu

| Field | Value |
|-------|-------|
| UUID | 004c080f-5966-44ae-9260-16b6d55e11e3 |
| Hostname | ubuntu-8cpu-128gb-us-chi1 |
| Plan | PREMIUM-8xCPU-128GB |
| Zone | us-chi1 |
| State | started |
| CPU | 8 cores |
| RAM | 128 GB |
| Storage | 400 GB maxiops |
| Public IP | 152.44.35.44 |
| Private IP | 10.3.7.136 |
| SSH | publickey-only, no available key |

---

## Temporary/Orphan Servers

### kilo-foothold

| Field | Value |
|-------|-------|
| UUID | 000e73d0-082a-4da9-b7af-065bc81d5028 |
| Plan | 1xCPU-1GB |
| Public IP | 87.58.149.82 |
| Private IP | 10.6.23.7 |
| SSH | ✅ kilocloud key |
| Password | kudbee-temp-password |
| Purpose | Kilo investigation foothold |

### kilo-orphan-v1, kilo-orphan-v2

| Field | Value |
|-------|-------|
| UUIDs | 00d270d5, 0035a60c |
| Plans | 1xCPU-1GB each |
| Purpose | Failed SSH injection attempts — safe to delete |

### kudbee-test

| Field | Value |
|-------|-------|
| UUID | 00b49236-0baa-4815-b7c0-36971cf42a74 |
| Plan | PREMIUM-2xCPU-4GB |
| Purpose | Test server |
