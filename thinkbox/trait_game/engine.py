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
    ("U26", "scout_peek"),
    ("U27", "rest_turn"),
    ("U28", "convert_energy"),
    ("U29", "convert_dust"),
    ("U30", "pin_trait"),
    ("U31", "unpin_trait"),
    ("U32", "lock_collection"),
    ("U33", "unlock_collection"),
    ("U34", "unfocus"),
    ("U35", "unbind_trait"),
    ("U36", "focus_duration"),
    ("U37", "risk_cooldown"),
    ("U38", "pity_weights"),
    ("U39", "last_stand"),
    ("U40", "late_set"),
    ("U41", "dust_interest"),
    ("U42", "shield_residue"),
    ("U43", "thesis_defense"),
    ("U44", "daily_mark"),
    ("U45", "operator_name"),
    ("U46", "encode_replay"),
    ("U47", "play_replay"),
    ("U48", "coach_hint"),
    ("U49", "rules_checksum"),
    ("U50", "leftover_score"),
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
    """U03 + U09 + U14 + U32 + U30 + U38. Stable order: collection, then index."""
    focus = state.get("focus") or ""
    multiplier = int(rules["focus_multiplier"])
    locked = set(state.get("locked") or [])
    pin = state.get("pin") or {}
    pity = int(rules.get("pity_step") or 0) * int(state.get("turn") or 0)
    pin_mult = int(rules.get("pin_multiplier") or 1)
    items: list[tuple[dict[str, Any], int]] = []
    for row in _traits(rules):
        if row["collection"] in locked:
            continue
        if risk and row["rarity"] == "common":
            continue
        weight = int(rules["weights"][row["rarity"]])
        if focus and row["collection"] == focus:
            weight *= multiplier
        if not _owned(state, row["collection"], row["name"]):
            weight += pity
        if pin and pin.get("collection") == row["collection"] and pin.get("trait") == row["name"]:
            weight *= pin_mult
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


def _in_last_stand(rules: dict[str, Any], state: dict[str, Any]) -> bool:
    return int(state["turns_max"]) - int(state["turn"]) <= int(rules.get("last_stand_turns") or 0)


def _combo_multiplier(rules: dict[str, Any], state: dict[str, Any], combo: int) -> float:
    cap = int(rules["combo_cap"])
    if _in_last_stand(rules, state):
        cap += int(rules.get("last_stand_combo") or 0)
    capped = min(max(combo, 0), cap)
    return 1.0 + float(rules["combo_step"]) * capped


def _refresh_rival(rules: dict[str, Any], state: dict[str, Any]) -> None:
    pace = int(rules["difficulties"][state["difficulty"]]["rival_per_turn"])
    late_n = int(rules.get("last_stand_turns") or 0)
    late_mult = int(rules.get("rival_last_mult") or 1)
    turn = int(state["turn"])
    normal_until = max(0, int(state["turns_max"]) - late_n)
    normal = min(turn, normal_until)
    late = max(0, turn - normal_until)
    state["rival_xp"] = normal * pace + late * pace * late_mult


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
    if state.get("scout"):
        earned.add("lens")
    if state.get("daily") and state.get("over"):
        earned.add("daily")
    if state.get("defended"):
        earned.add("defense")


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
        gained = int(int(rules["xp_by_rarity"][row["rarity"]]) * _combo_multiplier(rules, state, state["combo"]))
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
            if _in_last_stand(rules, state) or int(state["turns_max"]) - int(state["turn"]) <= int(rules.get("late_set_turns") or 0):
                late = int(rules.get("late_set_bonus") or 0)
                state["xp"] += late
                event["xp_delta"] += late
                event["late_set"] = True
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


