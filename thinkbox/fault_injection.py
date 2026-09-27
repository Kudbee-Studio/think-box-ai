"""Fault-injection (chaos) harness for verified execution.

Flight readiness item 3 (docs/guides/flight-readiness.md): "Under timeouts,
garbage and crashes, does anything report false success?"

Item 1 (mutation testing) asks whether the tests catch bugs in the code.
Item 2 (Power of 10) asks whether the code follows safe coding rules. This
module asks a different question of the *running system*: drive a real
``VerifiedRetrySession`` end to end against a provider that is actively
lying -- truncated JSON, a persistent wrong key, a schema-valid answer that
is off by one, a starved retry budget, a hung call -- and mechanically judge
every outcome against ground truth. The judge never trusts the verifier's
own boolean; it independently knows, from how the fault was constructed,
whether a genuine success was possible. The one property this campaign
exists to prove: a response that should never be accepted is never
reported ``valid=True``. AGENTS.md 4.4 calls that a "fake success"; this is
the adversarial proof that the verified-execution path does not produce one.

Nothing here calls a model or the network. The "provider" is a pure
function returning pre-scripted, deterministically corrupted JSON.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from thinkbox.pop_arena import (
    BudgetExhausted,
    VerifiedCallResult,
    VerifiedRetryConfig,
    VerifiedRetrySession,
    deterministic_emission_v2,
    extract_json,
    retry_prompt_for,
    system_prompt_for_v2,
    verify_v2,
)


class TimeoutFault(Exception):
    """Raised by a faulted provider standing in for a hung/timed-out call."""


class FaultKind(str, Enum):
    """One realistic provider failure mode, each mapped onto a real
    verify_v2 taxonomy branch so the campaign exercises production code,
    not a bespoke judge."""

    MALFORMED_JSON = "malformed_json"
    TRUNCATED_JSON = "truncated_json"
    WRONG_KEY_TRANSIENT = "wrong_key_transient"
    WRONG_KEY_PERSISTENT = "wrong_key_persistent"
    OFF_BY_ONE = "off_by_one"
    MULTIFIELD_INCONSISTENT = "multifield_inconsistent"
    TIMEOUT = "timeout"
    BUDGET_STARVE = "budget_starve"


# Families each fault kind is meaningful against. WRONG_KEY_TRANSIENT is
# only retryable for "distractor" (that family's verifier reports
# distractor-compliance) and "compute"/"multifield" (wrong-key); off-by-one
# and multifield-inconsistent are family-specific by construction.
FAULT_FAMILIES: dict[FaultKind, tuple[str, ...]] = {
    FaultKind.MALFORMED_JSON: ("compute", "distractor", "multifield"),
    FaultKind.TRUNCATED_JSON: ("compute", "distractor", "multifield"),
    FaultKind.WRONG_KEY_TRANSIENT: ("compute", "distractor", "multifield"),
    FaultKind.WRONG_KEY_PERSISTENT: ("compute", "distractor", "multifield"),
    FaultKind.OFF_BY_ONE: ("compute", "distractor", "multifield"),
    FaultKind.MULTIFIELD_INCONSISTENT: ("multifield",),
    FaultKind.TIMEOUT: ("compute", "distractor", "multifield"),
    FaultKind.BUDGET_STARVE: ("compute", "distractor", "multifield"),
}

# Ground truth for what a correct verified-execution path must do. The
# judge compares the observed outcome against this, never against the
# system's own verdict.
EXPECTED_OUTCOME: dict[FaultKind, str] = {
    FaultKind.MALFORMED_JSON: "never_succeeds",
    FaultKind.TRUNCATED_JSON: "never_succeeds",
    FaultKind.WRONG_KEY_TRANSIENT: "recovers",
    FaultKind.WRONG_KEY_PERSISTENT: "never_succeeds",
    FaultKind.OFF_BY_ONE: "never_succeeds",
    FaultKind.MULTIFIELD_INCONSISTENT: "never_succeeds",
    FaultKind.TIMEOUT: "raises_timeout",
    FaultKind.BUDGET_STARVE: "raises_budget_exhausted",
}


def _wrong_key_response(family: str, spec: dict[str, Any]) -> str:
    """A schema-violating response with the answer under the wrong key."""
    bad_key = "result" if family == "distractor" else "value"
    return f'{{"{bad_key}": {spec["expected"]}}}'


def _off_by_one_response(family: str, spec: dict[str, Any]) -> str:
    """A schema-VALID response whose numeric answer is wrong by one.

    The near-miss case: this must never be accepted, since it looks
    exactly like a correct response except for the value.
    """
    wrong = spec["expected"] + 1
    if family == "multifield":
        return f'{{"answer": {wrong}, "parity": "{spec["parity"]}", "double": {spec["double"]}}}'
    return f'{{"answer": {wrong}}}'


def _multifield_inconsistent_response(spec: dict[str, Any]) -> str:
    """Correct answer, but a derived field (double) doesn't match it."""
    return f'{{"answer": {spec["expected"]}, "parity": "{spec["parity"]}", "double": {spec["double"] + 2}}}'


