# P3.77 security batch B (items 5 to 9 of 10)

| # | Item | State | Basis |
|---|---|---|---|
| 5 | Secret scanner as a gate step (`secrets`): tracked files and every commit, compared with a reviewed baseline | PROVEN | `tests/secret-scan.test.ts` (finds keys, private keys, assigned secrets; ignores placeholders, `skip_special_tokens`, `tokenId`; finds a secret removed in a later commit; baseline holds hashes, not secrets). Run on this repo: 115 tracked-file findings at first pass (mostly identifiers such as `skip_special_tokens`); after tightening, every remaining one is a test fixture or a doc, and 20 distinct fingerprints are baselined. |
| 6 | Dependency audit as a gate step (`audit`): high or critical fails; no report is `not_run`, never pass | PROVEN for the rules (`tests/dep-audit.test.ts`); UNPROVEN that it fails on a real vulnerable tree (this tree has 0 vulnerabilities, so only the parser was exercised) |
| 7 | WebSocket frame cap (1 MB, protocol level, close code 1009) and per-connection message limit (120 per 10 s) | PROVEN on the real server: `tests/security-b-integration.test.ts` (1.1 MB frame closes with 1009; 400 messages get "slow down"; a fresh connection is unaffected). Integration test was written after wiring, not before; unit tests for the limiter were first. |
| 8 | `kudbee doctor` (CLI, `/api/doctor`, Tools > Health check) | PROVEN offline checks on a clean and a dirty temp repo (`tests/doctor.test.ts`); network checks (`--online`) run once by hand on this repo: audit 0/0/0/0, 4 outdated packages. Offline mode says "skipped", never "ok". |
| 9 | Data folder private: server start sets umask 077 and chmods existing entries to 700/600 | PROVEN on the real server (data folder 700, runs.json 600, doctor reports ok). Symlinks are not followed (`tests/data-permissions.test.ts`). |

## Not claimed
- **Two real secrets are in git history and are only baselined, not removed or rotated**: an old Mercury key in `run_box_mercury.sh` (commit 6e7cf318) and the private key in `kilo-upcloud-recovered` (commit c62e50d1). The scanner now reports them as warnings. Rotating them is the founder's job; rewriting public history is not done.
- Pattern-based scanning misses unusual secret shapes; the baseline is a human judgement that these findings were looked at.
- The rate limit is per connection: a client can open many connections. No per-IP limit.
- `npm audit` needs the network; with no network the gate step is `not_run`, which fails the verdict (use `--skip audit` knowingly).
- The 1 MB cap applies to WebSocket frames only; HTTP bodies are covered by batch A.
- umask 077 applies to the whole server process, so files it creates elsewhere (workspaces, clones) are owner-only too.
