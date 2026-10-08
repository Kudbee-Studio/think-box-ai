# P3.73: a tamper-evident audit log

**What is recorded** (`audit.db` in the data directory, `audit-log.ts`): every approval asked (tool, reason, argument summary) and how it was answered (approved, denied, or no answer in time) and by which channel; every finished run with model, tokens, cost and approvals; choosing or clearing the agent's repository; undoing the agent's changes; opening a draft pull request (done or refused). Read it with `GET /api/audit`, `GET /api/audit/verify` or `kudbee audit [--verify] [--kind K] [--run ID] [--json]`.

**What is NOT recorded:** file contents, command output, prompts or answers. Tool arguments are reduced to names, sizes and a short start of text values, and everything passes the same secret redaction as Think Tokens.

**Tamper evidence, proven by tests:** each row stores the hash of the row before it. An edited row, a removed row, an inserted row and a reordered pair are each detected, with the row number (`tests/audit-log.test.ts`). **Limit, tested and stated:** cutting rows off the END of the log is not detectable from the log alone; `verify` returns the newest row's hash (`head`), and writing it down elsewhere makes a later cut visible.

**On the real server** (`tests/audit-integration.test.ts`): an approve and a deny of a Think Token action produced four rows in order (requested, resolved by `dashboard`, requested, resolved by `dashboard`), the tool and reason were recorded, the API listed them, the chain verified, and `kudbee audit --verify` read the same file and printed the same head. Repository choice, undo (and a refused undo recording nothing) and the refused draft-PR attempt are covered in `tests/audit-routes.test.ts` and `tests/agent-pr-socket.test.ts`.

**Honest limits:**
- **Who:** there is no login yet, so the "actor" is the channel (`dashboard`, `timeout`, `human`, `agent`, `system`), not a person. When accounts exist the actor becomes the user.
- **Not an immutable store:** someone with write access to the machine can delete the whole file. The log makes quiet edits visible; it does not make them impossible.
- A failing write is reported on stderr and never stops the thing being audited.
- No dashboard viewer yet (API and CLI only).
