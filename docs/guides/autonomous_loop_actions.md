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
* `tests/unit/test_autonomous_loop_action_api.py` (PR #249) covers token extraction
  (`X-Governance-Token`, Bearer, precedence, whitespace, absent), action validation,
  state persistence, and API module surface — hermetically, without FastAPI installed.
* `tests/unit/test_autonomous_loop_ui_static.py` asserts the HTML contains the
  `actionList` panel, action controls, buttons, token input, and the actions API
  markers; and that the JS exports the action helpers and `X-Governance-Token` header.

## Future Work

* Validate the token against the governance layer (AdmissionGate) rather than only
  enforcing its presence.
* Persist loop actions to SQLite so the audit trail survives a process restart.
* Emit `LOOP_ACTION_RECORDED` dashboard events so the panel can stream updates.
