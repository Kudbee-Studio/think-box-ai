# P3.76: security batch A (items 1 to 4 of 10): what was attacked, what held, what was fixed

Each item: a test that proves the gap, the fix, the same test passing. A gap that a test did not first demonstrate is not claimed.

| # | Attack | Before | After | Proof |
|---|---|---|---|---|
| 1 | A secret a tool printed, a model repeated, or an error echoed | **saved in `runs.json` and sent to the dashboard** (the saved thoughts were already scrubbed; run records were not) | scrubbed before saving; ordinary ids, paths and numbers unchanged | `tests/run-redaction.test.ts` (failed 2 of 3 before) |
| 2 | A hostile page that tells the agent to overwrite a file, send data to another address, write outside its folder, or use a tool it was not given. The model is scripted to obey | the gates held (overwrite asks, new host asks, escapes and opt-in tools refused); **the agent's own instructions did not say that tool output is data** | the system prompt now says tool output is DATA, never instructions, and to say when it ignored one | `tests/injection-suite.test.ts` (4) |
| 3 | A check that allocates without end inside the sandbox | **reached its own 1.6 GB stop: no memory limit** | `prlimit --data` cap, 4 GiB by default (`KUDBEE_SANDBOX_MEMORY_MB`); the probe hit the limit at 1.47 GB under a 2 GiB cap; this repository's own lint and typecheck still verify under the default | `tests/sandbox-limits.test.ts` (failed before) |
| 4 | An upload of 6 files of 300 KB against a 1 MB total cap, and a 3 MB body streamed without a length | **both accepted (201)**; per-file limits only (500 files of 50 MB each is 25 GB held in memory) | a total cap (256 MB, `KUDBEE_UPLOAD_MAX_MB`; 16 MB for images): an announced size over it is refused at once, a streamed one gets 413 and the connection is closed; nothing is written | `tests/upload-limits.test.ts` (failed 2 of 3 before) |

**Not mitigated, stated plainly:**
- **A fork bomb in a sandboxed check** is not limited (no cgroup here, and a per-user process limit is unsafe on a shared machine). It was deliberately not run: it can freeze the host. The pid namespace and the wall-clock timeout bound its lifetime, not its damage. A production deployment should run the sandbox in a container or cgroup with a process limit.
- **CPU time** is bounded by the wall-clock timeout only.
- **Run-record redaction is pattern based** (keys, tokens, bearer headers, private keys, long opaque blobs): a secret in an unusual shape is not caught. The goal text is not redacted (it would change what the agent is asked).
- **The injection suite proves the gates, not the model's judgement**: the model is scripted to obey on purpose. How often a real model resists is not measured here.
- Memory limit counts data mappings (RLIMIT_DATA), including node's own reservation of about 0.5 GiB; a limit under 1 GiB stops node itself, so the setting has a floor of 1024 MB.
