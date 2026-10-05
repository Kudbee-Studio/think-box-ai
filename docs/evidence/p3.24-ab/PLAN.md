# P3.24 A/B pre-registration (written BEFORE any run)

Question: does a **real stored Think Token, retrieved by the existing recall**, make a small local model more correct and more grounded? And does the engine-run absence search (P3.24 step 1) fix what a lesson could not?

## Frozen inputs
- **Goals:** 30, defined in `apps/web/tests/helpers/ab-fixture.ts` (`AB_GOALS`), sha256 of ids+class+wording = `8f0526aee8b66d80325b917740213082b6815851d5bf544bc0f134d5e5421b6c`. 15 live-data lookups (5 facts x 3 new phrasings) and 15 repository goals (5 "find an untested function", 5 "which file defines CONSTANT", 5 "find a function that does not exist"). None reuses a wording from the earlier eval (`local-eval.ts`); a test enforces that. Goals are not edited after this file is committed.
- **World:** the deterministic fixture (fake GitHub + a small repository on disk), no network, 127.0.0.1 only.
- **Models:** `qwen2.5:3b` and `qwen2.5:1.5b` via local Ollama, temperature 0, fixed `seed = 1000 + goal index` (same seed for the same goal in every arm).
- **Tokens:** the accepted tokens in the real `apps/web/data/think-tokens.db` (copied, never modified), retrieved with `SqliteTokenStore.retrieve(goal, 3, { goalVector, embedModel })`: the hybrid BM25 + MiniLM cosine path the server uses, then injected with the server's `formatTokensForPrompt`. No hand-written lessons. The store's 15 accepted tokens were written by earlier runs about GitHub PR lookups, file listing and write_file; **none is about absence claims.** That is a property of the store, and it is reported, not fixed up.

## Arms
- **A** no token, engine absence search OFF (the behaviour before step 1).
- **B** retrieved tokens in the prompt, engine absence search OFF.
- **C** retrieved tokens in the prompt, engine absence search ON.

A and B differ only in the token text. B and C differ only in the engine, which only acts on repository findings that claim something is missing (so C = B in distribution on lookups; those runs are repeated, and agreement is reported as a determinism check).

## Outcome definitions (from `local-eval.ts` `scoreTrial`)
- **pass:** the loop finished, the result was GROUNDED by the validator, and the machine check of the fixture fact passed.
- **grounded:** finished and GROUNDED (pass or wrong). Reported separately because grounded-but-wrong is a different failure from ungrounded.
- Latency: wall time per goal; mean, p50, p95.

## Pre-registered decisions
1. **Learning benefit (primary):** for a model, "B is better than A" means ALL of: pass-rate difference B-A >= +10 percentage points; paired-bootstrap (10 000 resamples over goals, seed 20261005) 95% interval for B-A excludes 0; Fisher exact two-sided p < 0.025 (Bonferroni over the two models); grounded rate of B not lower than A by more than 5 points; p95 latency of B within 1.5x of A. Learning benefit is called **PROVEN** only if this holds for at least one model AND the other model's B-A is not negative with an interval excluding 0. Otherwise it stays **UNPROVEN**, and the report says so in those words.
2. **Testability guard:** if fewer than 50% of the 30 goals retrieve at least one token, B vs A is reported as "tokens rarely applied" and the primary result is UNPROVEN regardless of the numbers.
3. **Engine (secondary):** "C is better than B" on the repository "untested function" goals: pass-rate difference C-B >= +20 points with a bootstrap 95% interval excluding 0 and Fisher p < 0.025, and no increase in the count of ungrounded-but-reported claims that a human re-check (the fixture's ground truth) shows false.
4. Subgroups (lookup / repo; untested-function goals) are descriptive. They are not used to rescue a failed primary.
5. No trial is dropped, re-run or edited. A run that errors is recorded as `failed`. Raw per-trial rows are in `raw-<model>.jsonl` and the analysis is computed from them by `apps/web/tests/e2e/token-ab-report.ts` only.

## Known limits (stated now)
- 30 goals per arm gives wide intervals; only a large effect can clear the bar above.
- Synthetic fixtures, two small models, one retrieval method.
- The token store is not curated for these goals; a null result here shows only that **these stored tokens did not help these goals**, not that Think Tokens cannot help.
