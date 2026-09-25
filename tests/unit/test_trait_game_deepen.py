"""Hermetic tests for Trait Lab deepen systems U26–U50."""

from __future__ import annotations

import unittest

from thinkbox.trait_game.engine import (
    UPDATES,
    TraitGameError,
    act,
    bag_weights,
    encode_replay,
    hint,
    load_rules,
    new_run,
    peek,
    play_replay,
    proof_scorecard,
    rules_checksum,
)


class TestTraitGameDeepen(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = load_rules()

    def test_u26_scout_peeks_without_advancing(self) -> None:
        state = new_run(self.rules, seed=42, difficulty="lab")
        predicted = peek(self.rules, state)
        scouted = act(self.rules, state, "scout")
        self.assertTrue(scouted["ok"])
        self.assertEqual(scouted["state"]["rng"], state["rng"])
        self.assertEqual(scouted["state"]["scout"]["trait"], predicted["name"])
        drawn = act(self.rules, scouted["state"], "draw")
        self.assertEqual(drawn["event"]["trait"], predicted["name"])

    def test_u27_rest_advances_rival(self) -> None:
        state = new_run(self.rules, seed=3, difficulty="lab")
        state["energy"] = 0
        rested = act(self.rules, state, "rest")
        self.assertTrue(rested["ok"])
        self.assertEqual(rested["state"]["turn"], 1)
        self.assertEqual(rested["state"]["energy"], 1)
        self.assertEqual(rested["state"]["rival_xp"], self.rules["difficulties"]["lab"]["rival_per_turn"])

    def test_u28_convert_energy(self) -> None:
        state = new_run(self.rules, seed=3)
        converted = act(self.rules, state, "convert_energy")
        self.assertTrue(converted["ok"])
        self.assertEqual(converted["state"]["energy"], state["energy"] - 3)
        self.assertEqual(converted["state"]["dust"], 2)
        state["energy"] = 2
        denied = act(self.rules, state, "convert_energy")
        self.assertEqual(denied["error"], "insufficient_energy")

    def test_u29_convert_dust(self) -> None:
        state = new_run(self.rules, seed=3)
        state["dust"] = 4
        state["energy"] = 0
        converted = act(self.rules, state, "convert_dust")
        self.assertTrue(converted["ok"])
        self.assertEqual(converted["state"]["energy"], 1)
        self.assertEqual(converted["state"]["dust"], 0)
        poor = act(self.rules, converted["state"], "convert_dust")
        self.assertEqual(poor["error"], "insufficient_dust")

    def test_u30_pin_raises_weight(self) -> None:
        state = new_run(self.rules, seed=3)
        pinned = act(self.rules, state, "pin", collection="signals", trait="Proof")
        self.assertTrue(pinned["ok"])
        plain = next(weight for row, weight in bag_weights(self.rules, state, risk=False) if row["name"] == "Proof")
        lens = next(
            weight
            for row, weight in bag_weights(self.rules, pinned["state"], risk=False)
            if row["name"] == "Proof"
        )
        self.assertEqual(lens, plain * self.rules["pin_multiplier"])

    def test_u31_unpin_clears(self) -> None:
        state = new_run(self.rules, seed=3)
        pinned = act(self.rules, state, "pin", collection="eyes", trait="Void")["state"]
        cleared = act(self.rules, pinned, "unpin")
        self.assertIsNone(cleared["state"]["pin"])
        empty = act(self.rules, cleared["state"], "unpin")
        self.assertEqual(empty["error"], "unknown_trait")

    def test_u32_lock_skips_collection(self) -> None:
        state = new_run(self.rules, seed=3)
        locked = act(self.rules, state, "lock", collection="eyes")
        self.assertTrue(locked["ok"])
        items = bag_weights(self.rules, locked["state"], risk=False)
        self.assertTrue(all(row["collection"] != "eyes" for row, _ in items))

    def test_u33_unlock_restores(self) -> None:
        state = act(self.rules, new_run(self.rules, seed=3), "lock", collection="frames")["state"]
        opened = act(self.rules, state, "unlock", collection="frames")
        self.assertNotIn("frames", opened["state"]["locked"])
        items = bag_weights(self.rules, opened["state"], risk=False)
        self.assertTrue(any(row["collection"] == "frames" for row, _ in items))

    def test_u34_unfocus(self) -> None:
        state = act(self.rules, new_run(self.rules, seed=3), "focus", collection="signals")["state"]
        self.assertEqual(state["focus"], "signals")
        cleared = act(self.rules, state, "unfocus")
        self.assertEqual(cleared["state"]["focus"], "")
        self.assertEqual(cleared["state"]["focus_left"], 0)

    def test_u35_unbind_spends_dust(self) -> None:
        state = new_run(self.rules, seed=3)
        state["dust"] = 20
        forged = act(self.rules, state, "forge", collection="eyes", trait="Laser")["state"]
        bound = act(self.rules, forged, "unbind", collection="eyes", trait="Laser")
        self.assertTrue(bound["ok"])
        self.assertNotIn("Laser", bound["state"]["inventory"]["eyes"])
        self.assertLess(bound["state"]["dust"], forged["dust"])

    def test_u36_focus_expires(self) -> None:
        state = act(self.rules, new_run(self.rules, seed=8), "focus", collection="signals")["state"]
        self.assertEqual(state["focus_left"], 2)
        first = act(self.rules, state, "draw")["state"]
        self.assertEqual(first["focus"], "signals")
        second = act(self.rules, first, "draw")["state"]
        self.assertEqual(second["focus"], "")

    def test_u37_risk_has_cooldown(self) -> None:
        state = new_run(self.rules, seed=21, difficulty="survey")
        first = act(self.rules, state, "risk_draw")
        self.assertTrue(first["ok"])
        again = act(self.rules, first["state"], "risk_draw")
        self.assertEqual(again["error"], "risk_cooldown")
        cooled = act(self.rules, first["state"], "focus", collection="eyes")
        third = act(self.rules, cooled["state"], "risk_draw")
        self.assertTrue(third["ok"])

    def test_u38_pity_grows_with_turns(self) -> None:
        state = new_run(self.rules, seed=1)
        early = bag_weights(self.rules, state, risk=False)
        state["turn"] = 5
        late = bag_weights(self.rules, state, risk=False)
        pulse_early = next(weight for row, weight in early if row["name"] == "Pulse")
        pulse_late = next(weight for row, weight in late if row["name"] == "Pulse")
        self.assertEqual(pulse_late, pulse_early + 5 * self.rules["pity_step"])

    def test_u39_last_stand_raises_rival(self) -> None:
        state = new_run(self.rules, seed=2, difficulty="lab")
        state["turn"] = 11
        state["energy"] = 2
        done = act(self.rules, state, "draw")
        self.assertTrue(done["ok"])
        self.assertGreater(done["state"]["rival_xp"], 11 * self.rules["difficulties"]["lab"]["rival_per_turn"])

    def test_u40_late_set_bonus(self) -> None:
        state = new_run(self.rules, seed=3, difficulty="survey")
        state["turn"] = 14
        state["dust"] = 99
        eyes = list(self.rules["collections"]["eyes"])
        for trait in eyes[:-1]:
            state["inventory"]["eyes"].append(trait)
        before = state["xp"]
        hit = act(self.rules, state, "forge", collection="eyes", trait=eyes[-1])
        self.assertTrue(hit["event"].get("late_set"))
        self.assertGreaterEqual(hit["state"]["xp"], before + self.rules["set_bonus"]["eyes"] + self.rules["late_set_bonus"])

    def test_u41_dust_interest_on_finish(self) -> None:
        state = new_run(self.rules, seed=1)
        state["dust"] = 5
        finished = act(self.rules, state, "finish")
        self.assertEqual(finished["state"]["leftover_xp"], 5 * self.rules["dust_interest"])
        self.assertEqual(finished["state"]["xp"], 5 * self.rules["dust_interest"])

    def test_u42_shield_residue(self) -> None:
        state = new_run(self.rules, seed=1)
        armed = act(self.rules, state, "arm_shield")["state"]
        finished = act(self.rules, armed, "finish")
        self.assertEqual(finished["state"]["leftover_xp"], self.rules["shield_bank_xp"])

    def test_u43_thesis_defense(self) -> None:
        state = new_run(self.rules, seed=1, difficulty="thesis")
        state["synergies"] = [item["id"] for item in self.rules["synergies"]]
        finished = act(self.rules, state, "finish")
        self.assertTrue(finished["state"]["defended"])
        self.assertIn("defense", finished["state"]["achievements"])
        self.assertGreaterEqual(finished["state"]["leftover_xp"], self.rules["thesis_defense_xp"])

    def test_u44_daily_mark(self) -> None:
        state = new_run(self.rules, seed=20260925, daily=True)
        finished = act(self.rules, state, "finish")
        self.assertIn("daily", finished["state"]["achievements"])
        self.assertTrue(proof_scorecard(finished["state"])["daily"])

    def test_u45_operator_on_proof(self) -> None:
        state = new_run(self.rules, seed=7, operator="ada-lovelace")
        card = proof_scorecard(act(self.rules, state, "finish")["state"])
        self.assertEqual(card["operator"], "ada-lovelace")

    def test_u46_encode_replay(self) -> None:
        state = act(self.rules, new_run(self.rules, seed=42, difficulty="lab"), "draw")["state"]
        code = encode_replay(state)
        self.assertTrue(code.startswith("42|lab|0|-|"))
        self.assertIn("draw", code)

    def test_u47_play_replay_matches_and_rejects(self) -> None:
        first = act(self.rules, new_run(self.rules, seed=42, difficulty="lab"), "draw")["state"]
        replayed = play_replay(self.rules, encode_replay(first))
        self.assertEqual(replayed["xp"], first["xp"])
        self.assertEqual(replayed["log"][0]["trait"], first["log"][0]["trait"])
        with self.assertRaises(TraitGameError) as err:
            play_replay(self.rules, "bad")
        self.assertEqual(err.exception.code, "invalid_replay")

    def test_u48_hint_is_deterministic(self) -> None:
        empty = new_run(self.rules, seed=1)
        self.assertEqual(hint(self.rules, empty), "scout")
        empty["energy"] = 0
        self.assertEqual(hint(self.rules, empty), "rest")
        empty["dust"] = 4
        self.assertEqual(hint(self.rules, empty), "convert_dust")

    def test_u49_rules_checksum_stable(self) -> None:
        digest = rules_checksum(self.rules)
        self.assertEqual(digest, rules_checksum(self.rules))
        self.assertEqual(len(digest), 64)

    def test_u50_catalog_and_leftover_once(self) -> None:
        self.assertEqual(len(UPDATES), 50)
        state = new_run(self.rules, seed=1)
        state["dust"] = 2
        finished = act(self.rules, state, "finish")["state"]
        self.assertEqual(finished["leftover_xp"], 16)
        blocked = act(self.rules, finished, "finish")
        self.assertEqual(blocked["error"], "run_complete")


if __name__ == "__main__":
    unittest.main()
