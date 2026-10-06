# Scratch runner: design, threat model and the slices to come

Status: slice 1 built (PR #377). Slices 2 to 5 are planned here and **not built**; each needs its own PR, its own evidence and, where it widens what the agent can do, the founder's explicit go-ahead.

## Why

The agent can read the repository and, since #371, escalate a hard investigation to Mercury. It cannot yet **verify a change**. The Mayor already refuses `SIMULATE` and `AUTONOMOUS` convoys with "it needs a scratch workspace and a test runner" (`mayor.ts`). This is that test runner. A proposed change is worth something only if the repository's own checks pass on it, run somewhere that cannot hurt the founder's machine, tree or credentials.

## What slice 1 builds (`apps/web/scratch-runner.ts`)

`runScratch({ repoRoot, ref, patch?, checks })` returns a report: the commit it ran, the patch hash and what the patch touches, the sandbox attestation, each check's exit code, duration, output tail and test counts, and `verified`.

| Step | What happens |
|---|---|
| 1. Pick a commit | `ref` must be a commit, branch or tag of the **local** repository (`git rev-parse --verify ref^{commit}`; a leading `-`, `..` or odd characters are refused). The working tree is never used: uncommitted work, `.env` and local files are not in the copy. |
| 2. Copy | `git archive` of that one commit, unpacked into a fresh temp directory, re-initialised as a new local git repository with **no remote** (so tests that look at git work and nothing can be pushed). |
| 3. Patch (optional) | A unified git diff, reviewed first (below), checked with `git apply --check`, applied to the **copy only**. |
| 4. Check | Only a **named** check runs: `lint`, `typecheck`, `tsc`, `test` (the repo's own `npm run` scripts) or `test_file tests/<name>.test.ts`. There is no way to pass a command string. |
| 5. Sandbox | Every check runs inside bubblewrap (below). |
| 6. Clean up | The temp directory is always removed. |
| 7. Verdict | `verified` is true only if every requested check ran to exit 0 inside the proven sandbox. A check that did not run is not a pass. |

## Guarantees and how each is enforced and tested

| Guarantee | Enforced by | Tested by |
|---|---|---|
| No network except a private loopback | `bwrap --unshare-all` (own network namespace); the tests' own servers on 127.0.0.1 still work inside | probe from inside; a check that tries the internet and a real **host** loopback server (both blocked) while its own loopback server works |
| No host files | only `/usr /lib /lib64 /bin`, node's install and the work copy are mounted; `$HOME` contents are not | a canary file on the host is unreadable from inside; the probe lists the host home from inside |
| System and dependencies cannot be modified | read-only binds; `node_modules` is mounted read-only from the installed copy | writes to `/usr` and `node_modules` fail from inside |
| No credentials | `--clearenv` then a fixed list of variables (`PATH`, `HOME=/tmp/home`, `CI`, ...); nothing inherited | a canary key and `INCEPTION_API_KEY` set on the host never appear inside; the list is asserted in a unit test |
| Writes stay in the copy | only the work copy is bound writable | what a check wrote is absent from the real repository; the repository's `HEAD`, status and ignored files are hashed before and after |
| A runaway check ends | process-group kill at a timeout, a private pid namespace that dies with its parent, `prlimit --fsize` on any one file, output kept to a 60 KB tail | a never-ending check is killed; a 400 KB-loud check is capped and says so |
| One run at a time | a queue | two concurrent runs both finish |
| No unsandboxed fallback | `probeSandbox()` proves the properties from inside before the first run; if it cannot, `runScratch` throws and nothing runs | mutation checks: weakening `--unshare-all`, `--clearenv` or the read-only dependency bind makes tests fail |

### Patch policy (`reviewPatch`, pure)

A patch is refused if it is empty, over 200,000 characters, contains NUL, is not a git diff, is binary, creates a symlink, names no file or more than 50, or names a path that escapes the repository, is absolute, is a secret (`.env`, keys, `.db`, anything with "secret" or "credential" in its name), is inside `.git`, `node_modules`, `data` or other excluded folders, or is not source text. Both sides of a rename or copy are checked.

Two things are **flagged, not refused**, and a later approval prompt must show them: `touches_tests` (a patch that edits the tests that judge it can make a broken change look green) and `touches_ci_or_gates` (`.github/`, `gates.ts`, `package.json`, `tsconfig`, coverage config). `deletes_files` is flagged too.

## What slice 1 does not do

It is not wired into the agent, the server, the dashboard or the Mayor: nothing calls it yet except its tests and `npm run test:live-scratch`. It does not fetch from GitHub (it exports a commit that is already in the local repository, so a stale local `main` is a stale copy; the report names the sha). It does not push, open a pull request, merge, write to the real tree, read a key, or run a model. It is Linux with bubblewrap only; anywhere else it refuses to run.

## Residual risks (stated, not hidden)

- **Sandbox escape.** bubblewrap relies on the kernel's namespaces. A kernel bug could defeat it. Mitigation: it runs as the unprivileged user, has no credentials or network inside, and the probe refuses to run if a property is missing.
- **CPU and disk.** Memory is not limited (a Node address-space limit breaks Node). A check can use CPU and fill the temp directory until its timeout or the 256 MB per-file limit. Bounded by the timeout; a later slice should add a disk watchdog.
- **Trusted dependencies.** The installed `node_modules` are trusted as they are on the founder's machine; a compromised dependency would run, but without network, credentials or any writable host path.
- **Reward hacking.** A change may edit the tests or gates to pass. It is flagged in the report; judging whether the edit is legitimate stays with the human reviewer.
- **Checks prove less than they seem.** A green run means the repository's own checks pass on the copy. It is not proof the change is correct.

## Slices still to come (each its own PR, in this order)

2. **Governed tool.** `run_checks` as a tool with `exec` permission, through `runGovernedTool`: the approval prompt shows the commit, the check names, the files the patch touches and its flags; never auto-approved; a run record with the full report; the grounding rule that a model may only say "verified" for a report whose `verified` is true. Needs the founder's go-ahead because it makes execution reachable from the agent.
3. **SIMULATE convoy mode.** The Mayor plans a worker that proposes a patch (Mercury, since a 3B local model cannot, see P3.33 to P3.35) and a worker that runs the checks; the human approves the plan once, and the runner is called only with that approval.
4. **Draft pull request.** Fetch from GitHub and open a **draft** PR from a branch, with the report as the body; never ready, never merged by the agent. Needs credentials only the founder holds and a separate explicit approval each time. The founder's `origin` remote currently points at GitLab, so this also needs a decision about which remote is the source of truth.
5. **A write-capable loop** that iterates propose, verify, revise within the budget and the spend cap. Last, and only once 2 to 4 have live evidence.

## Decisions this design records

| Question put to the founder | Answer built in slice 1 |
|---|---|
| May it clone to a temporary directory? | Yes, an export of a local commit into a temp directory, removed after every run. No fetch from GitHub yet. |
| May it run the repository's own test commands there? | Yes, only the named checks above, only inside the proven sandbox, with no network or credentials. |
| May it only ever open draft PRs? | Not built. Slice 4 is draft-only by design, with separate approval and founder-held credentials. |
