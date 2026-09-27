# Autonomous Loop Actions Documentation

## Overview

The autonomous decision loop now tracks user‑initiated actions (start, stop, run, reset) via an audit trail.  Each action creates a **LoopActionEntry** record that is stored in the dashboard state and can be queried through the control‑plane API.

## Data Model

```python
@dataclass
class LoopActionEntry:
    """Audit record for an action performed on an autonomous loop."""
    action_id: str               # Unique identifier, auto‑generated if empty
    loop_id: str                  # Identifier of the loop the action applies to
    action: str                   # One of: start, stop, run, reset
    timestamp: str = ""          # ISO‑8601, auto‑filled if empty
    result: Any = None            # Optional payload returned by the action
    source: str = ""             # Optional caller identifier
    evidence_label: str = "simulated"

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.action_id:
            self.action_id = f"act_{uuid.uuid4().hex[:12]}"

    def model_dump(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "loop_id": self.loop_id,
            "action": self.action,
            "timestamp": self.timestamp,
            "result": self.result,
            "source": self.source,
            "evidence_label": self.evidence_label,
        }
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/autonomous-loop/loops/{loop_id}/actions/{action}` | Record an action (`start`, `stop`, `run`, `reset`). **Requires a governance token.** Accepts an optional JSON payload that becomes the `result` field. Returns the created `LoopActionEntry` as JSON. |
| `GET`  | `/api/v1/autonomous-loop/loops/{loop_id}/actions` | List all actions recorded for the given loop. |
| `GET`  | `/api/v1/autonomous-loop/actions` | List *all* actions across all loops. |

### Governance Token Requirement

`POST /loops/{loop_id}/actions/{action}` is a side effect and therefore requires a
governance token. Supply it with **either** header:

```
X-Governance-Token: <token>
Authorization: Bearer <token>
```

Requests without a token are rejected with **HTTP 401** (`Missing governance token`).
`X-Governance-Token` takes precedence when both are supplied. Whitespace-only values
are treated as absent. The pure helper `extract_governance_token(authorization, x_governance_token)`
in `backend/api/v1/autonomous_loop.py` implements this and is unit-tested hermetically.

Allowed actions are `start`, `stop`, `run`, `reset`; any other action is rejected with
**HTTP 400**.

### Request Example (start)
```json
POST /api/v1/autonomous-loop/loops/loopA/actions/start
Content-Type: application/json

{ "msg": "loop started" }
```

### Response Example
```json
{
  "action_id": "act_1a2b3c4d5e6f",
  "loop_id": "loopA",
  "action": "start",
  "timestamp": "2026-09-26T05:44:55.123456Z",
  "result": { "msg": "loop started" },
  "source": "",
  "evidence_label": "simulated"
}
```

## Dashboard Integration

* The `last_action` field on `AutonomousLoopEntry` is updated to the most recent action name.
* The UI (`public/control-plane/autonomous_loop.html` and accompanying JS) adds an **Actions** panel displaying recent actions per loop, using the new endpoints.
* Action audit entries are emitted as `DashboardEvent` of type `LOOP_ACTION_RECORDED` (future UI hook).

## Control-Plane UI Panel (PR #249)

The autonomous loop page now contains a dedicated actions UI so an operator can both
*view* and *trigger* loop actions from one place.

### Recent Loop Actions panel

A `Recent Loop Actions` panel (`#actionList`) renders the most recent 10 actions for
the currently selected loop. Each row shows the action name, the wall-clock time, and
the `action_id`. It is refreshed by `refreshSelectedDetail()` alongside the loop
detail and telemetry fetch, and re-rendered after every successful action submission.

### Action controls toolbar

A hidden-by-default toolbar (`#actionControls`) becomes visible as soon as a loop is
selected. It contains four buttons — Start / Stop / Run / Reset (`#btnActionStart`,
`#btnActionStop`, `#btnActionRun`, `#btnActionReset`) — plus a password input
(`#governanceTokenInput`) for the governance token and a status line (`#actionStatus`).

Behaviour:

1. Clicking an action button reads the token from `#governanceTokenInput`.
2. If no loop is selected → status shows `Select a loop first` (no request sent).
3. If the token input is empty → status shows `Governance token required` (no request sent),
   so no unauthenticated side effect can leave the browser.
