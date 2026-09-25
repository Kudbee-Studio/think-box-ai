"""Deterministic Trait Lab rules.

The browser client ports this file. Keep the LCG, weights, and action
order aligned with ``public/nfts/trait_game.js``. No network. No chain.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

RULES_REL = Path("public/nfts/trait_game_rules.json")
GRADE_ORDER = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}


class TraitGameError(ValueError):
    """Fail-closed trait-lab error. State is left unchanged by ``act``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def load_rules(path: Path | None = None) -> dict[str, Any]:
    """Load the shared rules document used by the page."""
    target = path or Path(__file__).resolve().parents[2] / RULES_REL
    return json.loads(target.read_text(encoding="utf-8"))


def updates(rules: dict[str, Any] | None = None) -> tuple[tuple[str, str], ...]:
    doc = rules if rules is not None else load_rules()
    return tuple((item["id"], item["name"]) for item in doc["updates"])


UPDATES = (
    ("U01", "seeded_run"),
    ("U02", "energy_budget"),
    ("U03", "weighted_rarity"),
    ("U04", "five_collections"),
    ("U05", "set_bonus"),
    ("U06", "duplicate_dust"),
    ("U07", "dust_forge"),
    ("U08", "combo_chain"),
    ("U09", "focus_lens"),
    ("U10", "mulligan"),
    ("U11", "turn_clock"),
    ("U12", "jackpot_perfect_set"),
    ("U13", "cross_set_synergy"),
    ("U14", "risk_draw"),
    ("U15", "shield_bank"),
    ("U16", "rival_pace"),
    ("U17", "letter_grade"),
    ("U18", "achievements"),
    ("U19", "one_step_undo"),
    ("U20", "replay_log"),
    ("U21", "local_leaderboard"),
    ("U22", "daily_seed"),
    ("U23", "difficulty_tiers"),
    ("U24", "fail_closed_actions"),
    ("U25", "proof_scorecard"),
)


def daily_seed(day: str) -> int:
    """Stable seed from ``YYYY-MM-DD``. U22."""
    parts = day.split("-")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise TraitGameError("invalid_day", "daily seed requires YYYY-MM-DD")
    year, month, date = (int(part) for part in parts)
    if not (1 <= month <= 12 and 1 <= date <= 31):
        raise TraitGameError("invalid_day", "daily seed requires a real calendar day")
    return year * 10000 + month * 100 + date


def _step(rng: int) -> tuple[int, int]:
    nxt = (rng * 1664525 + 1013904223) & 0xFFFFFFFF
    return nxt, nxt


