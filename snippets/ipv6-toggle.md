# UPC-003: IPv6 Toggle Per-Interface

**Status:** VERIFIED via official docs
**Source:** https://developers.upcloud.com/1.3/8-servers/#create-server

## How to Control IPv6

IPv6 addresses are controlled per-interface in the `networking` block.

### IPv4 Only (No IPv6)

```json
{
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
  }
}
```

### IPv4 + IPv6

```json
{
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
        },
        {
          "ip_addresses": {"ip_address": [{"family": "IPv6"}]},
          "type": "public"
        }
      ]
    }
  }
}
```

## Key Insight

IPv6 is NOT automatic. To disable IPv6, don't include an interface with `"family": "IPv6"`.

## Available Interface Types

| Type | Description |
|------|-------------|
| `public` | Public internet (IPv4 and/or IPv6) |
| `utility` | Private network between servers (always IPv4) |
| `private` | SDN private network (requires network UUID) |
