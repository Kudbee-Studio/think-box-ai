# Network Topology

**Last Updated:** 2026-08-30

---

## Overview

All production servers are in **fi-hel2** (Finland) except one in **us-chi1** (Chicago).
Two network types: **public** (DHCP-assigned) and **utility** (private, server-to-server).

---

## Network Map

```
                        INTERNET
                           │
                           │
              ┌────────────┴────────────┐
              │  Public: 87.58.148.0/22 │
              │  (fi-hel2)              │
              │  No router attached     │
              └────────────┬────────────┘
                           │
    ┌──────────┬───────────┼───────────┬──────────┐
    │          │           │           │          │
 GPU        Mercury     Command     Access     Debian
 .32        .183        .70         .45        .93
 .103(f)    .132(f)

              ┌────────────┴────────────┐
              │  Utility: 10.6.20.0/22  │
              │  (fi-hel2)              │
              │  Router: Utility fi-hel2│
              └────────────┬────────────┘
                           │
    ┌──────────┬───────────┼───────────┬──────────┐
    │          │           │           │          │
 GPU        Mercury     Foothold    Debian     Test
 .13.220    .22.159     .23.7       .23.10     .23.8


              ┌────────────┴────────────┐
              │  Private: 10.0.2.0/24   │
              │  "My Network"           │
              │  Router: data-plane     │
              └────────────┬────────────┘
                           │
                     Mercury
                     .2.2


              ┌────────────┴────────────┐
              │  Public: 212.147.240/22 │
              │  (fi-hel2)              │
              └────────────┬────────────┘
                           │
                     Mercury
                     .250.183
```

---

## Networks (fi-hel2)

| Network | UUID | Type | Subnet | Router |
|---------|------|------|--------|--------|
| Public fi-hel2 87.58.148.0/22 | 03014f00 | public | 87.58.148.0/22 | None |
| Private 10.6.12.0/22 | 03334b38 | utility | 10.6.12.0/22 | Utility fi-hel2 |
| Private 10.6.20.0/22 | 03c3fc67 | utility | 10.6.20.0/22 | Utility fi-hel2 |
| My Network | 0345acbc | private | 10.0.2.0/24 | think-box-test-data-plane |
| Public fi-hel2 212.147.240/22 | 0319845a | public | 212.147.240/22 | None |
| Public 2a04:3545:1000:720::/64 | 03000000 | public IPv6 | 2a04:3545:1000:720::/64 | None |

---

## Routers

| Router | UUID | Type | Attached Networks |
|--------|------|------|------------------|
| Utility network router for zone fi-hel2 | 045d230a | service | 10.6.12.0/22, 10.6.20.0/22 |
| Utility network router for zone us-chi1 | 04840459 | service | 10.3.4.0/22 |
| think-box-test-data-plane | 04e679ba | normal | My Network (10.0.2.0/24) |

---

## Server Network Interfaces

### kudbee-gpu-primary (002b8e55)

| Interface | Network | IP | Type |
|-----------|---------|-----|------|
| eth0 | Public fi-hel2 | 87.58.149.32 | Public |
| eth0 | Floating | 87.58.149.103 | Floating |
| eth1 | Utility 10.6.12.0/22 | 10.6.13.220 | Private |
| eth2 | Public IPv6 | 2a04:3545:1000:720:... | Public |

### kudbee-host-v1-mercury (000d8567)

| Interface | Network | IP | Type |
|-----------|---------|-----|------|
| eth0 | My Network | 10.0.2.2 | Private |
| eth1 | Utility 10.6.20.0/22 | 10.6.22.159 | Private |
| eth2 | Public fi-hel2 212.147.240/22 | 212.147.250.183 | Public |
| eth2 | Floating | 87.58.151.132 | Floating |

---

## Connectivity Matrix (from kilo-foothold)

| Target | IP | SSH (22) | Ping |
|--------|-----|----------|------|
| kudbee-gpu-primary | 10.6.13.220 | ✅ Open | ✅ 0% loss |
| kudbee-host-v1-mercury | 10.6.22.159 | ✅ Open | ✅ 0% loss |
| kudbee-debian | 10.6.23.10 | ✅ Open | ✅ 0% loss |
| kudbee-command | 10.6.23.9 | ❌ Closed | ❌ Timeout |
| kudbee-access | 10.6.23.4 | ❌ Closed | ❌ Timeout |

**Note:** kudbee-command and kudbee-access are on a different utility network subnet (10.6.23.x) that is not routed from the foothold's utility network (10.6.20.x/10.6.23.x).

---

## DNS

| Server | DNS |
|--------|-----|
| UpCloud default | 94.237.127.9, 94.237.40.9 |

---

## Floating IP Notes

Floating IPs require OS-level configuration to route properly. Currently:
- `87.58.149.103` → kudbee-gpu-primary (timing out — OS config needed)
- `87.58.151.132` → kudbee-host-v1-mercury (timing out — OS config needed)

The floating IP must be configured inside the OS (usually via DHCP or static route) after attachment.
