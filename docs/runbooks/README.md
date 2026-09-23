# Runbooks

Operator and agent runbooks for Think Box AI / KILO. Hermetic checklists live here;
Live proof evidence is recorded separately under `data/thinkboxmd/artifacts/` and audit passes.

| Runbook | Purpose |
|---------|---------|
| [kilo-live-proof-readiness.md](./kilo-live-proof-readiness.md) | PR **#141–#150** arc: prerequisites and gates before KILO **Live proof** (not the proof itself); operator verify through `live-proof-exec` |
| [branch-hygiene.md](./branch-hygiene.md) | PR **#151** post-season: safe cleanup of merged `cursor/*` remotes (dry-run default) |

**Four-state on spine docs:** CODE COMPLETE / TEST VERIFIED only until a dedicated Live proof pass earns LIVE VERIFIED.
