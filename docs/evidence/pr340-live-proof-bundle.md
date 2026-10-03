# PR #340: Phase 3 items 4 + 3 — live-proof bundle builder and SSH hardening

**Status:** CODE COMPLETE / TEST VERIFIED for both item 4 (bundle tooling) and item 3 (SSH hardening).
The bundle from a real worker-02 run is **UNPROVEN**, and the newly pinned SSH path is **not
LIVE VERIFIED** — no real worker-02 run occurred. Not PRODUCTION READY.

This branch carries two related Phase 3 items:

- **Item 4** — redacting live-proof bundle builder + operator runner (below).
- **Item 3** — SSH host-key pinning and non-root user support (see "SSH hardening" section), folded
  in because it directly hardens the provenance of the bundle item 4 produces.

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

## SSH hardening (Phase 3 item 3)

Smallest change that gives a clear host-key boundary:

- `SSHWorkerConfig` gains `hardened: bool` and `known_hosts_path: str`.
- Hardened `_ssh_argv` emits `-o StrictHostKeyChecking=yes` and
  `-o UserKnownHostsFile=<path>`; it **never** emits `accept-new`.
- `SSHWorkerConfig.validate()` fails closed with a typed `InvalidSSHConfig` error
  (`reason: "hardened mode requires a known_hosts_path to pin the host key"`) when hardened mode is
  requested without a known_hosts source.
- `UpCloudSSHExecutionConfig.from_env` reads `UPCLOUD_SSH_HARDENED` (1/true/yes/on) and
  `UPCLOUD_SSH_KNOWN_HOSTS`; `is_complete()` returns False for hardened-without-known_hosts, so the
  adapter refuses to run.
- The SSH username stays parameterized (`UPCLOUD_SSH_USER`, default `root`). New `is_non_root()`
  makes the non-root expectation explicit; `root` is documented as a development default, not the
  recommended production configuration.
- No fingerprint handling was added; a trusted known_hosts file is sufficient for this phase.

## Tests

Item 4 — `python3 -m unittest tests.unit.test_live_proof_bundle` → **17/17 OK**.
Covers: valid run → verified bundle; hash mismatch refused; non-COMPLETED refused; unverified
receipt refused; wrong provider refused; secret in stdout refused; missing artifact refused;
absolute paths never survive; unknown artifact fields dropped; unknown remote host redacted;
missing checkpoint warns; JSON+Markdown writers; secret-scan patterns.

Item 3 — new focused tests in `test_cloud_execution_ssh_provider.py` and
`test_upcloud_ssh_execution_adapter.py`:

1. Hardened mode + known_hosts emits `StrictHostKeyChecking=yes` and the configured `UserKnownHostsFile`.
2. `accept-new` is absent from the hardened argv.
3. Hardened mode without known_hosts fails closed with the typed config error.
4. `UPCLOUD_SSH_USER=hermes` reaches the final SSH argv (`hermes@host`).
5. Non-hardened config still validates and keeps `accept-new` (existing behavior intact).
6. Common truthy values for `UPCLOUD_SSH_HARDENED` and `root` vs non-root classification.

Regression (item 3 + item 4 targeted set, excluding the fastapi-gated resume HTTP test which fails
to import in this environment on the pre-change baseline too):
**103/103 OK** across `test_cloud_execution_ssh_provider`, `test_upcloud_ssh_execution_adapter`,
`test_live_proof_bundle`, `test_remote_exec_policy`, `test_governed_execution_lifecycle`,
`test_lifecycle_harden`, `test_lifecycle_reclaim`.

**Mutation proof:** removing the hardened argv branch makes `test_hardened_argv_pins_host_key` and
`test_hardened_argv_never_uses_accept_new` fail (2 failures), so the pinning behavior is protected.

## Operator command (founder, once worker-02 SSH access is present)

```bash
cd ~/projects/think-box-ai
export UPCLOUD_SERVER_IP=209.50.51.174   # worker-02, NOT 212.147.250.183
export UPCLOUD_SSH_USER=hermes           # non-root preferred; `root` is a dev default
export UPCLOUD_SSH_KEY_PATH=/path/to/worker-02-key
export UPCLOUD_SSH_HARDENED=1
export UPCLOUD_SSH_KNOWN_HOSTS=/path/to/known_hosts   # required by hardened mode
python3 scripts/run_live_proof_bundle.py --command hostname
git add docs/evidence/live-proof/ && git commit -m "docs(evidence): live-proof bundle from worker-02"
```

Expected on success: a bundle JSON + Markdown whose `artifact.sha256` matches the receipt, stdout
`kudbee-hermes-worker-02`, exit 0, and no secret strings.

## Blockers (why the bundle and the pinned path are UNPROVEN here)

- `UPCLOUD_SERVER_IP=212.147.250.183` / `UPCLOUD_SERVER_HOSTNAME=kudbee-host-v1` is the **historical
  dead host** (AGENTS.md "Case C"), not worker-02 (`209.50.51.174`). It was not touched.
- `UPCLOUD_SSH_KEY_PATH=~/.ssh/kilo-upcloud` **does not exist**; the recovered key was purged in
  PR #271 and must not be reintroduced. No key was invented or fabricated.
- No live UpCloud execution or live credentials were used for this PR.

The runner confirms this honestly:

```
$ python3 scripts/run_live_proof_bundle.py --command hostname --dry-run
{"ok":false,"error":"upcloud-ssh not configured","required":["UPCLOUD_SERVER_IP set to the
worker-02 address","UPCLOUD_SSH_KEY_PATH existing file"],"hardened":false, ...}
```

## Four-state

| State | Item 4 bundle tooling | Item 3 SSH hardening | Real worker-02 pinned path |
|-------|----------------------|----------------------|----------------------------|
| CODE COMPLETE | yes | yes | n/a |
| TEST VERIFIED | yes (17/17) | yes (focused + 103/103 regression) | n/a |
| LIVE VERIFIED | **no** | **no** | **UNPROVEN** |
| PRODUCTION READY | **no** | **no** | **no** |
