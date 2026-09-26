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
| `POST` | `/api/v1/autonomous-loop/loops/{loop_id}/actions/{action}` | Record an action (`start`, `stop`, `run`, `reset`). Accepts an optional JSON payload that becomes the `result` field. Returns the created `LoopActionEntry` as JSON. |
| `GET`  | `/api/v1/autonomous-loop/loops/{loop_id}/actions` | List all actions recorded for the given loop. |
| `GET`  | `/api/v1/autonomous-loop/actions` | List *all* actions across all loops. |

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

## Testing

* `tests/unit/autonomous_loop/test_control_actions.py` validates model creation, storage, and retrieval.
* API surface tests (`tests/unit/test_autonomous_loop_api.py`) cover the new endpoints and error handling for invalid actions.

## Future Work

* **Implemented** token requirement: POST `/loops/{loop_id}/actions/{action}` now requires a valid governance token (Bearer or `X‑Governance‑Token` header). The token presence is enforced; validation is performed by the admission gate elsewhere.
* UI integration now includes the token when invoking actions from the control‑plane.
