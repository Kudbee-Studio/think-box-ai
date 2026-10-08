# P3.78 security item 10: `remember` asks a human when the run read a web page

Before: a hostile page could make a model call `remember`; the evidence rule only checked that "something external was observed", so the planted text was saved to memory with no human involved (test failed before the change: the fact was saved, nobody was asked).

After: if the run has read a web page, feed or live lookup (`webObserved`) and the user's own goal did not ask to remember, `remember` goes through the approval gate ("Saves to memory ... after reading a web page this run").

| Claim | State | Basis |
|---|---|---|
| A scripted-obedient model cannot save web-planted text without a yes | PROVEN | `tests/injection-suite.test.ts` (failed before, passes after) |
| A yes saves it; a goal that says "remember that..." is not asked again; reading only a local file does not ask | PROVEN | same file, two more tests |
| A real model resists planted instructions | NOT CLAIMED | the model is scripted to obey; this proves the gate only |
| Text the user copies into the goal is trusted | By design | the goal is the human's own instruction, so it counts as their yes |
| Facts in non-web observed data (a repo file) | NOT GATED | only web-sourced runs ask; a hostile file in a cloned repo can still plant a memory without a question |