def _traits(rules: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rarities = list(rules["rarity_by_index"])
    for collection, names in rules["collections"].items():
        for index, name in enumerate(names):
            rows.append(
                {
                    "collection": collection,
                    "name": name,
                    "index": index,
                    "rarity": rarities[index],
                }
            )
    return rows


def _find(rules: dict[str, Any], collection: str, name: str) -> dict[str, Any]:
    for row in _traits(rules):
        if row["collection"] == collection and row["name"] == name:
            return row
    raise TraitGameError("unknown_trait", f"unknown trait {collection}/{name}")


def _owned(state: dict[str, Any], collection: str, name: str) -> bool:
    return name in state["inventory"].get(collection, [])


def _rank(rules: dict[str, Any], rarity: str) -> int:
    return list(rules["rarity_by_index"]).index(rarity)


def bag_weights(rules: dict[str, Any], state: dict[str, Any], *, risk: bool) -> list[tuple[dict[str, Any], int]]:
    """U03 + U09 + U14. Stable order: collection name, then trait index."""
    focus = state.get("focus") or ""
    multiplier = int(rules["focus_multiplier"])
    items: list[tuple[dict[str, Any], int]] = []
    for row in _traits(rules):
        if risk and row["rarity"] == "common":
            continue
        weight = int(rules["weights"][row["rarity"]])
        if focus and row["collection"] == focus:
            weight *= multiplier
        items.append((row, weight))
    return items


def _pick(rules: dict[str, Any], state: dict[str, Any], *, risk: bool) -> dict[str, Any]:
    items = bag_weights(rules, state, risk=risk)
    if not items:
        raise TraitGameError("no_risk_targets", "risk draw has no rare-or-better traits")
    total = sum(weight for _, weight in items)
    rng, roll_src = _step(int(state["rng"]))
    state["rng"] = rng
    roll = roll_src % total
    cursor = 0
    for row, weight in items:
        cursor += weight
        if roll < cursor:
            return row
    return items[-1][0]


def _combo_multiplier(rules: dict[str, Any], combo: int) -> float:
    capped = min(max(combo, 0), int(rules["combo_cap"]))
    return 1.0 + float(rules["combo_step"]) * capped


def _refresh_rival(rules: dict[str, Any], state: dict[str, Any]) -> None:
    pace = int(rules["difficulties"][state["difficulty"]]["rival_per_turn"])
    state["rival_xp"] = int(state["turn"]) * pace


def _grade(state: dict[str, Any]) -> str:
    sets = len(state["completed"])
    ahead = int(state["xp"]) >= int(state["rival_xp"])
    if sets >= 5:
        return "S"
    if ahead and sets >= 3:
        return "A"
    if ahead and sets >= 1:
        return "B"
    if sets >= 1:
        return "C"
    return "D"


def _achievements(state: dict[str, Any]) -> None:
    earned = state["achievements"]
    if any(state["inventory"].values()):
        earned.add("spark")
    if state["completed"]:
        earned.add("bound")
    if int(state["combo"]) >= 3:
        earned.add("chain")
    if int(state["dust"]) >= 8:
        earned.add("residue")
    if int(state["turn"]) >= 3 and int(state["xp"]) >= int(state["rival_xp"]):
        earned.add("ahead")
    if len(state["completed"]) >= 3:
        earned.add("atlas")
    if state["difficulty"] == "thesis" and state.get("over") and _grade(state) in {"S", "A"}:
        earned.add("thesis")


def _maybe_close(rules: dict[str, Any], state: dict[str, Any]) -> None:
    limit = int(rules["difficulties"][state["difficulty"]]["turns"])
    if int(state["turn"]) >= limit:
        state["over"] = True
        state["grade"] = _grade(state)
    _achievements(state)


def _synergy_gain(rules: dict[str, Any], state: dict[str, Any]) -> list[str]:
    gained: list[str] = []
    for item in rules["synergies"]:
        sid = item["id"]
        if sid in state["synergies"]:
            continue
        left, right = item["a"], item["b"]
        if _owned(state, left[0], left[1]) and _owned(state, right[0], right[1]):
            state["synergies"].append(sid)
            state["xp"] += int(item["xp"])
            gained.append(sid)
    return gained


def _grant(
    rules: dict[str, Any],
    state: dict[str, Any],
    row: dict[str, Any],
    *,
    action: str,
    energy_spent: int,
) -> dict[str, Any]:
    collection = row["collection"]
    name = row["name"]
    combo_before = int(state["combo"])
    event: dict[str, Any] = {
        "action": action,
        "collection": collection,
        "trait": name,
        "rarity": row["rarity"],
        "energy_spent": energy_spent,
        "combo_before": combo_before,
        "duplicate": False,
        "set_completed": False,
        "jackpot": False,
        "synergies": [],
        "shield_consumed": False,
        "xp_delta": 0,
        "dust_delta": 0,
    }
    if _owned(state, collection, name):
        dust = 1 + _rank(rules, row["rarity"]) * int(rules["dust_per_duplicate_rank"])
        state["dust"] += dust
        state["combo"] = 0
        event["duplicate"] = True
        event["dust_delta"] = dust
    else:
        state["inventory"].setdefault(collection, []).append(name)
        state["combo"] = combo_before + 1
        gained = int(int(rules["xp_by_rarity"][row["rarity"]]) * _combo_multiplier(rules, state["combo"]))
        if state.get("shield_armed"):
            gained = int(gained * float(rules["shield_multiplier"]))
            state["shield_armed"] = False
            event["shield_consumed"] = True
        state["xp"] += gained
        event["xp_delta"] += gained
        owned_now = state["inventory"][collection]
        names = rules["collections"][collection]
        if collection not in state["completed"] and all(trait in owned_now for trait in names):
            bonus = int(rules["set_bonus"][collection])
            state["xp"] += bonus
            event["xp_delta"] += bonus
            event["set_completed"] = True
            state["completed"].append(collection)
            if int(state["combo"]) >= int(rules["jackpot_combo"]):
                state["xp"] += int(rules["jackpot_xp"])
                event["xp_delta"] += int(rules["jackpot_xp"])
                event["jackpot"] = True
        synergies = _synergy_gain(rules, state)
        event["synergies"] = synergies
        event["xp_delta"] += sum(int(item["xp"]) for item in rules["synergies"] if item["id"] in synergies)
    state["turn"] = int(state["turn"]) + 1
    _refresh_rival(rules, state)
    state["log"].append(event)
    _maybe_close(rules, state)
    return event


def new_run(rules: dict[str, Any], *, seed: int, difficulty: str = "lab") -> dict[str, Any]:
    """Open a seeded run. U01, U04, U11, U16, U23."""
    if difficulty not in rules["difficulties"]:
        raise TraitGameError("unknown_difficulty", f"unknown difficulty {difficulty}")
    if seed <= 0:
        raise TraitGameError("invalid_seed", "seed must be a positive integer")
    profile = rules["difficulties"][difficulty]
    inventory = {name: [] for name in rules["collections"]}
    return {
        "game_id": rules["game_id"],
        "version": int(rules["version"]),
        "seed": int(seed),
        "rng": int(seed) & 0xFFFFFFFF,
        "difficulty": difficulty,
        "turn": 0,
        "turns_max": int(profile["turns"]),
        "energy": int(profile["energy"]),
        "energy_max": int(profile["energy"]),
        "dust": 0,
        "xp": 0,
        "rival_xp": 0,
        "combo": 0,
        "focus": "",
        "shield_armed": False,
        "mulligan_used": False,
        "inventory": inventory,
        "completed": [],
        "synergies": [],
        "achievements": set(),
        "log": [],
        "undo": None,
        "over": False,
        "grade": "",
        "live_verified": False,
    }


def _snapshot(state: dict[str, Any]) -> dict[str, Any]:
    saved = deepcopy(state)
    saved["undo"] = None
    saved["achievements"] = set(state["achievements"])
    return saved


def _spend_energy(state: dict[str, Any], cost: int) -> None:
    if int(state["energy"]) < cost:
        raise TraitGameError("insufficient_energy", "not enough energy")
    state["energy"] = int(state["energy"]) - cost


def _require_open(state: dict[str, Any]) -> None:
    if state.get("over"):
        raise TraitGameError("run_complete", "the run is already over")


def _acquire(rules: dict[str, Any], state: dict[str, Any], *, action: str, risk: bool) -> dict[str, Any]:
    cost = int(rules["energy_cost"][action])
    _spend_energy(state, cost)
    row = _pick(rules, state, risk=risk)
    return _grant(rules, state, row, action=action, energy_spent=cost)


def _forge(rules: dict[str, Any], state: dict[str, Any], collection: str, name: str) -> dict[str, Any]:
    if collection not in rules["collections"]:
        raise TraitGameError("unknown_collection", f"unknown collection {collection}")
    row = _find(rules, collection, name)
    if _owned(state, collection, name):
        raise TraitGameError("already_owned", "that trait is already in the lab")
    cost = int(rules["forge_dust_base"]) + _rank(rules, row["rarity"])
    if int(state["dust"]) < cost:
        raise TraitGameError("insufficient_dust", "not enough dust to forge")
    state["dust"] -= cost
    event = _grant(rules, state, row, action="forge", energy_spent=0)
    event["dust_delta"] -= cost
    return event


def _mulligan(rules: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    if state["mulligan_used"]:
        raise TraitGameError("mulligan_spent", "mulligan was already used")
    if not state["log"] or state["log"][-1]["action"] not in {"draw", "risk_draw"}:
        raise TraitGameError("nothing_to_mulligan", "mulligan only reverses the last draw")
    event = state["log"][-1]
    if event["duplicate"]:
        state["dust"] -= int(event["dust_delta"])
        state["combo"] = int(event["combo_before"])
    else:
        collection = event["collection"]
        trait = event["trait"]
        if trait in state["inventory"].get(collection, []):
            state["inventory"][collection].remove(trait)
        if event["set_completed"] and collection in state["completed"]:
            state["completed"].remove(collection)
        for sid in event["synergies"]:
            if sid in state["synergies"]:
                state["synergies"].remove(sid)
        state["xp"] -= int(event["xp_delta"])
        state["combo"] = int(event["combo_before"])
        if event["shield_consumed"]:
            state["shield_armed"] = True
    state["energy"] += int(event["energy_spent"])
    state["turn"] = max(0, int(state["turn"]) - 1)
    state["log"].pop()
    state["mulligan_used"] = True
    state["over"] = False
    state["grade"] = ""
    _refresh_rival(rules, state)
    note = {"action": "mulligan", "collection": event.get("collection", ""), "trait": event.get("trait", "")}
    state["log"].append(note)
    _achievements(state)
    return note


def act(rules: dict[str, Any], state: dict[str, Any], action: str, **args: str) -> dict[str, Any]:
    """Apply one action. Failures return the original state."""
    original = deepcopy(state)
    original["achievements"] = set(state["achievements"])
    working = deepcopy(state)
    working["achievements"] = set(state["achievements"])
    try:
        _require_open(working)
        if action == "undo":
            if not working.get("undo"):
                raise TraitGameError("nothing_to_undo", "no action to undo")
            restored = working["undo"]
            restored["achievements"] = set(restored.get("achievements") or [])
            restored["undo"] = None
            return {"ok": True, "error": "", "state": restored, "event": {"action": "undo"}}
        working["undo"] = _snapshot(working)
        if action == "draw":
            event = _acquire(rules, working, action="draw", risk=False)
        elif action == "risk_draw":
            event = _acquire(rules, working, action="risk_draw", risk=True)
        elif action == "focus":
            collection = str(args.get("collection") or "")
            if collection not in rules["collections"]:
                raise TraitGameError("unknown_collection", f"unknown collection {collection}")
            working["focus"] = collection
            event = {"action": "focus", "collection": collection, "trait": ""}
            working["log"].append(event)
        elif action == "forge":
            event = _forge(rules, working, str(args.get("collection") or ""), str(args.get("trait") or ""))
        elif action == "mulligan":
            event = _mulligan(rules, working)
        elif action == "arm_shield":
            if working["shield_armed"]:
                raise TraitGameError("shield_armed", "a shield is already armed")
            _spend_energy(working, int(rules["energy_cost"]["arm_shield"]))
            working["shield_armed"] = True
            event = {"action": "arm_shield", "collection": "", "trait": ""}
            working["log"].append(event)
        elif action == "finish":
            working["over"] = True
            _refresh_rival(rules, working)
            working["grade"] = _grade(working)
            _achievements(working)
            event = {"action": "finish", "collection": "", "trait": ""}
            working["log"].append(event)
        else:
            raise TraitGameError("unknown_action", f"unknown action {action}")
    except TraitGameError as exc:
        return {"ok": False, "error": exc.code, "state": original, "event": None}
    return {"ok": True, "error": "", "state": working, "event": event}


def proof_scorecard(state: dict[str, Any]) -> dict[str, Any]:
    """U25. Public, replayable, never live-verified."""
    body = {
        "game_id": state["game_id"],
        "version": state["version"],
        "seed": state["seed"],
        "difficulty": state["difficulty"],
        "xp": state["xp"],
        "rival_xp": state["rival_xp"],
        "turn": state["turn"],
        "completed": list(state["completed"]),
        "synergies": list(state["synergies"]),
        "grade": state["grade"] or (_grade(state) if state["over"] else ""),
        "log_actions": [entry.get("action") for entry in state["log"]],
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body["proof_sha256"] = hashlib.sha256(encoded).hexdigest()
    return body


def rank_board(entries: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    """U21. Local names only. Highest XP, then grade, then fewer turns."""
    def key(entry: dict[str, Any]) -> tuple[int, int, int]:
        return (
            int(entry.get("xp") or 0),
            GRADE_ORDER.get(str(entry.get("grade") or ""), 0),
            -int(entry.get("turn") or 0),
        )

    ranked = sorted(entries, key=key, reverse=True)
    return ranked[: max(1, limit)]
