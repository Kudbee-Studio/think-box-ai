# P3.37 true counts: live verification criteria (written BEFORE the run)

What changed: `live_lookup` for `open_issues` and `open_prs` now makes a second read-only request to GitHub's search endpoint for the exact total; the facts state it; the grounding validator accepts a count only when it equals that total (or is hedged as "the N most recent"); a "no open issues" denial is rejected when the total says otherwise. Branches have no cheap exact count in a body-only reply and are unchanged (a count of branches from the first page is still refused).

## Live check (real GitHub, read-only; real Ollama; no Mercury)
1. **Total equals an independent count.** For `Kudbee-Studio/think-box-ai`, the `total` from the live tool equals the count obtained independently through the authenticated `gh` CLI by paginating the REST list (`/issues?state=open` minus pull requests; `/pulls?state=open`). The two reads are made within seconds of each other; a mismatch is reported as such (a repository can change between reads).
2. **No wrong count is shown as verified.** For each of `gemma3:4b` and `qwen2.5:3b` and each of the questions "How many issues are open?", "How many pull requests are open?", "How many branches are there?": run the governed local loop (`live_lookup`, the shared validator). Record the answer, the verdict and whether a stated count equals the independent total. Criterion: any GROUNDED answer to the issue or PR question states the true total, and no GROUNDED answer to the branch question states a count (there is no total for branches; the honest outcomes are a refusal, a hedge, or no number).
3. **Reported, not required:** how often each model produces a grounded correct count (a model that words the data badly is refused by the validator, which is the safe outcome).

## Known limits (stated now)
- One repository, three questions, two models, one run each. This verifies the mechanism against real data, not the models' reliability.
- GitHub's unauthenticated search endpoint is rate limited (10 per minute); a rate-limited count is "unknown" and the list-only behaviour applies, which the run records.
- Branches are not covered by this change.