4. Otherwise the client issues `POST /api/v1/autonomous-loop/loops/{loop_id}/actions/{action}`
   with the `X-Governance-Token` header.
5. On success the panel reloads that loop's actions; on failure the HTTP status and
   error detail are surfaced in `#actionStatus`.
6. Buttons are disabled while the request is in flight and re-enabled afterwards.

The button is wired through `sendLoopAction(action)`, and all helpers are exported on
`window.TBAutonomousLoopClient` (`fetchLoopActions`, `fetchAllActions`, `postLoopAction`,
`renderActionList`, `showActionStatus`, `sendLoopAction`) for headless verification.

### Client API (JS)

| Helper | Description |
|--------|-------------|
| `fetchLoopActions(loopId)` | GET actions for one loop; `[]` on failure |
| `fetchAllActions()` | GET all actions across loops; `[]` on failure |
| `postLoopAction(loopId, action, payload, token)` | POST an action with the token; returns `{ok, status, data/error}` |
| `renderActionList(actions)` | Render up to 10 actions into `#actionList` |
| `showActionStatus(message, isError)` | Update `#actionStatus` text and colour |
| `sendLoopAction(action)` | Full click handler: validate → POST → refresh → status |

## Testing

* `tests/unit/autonomous_loop/test_control_actions.py` validates model creation, storage, and retrieval.
* API surface tests (`tests/unit/test_autonomous_loop_api.py`) cover the new endpoints and error handling for invalid actions.
* `tests/unit/test_autonomous_loop_action_store.py` (PR #251) covers receipts:
  hash linkage, tamper detection via raw `sqlite3` mutation, reopen survival,
  hydration across a simulated restart, idempotency, env configuration branches,
  one-call attach/recovery, and graceful degradation when storage fails.
* `tests/unit/test_autonomous_loop_integrity_ui.py` asserts the integrity
  indicator's source contract and runs Node assertions against the real client.
* `tests/unit/test_autonomous_loop_action_api.py` (PR #249) covers token extraction
  (`X-Governance-Token`, Bearer, precedence, whitespace, absent), action validation,
  state persistence, and API module surface — hermetically, without FastAPI installed.
* `tests/unit/test_autonomous_loop_ui_static.py` asserts the HTML contains the
  `actionList` panel, action controls, buttons, token input, and the actions API
  markers; and that the JS exports the action helpers and `X-Governance-Token` header.

## Durable Action Receipts (PR #251)

Before PR #251, actions lived only in `DashboardState.loop_actions` — an in-memory
dict — so the operator audit trail was lost on every restart. Actions are now also
persisted to SQLite in an append-only, tamper-evident chain.

### Store — `thinkbox/autonomous_loop_action_store.py`

| Item | Description |
|------|-------------|
| `LoopActionReceipt` | `receipt_id`, `loop_id`, `action`, `source`, `evidence_label`, `timestamp`, `prev_hash`, `entry_hash`, `result`, `loop_action_id` (links back to the in-memory `LoopActionEntry.action_id`) |
| `LoopActionStore` | SQLite append-only store; table `loop_action_receipts` |
| `open_loop_action_store(path)` | Opens a store, creating the parent directory |
| `default_loop_action_db_path()` | `data/thinkboxmd/db/loop_actions.db` |

Each row's `entry_hash` is a SHA-256 (truncated to 32 hex chars) over the payload
**including the previous row's hash**, mirroring the `ActionReceiptStore` pattern
already used by the agent control plane. The first row's `prev_hash` is `GENESIS`.

```python
from thinkbox.autonomous_loop_action_store import open_loop_action_store

store = open_loop_action_store()          # or :memory: via LoopActionStore()
receipt = store.append("loopA", "start", {"msg": "go"}, source="ui")
store.verify()                            # True until something is tampered with
store.by_loop("loopA")                    # oldest-first receipts for one loop
store.latest(10)                          # newest-first across all loops
store.count()
```

`verify()` re-walks the chain and recomputes every hash, returning **False** if any
row was edited, deleted, or had its hash rewritten. This is tested directly:
the unit suite mutates rows via raw `sqlite3` and asserts `verify()` fails.

Durability claim (tested, not assumed): append two receipts, `close()`, reopen the
same path with a fresh `LoopActionStore` — both receipts are present and
`verify()` is still `True`.

### Dashboard wiring

Durability alone does not make history visible: after a restart the in-memory dict
is empty, so the API and panel would report "no actions recorded" even though the
receipts are safe on disk. Two pieces close that gap:

- **`DashboardState.hydrate_loop_actions_from_store()`** replays receipts into
  `loop_actions` and restores each loop's `last_action`. It is **idempotent** —
  actions already present are matched on `action_id` and skipped, so calling it
  repeatedly never duplicates entries. Returns the number restored.
- **`LoopActionStore.all_receipts(limit=None)`** is the oldest-first read path used
  by hydration.

Both storage read and write paths fail soft: a corrupt or unavailable store is
logged and reported as `0` rather than breaking control flow.

### Configuration (env)

`THINKBOX_LOOP_ACTION_DB` controls durability:

| Value | Meaning |
|-------|---------|
| unset / empty | default durable path `data/thinkboxmd/db/loop_actions.db` |
| `off`, `0`, `false`, `none`, `disabled` | durability **disabled** (no store attached) |
| `:memory:` | ephemeral in-memory store (tests) |
| any other value | that filesystem path |

Discrete values return `None` rather than the default, so callers can distinguish
"disabled" from "use the default".

### One-call startup wiring

```python
from thinkbox.autonomous_loop_action_store import attach_durable_loop_actions

store, restored = attach_durable_loop_actions(state)   # open + attach + recover
```

Or honour configuration so deployments can turn it off explicitly:

```python
from thinkbox.autonomous_loop_action_store import maybe_attach_loop_action_store

store = maybe_attach_loop_action_store(state)   # None when disabled
```

The startup call site is still explicit (this doc tracks auto-wiring as future
work) but is now a single line that both persists *and* recovers.

### UI integrity indicator

The control-plane page shows an **Action Audit Chain (durable)** strip backed by
`GET /actions/integrity`, refreshed on every poll cycle. It distinguishes four
states rather than collapsing them into one "ok/not ok":

| Badge | Meaning |
|-------|---------|
| `OFFLINE` | integrity endpoint unreachable |
| `NOT ATTACHED` | durability disabled — deliberately does **not** imply a chain exists |
| `VALID` | N receipts persisted, hash chain intact |
| `TAMPERED` | N receipts persisted, hash chain **BROKEN** |

The renderer resets its inline warning styles when a chain recovers, so the
indicator cannot stay stuck red. Runtime behaviour is asserted in Node against the
real client file (`tests/js/autonomous_loop_client_integrity.test.js`); the Python
suite skips that part cleanly when `node` is unavailable.



`DashboardState` gained `set_loop_action_store(store)` / `get_loop_action_store()`.
When a store is attached, `record_loop_action()` additionally appends a receipt, so
every existing caller (including the `POST /actions/{action}` route) becomes durable
without further changes. Persistence is **best-effort for observability**: a storage
failure is logged and swallowed so it can never break the in-memory control flow.
With no store attached the behaviour is exactly as before.

### API

`GET /api/v1/autonomous-loop/actions/integrity` returns:

```json
{
  "attached": true,
  "count": 2,
  "valid": true,
  "latest": [ { "receipt_id": "lar_...", "action": "start", ... } ],
  "api_version": "autonomous-loop-api-v1"
}
```

`attached: false` means no durable store is configured (not an error, and not a claim
that a chain exists). `valid: false` means tampering was detected.

### Evidence

Receipts carry `evidence_label: "simulated"` — they prove the action was *requested
and recorded* through the control plane. They do **not** prove the loop performed a
corresponding observable side effect.

## Future Work

* Validate the token against the governance layer (AdmissionGate) rather than only
  enforcing its presence.
* Wire `maybe_attach_loop_action_store()` into application startup; the helper is
  one line now, but the call site is still explicit rather than implicit.
* Emit `LOOP_ACTION_RECORDED` dashboard events so the panel can stream updates.
* ~~Add an operator-facing integrity indicator in the UI~~ — done (see above).
* Add retention/pruning for receipts (the table grows without bound today).
