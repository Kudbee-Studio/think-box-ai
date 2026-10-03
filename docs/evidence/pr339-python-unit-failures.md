# PR #339: failing Python unit tests on `main`, fixed by root cause

Code head tested by the gates below: `bdcf3e4e`. The commits after it change only documentation (this file, the files it links, `AGENTS.md`, `docs/INDEX.md`).

#338's full run of `tests/unit` at its final code head, which is now `main`, had 172 failing tests. This PR groups them by root cause and fixes every cause that is not a founder decision. Each fix has a test that failed first; the commit messages carry the before and after runs.

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
| Power of 10 ratchet: 7 functions grew past 60 lines after its baseline (#280); #338 had made one of them, `_try_install_packages`, longer (67 to 76 lines) | 1 | `_try_install_packages` split into helpers (now under 60, helpers tested); 6 remain | `bdcf3e4e` |

`13752a04` corrects my #338 section in `AGENTS.md`, which said the `/stream` error detail goes to `logger.exception` (my first fix did that; the merged code logs only the type).

## Left failing: founder decisions

**KILO gate chain (count: see the full-suite section).** The first gate, PR #151 "post-season harden", requires `.github/workflows/test.yml` to contain `python3 -m unittest discover`, `verify_kilo_spine.py`, `pip install -e ".[lint]"`, `KILO_BEYOND_KILO_LINT_EXECUTE=1`, `verify_kilo_beyond_kilo_lint.py` and `scan_doc_secrets.py`. #308 removed those steps and the Python job ("easy to revert"). Every later gate requires the one before it, so the whole chain fails; #316's README rewrite also dropped the markers the PR #173 gate checks. One `spine_contract_summary()` takes 176.6 s under the profiler (`kilo-spine-profile.txt`): each gate re-evaluates every earlier gate without caching (`evaluate_live_smoke_evidence` runs 7,525 times for one summary), so the spine tests time out. Options: restore the six CI steps (a `.github/workflows/` change: founder token only, 0.1), retire the KILO gates and their tests, or leave them. This PR changes none of it.

**Power of 10 ratchet (1 test).** Six functions over 60 lines that are not in the baseline: `SSHCloudExecutionProvider.run` (81), `with_recovery` (92) and its `decorator` (72), `execute_governed_job_command` (64), `UpCloudSSHExecutionAdapter.execute` (125), `resume_queued_think_job` (74). Options: split them (a refactor PR) or add them to the baseline.

## Gates (AGENTS.md 0.1)

1. **Local checks.** `apps/web` is unchanged: `npm test` 549/549, `npm run typecheck` and `npm run lint` clean. Python: each changed module's test files on this branch (results in the commit messages) and the full suite below. `ruff` on the changed source files: same or fewer findings than `main` (`model_client.py` + `async_http.py`: 23 to 21); the test files gain only unittest-style notices (`PT009`, `PT027`) that every test in them already has.
2. **Local CI (`act`).** `test` / `web-typecheck` (the only workflow): green at `bdcf3e4e`: checkout, setup-node, `npm install`, typecheck, tests 549/549, skipped none (act 0.2.89, real clone with `origin` on GitHub). Log: `docs/evidence/ci-local/feat-pr339-p3-python-unit-failures-act.log`. There is no workflow for the Python tests.
3. **CodeQL against `main`.** Python, `python-code-scanning.qls` (CodeQL 2.27.1): `main` 17 alerts, this PR 17, **0 new**. One alert shows a new fingerprint: `py/path-injection` on `store_path.mkdir(...)` in `local_execution_adapter.py`, the same statement moved from line 93 into the `_upm_store` helper (line 68). It is the `job_id` finding #338 recorded (CodeQL does not model `validate_job_id` as a sanitizer). SARIF: `pr339-python-unit-failures/codeql-pr339-python.sarif`. JavaScript: no file under `apps/web` changed, so the #337 scan stands.
4. **Evidence.** This file and the PR body.
5. **Diff review.** No secrets, no `.db`/`.env` files; 0.4 guardrails intact. No route, schema or workflow changed; `jobs/schema.json` is a restored data file.

## Full Python unit suite, `main` and this PR

Pending: both runs (`pytest tests/unit --continue-on-collection-errors --timeout=60`, virtualenv activated; `main` `83424359` and this PR `bdcf3e4e`) are still running. This section and the KILO count are filled in before the PR leaves draft.

## Checks without mocks

- `thinkbox model check --provider ollama --base-url http://127.0.0.1:9` (nothing listening), real CLI: `main` prints `FAIL (33.14s): ... HTTP None: Connection error: [Errno 111] Connection refused`; this PR prints `FAIL (0.00s): ... unreachable at http://127.0.0.1:9/api/generate: ...` (`model-check-closed-port.txt`).
- `AsyncModelClient` against a local fake Ollama over a real socket: `generate` returns `144` on both; `stream` raises the `TypeError` on `main` and returns `144` here; `close` raises `AttributeError` on `main` and works here (`stream-close-real-socket.txt`).

## Four-state table

| Item | CODE | TEST | LIVE | PROD |
|---|---|---|---|---|
| Model client: fast failure, `close()`, `stream()` | complete | verified (mocked urlopen, plus a real socket and the real CLI) | UNPROVEN (no real model called) | UNPROVEN |
| Job schema, proof validation | complete | verified | n/a | UNPROVEN |
| Test-only fixes | complete | verified | n/a | n/a |
| Docs (index, padding removed, corrections) | complete | `test_docs_index.py` passes | n/a | n/a |
| KILO gate chain, 6 ratchet violations | not changed | still failing | n/a | founder decision |
| GitHub CI | | | | UNPROVEN (Actions billing-locked; no Python workflow exists) |

## Notes

- #338's full-suite comparison ran the virtualenv's Python without activating it, so tests that start `python3` used the system Python there. Both trees ran the same way, so its conclusion stands, but some of its absolute failure counts came from that. This PR's runs activate the virtualenv.
- Three `@unittest.expectedFailure` tests in `test_swarm_instrumentation.py` (dashboard pipeline rebuilt from storage) stay as they are: known gaps, marked so.
- `backend/api/v1/endpoints.py` has an inference endpoint that returns a made-up reply ("Placeholder"). Nothing imports or mounts it today; if it is ever mounted it must call the model client instead.
- `HttpResponse.aiter_lines` reads the whole body before yielding, so `stream()` delivers the reply at the end rather than token by token. Nothing calls `AsyncModelClient.stream()` outside tests today.
- 15 commits that change code, tests or docs, plus the evidence commit; the founder asked for about 20 per PR. I stopped at the real causes rather than split or pad them.
