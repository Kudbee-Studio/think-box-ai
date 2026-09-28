# ASCLEPIUS — Medication Label Research Agent

## What it is

ASCLEPIUS is a named, tool-scoped agent lane (`apps/web/agent.ts`, `AGENT_PROFILES.asclepius`),
built on the same pattern as HERMES (see `docs/HERMES_ALGORAND.md`).

**Tools:** `medication`, `recall`, `remember` — nothing else.

## The critical design constraint: this is not an interaction checker

`apps/web/medication.ts` does **not** compute or assert whether two drugs interact. A drug's
FDA label was written without knowledge of what else a specific patient is taking. What it
does instead: fetches each drug's own FDA-approved label section
(`drug_interactions`, `boxed_warning`, `contraindications`, or `warnings_and_cautions`) and,
for `compare`, returns several drugs' sections side by side for a human — ideally a pharmacist
or physician — to read and cross-reference.

This is enforced, not just documented:
- Every response carries `OPENFDA_DISCLAIMER` verbatim (openFDA's own "assume all results are
  unvalidated" language, plus an explicit instruction to consult a licensed pharmacist or
  physician).
- Every `compare` response's `note` field states plainly that the call does not cross-reference
  the drugs or compute an interaction.
- ASCLEPIUS's system prompt has a `CRITICAL SAFETY RULE`: never call a combination "safe",
  "fine", "not a problem", or definitively "dangerous". If asked for dosing, diagnosis, or
  treatment advice, decline and redirect to a healthcare professional.
- A test (`tests/medication.test.ts`) asserts the response JSON never contains a `"verdict"`,
  `"is_safe"`, or `"safe_together"` key, as a regression guard against someone later adding a
  computed verdict without updating the safety design.

## Why openFDA, not a structured interaction API

The standard free structured drug-interaction API — NIH's RxNav Interaction API
(`rxnav.nlm.nih.gov/REST/interaction/list.json`) — is dead. Verified directly before writing
any code:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://rxnav.nlm.nih.gov/REST/interaction/list.json?rxcuis=855332+141918"
# → 404
```

This matches NIH's public retirement of that endpoint (announced Jan 2024). RxNav's plain name
resolution (`rxcui.json?name=...`) is still live and is used by `resolveRxcui()` for RxNorm
cross-referencing, but no interaction-pair lookup exists there anymore.

openFDA's drug label API (`api.fda.gov/drug/label.json`) is live, free, requires no API key,
and returns the actual FDA-approved package insert text — authoritative in the sense that it's
the real regulatory label, not an authoritative *interaction verdict* (which is the distinction
this whole design is built around).

## Actions

| Action | Input | Output |
|---|---|---|
| `lookup` | `drug`, `section?` (default `drug_interactions`) | One drug's label section, brand/generic name, RxCUI(s), source URL |
| `compare` | `drugs` (2-5 names), `section?` | Same section for each drug, independently, plus the safety `note` |

Input is sanitized against a strict character allowlist (`[A-Za-z0-9 .\-/]`) before it's ever
placed in a URL — not because this is a code-execution risk (it's a read-only GET to a public
API), but so a crafted value can't widen the openFDA query syntax into an unintended match.

`compare` fetches sequentially with a small delay between requests (openFDA's unauthenticated
rate limit is 40 requests/minute/IP), not in parallel.

## Ambiguity

Many distinct approved products can share a generic name (different manufacturers, strengths,
combination products). `lookup`/`compare` return `total_matching_labels` and an `ambiguous: true`
flag when more than one label matched — the single label returned is one of possibly several,
and the model/user should be aware of that rather than treating it as the definitive text for
that drug name.

## Testing

`apps/web/tests/medication.test.ts` — 8 hermetic tests against a local mock HTTP server (no live
openFDA calls in CI): known-drug lookup, section selection, unknown drug (`found: false`, not a
thrown error), disclaimer present verbatim, `compare` makes one request per drug and never
computes a verdict, invalid input rejected before any network call, ambiguity flagging.

`apps/web/tests/agent.test.ts` — 6 ASCLEPIUS-specific cases mirroring HERMES's: allowlist
contents, function-list filtering, safety-critical role context present in the system prompt,
hard-backstop rejection of a simulated hallucinated `write_file` call, allowed tool (`medication`)
still goes through the normal approval gate, invalid input rejected before any approval prompt.

## Out of scope

Computed interaction checking of any kind, dosing guidance, diagnosis, treatment
recommendations, and anything requiring a paid/licensed drug-interaction database
(e.g. First Databank, Lexicomp, Micromedex) — those exist and are more clinically complete than
free-text label sections, but require a commercial license this repo doesn't have. If real
interaction-pair checking is wanted later, that's a distinct, explicit scope decision — not
something to retrofit into ASCLEPIUS's current label-lookup design.
