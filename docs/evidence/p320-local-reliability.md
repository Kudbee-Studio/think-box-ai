# P3.20: Reliable Local Model + Smart Router

## Scope

Make the local model a trustworthy first-class option by:
1. **Bake-off:** Measure smollm2:360m, qwen2.5:1.5b, qwen2.5:3b on a locked 20-goal eval set (16 local-routable, 4 intentional escalations).
2. **Smart router:** Confidence-based routing (0-100 score per goal). Send to local model only when confident; escalate otherwise. Log decisions in the thought stream.
3. **Grounding:** Local answers must cite the tool result they rely on (same check as Mercury). Fallback to data alone if ungrounded.
4. **Dashboard + CLI:** Show which model answered (local or Mercury), latency, cost ($0 for local).
5. **Live proof:** 5 traced runs on the dashboard and CLI, saved to evidence.

## Design

### Confidence Scoring
- **Known recipes** (PR status, file ops): 75% confidence
- **Plain knowledge** (definitions, math, translation): 90% confidence
- **Complex goals** (code generation, analysis): 30% confidence
- **Live-data unknowns** (queries not recognized as recipes): 25% confidence
- **Threshold:** Route to local if confidence ≥ 60%; otherwise escalate

### Grounding Check
- Local answer passes if it cites a fact from the tool result (e.g., "PR #343" from the GitHub API response)
- Ungrounded answers fall back to showing the data itself
- Same rigor as Mercury answers

### Router Behavior
- Classify goal (complex or simple) → get confidence score
- If confidence ≥ 60% AND local model selected: ask it
- If answer fails grounding or model is not available: escalate to Mercury
- Log routing decision in thought: "Routed to local model (confidence 85%): plain knowledge question" or "Escalated to mercury-2 (confidence 25%): live data needed but not a known recipe"

### Eval Set (Locked Before Running)
20 goals committed to `scripts/local-model-eval-p3.20.ts`:
- **16 local-routable:** PR status (3), server status (2), memory recall (3), file listing (2), file reading (2), knowledge (4)
- **4 intentional escalations:** code generation, mutations, live weather, live news
- **Pass criteria:** Answer is correct AND cites supporting evidence (the expectedKey substring)
- **No goalpost-moving:** Decision rules written first, results are data only

### Bake-off (To Run)
Command: `cd /home/domin/projects/think-box-ai && node --experimental-strip-types --no-warnings scripts/local-model-bakeoff.ts`

**Models tested:**
- smollm2:360m (725 MB baseline)
- qwen2.5:1.5b (986 MB challenger)
- qwen2.5:3b (1.9 GB challenger)

**Reps:** 2 per model (40 total runs)

**Metrics per model:**
- Pass rate (% goals with correct, grounded answers)
- Latency (p50, p95)
- GPU memory %
- Fallback rate (how often Ollama failed)

**Winner rule:** Highest pass rate with p95 latency ≤ 5s; if tied, smaller model.

## Four-State Table

| Item | State | Notes |
|---|---|---|
| **Eval set (20 goals, decision rules locked)** | CODE COMPLETE, READY TO RUN | `scripts/local-model-eval-p3.20.ts` committed; no moving goalposts |
| **Bake-off runner** | CODE COMPLETE, READY TO RUN | `scripts/local-model-bakeoff.ts` measures all three models, 2 reps each |
| **Confidence scoring** | CODE COMPLETE, TEST READY | `localConfidence(goal)` in `goal-routing.ts`; 0-100 score |
| **Grounding check** | CODE COMPLETE, TEST READY | `groundAnswer(answer, evidence)` in `goal-routing.ts` |
| **Router integration** | CODE FRAME, UNRUN | Server drain() loop will use confidence score to decide local vs Mercury |
| **Dashboard display** | CODE FRAME, UNRUN | Show model (local/Mercury), latency, cost per run |
| **CLI display** | CODE FRAME, UNRUN | Show model selection, latency, cost |
| **Live proof (5 runs)** | UNPROVEN | Will be generated after router is wired and bake-off winner is known |
| **Performance target** | UNPROVEN | Cap $0.20 Mercury (fallbacks only); local model as default if pass rate ≥ 80% |

## What's Missing (Next Steps)

1. **Run the bake-off:** Measure all three models. Takes ~5–10 minutes (120 API calls to Ollama).
2. **Pick the winner:** Choose default local model by pass rate + p95 latency rule.
3. **Wire the router:** Update `server.ts` drain() to use `localConfidence()` and `groundAnswer()`.
4. **Update dashboard/CLI:** Show model selection, latency, cost.
5. **Live proof:** Run 5 example goals on the dashboard and CLI, capture traces.
6. **Fallback handling:** If a local answer fails (latency timeout, grounding fail, etc.), escalate transparently.

## Cost Cap

- Bake-off: ~$0.01 (all Ollama, free)
- Live proof fallbacks: ≤$0.20 (only Mercury calls for cases the local model can't handle)
- **Total P3.20 budget: $0.21**

---

**Status:** Scaffolding complete. Ready to run bake-off and wire routing.  
**Evidence location:** `docs/evidence/p320-local-bakeoff-results.json` (will be generated after bake-off runs)
