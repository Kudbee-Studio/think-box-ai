# ADR 029 P3.7: live check, lesson-side recall, set 3 (2026-10-02)

Mercury spend: about **$0.03** (21 retrieval-text calls, 3 live goals with extraction capped at 0). The A/B was **not run**: hit@3 is not at least 7/10 on all three sets (set 1 is 5/10).

## 1. Live check of the real server path (embeddings on)

Real `server.ts`, real Mercury worker, a copy of the P3.3 seed (21 accepted lessons), the model loaded in the background at start. Raw: `p37-live-semantic.json`; script `scripts/think-token-live-semantic.mjs`.

| Goal | Ranker used | Retrieval latency | Goal wall time |
|---|---|---|---|
| 1 (blank document) | **hybrid** (`Xenova/all-MiniLM-L6-v2`) | 161 ms (includes embedding the 21 lessons once) | 11.5 s |
| 2 (swap a letter) | **hybrid** | 24 ms | 2.0 s |
| 3 (digest of an unknown report) | **hybrid** | 13 ms | 1.1 s |

Server RSS: 221 MB before any goal, **258 MB peak** after the three goals (about +37 MB). The ranker was reported in the run's own thought stream (`Think Token ranking: hybrid (...) , N ms, 3 found`; it says `lexical (reason)` when the model is not ready, off, or there are no accepted lessons). The server starts loading the model at boot when accepted lessons exist; 30 s was waited before the first goal. Not measured: a cold start with an empty cache (about 7 s to download and load), many lessons, concurrent goals.

## 2. Why the five set-1 misses missed (written before any lesson-side change)

Measured on the P3.3 seed with plain cosine (rank of the right lesson, its cosine, the best competitor):

| Goal / lesson | What the numbers say | Cause | Fixable on the lesson side? |
|---|---|---|---|
| `three-levels-down` / deep-mkdir | cosine rank **1** (0.36), but not in the hybrid top 3 | the hybrid's extra terms (the failure-mode lexicon fires "missing file" on "does not exist yet"; BM25, genericness) pushed it out | **no**: ranker side |
| `blank-document` / zero-byte | cosine rank 3 (0.29 vs 0.31) | vocabulary: goal says blank/size, lesson says empty/bytes | yes |
| `swap-the-letter` / replace-not-append | cosine rank **1** (0.29, third 0.19), but not in the hybrid top 3 | same: ranker-side terms outweigh a good cosine | **no**: ranker side |
| `dartboard-size` / emoji-utf8 | cosine rank 2 (0.29 vs 0.30) | vocabulary (pictograph vs emoji) and a thin, example-bound lesson | yes |
| `digest-of-unknown-report` / missing-no-invent | cosine rank 4 (0.17 vs 0.31) | vocabulary (digest/uploaded vs summary/missing); the failure-mode lexicon does not know "not sure it was uploaded" | yes (partly) |

So only three of the five are lesson-side problems.

## 3. Lesson-side fix and results

`when_to_use`: one or two plain sentences, written by the extraction model (new lessons: asked for in the extraction prompt; older ones: `backfillRetrievalText`), stored beside the lesson (`think_token_retrieval_text`, schema v4, automatic backup on migration), embedded with it ("Useful when: ..."), never shown as the lesson and screened like lesson text. The generating model sees only the lesson. **No ranker weight was changed.** The prompt was written after seeing the misses, in general terms (synonyms, everyday words); that is a degree of in-sample design. `p37-seed.db` is the P3.3 seed plus this text for all 21 lessons (`p37-seed.when-to-use.json`).

Each set run once (frozen clock, no tuning), `p37-eval-set{1,2,3}.json`:

| Set | lexical hit@1 / hit@3 | hybrid, P3.6 seed (before) | **hybrid, P3.7 seed (after)** |
|---|---|---|---|
| 1 | 2 / 3 | 2 / 5 | **2 / 5** |
| 2 | 4 / 6 | 6 / 9 | **5 / 9** |
| 3 (new, real lessons only) | 2 / 3 | 4 / 6 (`p37-eval-set3-on-p33-seed.json`) | **4 / 7** |

The bar for the A/B (hit@3 >= 7/10 on all three) is **not met**: set 1 is still 5/10, with the same five misses. Lesson-side text moved set 3 by one goal (6 -> 7), left set 1 unchanged and cost set 2 one hit@1: within noise. **Headline: lesson-side text did not lift set-1 recall.**

Set 3 uses the 10 real lessons that sets 1 and 2 also used (all 16 real seed lessons were already in use), so it tests new wording over known lessons, not unseen lessons; goals were committed before any run.

## 4. The finding that matters: the ranker is the weak link

Diagnostic only (not a result, not used to tune anything): plain cosine ranking over the same seeds and sets (`p37-cosine-only-diagnostic.json`):

| | set 1 hit@1 / hit@3 | set 2 | set 3 |
|---|---|---|---|
| plain cosine, P3.3 seed | 6 / **8** | 7 / **10** | 7 / **9** |
| plain cosine, P3.7 seed (with `when_to_use`) | 5 / **8** | 8 / **10** | 8 / **10** |
| the hybrid ranker, P3.7 seed | 2 / 5 | 5 / 9 | 4 / 7 |

On all three sets the hybrid (BM25 + failure modes + genericness + quality + diversity + cosine) ranks **worse** than cosine alone, which already clears 7/10 hit@3 on every set. The extra terms were built for lexical matching and now mostly add noise. Changing the ranker was out of scope for this round, and picking cosine-only because it scores best on these three sets would be selecting on the test sets: it must be confirmed on a fresh, untouched set (and with the real accumulated lessons) before it is adopted. `when_to_use` helped plain cosine a little on sets 2 and 3 (hit@1 7 -> 8) and not on set 1 (6 -> 5): small and mixed.

## 5. Four-state

| Item | CODE | TEST | LIVE | PROD |
|---|---|---|---|---|
| Live server path with embeddings (hybrid used, latency, RAM) | yes | n/a | **yes** (3 goals) | no |
| `when_to_use` at extraction + backfill + schema v4 + backup | yes | yes (11 hermetic tests in this file group) | yes (21 lessons backfilled with Mercury) | no |
| Set-1 recall lifted | | | **no** (5/10 before and after) | UNPROVEN |
| Set 3 | | | hit@3 7/10 | UNPROVEN |
| A/B with Mercury | not run | | | n/a |

**UNPROVEN:** that any lesson-side change helps; that cosine-only (or any ranker) generalizes beyond these seeds and 30 goals; behavior on a real accumulated store.
