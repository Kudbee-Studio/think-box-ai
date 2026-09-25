"""Hermetic tests for the 25 Trait Lab updates."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from thinkbox.trait_game.engine import (
    UPDATES,
    act,
    bag_weights,
    daily_seed,
    load_rules,
    new_run,
    proof_scorecard,
    rank_board,
    updates,
)

ROOT = Path(__file__).resolve().parents[2]


class TestTraitGame(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = load_rules()

    def test_u01_seeded_run_is_replayable(self) -> None:
        first = new_run(self.rules, seed=42, difficulty="lab")
        second = new_run(self.rules, seed=42, difficulty="lab")
        a = act(self.rules, first, "draw")
        b = act(self.rules, second, "draw")
        self.assertTrue(a["ok"] and b["ok"])
        self.assertEqual(a["event"]["trait"], b["event"]["trait"])
        self.assertEqual(a["event"]["collection"], b["event"]["collection"])
        other = act(self.rules, new_run(self.rules, seed=99, difficulty="lab"), "draw")
        self.assertTrue(other["ok"])

    def test_u02_energy_budget_fail_closed(self) -> None:
        state = new_run(self.rules, seed=7, difficulty="lab")
        state["energy"] = 0
        before = json.dumps(state["inventory"])
        result = act(self.rules, state, "draw")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "insufficient_energy")
        self.assertEqual(result["state"]["energy"], 0)
        self.assertEqual(json.dumps(result["state"]["inventory"]), before)
        self.assertEqual(result["state"]["turn"], 0)

    def test_u03_weights_prefer_common_mass(self) -> None:
        state = new_run(self.rules, seed=1, difficulty="survey")
        items = bag_weights(self.rules, state, risk=False)
        common = sum(weight for row, weight in items if row["rarity"] == "common")
        mythic = sum(weight for row, weight in items if row["rarity"] == "mythic")
        self.assertGreater(common, mythic)

    def test_u04_five_collections(self) -> None:
        self.assertEqual(len(self.rules["collections"]), 5)
        state = new_run(self.rules, seed=3)
        self.assertEqual(set(state["inventory"]), set(self.rules["collections"]))

    def test_u05_set_bonus_once(self) -> None:
        state = new_run(self.rules, seed=3, difficulty="survey")
        state["energy"] = 30
        eyes = list(self.rules["collections"]["eyes"])
        for trait in eyes[:-1]:
            state["dust"] = 99
            forged = act(self.rules, state, "forge", collection="eyes", trait=trait)
            self.assertTrue(forged["ok"], forged["error"])
            state = forged["state"]
        before = state["xp"]
        done = act(self.rules, state, "forge", collection="eyes", trait=eyes[-1])
        self.assertTrue(done["ok"])
        self.assertIn("eyes", done["state"]["completed"])
        self.assertGreaterEqual(done["state"]["xp"], before + self.rules["set_bonus"]["eyes"])
        again = act(self.rules, done["state"], "forge", collection="eyes", trait=eyes[-1])
        self.assertEqual(again["error"], "already_owned")

    def test_u06_duplicate_makes_dust_and_breaks_combo(self) -> None:
        state = new_run(self.rules, seed=11, difficulty="survey")
        state["energy"] = 10
        pulled = act(self.rules, state, "draw")
        self.assertTrue(pulled["ok"])
        owned = pulled["state"]
        owned["rng"] = 1
        forced = owned
        # Fill the roll by forging nothing: draw until a duplicate appears or bound the loop.
        seen = False
        cursor = forced
        for _ in range(40):
            cursor["energy"] = 5
            step = act(self.rules, cursor, "draw")
            if not step["ok"]:
                break
            if step["event"]["duplicate"]:
                self.assertGreater(step["event"]["dust_delta"], 0)
                self.assertEqual(step["state"]["combo"], 0)
                seen = True
                break
            cursor = step["state"]
        self.assertTrue(seen)

    def test_u07_forge_spends_dust(self) -> None:
        state = new_run(self.rules, seed=4, difficulty="lab")
        poor = act(self.rules, state, "forge", collection="signals", trait="Proof")
        self.assertEqual(poor["error"], "insufficient_dust")
        state["dust"] = 20
        forged = act(self.rules, state, "forge", collection="signals", trait="Proof")
        self.assertTrue(forged["ok"])
        self.assertIn("Proof", forged["state"]["inventory"]["signals"])
        self.assertLess(forged["state"]["dust"], 20)

    def test_u08_combo_raises_xp(self) -> None:
        state = new_run(self.rules, seed=5, difficulty="survey")
        state["energy"] = 20
        first = act(self.rules, state, "draw")
        second = act(self.rules, first["state"], "draw")
        self.assertGreater(second["state"]["combo"], first["state"]["combo"])
        if not second["event"]["duplicate"] and not first["event"]["duplicate"]:
            self.assertGreaterEqual(second["state"]["combo"], 2)

    def test_u09_focus_triples_collection(self) -> None:
        state = new_run(self.rules, seed=8)
        focused = act(self.rules, state, "focus", collection="signals")["state"]
        plain = bag_weights(self.rules, state, risk=False)
        lens = bag_weights(self.rules, focused, risk=False)
        plain_pulse = next(w for row, w in plain if row["name"] == "Pulse")
        lens_pulse = next(w for row, w in lens if row["name"] == "Pulse")
        self.assertEqual(lens_pulse, plain_pulse * self.rules["focus_multiplier"])
        bad = act(self.rules, state, "focus", collection="nope")
        self.assertEqual(bad["error"], "unknown_collection")

    def test_u10_mulligan_once(self) -> None:
        state = new_run(self.rules, seed=15, difficulty="lab")
        drawn = act(self.rules, state, "draw")
        self.assertTrue(drawn["ok"])
        back = act(self.rules, drawn["state"], "mulligan")
        self.assertTrue(back["ok"])
        self.assertTrue(back["state"]["mulligan_used"])
        self.assertEqual(back["state"]["turn"], 0)
        drawn_collection = drawn["event"]["collection"]
        self.assertNotIn(drawn["event"]["trait"], back["state"]["inventory"][drawn_collection])
        spent = act(self.rules, back["state"], "mulligan")
        self.assertEqual(spent["error"], "mulligan_spent")

    def test_u11_turn_clock_ends_run(self) -> None:
        state = new_run(self.rules, seed=2, difficulty="thesis")
        state["turn"] = state["turns_max"] - 1
        state["energy"] = 5
        done = act(self.rules, state, "draw")
        self.assertTrue(done["ok"])
        self.assertTrue(done["state"]["over"])
        self.assertTrue(done["state"]["grade"])
        blocked = act(self.rules, done["state"], "draw")
        self.assertEqual(blocked["error"], "run_complete")

    def test_u12_jackpot_when_combo_is_hot(self) -> None:
        state = new_run(self.rules, seed=3, difficulty="survey")
        state["combo"] = 3
        state["dust"] = 99
        state["energy"] = 20
        eyes = list(self.rules["collections"]["eyes"])
        for trait in eyes[:-1]:
            state = act(self.rules, state, "forge", collection="eyes", trait=trait)["state"]
            state["dust"] = 99
            state["combo"] = 3
        hit = act(self.rules, state, "forge", collection="eyes", trait=eyes[-1])
        self.assertTrue(hit["event"]["jackpot"])
        self.assertGreaterEqual(hit["event"]["xp_delta"], self.rules["set_bonus"]["eyes"] + self.rules["jackpot_xp"])

    def test_u13_synergy_once(self) -> None:
        state = new_run(self.rules, seed=1, difficulty="survey")
        state["dust"] = 30
        state = act(self.rules, state, "forge", collection="eyes", trait="Laser")["state"]
        state["dust"] = 30
        heated = act(self.rules, state, "forge", collection="grounds", trait="Fire")
        self.assertIn("heat", heated["state"]["synergies"])
        heated["state"]["dust"] = 30
        again = act(self.rules, heated["state"], "forge", collection="frames", trait="Obsidian")
        self.assertEqual(again["state"]["synergies"].count("heat"), 1)

    def test_u14_risk_draw_skips_commons(self) -> None:
        state = new_run(self.rules, seed=21, difficulty="survey")
        items = bag_weights(self.rules, state, risk=True)
        self.assertTrue(items)
        self.assertTrue(all(row["rarity"] != "common" for row, _ in items))
        state["energy"] = 1
        denied = act(self.rules, state, "risk_draw")
        self.assertEqual(denied["error"], "insufficient_energy")

    def test_u15_shield_multiplies_next_new_trait(self) -> None:
        state = new_run(self.rules, seed=6, difficulty="survey")
        armed = act(self.rules, state, "arm_shield")
        self.assertTrue(armed["state"]["shield_armed"])
        drawn = act(self.rules, armed["state"], "draw")
        if not drawn["event"]["duplicate"]:
            self.assertTrue(drawn["event"]["shield_consumed"])
            self.assertFalse(drawn["state"]["shield_armed"])

    def test_u16_rival_pace_tracks_turns(self) -> None:
        state = new_run(self.rules, seed=6, difficulty="lab")
        step = act(self.rules, state, "draw")["state"]
        self.assertEqual(step["rival_xp"], self.rules["difficulties"]["lab"]["rival_per_turn"])

    def test_u17_letter_grade(self) -> None:
        state = new_run(self.rules, seed=1, difficulty="survey")
        state["completed"] = list(self.rules["collections"])
        state["xp"] = 1
        state["rival_xp"] = 9999
        finished = act(self.rules, state, "finish")
        self.assertEqual(finished["state"]["grade"], "S")

    def test_u18_achievements(self) -> None:
        state = new_run(self.rules, seed=6, difficulty="lab")
        step = act(self.rules, state, "draw")["state"]
        self.assertIn("spark", step["achievements"])

    def test_u19_undo_one_step(self) -> None:
        state = new_run(self.rules, seed=6, difficulty="lab")
        step = act(self.rules, state, "draw")["state"]
        back = act(self.rules, step, "undo")
        self.assertTrue(back["ok"])
        self.assertEqual(back["state"]["turn"], 0)
        self.assertEqual(back["state"]["xp"], 0)
        empty = act(self.rules, back["state"], "undo")
        self.assertEqual(empty["error"], "nothing_to_undo")

    def test_u20_replay_log(self) -> None:
        state = new_run(self.rules, seed=6)
        step = act(self.rules, state, "draw")["state"]
        self.assertEqual(step["log"][0]["action"], "draw")
        self.assertIn("trait", step["log"][0])

    def test_u21_leaderboard_orders_xp(self) -> None:
        board = rank_board(
            [
                {"name": "ada", "xp": 100, "grade": "C", "turn": 9},
                {"name": "lin", "xp": 240, "grade": "B", "turn": 8},
                {"name": "kai", "xp": 240, "grade": "A", "turn": 8},
            ]
        )
        self.assertEqual([row["name"] for row in board], ["kai", "lin", "ada"])

    def test_u22_daily_seed(self) -> None:
        self.assertEqual(daily_seed("2026-09-25"), 20260925)
        with self.assertRaises(Exception):
            daily_seed("yesterday")

    def test_u23_difficulty_tiers(self) -> None:
        survey = new_run(self.rules, seed=1, difficulty="survey")
        thesis = new_run(self.rules, seed=1, difficulty="thesis")
        self.assertGreater(survey["turns_max"], thesis["turns_max"])
        self.assertGreater(survey["energy"], thesis["energy"])
        bad = act(self.rules, survey, "draw")
        self.assertTrue(bad["ok"])
        with self.assertRaises(Exception):
            new_run(self.rules, seed=1, difficulty="mythic")

    def test_u24_unknown_action_is_rejected(self) -> None:
        state = new_run(self.rules, seed=1)
        result = act(self.rules, state, "mint")
        self.assertEqual(result["error"], "unknown_action")
        self.assertEqual(result["state"]["xp"], 0)

    def test_u25_proof_is_stable_and_not_live(self) -> None:
        state = act(self.rules, new_run(self.rules, seed=42, difficulty="lab"), "finish")["state"]
        card = proof_scorecard(state)
        self.assertFalse(card["live_verified"])
        self.assertEqual(card["proof_sha256"], proof_scorecard(state)["proof_sha256"])
        self.assertEqual(len(card["proof_sha256"]), 64)

    def test_update_catalog_has_25(self) -> None:
        self.assertEqual(len(UPDATES), 25)
        self.assertEqual(updates(self.rules), UPDATES)
        text = (ROOT / "public/nfts/trait_game.js").read_text(encoding="utf-8")
        self.assertIn("1664525", text)
        self.assertIn("trait-lab", text)


if __name__ == "__main__":
    unittest.main()
