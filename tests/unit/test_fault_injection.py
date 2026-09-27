"""Tests for the fault-injection (chaos) harness.

Flight readiness item 3: does anything report a false success under
timeouts, garbage, or a persistently lying provider? These tests prove
both directions -- the harness passes on the real (honest) session, and
a hand-rolled "cheating" session that always claims success is caught.
"""

from __future__ import annotations

import unittest

from thinkbox.fault_injection import (
    EXPECTED_OUTCOME,
    FAULT_FAMILIES,
    FaultCampaignReport,
    FaultKind,
    FaultTrial,
    TimeoutFault,
    Verdict,
    build_trials,
    faulted_response,
    judge,
    run_fault_campaign,
    run_trial,
)
from thinkbox.pop_arena import (
    BudgetExhausted,
    VerifiedCallResult,
    extract_json,
    system_prompt_for_v2,
    verify_v2,
)


class TestFaultedResponses(unittest.TestCase):
    def test_malformed_json_does_not_parse(self) -> None:
        text = faulted_response(FaultKind.MALFORMED_JSON, "compute", {"expected": 13})
        self.assertEqual(extract_json(text), {})

    def test_truncated_json_does_not_parse(self) -> None:
        text = faulted_response(FaultKind.TRUNCATED_JSON, "compute", {"expected": 13})
        self.assertEqual(extract_json(text), {})

    def test_wrong_key_response_omits_answer_key(self) -> None:
        for family in ("compute", "distractor", "multifield"):
            text = faulted_response(FaultKind.WRONG_KEY_TRANSIENT, family, {"expected": 5})
            self.assertNotIn('"answer"', text)

    def test_distractor_wrong_key_is_the_documented_distractor_key(self) -> None:
        text = faulted_response(FaultKind.WRONG_KEY_TRANSIENT, "distractor", {"expected": 5})
        self.assertIn('"result"', text)

    def test_off_by_one_is_schema_valid_but_wrong_value(self) -> None:
        spec = {"expected": 10, "parity": "even", "double": 20}
        text = faulted_response(FaultKind.OFF_BY_ONE, "compute", spec)
        parsed = extract_json(text)
        self.assertEqual(parsed, {"answer": 11})

    def test_off_by_one_multifield_keeps_other_fields_consistent(self) -> None:
        spec = {"expected": 10, "parity": "even", "double": 20}
        parsed = extract_json(faulted_response(FaultKind.OFF_BY_ONE, "multifield", spec))
        # Only the answer is wrong; parity/double still describe the WRONG
        # answer's neighbor truthfully-shaped, proving verify_v2 catches
        # the value mismatch rather than a shape mismatch.
        self.assertEqual(parsed["answer"], 11)

    def test_multifield_inconsistent_answer_is_correct_but_double_is_not(self) -> None:
        spec = {"expected": 10, "parity": "even", "double": 20}
        parsed = extract_json(faulted_response(FaultKind.MULTIFIELD_INCONSISTENT, "multifield", spec))
        self.assertEqual(parsed["answer"], 10)
        self.assertEqual(parsed["double"], 22)  # pins the exact +2 offset, not just "wrong"

    def test_budget_starve_response_is_retryable_wrong_key(self) -> None:
        spec = {"expected": 5}
        text = faulted_response(FaultKind.BUDGET_STARVE, "compute", spec)
        valid, taxonomy = verify_v2("compute", extract_json(text), spec)
        self.assertFalse(valid)
        self.assertEqual(taxonomy, "wrong-key")

    def test_timeout_and_persistent_have_no_scripted_response(self) -> None:
        # Documented contract: these two fire an exception path, not a
        # single scripted string, so faulted_response is never called for
        # them by run_trial. Calling it directly should say so, not crash
        # with a confusing KeyError deep in string formatting.
        with self.assertRaises(ValueError):
            faulted_response(FaultKind.TIMEOUT, "compute", {"expected": 1})


