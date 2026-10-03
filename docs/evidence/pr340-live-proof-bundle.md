# PR #340: Phase 3 item 4 — redacting live-proof bundle builder

**Status:** CODE COMPLETE / TEST VERIFIED. The bundle from a real worker-02 run is **UNPROVEN** —
it could not be produced in this worktree (see Blockers). Not LIVE VERIFIED, not PRODUCTION READY.

## What this changes

Phase 3 item 4 asks for a committed, redacted receipt/artifact/checkpoint from a real governed
`upcloud-ssh` run so LIVE VERIFIED claims are independently checkable. This PR ships the tooling
that turns a raw run into that safe bundle, and the one-command operator runner that performs the
run. The raw files themselves are git-ignored under `.thinkbox/`; only the redacted bundle is
committed under `docs/evidence/live-proof/`.

| File | Purpose |
|------|---------|
| `thinkbox/live_proof_bundle.py` | Validates raw artifact/receipt/checkpoint, redacts, re-hashes, refuses secrets, writes bundle JSON + Markdown |
| `scripts/run_live_proof_bundle.py` | Operator CLI: runs one exactly-allowed read-only command via `UpCloudSSHExecutionAdapter`, then builds the bundle |
| `tests/unit/test_live_proof_bundle.py` | 17 hermetic tests |

No new execution path, endpoint, or dependency. The runner reuses the committed
`UpCloudSSHExecutionAdapter` from PR #282 and the six-command allow-list from `remote_exec_policy`.

## Fail-closed checks

`build_live_proof_bundle` refuses to emit unless **all** hold:

1. `_sha256_file(artifact) == receipt.artifact_hash` (tamper detection on the artifact).
2. `receipt.status == "COMPLETED"` and `receipt.verified is True`.
3. artifact provider is `upcloud-ssh`.
4. No private-key block, bearer token, API key, Upstash token or `.ssh/` path anywhere in the bundle.
5. No forbidden-key field survives (absolute `path`, `artifact_path`, `receipt_path`, `remote_user`, …).
6. Only an artifact-field allow-list is copied; unknown fields are dropped.

## Tests

`python3 -m unittest tests.unit.test_live_proof_bundle` → **17/17 OK**.

Covers: valid run → verified bundle; hash mismatch refused; non-COMPLETED refused; unverified
receipt refused; wrong provider refused; secret in stdout refused; missing artifact refused;
absolute paths never survive; unknown artifact fields dropped; unknown remote host redacted;
missing checkpoint warns; JSON+Markdown writers; secret-scan patterns.

Related regression (`test_cloud_execution_ssh_provider`, `test_upcloud_ssh_execution_adapter`):
**40/40 OK**.

## Operator command (founder, once worker-02 SSH access is present)

```bash
cd ~/projects/think-box-ai
export UPCLOUD_SERVER_IP=209.50.51.174   # worker-02, NOT 212.147.250.183
export UPCLOUD_SSH_USER=root
export UPCLOUD_SSH_KEY_PATH=/path/to/worker-02-key
python3 scripts/run_live_proof_bundle.py --command hostname
git add docs/evidence/live-proof/ && git commit -m "docs(evidence): live-proof bundle from worker-02"
```

Expected on success: a bundle JSON + Markdown whose `artifact.sha256` matches the receipt, stdout
`kudbee-hermes-worker-02`, exit 0, and no secret strings.

## Blockers (why the bundle is UNPROVEN here)

- `UPCLOUD_SERVER_IP=212.147.250.183` / `UPCLOUD_SERVER_HOSTNAME=kudbee-host-v1` is the **historical
  dead host** (AGENTS.md "Case C"), not worker-02 (`209.50.51.174`).
- `UPCLOUD_SSH_KEY_PATH=~/.ssh/kilo-upcloud` **does not exist**; the recovered key was purged in
  PR #271 and must not be reintroduced.

The runner confirms this honestly:

```
$ python3 scripts/run_live_proof_bundle.py --command hostname --dry-run
{"ok":false,"error":"upcloud-ssh not configured","required":["UPCLOUD_SERVER_IP set to the
worker-02 address","UPCLOUD_SSH_KEY_PATH existing file"], ...}
```

## Four-state

| State | This PR |
|-------|---------|
| CODE COMPLETE | yes (bundler + runner + tests) |
| TEST VERIFIED | yes (17/17 hermetic) |
| LIVE VERIFIED | **no** — no real worker-02 run in this worktree |
| PRODUCTION READY | **no** |
