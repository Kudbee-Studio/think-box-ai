# P3.26 live check, written before the run

Question: with empty-reply recovery on, how many of the 10 untested-function TRAINING goals does qwen2.5:3b pass?

- Goals: the first 10 of `TRAIN_GOALS` (`train-untested-*`), same world, same seeds (5000 + goal index), same model and settings as the P3.25 stage-1 run (engine absence search ON, `maxSteps` 4). Only the recovery differs.
- Before: P3.25 stage 1, `docs/evidence/p3.25-repo-tokens/harvest-qwen2.5-3b.json` = **0/10** (5 wrong "reported nothing", 5 failed).
- Pass = the loop finished, the finding was GROUNDED, and the fixture check passed (names the function that really has no test, in the file the goal names).
- Each run records which recovery step ran and whether it recovered the run.
- Decision: **>= 5/10** passes means the P3.27 follow-up note is written in the PR. **Below 5/10** is reported as it is, with the failure breakdown, and work stops. No trial is re-run or edited. The held-out A/B is NOT run.
- Limits: 10 goals, one model, one seed per goal, a synthetic repository. A pass here does not show the model understands absence; the engine's assist hands it the evidence.