class TestBuildTrials(unittest.TestCase):
    def test_every_fault_kind_produces_at_least_one_trial(self) -> None:
        trials = build_trials()
        kinds_seen = {t.kind for t in trials}
        self.assertEqual(kinds_seen, set(FaultKind))

    def test_trial_count_matches_fault_families_table(self) -> None:
        trials = build_trials()
        expected = sum(len(families) for families in FAULT_FAMILIES.values())
        self.assertEqual(len(trials), expected)

    def test_task_ids_are_unique(self) -> None:
        ids = [t.task_id for t in build_trials()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_filtering_by_fault_kind(self) -> None:
        trials = build_trials((FaultKind.TIMEOUT,))
        self.assertTrue(all(t.kind == FaultKind.TIMEOUT for t in trials))
        self.assertEqual(len(trials), len(FAULT_FAMILIES[FaultKind.TIMEOUT]))

    def test_multifield_inconsistent_only_applies_to_multifield(self) -> None:
        trials = build_trials((FaultKind.MULTIFIELD_INCONSISTENT,))
        self.assertEqual({t.family for t in trials}, {"multifield"})


class TestRunTrialAgainstRealSession(unittest.TestCase):
    """These drive the real VerifiedRetrySession -- an integration test of
    production code, not a mock of it."""

    def _trial(self, kind: FaultKind, family: str = "compute", variant: str = "add_small") -> FaultTrial:
        prompt, spec = system_prompt_for_v2(family, variant)
        return FaultTrial(
            kind=kind, family=family, variant=variant,
            task_id=f"t-{kind.value}-{family}", prompt=prompt, spec=spec,
            expected=EXPECTED_OUTCOME[kind],
        )

    def test_malformed_json_never_succeeds(self) -> None:
        result, exc = run_trial(self._trial(FaultKind.MALFORMED_JSON))
        self.assertIsNone(exc)
        self.assertFalse(result.valid)

    def test_off_by_one_never_succeeds_and_never_retries(self) -> None:
        result, exc = run_trial(self._trial(FaultKind.OFF_BY_ONE))
        self.assertIsNone(exc)
        self.assertFalse(result.valid)
        self.assertEqual(result.taxonomy, "arithmetic")
        self.assertFalse(result.converted)
        self.assertEqual(result.attempts, 1)  # arithmetic is not retryable

    def test_wrong_key_transient_recovers_on_retry(self) -> None:
        result, exc = run_trial(self._trial(FaultKind.WRONG_KEY_TRANSIENT, "distractor", "wrongkey"))
        self.assertIsNone(exc)
        self.assertTrue(result.valid)
        self.assertTrue(result.converted)
        self.assertEqual(result.attempts, 2)

    def test_wrong_key_persistent_exhausts_the_one_retry_and_still_fails(self) -> None:
        result, exc = run_trial(self._trial(FaultKind.WRONG_KEY_PERSISTENT, "distractor", "wrongkey"))
        self.assertIsNone(exc)
        self.assertFalse(result.valid)
        self.assertEqual(result.attempts, 2)  # it DID retry, and still failed honestly

    def test_timeout_raises_and_does_not_return_a_result(self) -> None:
        result, exc = run_trial(self._trial(FaultKind.TIMEOUT))
        self.assertIsNone(result)
        self.assertIsInstance(exc, TimeoutFault)

    def test_budget_starve_raises_budget_exhausted(self) -> None:
        result, exc = run_trial(self._trial(FaultKind.BUDGET_STARVE, "distractor", "wrongkey"))
        self.assertIsNone(result)
        self.assertIsInstance(exc, BudgetExhausted)

    def test_multifield_inconsistent_never_succeeds(self) -> None:
        result, exc = run_trial(self._trial(FaultKind.MULTIFIELD_INCONSISTENT, "multifield", "parity"))
        self.assertIsNone(exc)
        self.assertFalse(result.valid)
        self.assertEqual(result.taxonomy, "inconsistency")


class TestJudgeCatchesACheatingSession(unittest.TestCase):
    """The load-bearing test: if a session were buggy and claimed success
    on a fault that should never succeed, the judge must call it out as
    SILENT_SUCCESS -- not quietly agree with it."""

    def _trial(self, expected: str) -> FaultTrial:
        return FaultTrial(
            kind=FaultKind.OFF_BY_ONE, family="compute", variant="add_small",
            task_id="cheat", prompt="p", spec={"expected": 13}, expected=expected,
        )

    def test_fabricated_valid_true_on_never_succeeds_is_silent_success(self) -> None:
        fake = VerifiedCallResult(
            valid=True, taxonomy="valid", attempts=1, retries_used=0,
            converted=False, trace=None, calls_spent=1,  # type: ignore[arg-type]
        )
        self.assertEqual(judge(self._trial("never_succeeds"), fake, None), Verdict.SILENT_SUCCESS)

    def test_honest_valid_false_on_never_succeeds_is_loud_failure(self) -> None:
        fake = VerifiedCallResult(
            valid=False, taxonomy="arithmetic", attempts=1, retries_used=0,
            converted=False, trace=None, calls_spent=1,  # type: ignore[arg-type]
        )
        self.assertEqual(judge(self._trial("never_succeeds"), fake, None), Verdict.LOUD_FAILURE)

    def test_valid_without_conversion_on_recovers_is_silent_success(self) -> None:
        # valid=True but converted=False on a "recovers" trial means the
        # FIRST (necessarily-faulted) attempt was accepted -- exactly the
        # bug this harness hunts, and must not be waved through as
        # RECOVERED_SUCCESS just because valid happens to be True.
        fake = VerifiedCallResult(
            valid=True, taxonomy="valid", attempts=1, retries_used=0,
            converted=False, trace=None, calls_spent=1,  # type: ignore[arg-type]
        )
        self.assertEqual(judge(self._trial("recovers"), fake, None), Verdict.SILENT_SUCCESS)

    def test_valid_false_on_recovers_is_under_recovered_not_silently_fine(self) -> None:
        # A fixable fault that the retry mechanism failed to fix: safe
        # (no fabricated success) but a real, distinctly-labeled regression
        # in a guarantee Arena v3 proved (conversion of retryable faults).
        fake = VerifiedCallResult(
            valid=False, taxonomy="wrong-key", attempts=2, retries_used=1,
            converted=False, trace=None, calls_spent=2,  # type: ignore[arg-type]
        )
        self.assertEqual(judge(self._trial("recovers"), fake, None), Verdict.UNDER_RECOVERED)

    def test_unexpected_exception_type_is_crashed_not_silently_passed(self) -> None:
        self.assertEqual(judge(self._trial("never_succeeds"), None, RuntimeError("boom")), Verdict.CRASHED)

    def test_missing_timeout_on_timeout_trial_with_valid_result_is_silent_success(self) -> None:
        fake = VerifiedCallResult(
            valid=True, taxonomy="valid", attempts=1, retries_used=0,
            converted=False, trace=None, calls_spent=1,  # type: ignore[arg-type]
        )
        self.assertEqual(judge(self._trial("raises_timeout"), fake, None), Verdict.SILENT_SUCCESS)

    def test_unknown_expectation_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            judge(self._trial("no-such-expectation"), None, None)

    def test_no_exception_and_no_result_on_timeout_trial_is_unexpected(self) -> None:
        # The fault was built to always raise; if it somehow raised
        # nothing AND returned nothing, that is a harness-construction
        # anomaly, not a crash and not a fabricated success.
        self.assertEqual(judge(self._trial("raises_timeout"), None, None), Verdict.UNEXPECTED)

    def test_fault_trial_is_frozen(self) -> None:
        trial = self._trial("never_succeeds")
        with self.assertRaises(Exception):
            trial.expected = "recovers"  # type: ignore[misc]


class TestFullCampaign(unittest.TestCase):
    def test_real_campaign_has_zero_silent_successes_and_passes(self) -> None:
        report = run_fault_campaign()
        self.assertEqual(report.silent_successes, 0, report.to_dict())
        self.assertEqual(report.crashed, 0, report.to_dict())
        self.assertEqual(report.unexpected, 0, report.to_dict())
        self.assertTrue(report.passed)

    def test_campaign_covers_every_declared_trial(self) -> None:
        report = run_fault_campaign()
        self.assertEqual(report.total, len(build_trials()))

    def test_campaign_is_deterministic_across_runs(self) -> None:
        a = run_fault_campaign().to_dict()
        b = run_fault_campaign().to_dict()
        self.assertEqual(a, b)

    def test_recovered_successes_are_exactly_the_transient_trials(self) -> None:
        report = run_fault_campaign()
        self.assertEqual(
            report.recovered_successes,
            len(FAULT_FAMILIES[FaultKind.WRONG_KEY_TRANSIENT]),
        )

    def test_to_dict_is_json_serializable(self) -> None:
        import json
        json.dumps(run_fault_campaign().to_dict())


class TestFaultCampaignReportPassedProperty(unittest.TestCase):
    """Direct tests of the pass/fail gate, independent of a real campaign
    run, so each failure category is pinned on its own rather than relying
    on the real campaign happening to never exercise it."""

    def _report(self, **overrides: int) -> FaultCampaignReport:
        base = dict(silent_successes=0, crashed=0, unexpected=0, under_recovered=0)
        base.update(overrides)
        return FaultCampaignReport(**base)

    def test_all_zero_passes(self) -> None:
        self.assertTrue(self._report().passed)

    def test_one_silent_success_fails_even_if_everything_else_is_clean(self) -> None:
        self.assertFalse(self._report(silent_successes=1).passed)

    def test_one_crash_fails(self) -> None:
        self.assertFalse(self._report(crashed=1).passed)

    def test_one_unexpected_fails(self) -> None:
        self.assertFalse(self._report(unexpected=1).passed)

    def test_one_under_recovered_fails(self) -> None:
        self.assertFalse(self._report(under_recovered=1).passed)


if __name__ == "__main__":
    unittest.main()