def new_run(
    rules: dict[str, Any],
    *,
    seed: int,
    difficulty: str = "lab",
    daily: bool = False,
    operator: str = "",
) -> dict[str, Any]:
    """Open a seeded run. U01, U04, U11, U16, U23, U44, U45."""
    if difficulty not in rules["difficulties"]:
        raise TraitGameError("unknown_difficulty", f"unknown difficulty {difficulty}")
    if seed <= 0:
        raise TraitGameError("invalid_seed", "seed must be a positive integer")
    profile = rules["difficulties"][difficulty]
    inventory = {name: [] for name in rules["collections"]}
    name = "".join(ch for ch in operator if ch.isalnum() or ch in "._-")[:24]
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
        "focus_left": 0,
        "shield_armed": False,
        "mulligan_used": False,
        "risk_blocked": False,
        "scout": None,
        "pin": None,
        "locked": [],
        "operator": name,
        "daily": bool(daily),
        "defended": False,
        "leftover_xp": 0,
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


def peek(rules: dict[str, Any], state: dict[str, Any], *, risk: bool = False) -> dict[str, Any]:
    """U26. Next draw under current weights. Does not advance the seed."""
    probe = deepcopy(state)
    probe["achievements"] = set(state.get("achievements") or [])
    return _pick(rules, probe, risk=risk)


def _tick_focus(state: dict[str, Any]) -> None:
    left = int(state.get("focus_left") or 0)
    if left <= 0:
        return
    state["focus_left"] = left - 1
    if state["focus_left"] <= 0:
        state["focus"] = ""
        state["focus_left"] = 0


def _clear_risk_block(state: dict[str, Any]) -> None:
    state["risk_blocked"] = False


def _acquire(rules: dict[str, Any], state: dict[str, Any], *, action: str, risk: bool) -> dict[str, Any]:
    if risk and state.get("risk_blocked"):
        raise TraitGameError("risk_cooldown", "risk draw needs another action first")
    cost = int(rules["energy_cost"][action])
    _spend_energy(state, cost)
    row = _pick(rules, state, risk=risk)
    event = _grant(rules, state, row, action=action, energy_spent=cost)
    _tick_focus(state)
    state["risk_blocked"] = bool(risk)
    return event


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
    _tick_focus(state)
    _clear_risk_block(state)
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
    _clear_risk_block(state)
    note = {"action": "mulligan", "collection": event.get("collection", ""), "trait": event.get("trait", "")}
    state["log"].append(note)
    _achievements(state)
    return note


def _note(action: str, collection: str = "", trait: str = "", **extra: Any) -> dict[str, Any]:
    event: dict[str, Any] = {"action": action, "collection": collection, "trait": trait}
    event.update(extra)
    return event


def _apply_leftovers(rules: dict[str, Any], state: dict[str, Any]) -> int:
    gained = int(state.get("dust") or 0) * int(rules.get("dust_interest") or 0)
    if state.get("shield_armed"):
        gained += int(rules.get("shield_bank_xp") or 0)
    if state.get("difficulty") == "thesis" and len(state.get("synergies") or []) >= len(rules.get("synergies") or []):
        gained += int(rules.get("thesis_defense_xp") or 0)
        state["defended"] = True
    state["xp"] = int(state["xp"]) + gained
    state["leftover_xp"] = gained
    return gained


