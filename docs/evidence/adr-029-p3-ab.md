# ADR 029 P3 — A/B: do Think Tokens help real runs?

Date: 2026-10-02. Driver: [`scripts/think-token-ab-live.mjs`](../../scripts/think-token-ab-live.mjs). Raw rows: [`adr-029-p3/ab-result.json`](./adr-029-p3/ab-result.json).

**Headline: not shown. In this measurement retrieval made no measurable difference, and the sample is too small to detect a small one.**
An earlier draft of this PR (left in the working tree by a bot) reported "yes" from an offline simulator whose success rule was hard-coded to
favor the "on" arm. That simulator and its numbers were removed; nothing from it is cited anywhere.

## Method (nothing simulated)

- Two real `server.ts` instances, one per arm, on 127.0.0.1, each with its own copy of the same seed database (`VACUUM INTO` of the real token database:
  12 accepted, 5 candidate, 1 scored) and its own throwaway data and workspace directories.
- Arm **off**: `THINKBOX_TOKEN_RETRIEVAL=off`. Arm **on**: retrieval on (top 3 accepted tokens injected, ids cited). Both: `THINKBOX_TOKEN_MODEL_CALLS_PER_RUN=0`,
  so no run learns anything and both arms see an identical token set.
- Real model (Mercury 2 via the repo `.env` key, never printed), real WebSocket protocol, real tools. 6 goals x 2 arms x 2 repetitions = 24 runs.
  4 goals are file tasks that the seed tokens are about (`write_file` then verify); 2 are unrelated controls that need no tools.
- Per run, from the server's own run record: status, steps, tool calls, prompt and completion tokens, duration. Plus an objective check on the files the run left behind.

## Results

| Subset | Arm | Completed runs | Objective check passed | Tool calls (mean) | Steps (mean) | Prompt tokens (mean) | Completion tokens (mean) | Duration ms (mean) |
|---|---|---|---|---|---|---|---|---|
| 4 related goals | off | 8 of 8 | 8 | 2.13 | 5.25 | 4,904 | 408 | 2,981 |
| 4 related goals | on | 7 of 8 | 7 | 2.14 | 5.29 | 5,542 | 306 | 3,642 |
| 2 control goals | off | 4 of 4 | 4 | 0.00 | 1.00 | 1,377 | 63 | 1,113 |
| 2 control goals | on | 4 of 4 | 4 | 0.00 | 1.00 | 1,504 | 45 | 769 |

Means are over completed runs. The one non-completed run (arm on, `two-files`, repetition 1) died at once with a provider error,
`Inception API HTTP 503`, before taking any step: an infrastructure failure, not evidence about tokens (its repetition 2 completed and passed).

## Reading it

- Success: every completed run passed its objective check in both arms. With every run passing, success cannot discriminate between arms; the goals were too easy.
- Efficiency: tool calls and steps are the same on related goals (2.13 vs 2.14, 5.25 vs 5.29). Retrieval costs about 640 more prompt tokens per related run (the injected lessons).
  The "fewer completion tokens" and duration differences are within the spread between repetitions of the same goal (for example the same `notes` goal took 2.7 s and 8.7 s with retrieval off).
- Why no effect is unsurprising: the seed lessons are almost all one idea (write a file, then confirm it with `list_files`; most of the 13 model-written tokens), and the model already does that without being told.
- Sample: 24 runs, 2 repetitions per cell. This cannot detect a small improvement and does not show one exists. Tokens are **not** shown to help.

## What would make this a real test

Goals where the correct move is non-obvious without the lesson (a quirk of a specific tool or file format that the lesson records), a seed of lessons that are not near-duplicates, and enough repetitions to see the run-to-run spread.
The driver takes a seed database and a repetition count, so that is a data change, not a code change.

## Re-run

```bash
node scripts/think-token-ab-live.mjs <seed-think-tokens.db> out.json 2   # needs INCEPTION_API_KEY in the repo .env; about 1 minute
```
