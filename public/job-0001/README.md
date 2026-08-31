# THINK JOB #0001 — Researcher

**Intent:** Do public indexers agree on early DOGI deploy and supply?

**Plan:**
1. Query live public indexers for DOGI inscription data
2. Compare responses across sources
3. Record agreement or disagreement

**Execution:**
- doginals_org: 200 OK (health); inscription endpoints 404
- dogechain: 403 Forbidden
- ordinalsdotcom: unreachable (timeout)
- wonky: unreachable (DNS dead)
- unisat: 404 Not Found
- 3 inscription IDs tested: all returned no data

**Artifacts:**
- [finding.md](finding.md) — full report
- [job.json](job.json) — structured job record

**Verdict:** UNPROVEN — public APIs do not show both DOGI deploys. Cannot verify indexer split.

**Receipts:** not metered yet (box_minutes: 0, gpu_minutes: 0, http_calls: 0)