def _unbind(rules: dict[str, Any], state: dict[str, Any], collection: str, name: str) -> dict[str, Any]:
    if collection not in rules["collections"]:
        raise TraitGameError("unknown_collection", f"unknown collection {collection}")
    _find(rules, collection, name)
    if not _owned(state, collection, name):
        raise TraitGameError("unknown_trait", "that trait is not in the lab")
    cost = int(rules.get("unbind_dust") or 0)
    if int(state["dust"]) < cost:
        raise TraitGameError("insufficient_dust", "not enough dust to unbind")
    state["dust"] -= cost
    state["inventory"][collection].remove(name)
    if collection in state["completed"]:
        state["completed"].remove(collection)
    for item in list(rules["synergies"]):
        sid = item["id"]
        if sid in state["synergies"] and not (
            _owned(state, item["a"][0], item["a"][1]) and _owned(state, item["b"][0], item["b"][1])
        ):
            state["synergies"].remove(sid)
    state["turn"] = int(state["turn"]) + 1
    _refresh_rival(rules, state)
    _tick_focus(state)
    _clear_risk_block(state)
    event = _note("unbind", collection, name, dust_delta=-cost)
    state["log"].append(event)
    _maybe_close(rules, state)
    return event


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
            working["focus_left"] = int(rules.get("focus_duration") or 2)
            _clear_risk_block(working)
            event = _note("focus", collection)
            working["log"].append(event)
        elif action == "unfocus":
            if not working.get("focus"):
                raise TraitGameError("unknown_collection", "no focus is set")
            working["focus"] = ""
            working["focus_left"] = 0
            _clear_risk_block(working)
            event = _note("unfocus")
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
            _clear_risk_block(working)
            event = _note("arm_shield")
            working["log"].append(event)
        elif action == "scout":
            _spend_energy(working, int(rules["energy_cost"]["scout"]))
            row = peek(rules, working, risk=False)
            working["scout"] = {"collection": row["collection"], "trait": row["name"], "rarity": row["rarity"]}
            _clear_risk_block(working)
            event = _note("scout", row["collection"], row["name"], rarity=row["rarity"])
            working["log"].append(event)
            _achievements(working)
        elif action == "rest":
            gain = int(rules.get("rest_energy") or 1)
            working["energy"] = min(int(working["energy_max"]), int(working["energy"]) + gain)
            working["turn"] = int(working["turn"]) + 1
            _refresh_rival(rules, working)
            _tick_focus(working)
            _clear_risk_block(working)
            event = _note("rest", energy=gain)
            working["log"].append(event)
            _maybe_close(rules, working)
        elif action == "convert_energy":
            need = int(rules.get("convert_energy_in") or 3)
            _spend_energy(working, need)
            working["dust"] += int(rules.get("convert_dust_out") or 2)
            _clear_risk_block(working)
            event = _note("convert_energy", dust_delta=int(rules.get("convert_dust_out") or 2))
            working["log"].append(event)
        elif action == "convert_dust":
            need = int(rules.get("convert_dust_in") or 4)
            if int(working["dust"]) < need:
                raise TraitGameError("insufficient_dust", "not enough dust to convert")
            working["dust"] -= need
            working["energy"] = min(int(working["energy_max"]), int(working["energy"]) + int(rules.get("convert_energy_out") or 1))
            _clear_risk_block(working)
            event = _note("convert_dust", dust_delta=-need)
            working["log"].append(event)
        elif action == "pin":
            collection = str(args.get("collection") or "")
            trait = str(args.get("trait") or "")
            if collection not in rules["collections"]:
                raise TraitGameError("unknown_collection", f"unknown collection {collection}")
            _find(rules, collection, trait)
            if _owned(working, collection, trait):
                raise TraitGameError("already_owned", "pin an unowned trait")
            working["pin"] = {"collection": collection, "trait": trait}
            _clear_risk_block(working)
            event = _note("pin", collection, trait)
            working["log"].append(event)
        elif action == "unpin":
            if not working.get("pin"):
                raise TraitGameError("unknown_trait", "nothing is pinned")
            working["pin"] = None
            _clear_risk_block(working)
            event = _note("unpin")
            working["log"].append(event)
        elif action == "lock":
            collection = str(args.get("collection") or "")
            if collection not in rules["collections"]:
                raise TraitGameError("unknown_collection", f"unknown collection {collection}")
            if collection in working.get("locked", []):
                raise TraitGameError("unknown_collection", "that collection is already locked")
            _spend_energy(working, int(rules["energy_cost"]["lock"]))
            working.setdefault("locked", []).append(collection)
            _clear_risk_block(working)
            event = _note("lock", collection)
            working["log"].append(event)
        elif action == "unlock":
            collection = str(args.get("collection") or "")
            if collection not in (working.get("locked") or []):
                raise TraitGameError("unknown_collection", "that collection is not locked")
            working["locked"].remove(collection)
            _clear_risk_block(working)
            event = _note("unlock", collection)
            working["log"].append(event)
        elif action == "unbind":
            event = _unbind(rules, working, str(args.get("collection") or ""), str(args.get("trait") or ""))
        elif action == "finish":
            leftover = _apply_leftovers(rules, working)
            working["over"] = True
            _refresh_rival(rules, working)
            working["grade"] = _grade(working)
            _achievements(working)
            event = _note("finish", leftover_xp=leftover)
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
        "operator": state.get("operator") or "",
        "daily": bool(state.get("daily")),
        "leftover_xp": int(state.get("leftover_xp") or 0),
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


