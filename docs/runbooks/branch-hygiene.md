# Branch hygiene runbook (post-season #151)

**Purpose:** Safely list and delete **merged** remote agent branches (`cursor/*`, optional `convoy/*`) without touching protected branches or force-pushing `main`.

**Four-state:** This runbook is **CODE COMPLETE / TEST VERIFIED** only. It does not earn KILO LIVE VERIFIED.

## Protected branches (never deleted)

- `main`, `master`, `develop`, `development`, `release`, `production`

The cleanup script refuses these names at any path segment.

## Default behavior

```bash
python3 scripts/cleanup_merged_cursor_branches.py
```

- **Dry-run only** — prints branches that *would* be deleted.
- Only branches whose tip is merged into `origin/main` are eligible.
- Requires `git fetch origin main` first when auditing locally.

## Execute deletes (founder-only)

```bash
git fetch origin main
python3 scripts/cleanup_merged_cursor_branches.py --execute
```

Deletes remotes with `git push origin --delete <branch>`. **Never** use `--force` on `main`.

## Custom prefixes

```bash
python3 scripts/cleanup_merged_cursor_branches.py --prefix cursor/ --prefix feat/pr129-
```

## Verification

```bash
python3 scripts/verify_kilo_post_season_harden.py
python3 scripts/scan_doc_secrets.py
```

## When not to run

- Open PRs still targeting a `cursor/*` branch
- Branches not yet merged to `main`
- Shared long-lived `feat/**` product branches (use prefix filter carefully)
