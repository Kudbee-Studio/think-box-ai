# DOGI Indexer Split

**Date:** 2026-08-31
**Status:** Unproven
**Verdict:** Cannot verify via public APIs alone

## Summary

This research job attempted to verify the Doginals indexer-split case for DOGI (21M vs 2.1B deploys) against live public APIs.

## Methodology

1. Queried 5 public Doginals/DRC-20 indexers for inscription data
2. Compared responses across indexers
3. Attempted to identify canonical vs non-canonical deployments

## Findings

- **api.doginals.org**: Health endpoint OK, inscription endpoints 404 (not public)
- **dogechain.info**: HTTP 403 (Cloudflare anti-bot challenge)
- **wonky-ordinals.fly.dev**: DNS resolution failure
- **ordinalswallet.com**: HTTP 522 (connection timeout)
- **api.inception.ai**: TLS alert 112 (CDN SNI reject from AWS IPs)

## Conclusion

The indexer-split thesis is **not provable via public APIs alone**. Most inscription indexers don't expose public endpoints, require auth, or are unreachable. To prove the thesis, we need a paid API, residential proxy, or local indexer.

## Next Steps

- Run a local Doginals indexer
- Use residential proxy for Cloudflare-protected APIs
- Consider paid indexer APIs
