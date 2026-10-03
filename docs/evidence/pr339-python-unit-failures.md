# PR #339: failing Python unit tests on `main`, fixed by root cause

Code head tested by the gates below: `29457c3b`. The commits after it change only documentation (this file, the files it links, `AGENTS.md`, `docs/INDEX.md`).

#338's full run of `tests/unit` at its final code head, which is now `main`, had 172 failing tests. This PR groups them by root cause and fixes every cause outside the KILO gate chain and the Power of 10 ratchet (the next two PRs). Each fix has a test that failed first; the commit messages carry the before and after runs.

## Root causes and fixes

| Root cause | Tests failing on `main` | Fix | Commit |
|---|---|---|---|
| The model client retried a refused connection with 2 + 4 + 8 + 16 s of backoff: `HttpConnectionError` subclasses `HttpError`, so the transient branch caught it and the connection branch was dead. Every call to a stopped Ollama took about 30 s, and the error came back retryable | the engine and CLI tests that hit the timeout, plus `test_unreachable_raises_non_retryable` | refused connection: raised at once, non-retryable, `unreachable at <url>`; transient statuses and timeouts keep the backoff; the message no longer doubles `HTTP 500: HTTP 500` | `c5956323` |
| `AsyncModelClient.close()` awaited `aclose()`, which the stdlib `AsyncHttpClient` does not have | 13 (10 swarm integration, 3 connection pool) | calls `close()` | `ec961061` |
| `AsyncHttpClient.stream` was `async def`, so `async with client.stream(...)` raised `TypeError`: `AsyncModelClient.stream()` failed on every call | none (no test) | plain method; 4 new stream tests | `32b7ab52` |
| urlopen mocks without `.status` (the client reads it) | 7 | the mock has `status = 200`, like a real response | `a2415cac` |
| `ModelCallError` not imported in `test_provider_pool.py` | 1 | import | `154cf955` |
| `jobs/schema.json` never reached `main` (its history starts at #264); `test_jobs.py` looked in `tests/jobs/` | 4 | schema restored unchanged from `8932f62c`; test reads the repository's `jobs/` | `2e5fe6c4` |
| Box route tests expected `/status`; FastAPI puts the router prefix into the path | 2 | tests check `/think/box-status/status`, `/think/box-mercury/status`, `/think/box-mercury/results` (200 in the real app; `/think/box-status` is 404) | `18fb84ea` |
| `test_aggregate_layer_telemetry_deterministic` sat at module level with `self`: unittest never collected it, pytest failed at setup. Moved into its class it failed: it unpacked a per-goal tuple from a variant (`8c089431`) that never reached `main` | 1 | checks the function `main` has (one list, as both callers use it) | `d0985795` |
| The dry-run tests started `python3` from `PATH` (without the virtualenv: no fastapi) | 2 | `sys.executable`; the demo script gets that interpreter first on `PATH` | `84a7448c` |
| #253 labeled 14 swarm proofs `partial_run` so they validate; #280 added a test that one of them must fail validation. The real gap: the same proof without the label also validated | 1 | `validate_proof_document` rejects an unlabeled validator skip; the test checks both halves; 38/38 committed proofs still validate | `81412b80` |
| `docs/INDEX.md` stale (two of the missing files were my #337/#338 evidence) | 1 | regenerated, after removing five padding files from #333 to #335 (`7dee1831`) and adding correction notes to the #333/#334 evidence (`62b8e250`) | `59ad479a` |
| Power of 10 ratchet: 7 functions grew past 60 lines after its baseline (#280); #338 had made one of them, `_try_install_packages`, longer (67 to 76 lines) | 1 | `_try_install_packages` split into helpers (now under 60, helpers tested); 6 remain, next PR | `bdcf3e4e` |
| **A real race, found as a flaky test** (`test_concurrent_resume_single_claim`, about 1 run in 6). `open_lifecycle_repo()` returns a new `Repository` per call, so racing workers share no lock; `_save_job` used `write_text`, which truncates first, so a concurrent reader saw an empty file and `_load_job` reported "no such job"; `persist_lifecycle_phase` then re-created the job, erasing its transitions; the compare-and-set in `update_job` was check-then-write with nothing shared between instances | 1 (flaky) | atomic writes (temp file, `fsync`, `os.replace`) for job, worktree-metadata and checkpoint files; `_exclusive_jobs`: the instance lock plus an `flock` on `.thinkbox/jobs/.lock` (gitignored), re-entrant per instance because `flock` is per open file description, around every job read-modify-write; `ensure_job`, an atomic get-or-create; the compare-and-set stays in `update_job`. Job files are now `0600` | tests `e583fba9`, fix `29457c3b` |

`13752a04` corrects my #338 section in `AGENTS.md`, which said the `/stream` error detail goes to `logger.exception` (my first fix did that; the merged code logs only the type).

### The race, measured (`repository-race-proof.txt`)

Six workers per round, each with its own `Repository`, racing to resume one queued job through `resume_queued_job`, with an observer reading the job file throughout; 100 rounds, same script on both trees.

| | `main` | the fix |
|---|---|---|
| rounds with exactly one execution | 99 of 100 | 100 of 100 |
| a round that executed nothing | 1 | 0 |
| jobs unloadable afterwards | 4 | 0 |
| worker crashes (`FileNotFoundError`, `LifecycleError`) | 2 | 0 |
| observer reads that found no job | 862 of 18,322 | 0 of 17,336 |
| claims recorded per job | 1 for 96 jobs, none for 4 | 1 for all 100 |

At the repository level the compare-and-set let up to **6 of 6** instances win one claim (`claimed by [3, 2, 4, 5, 0, 1]`). A double execution through `resume_queued_job` was **not** observed on `main` in these 100 rounds; what was observed is lost jobs, no execution, crashes and empty reads. The originally flaky test passes 40 of 40 runs. A mutation check: without the re-entrancy guard `ensure_job` deadlocks (its test times out), so the guard is load-bearing. Tests: `tests/unit/test_repository_concurrency.py` (4) and a 4-worker x 15-round test in `test_lifecycle_resume.py`; all 5 fail on `main` and pass with the fix.

## Not in this PR

**KILO gate chain: the next PR (#340).** With this PR the spine tests still time out on `main`'s code (one `spine_contract_summary()` makes 376,591 gate-function executions for 176 distinct ones and takes 120 to 200 s; `kilo-spine-profile.txt`), which is also what crashed pytest in #338's and this PR's first full runs. #340 evaluates each gate once per call, finds the single root cause behind the chain (the CI-workflow manifest that #308 made untrue), and fixes the lint lane and README checks that the timeouts were hiding.

**Power of 10 ratchet (1 test): the PR after that.** Six functions over 60 lines that are not in the baseline: `SSHCloudExecutionProvider.run` (81), `with_recovery` (92) and its `decorator` (72), `execute_governed_job_command` (64), `UpCloudSSHExecutionAdapter.execute` (125), `resume_queued_think_job` (74).

## Gates (AGENTS.md 0.1)

1. **Local checks.** `apps/web` is unchanged: `npm test` 549/549, `npm run typecheck` and `npm run lint` clean. Python: the full suite below. `ruff` on the changed source files: `model_client.py` + `async_http.py` 23 to 21 findings, `repository.py` 2 to 2, `governed_execution_lifecycle.py` 0 to 0; the test files gain only unittest-style notices (`PT009`, `PT027`) that every test in them already has.
2. **Local CI (`act`).** `test` / `web-typecheck` (the only workflow): green at `bdcf3e4e`: checkout, setup-node, `npm install`, typecheck, tests 549/549, skipped none (act 0.2.89, real clone with `origin` on GitHub). Log: `docs/evidence/ci-local/feat-pr339-p3-python-unit-failures-act.log`. Every commit since changes Python, tests or docs only, so that job's inputs are unchanged. There is no workflow for the Python tests.
3. **CodeQL against `main`.** Python, `python-code-scanning.qls` (CodeQL 2.27.1), run at the final code head `29457c3b`: `main` 17 alerts, this PR 17, **0 new**. One alert shows a new fingerprint: `py/path-injection` on `store_path.mkdir(...)` in `local_execution_adapter.py`, the same statement moved from line 93 into the `_upm_store` helper (line 68). It is the `job_id` finding #338 recorded (CodeQL does not model `validate_job_id` as a sanitizer). The atomic-write and lock code in `repository.py` adds none. SARIF: `pr339-python-unit-failures/codeql-pr339-python.sarif`. JavaScript: no file under `apps/web` changed, so the #337 scan stands.
4. **Evidence.** This file and the PR body.
5. **Diff review.** No secrets, no `.db`/`.env` files; 0.4 guardrails intact. No route or workflow changed; `jobs/schema.json` is a restored data file; `Repository` job files are written `0600` and a gitignored `.thinkbox/jobs/.lock` appears next to them.

## Full Python unit suite, `main` and this PR

`pytest tests/unit` could not be run as one process on either tree: the slow KILO spine tests hit `pytest-timeout`, and when its signal lands in a certain place Python 3.11 hands pytest a traceback frame with no line number, so pytest dies with `INTERNALERROR` (`TypeError ... NoneType - int`) at about 39%, every test after it unrun (it happened to both trees in the first run of this PR; `main`'s earlier crashes in #338 were the same). The suite is therefore run in two groups, virtualenv activated, `--timeout=60`:

**Group 1: the 276 files that do not mention KILO** (`nonkilo-main-failing.txt`, `nonkilo-final-failing.txt`)

| | `main` `83424359` | this PR `29457c3b` |
|---|---|---|
| tests | 3,804 | 3,817 |
| passed | 3,756 | 3,812 |
| failed or errored | 43 failed, 1 error | **1 failed**: the Power of 10 ratchet |
| wall time | 26 min 13 s | 62 s |

**Group 2: the 106 files that mention KILO**, one pytest process per file, 20 s per test so a crash costs one file (`kilo-group-main-vs-339.txt`)

| | `main` | this PR |
|---|---|---|
| tests | 829 | 839 |
| passed | 719 | 727 |
| failed | 62 | 61 |
| timed out | 48 | 51 |

Of the 827 tests in both runs exactly one changed status (`test_swarm_stats::test_validator_wave_skip_is_detected`, failed to passed). **No test went from passing to failing.** The timeouts are the spine tests, unchanged by this PR; the rest of the KILO failures are the chain described above.

## Checks without mocks

- `thinkbox model check --provider ollama --base-url http://127.0.0.1:9` (nothing listening), real CLI: `main` prints `FAIL (33.14s): ... HTTP None: Connection error: [Errno 111] Connection refused`; this PR prints `FAIL (0.00s): ... unreachable at http://127.0.0.1:9/api/generate: ...` (`model-check-closed-port.txt`).
- `AsyncModelClient` against a local fake Ollama over a real socket: `generate` returns `144` on both; `stream` raises the `TypeError` on `main` and returns `144` here; `close` raises `AttributeError` on `main` and works here (`stream-close-real-socket.txt`).
- The race: 100 rounds of 6 workers through the real resume path, table above.

## Four-state table

| Item | CODE | TEST | LIVE | PROD |
|---|---|---|---|---|
| Model client: fast failure, `close()`, `stream()` | complete | verified (mocked urlopen, plus a real socket and the real CLI) | UNPROVEN (no real model called) | UNPROVEN |
| Repository: atomic job files, one claim across instances | complete | verified (stress tests, plus 100 rounds x 6 workers through `resume_queued_job`) | n/a (no live infrastructure involved) | UNPROVEN (single machine, local filesystem; `flock` is absent on Windows, where only threads of one process are serialized) |
| Job schema, proof validation | complete | verified | n/a | UNPROVEN |
| Test-only fixes | complete | verified | n/a | n/a |
| Docs (index, padding removed, corrections) | complete | `test_docs_index.py` passes | n/a | n/a |
| KILO gate chain, 6 ratchet violations | not changed here | still failing | n/a | next PRs |
| GitHub CI | | | | UNPROVEN (Actions billing-locked; no Python workflow exists) |

## Notes

- #338's full-suite comparison ran the virtualenv's Python without activating it, so tests that start `python3` used the system Python there. Both trees ran the same way, so its conclusion stands, but some of its absolute failure counts came from that. This PR's runs activate the virtualenv.
- Three `@unittest.expectedFailure` tests in `test_swarm_instrumentation.py` (dashboard pipeline rebuilt from storage) stay as they are: known gaps, marked so.
- `backend/api/v1/endpoints.py` has an inference endpoint that returns a made-up reply ("Placeholder"). Nothing imports or mounts it today; if it is ever mounted it must call the model client instead.
- `HttpResponse.aiter_lines` reads the whole body before yielding, so `stream()` delivers the reply at the end rather than token by token. Nothing calls `AsyncModelClient.stream()` outside tests today.
- My first version of the repository lock deadlocked: `ensure_job` calls `create_job`, both took the lock, and `flock` blocks a second `open` of the same file in the same process. Found in self-review before the first run, then pinned by a mutation check.
- 18 commits that change code, tests or docs, plus this evidence commit; the founder asked for about 20 per PR. I stopped at the real causes rather than split or pad them.
