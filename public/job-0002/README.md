# THINK JOB #0002 — Researcher

**Intent:** Compare DOGI (claimed 21M) and DBIT (claimed 2.1T) as separate tickers across public indexers.

**Note:** DBIT is a separate ticker, not the 2.1B DOGI deploy.

**Plan:**
1. Check indexer health
2. Fetch each ticker from available indexers
3. Compare responses across sources
4. Record agreement or disagreement

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

**Verdict:** UNPROVEN — public APIs cannot fetch inscription content for either ticker.

**Receipts:** box_minutes: 0, gpu_minutes: 0, http_calls: 0