def faulted_response(kind: FaultKind, family: str, spec: dict[str, Any]) -> str:
    """The single corrupted response a lying provider returns for `kind`.

    Pure and deterministic: same inputs always produce the same bytes, so
    a campaign run is reproducible byte-for-byte.
    """
    if kind == FaultKind.MALFORMED_JSON:
        return "not json at all, sorry"
    if kind == FaultKind.TRUNCATED_JSON:
        return f'{{"answer": {spec["expected"]}'  # missing closing brace
    if kind in (FaultKind.WRONG_KEY_TRANSIENT, FaultKind.WRONG_KEY_PERSISTENT):
        return _wrong_key_response(family, spec)
    if kind == FaultKind.OFF_BY_ONE:
        return _off_by_one_response(family, spec)
    if kind == FaultKind.MULTIFIELD_INCONSISTENT:
        return _multifield_inconsistent_response(spec)
    if kind == FaultKind.BUDGET_STARVE:
        # A retryable taxonomy, so the session *wants* a second call --
        # the fault is that no budget remains to make it.
        return _wrong_key_response(family, spec)
    raise ValueError(f"{kind} has no scripted response (raises instead)")


@dataclass(frozen=True)
class FaultTrial:
    """One (fault kind, family, variant) instance to run through the
    session, plus the ground truth the judge checks the outcome against."""

    kind: FaultKind
    family: str
    variant: str
    task_id: str
    prompt: str
    spec: dict[str, Any]
    expected: str


def build_trials(fault_kinds: tuple[FaultKind, ...] | None = None) -> list[FaultTrial]:
    """One trial per (fault kind, applicable family), using that family's
    first V2 variant. Deterministic order; no randomness anywhere."""
    kinds = fault_kinds or tuple(FaultKind)
    trials: list[FaultTrial] = []
    for kind in kinds:
        for family in FAULT_FAMILIES[kind]:
            variant = {"compute": "add_small", "distractor": "wrongkey", "multifield": "parity"}[family]
            prompt, spec = system_prompt_for_v2(family, variant)
            trials.append(
                FaultTrial(
                    kind=kind,
                    family=family,
                    variant=variant,
                    task_id=f"fault-{kind.value}-{family}-{variant}",
                    prompt=prompt,
                    spec=spec,
                    expected=EXPECTED_OUTCOME[kind],
                )
            )
    return trials


class Verdict(str, Enum):
    """The judge's classification of one trial's outcome."""

    RECOVERED_SUCCESS = "recovered_success"  # genuinely correct after retry
    LOUD_FAILURE = "loud_failure"            # correctly refused / raised
    SILENT_SUCCESS = "silent_success"        # THE bug this harness hunts
    UNDER_RECOVERED = "under_recovered"       # a fixable fault wasn't fixed (safe, but a weaker guarantee broke)
    CRASHED = "crashed"                      # unrecognized exception escaped
    UNEXPECTED = "unexpected"                # the fault didn't fire as constructed (harness assumption broke)


_KNOWN_EXPECTATIONS = frozenset(EXPECTED_OUTCOME.values())


def _make_complete(trial: FaultTrial) -> Callable[[str], str]:
    """The lying provider for one trial. First call always returns the
    scripted fault (or raises); WRONG_KEY_TRANSIENT's retry call returns
    the genuinely correct response, so a working retry mechanism recovers
    it and a broken one does not."""
    calls: list[int] = [0]

    def complete(_prompt: str) -> str:
        calls[0] += 1
        if trial.kind == FaultKind.TIMEOUT:
            raise TimeoutFault(f"provider hung on {trial.task_id}")
        if calls[0] == 1:
            return faulted_response(trial.kind, trial.family, trial.spec)
        if trial.kind == FaultKind.WRONG_KEY_TRANSIENT:
            return deterministic_emission_v2(trial.family, trial.variant, trial.spec)
        return faulted_response(trial.kind, trial.family, trial.spec)

    return complete


