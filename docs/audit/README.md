# Repository audit ledger (PR #125)

Persistent, git-tracked audit state for Kudbee Studio / Think Box AI. Conversations and CI runs are ephemeral; this tree is the canonical record of what was reviewed, when, and at which commit.

## Layout

| Path | Purpose |
|------|---------|
| `AUDIT_INDEX.json` | Index of audit passes and checked areas |
| `passes/YYYY-MM-DD-pr125.json` | One ranked finding list per audit pass |
| `checklists/*.md` | Human-readable checklists by area (incl. `kilo-spine-pr141.md`, `kilo-env-matrix-pr142.md`, `kilo-substrate-checklist-pr143.md`, `kilo-governance-evidence-pr145.md`) |
| `checked/<area>.json` | Machine-readable check records per area |

Each **checked item** includes:

- `path` — repository-relative file or directory
- `checked_at` — ISO-8601 UTC timestamp
- `commit_sha` — git SHA when the check was recorded
- `checker` — agent or human id
- `status` — `pass` \| `fail` \| `warn` \| `skip`
- `finding_ids` — links into the pass JSON (`F001`, …)
- `notes` — free text

## CLI

```bash
python3 scripts/audit_ledger.py list
python3 scripts/audit_ledger.py list --area security --json
python3 scripts/audit_ledger.py mark-checked tests unit/test_audit_ledger.py pass \
  --area tests --finding-ids F002 --checker pr125-agent
python3 scripts/audit_ledger.py stale --fail-on-stale
```

`stale` flags items whose `commit_sha` is not `HEAD` or whose `path` changed since that commit.

## Workflow

1. Open or continue a pass under `passes/`.
2. Run checklists; record outcomes with `mark-checked`.
3. Implement **P0/P1** fixes in the same PR when possible; leave **P2/P3** as `open` in the pass file.
4. Update `docs/CONTINUITY.md` and `docs/STATUS.md` with suite counts and Four-State labels — never claim LIVE/PRODUCTION without proof artifacts.

## Deploy (Vercel)

See `checklists/deploy-vercel.md` and finding **F018** in the latest pass. No production deploy is claimed from this ledger without a preview URL and evidence artifact.