def encode_replay(state: dict[str, Any]) -> str:
    """U46. Seed, difficulty, daily flag, operator, then logged actions."""
    parts: list[str] = []
    for entry in state.get("log") or []:
        action = str(entry.get("action") or "")
        collection = str(entry.get("collection") or "")
        trait = str(entry.get("trait") or "")
        if action in {"focus", "lock", "unlock"} and collection:
            parts.append(f"{action}:{collection}")
        elif action in {"forge", "pin", "unbind", "scout"} and collection and trait:
            parts.append(f"{action}:{collection}:{trait}")
        elif action:
            parts.append(action)
    name = state.get("operator") or "-"
    daily = "1" if state.get("daily") else "0"
    return f"{state['seed']}|{state['difficulty']}|{daily}|{name}|{','.join(parts)}"


def play_replay(rules: dict[str, Any], code: str) -> dict[str, Any]:
    """U47. Replay a code. Invalid codes fail closed and do not mint a run."""
    bits = str(code or "").split("|")
    if len(bits) < 5:
        raise TraitGameError("invalid_replay", "replay code is incomplete")
    try:
        seed = int(bits[0])
    except ValueError as exc:
        raise TraitGameError("invalid_replay", "replay seed must be an integer") from exc
    difficulty = bits[1]
    daily = bits[2] == "1"
    operator = "" if bits[3] in {"", "-"} else bits[3]
    state = new_run(rules, seed=seed, difficulty=difficulty, daily=daily, operator=operator)
    raw = bits[4]
    if not raw:
        return state
    for spec in raw.split(","):
        chunks = spec.split(":")
        action = chunks[0]
        args: dict[str, str] = {}
        if len(chunks) >= 2:
            args["collection"] = chunks[1]
        if len(chunks) >= 3:
            args["trait"] = chunks[2]
        if action == "scout":
            result = act(rules, state, "scout")
        elif action in {"forge", "pin", "unbind", "focus", "lock", "unlock"}:
            result = act(rules, state, action, **args)
        else:
            result = act(rules, state, action)
        if not result["ok"]:
            raise TraitGameError("replay_rejected", result["error"])
        state = result["state"]
    return state


def hint(rules: dict[str, Any], state: dict[str, Any]) -> str:
    """U48. Deterministic coach. Not a model. Not live."""
    if state.get("over"):
        return "run closed"
    if int(state.get("energy") or 0) <= 0 and int(state.get("dust") or 0) >= int(rules.get("convert_dust_in") or 4):
        return "convert_dust"
    if int(state.get("energy") or 0) <= 0:
        return "rest"
    for collection, names in rules["collections"].items():
        owned = set(state["inventory"].get(collection, []))
        missing = [name for name in names if name not in owned]
        if len(missing) != 1:
            continue
        row = _find(rules, collection, missing[0])
        cost = int(rules["forge_dust_base"]) + _rank(rules, row["rarity"])
        if int(state.get("dust") or 0) >= cost:
            return f"forge:{collection}:{missing[0]}"
    if not state.get("scout") and int(state.get("energy") or 0) >= int(rules["energy_cost"]["scout"]) + 1:
        return "scout"
    if int(state.get("dust") or 0) < 2 and int(state.get("energy") or 0) >= int(rules.get("convert_energy_in") or 3):
        return "convert_energy"
    return "draw"


def rules_checksum(rules: dict[str, Any]) -> str:
    """U49. Hash of the public rules contract, not a live proof."""
    body = {
        "game_id": rules.get("game_id"),
        "version": rules.get("version"),
        "collections": rules.get("collections"),
        "weights": rules.get("weights"),
        "difficulties": rules.get("difficulties"),
        "synergies": rules.get("synergies"),
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
