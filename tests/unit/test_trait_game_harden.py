"""Harden Trait Lab: clock leftovers, undo after close, honest errors."""

from __future__ import annotations

import copy
import unittest

from thinkbox.trait_game.engine import (
    TraitGameError,
    act,
    load_rules,
    new_run,
    proof_scorecard,
    rules_checksum,
)


class TestTraitGameHarden(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = load_rules()

    def test_clock_close_applies_leftover_once(self) -> None:
        state = new_run(self.rules, seed=2, difficulty="thesis")
        state["turn"] = state["turns_max"] - 1
        state["energy"] = 5
        state["dust"] = 4
        closed = act(self.rules, state, "draw")
        self.assertTrue(closed["ok"])
        self.assertTrue(closed["state"]["over"])
        self.assertEqual(closed["state"]["leftover_xp"], 4 * self.rules["dust_interest"])
        again = act(self.rules, closed["state"], "draw")
        self.assertEqual(again["error"], "run_complete")
        self.assertEqual(again["state"]["leftover_xp"], closed["state"]["leftover_xp"])

    def test_undo_after_finish(self) -> None:
        state = new_run(self.rules, seed=6, difficulty="lab")
        drawn = act(self.rules, state, "draw")["state"]
        filed = act(self.rules, drawn, "finish")["state"]
        self.assertTrue(filed["over"])
        back = act(self.rules, filed, "undo")
        self.assertTrue(back["ok"])
        self.assertFalse(back["state"]["over"])
        self.assertEqual(back["state"]["turn"], drawn["turn"])

    def test_mulligan_after_clock_close(self) -> None:
        state = new_run(self.rules, seed=2, difficulty="thesis")
        state["turn"] = state["turns_max"] - 1
        state["energy"] = 5
        closed = act(self.rules, state, "draw")["state"]
        self.assertTrue(closed["over"])
        back = act(self.rules, closed, "mulligan")
        self.assertTrue(back["ok"])
        self.assertFalse(back["state"]["over"])
        self.assertEqual(back["state"]["turn"], state["turn"])

    def test_empty_bag_is_not_a_risk_miss(self) -> None:
        state = new_run(self.rules, seed=3)
        state["energy"] = 10
        for collection in self.rules["collections"]:
            state = act(self.rules, state, "lock", collection=collection)["state"]
        denied = act(self.rules, state, "draw")
        self.assertEqual(denied["error"], "no_targets")
        self.assertEqual(denied["state"]["energy"], state["energy"])

    def test_focus_does_not_tick_on_rest(self) -> None:
        focused = act(self.rules, new_run(self.rules, seed=8), "focus", collection="signals")["state"]
        rested = act(self.rules, focused, "rest")["state"]
        self.assertEqual(rested["focus"], "signals")
        self.assertEqual(rested["focus_left"], 2)

    def test_distinct_fail_closed_codes(self) -> None:
        state = new_run(self.rules, seed=3)
        self.assertEqual(act(self.rules, state, "unfocus")["error"], "no_focus")
        self.assertEqual(act(self.rules, state, "unpin")["error"], "nothing_pinned")
        locked = act(self.rules, state, "lock", collection="eyes")["state"]
        self.assertEqual(act(self.rules, locked, "lock", collection="eyes")["error"], "already_locked")
        self.assertEqual(act(self.rules, state, "unlock", collection="eyes")["error"], "not_locked")

    def test_operator_is_ascii(self) -> None:
        state = new_run(self.rules, seed=7, operator="Ada Λovelace!")
        self.assertEqual(state["operator"], "Adaovelace")

    def test_proof_strips_live_claim(self) -> None:
        state = act(self.rules, new_run(self.rules, seed=1), "finish")["state"]
        state["live_verified"] = True
        card = proof_scorecard(state)
        self.assertFalse(card["live_verified"])

    def test_load_rules_rejects_broken_contract(self) -> None:
        broken = copy.deepcopy(self.rules)
        broken["live_verified"] = True
        with self.assertRaises(TraitGameError) as err:
            load_rules.__wrapped__(broken) if hasattr(load_rules, "__wrapped__") else _validate(broken)
        self.assertEqual(err.exception.code, "invalid_rules")

    def test_checksum_moves_when_weights_change(self) -> None:
        other = copy.deepcopy(self.rules)
        other["weights"]["common"] = 1
        self.assertNotEqual(rules_checksum(self.rules), rules_checksum(other))


def _validate(rules: dict) -> None:
    from thinkbox.trait_game.engine import validate_rules

    validate_rules(rules)


if __name__ == "__main__":
    unittest.main()
