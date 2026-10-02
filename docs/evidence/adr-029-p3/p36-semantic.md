# ADR 029 P3.6: semantic retrieval (2026-10-02)

Mercury spend: **$0**. The A/B was **not run**: the precondition (hit@3 of at least 7/10 on both held-out sets) was not met.

## What was built

- `think-token-embed.ts`: local sentence embeddings, CPU, no API key. Default `Xenova/all-MiniLM-L6-v2` (about 23 MB, quantized ONNX) through the optional dependency `@huggingface/transformers`; downloaded once from the Hugging Face hub, then used offline. If the package or model is unavailable the embedder is `null` and retrieval stays lexical.
- Schema v3: table `think_token_embeddings(token_id, model, dim, vector BLOB, text_sha256, created_at)`. No new database engine (ADR 026). Before a file database migrates, `VACUUM INTO <db>.bak-pre-v3-<date>` keeps a consistent copy (tested: the backup is the pre-migration state and passes `integrity_check`).
- Hybrid ranking in `retrieve()`: `relevance = 0.3 x BM25 + 0.5 x clamp((cosine - 0.15) / 0.5) + failure modes`, then the existing genericness factor, diversity and `(0.5 + score)`; frozen clock as before. The lexical ranker (0.6 x BM25 + failure modes) stays behind `THINKBOX_RETRIEVER=lexical` and is the fallback.
- The server embeds the goal (and any accepted lesson without a vector) before retrieval, but never waits for the model: it loads in the background (only when an accepted lesson exists) and goals are ranked lexically until it is ready. (A first version waited up to 20 s; the clean-worktree gate caught that it broke 7 integration tests, so it was changed.)
- The weights above were fixed in commit `adb35d5d` before either held-out set was run; nothing was tuned afterwards.

## Held-out results (frozen clock 2026-10-02T12:00:00Z, one run each)

Seed: the committed `p33-seed.db` (21 accepted lessons). Raw: `p36-eval-set1.json`, `p36-eval-set2.json`.

| Set | Ranker | hit@1 | hit@3 |
|---|---|---|---|
| Set 1 (the P3.5 paraphrased goals) | lexical (old) | 2 of 10 | 3 of 10 |
| Set 1 | **hybrid (new)** | 2 of 10 | **5 of 10** |
| Set 2 (10 new goals, 10 different lessons, marked first) | lexical (old) | 4 of 10 | 6 of 10 |
| Set 2 | **hybrid (new)** | **6 of 10** | **9 of 10** |

Both sets are improved by the hybrid ranker, but the bar for the A/B (hit@3 >= 7/10 on both) is **not met**: set 1 reaches 5 of 10. **Headline: semantic retrieval helps (hit@3 3 -> 5 and 6 -> 9) and is still not good enough on the harder set; no learning benefit is claimed or tested.**

## Reading it, honestly

- Set 2 is easier than set 1: 4 of its 10 target lessons are the unrelated "noise" topics (RSS, blockchain amounts, memory rules, site approval), which are far from the file-writing lessons, so even the lexical ranker finds 6 of 10. Set 1's lessons are all small variations on writing files, which is where retrieval is hard.
- Set 1 failures: `deep-mkdir`, `zero-byte`, `swap-the-letter`, `emoji-utf8` and `missing-no-invent` are not in the top 3 for either ranker. The embedding model is small; it separates topics better than it separates near-neighbor file-operation lessons.
- Goal wording was checked mechanically (a goal shares at most one distinctive word with its lesson, no path or quoted string); it is still one author's paraphrases, 10 goals per set, a single run each. Differences of one or two goals are within what rewording alone could change. Two small sets over 21 lessons are evidence of direction, not a benchmark.
- Not measured: query latency (the model loads in about 7 s on first use, then embeds in milliseconds), memory use, and behavior with a real accumulated token store rather than a 21-lesson seed.

## Four-state

| Item | CODE | TEST | LIVE | PROD |
|---|---|---|---|---|
| Local embeddings + vector BLOB table, backup before migration | yes | yes (6 hermetic tests incl. migration backup) | yes (real model loaded and used by the eval, 21 lessons embedded) | no |
| Hybrid ranker, lexical flag, frozen clock | yes | yes | yes (eval) | no |
| Server integration (non-blocking goal embedding) | yes | the existing server integration tests exercise the path with embeddings unavailable; none exercises a loaded model | not exercised in a live agent run | no |
| Held-out result | | | hit@3 5/10 and 9/10 | **UNPROVEN as a general result** |
| A/B with Mercury | not run | | | n/a |

## Operational notes

- The real token database (`apps/web/data/think-tokens.db`, schema v2) migrates to v3 the next time the server starts, with an automatic `.bak-pre-v3-<date>` copy beside it (gitignored via the existing `think-tokens.db*` ignore).
- `@huggingface/transformers` is an `optionalDependencies` entry; it pulls `onnxruntime-node` (about 550 MB on disk). `npm audit`: 0 vulnerabilities. Install scripts for `onnxruntime-node` are blocked by the npm install-scripts policy here and the library still loaded and ran.
