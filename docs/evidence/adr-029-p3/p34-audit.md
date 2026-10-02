# P3.4 post-merge audit of `bb059c17` (2026-10-02)

Scope: the P3.3 changes another agent session merged into PR #315 (Janus opt-in, held-out eval, push audit), re-checked offline. Mercury spend: $0.
The merge itself: [merge-breach.md](./merge-breach.md).

## Four-state table

| Item | CODE | TEST | LIVE | Notes |
|---|---|---|---|---|
| `main` @ `bb059c17` typecheck and tests | yes | **yes** (387 of 387, re-run here in a clean worktree) | n/a | |
| Janus opt-in (`KUDBEE_JANUS_ENABLED`) | yes | yes (`local-only.test.ts`, in the 387) | n/a | one gap found and fixed, below |
| `JANUS_MODEL` allow-list | yes | no test | n/a | it fixes the model **id**, not the revision; see below |
| Held-out retrieval eval: 6/8 hit@1, 7/8 hit@3 | yes | **not reproduced** | n/a | rerun gives 5/8 and 8/8; time-dependent and leak-prone, see below |
| Pooled A/B significance file | yes | **yes** (matches raw files) | yes (as recorded) | but the pooling choice matters, see below |
| Push audit | yes | n/a | n/a | inspected a different VM; same negative result on this machine |
| CodeQL: 57320d1f vs bb059c17 | n/a | **yes** | n/a | 35 vs 35, same rule/file counts, 0 new |
| Reduced-motion evidence | JSON only | n/a | **UNPROVEN here** | screenshot path is on another VM and is not in the repo |
| CI | | | | **never ran** (billing lock) |

## Janus review

- `server.ts`: `janusEnabled()` gates `requestJanus` and the monitor check. Correct; the default is off and `JANUS_BASE_URL` still defaults to loopback.
- **Gap fixed:** `docker-compose.yml` sets `JANUS_BASE_URL: http://janus:8001` on `agent-os` but not the new flag, so the `images` profile would silently stop working. The compose service now passes `KUDBEE_JANUS_ENABLED` (default `0`), and `docs/guides/environment-variables.md` documents it.
- `janus_service.py` rejects any `JANUS_MODEL` other than `deepseek-ai/Janus-Pro-1B` at import time. That does not remove the CVE exposure: the advisory is about the shard index inside a checkpoint, and the allowed id is still fetched from the hub with no pinned revision. Pinning a commit hash for the model (and the `accelerate` bump when a compatible fix exists) is the real mitigation. `docs/SECURITY.md` describes the risk as low; that is a judgment, not a measurement.
- No test covers the allow-list (the module needs torch).

## Held-out retrieval eval: not reproduced

`node scripts/think-token-retrieval-eval.mjs docs/evidence/adr-029-p3/p33-seed.db scripts/think-token-ab-goals-p33-heldout.mjs`:

| | hit@1 | hit@3 | per-goal ranks |
|---|---|---|---|
| committed (`p33-retrieval-eval.json`) | 6 of 8 | 7 of 8 | misses: `path-normalize` rank 2, `replace-not-append` outside top 3 |
| re-run today | 5 of 8 | **8 of 8** | deep-mkdir 2, zero-byte 2, path-normalize 1, recursive-list 1, size-match 1, replace-not-append 3, emoji-utf8 1, json-line 1 |

Why they differ: the ranking multiplies by `(0.5 + score)` and the score has a recency term (30-day half-life) computed from `Date.now()`, so the same seed ranks differently on different days. The eval is not a deterministic function of the committed files. The headline "6/8 and 7/8" is therefore **UNPROVEN as stated**; today's reproducible numbers are 5/8 and 8/8.

Why "held-out" is generous: the seed lessons were written by the same agent that wrote the goals, and their text repeats the goal's own strings (`deep/nested/out.txt`, `abcde`, `hello.txt`, `🎯`, `{"ok":true}`). BM25 matches that trivially. It shows the ranking can find a lesson that mirrors the goal, not that it generalizes. The retrieval weights were not changed in P3.3 (confirmed: no diff in `think-token-store.ts`).

## Pooled significance file: matches, with a caveat

Recomputed from the raw files: P3.1 (15/24 off, 14/24 on) + P3.3 (19/32 off, 20/32 on) = **34/56 vs 34/56**, matching `ab-pooled-significance.json`. But the pool mixes the old retrieval ranking (P3.1) with the new one (P3.3) and leaves out the P3.2 run (8/21 off, 12/21 on). Alternatives, Fisher exact two-sided:

| Pool | on vs off passes | p |
|---|---|---|
| P3.1 + P3.3 (the file) | 34/56 vs 34/56 | ~1.0 |
| all three (P3.1+P3.2+P3.3) | 46/77 vs 42/77 | 0.63 |
| new ranking only (P3.2+P3.3) | 32/53 vs 27/53 | 0.43 |
| P3.3 only | 20/32 vs 19/32 | 1.0 |

No pooling shows significance. The conclusion stands: **learning benefit not shown, not ruled out.**

## Push audit

The audit's checks (no active hooks, Cursor hooks run on commit only, no pre-push) were done on another VM. Here: no `.git/hooks` other than samples, no `core.hooksPath`, no `push.*` config, no VS Code `git.postCommitCommand`/autofetch setting. Nothing on this machine pushes on commit either. Cause of the early push of `32ab41a1` remains unknown.

## Housekeeping found

- Commit `7baf640e` ("approved") had added `p33-seed.db-shm` and `-wal` sidecars (created by opening the committed seed for the eval re-run). Removed from git and ignored via `.gitignore`.
- The reduced-motion screenshot and the CodeQL SARIF named in the P3.3 notes live under `/opt/cursor/artifacts` on the other VM; that path does not exist here, so they could not be moved into the repo. The reduced-motion JSON records a console 404 that the notes do not mention.
- The real token database was backed up (`think-tokens.db.bak-pre-v2-20261002`) and migrated to schema v2 by restarting the :3000 server (4 rows kept, legacy ids preserved). The :3000 server is not running at the time of writing.