def run_trial(trial: FaultTrial) -> tuple[VerifiedCallResult | None, Exception | None]:
    """Drive one trial through a real VerifiedRetrySession. Returns
    (result, exception): exactly one is not None."""
    max_calls = 1 if trial.kind == FaultKind.BUDGET_STARVE else 0
    session = VerifiedRetrySession(VerifiedRetryConfig(max_calls=max_calls))
    complete = _make_complete(trial)

    def verify(response: str) -> tuple[bool, str]:
        return verify_v2(trial.family, extract_json(response), trial.spec)

    def reprompt(taxonomy: str) -> str:
        return retry_prompt_for(trial.family, taxonomy, trial.spec)

    try:
        result = session.run(trial.task_id, trial.prompt, complete, verify, reprompt)
        return result, None
    except Exception as exc:  # noqa: BLE001 -- classified by judge, never swallowed
        return None, exc


def judge(trial: FaultTrial, result: VerifiedCallResult | None, exc: Exception | None) -> Verdict:
    """Classify one trial's outcome against ground truth. Never consults
    result.valid as the only signal: a SILENT_SUCCESS verdict requires the
    session to have reported valid=True on a trial ground truth says can
    never be genuinely correct -- including the "recovers" case, where
    only the SECOND (retried) response is ever allowed to be the one that
    validates."""
    if trial.expected not in _KNOWN_EXPECTATIONS:
        raise ValueError(f"unknown expectation: {trial.expected}")
    if trial.expected in ("raises_timeout", "raises_budget_exhausted"):
        expected_exc = TimeoutFault if trial.expected == "raises_timeout" else BudgetExhausted
        if isinstance(exc, expected_exc):
            return Verdict.LOUD_FAILURE
        if exc is not None:
            return Verdict.CRASHED
        if result is not None and result.valid:
            return Verdict.SILENT_SUCCESS
        return Verdict.UNEXPECTED  # the fault didn't fire the raise it was built to
    if exc is not None:
        return Verdict.CRASHED
    assert result is not None  # exc is None and neither expectation above raises
    if trial.expected == "recovers":
        if result.valid and result.converted:
            return Verdict.RECOVERED_SUCCESS
        if result.valid:
            # Accepted the FIRST (necessarily wrong) response as valid.
            return Verdict.SILENT_SUCCESS
        return Verdict.UNDER_RECOVERED
    return Verdict.SILENT_SUCCESS if result.valid else Verdict.LOUD_FAILURE


@dataclass
class FaultCampaignReport:
    """Per-trial verdicts plus the pass condition: zero silent successes
    and zero crashes across the whole taxonomy."""

    trials: list[dict[str, Any]] = field(default_factory=list)
    silent_successes: int = 0
    crashed: int = 0
    loud_failures: int = 0
    recovered_successes: int = 0
    under_recovered: int = 0
    unexpected: int = 0

    @property
    def total(self) -> int:
        return len(self.trials)

    @property
    def passed(self) -> bool:
        # under_recovered is safe (never a fabricated success) but still a
        # broken guarantee -- a fixable fault that the retry mechanism was
        # proven (Arena v3) to fix, no longer fixing it -- so it fails the
        # campaign too, just never for the reason silent_successes does.
        return (
            self.silent_successes == 0
            and self.crashed == 0
            and self.unexpected == 0
            and self.under_recovered == 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "silent_successes": self.silent_successes,
            "crashed": self.crashed,
            "loud_failures": self.loud_failures,
            "recovered_successes": self.recovered_successes,
            "under_recovered": self.under_recovered,
            "unexpected": self.unexpected,
            "passed": self.passed,
            "trials": self.trials,
        }


def run_fault_campaign(fault_kinds: tuple[FaultKind, ...] | None = None) -> FaultCampaignReport:
    """Run every applicable (fault kind, family) trial and judge it.

    Deterministic: no seed needed, since every trial is a fixed scripted
    transcript, not a random sample.
    """
    report = FaultCampaignReport()
    counters = {v: 0 for v in Verdict}
    for trial in build_trials(fault_kinds):
        result, exc = run_trial(trial)
        verdict = judge(trial, result, exc)
        counters[verdict] += 1
        report.trials.append(
            {
                "task_id": trial.task_id,
                "kind": trial.kind.value,
                "family": trial.family,
                "expected": trial.expected,
                "verdict": verdict.value,
                "valid": result.valid if result else None,
                "converted": result.converted if result else None,
                "exception_type": type(exc).__name__ if exc else None,
            }
        )
    report.silent_successes = counters[Verdict.SILENT_SUCCESS]
    report.crashed = counters[Verdict.CRASHED]
    report.loud_failures = counters[Verdict.LOUD_FAILURE]
    report.recovered_successes = counters[Verdict.RECOVERED_SUCCESS]
    report.under_recovered = counters[Verdict.UNDER_RECOVERED]
    report.unexpected = counters[Verdict.UNEXPECTED]
    return report
