"""KUDBEE Control Fabric — THINK burst runner.

Turns a short, paid GPU window into high-signal contrast pairs: a grounded
call (fact-card / occupancy mesh context) and an ungrounded disruptor twin
for the same question, reasoning channel captured, scored by the verifier,
and recorded against a governance token with an elastic-cash ceiling.

Offline (default) uses a synthetic model so unit tests and demos need no
GPU. Live mode targets the loopback vLLM endpoint only:
  http://127.0.0.1:8001  Authorization: Bearer EMPTY  model openai/gpt-oss-20b
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from thinkbox.admission import AdmissionGate
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.reasoning import NormalizedCompletion, ReasoningNormalizer, capture_completion
from thinkbox.thinktrace import ThinkTrace, ThinkTraceCapture

DEFAULT_FACT_CARDS: dict[str, str] = {
    "What is 2+2?": "fact_arith: 2+2=4",
    "What is the capital of France?": "fact_geo: Paris is the capital of France",
    "What does CRDT stand for?": "fact_crdt: Conflict-free Replicated Data Type",
    "What does SSM stand for in AWS?": "fact_aws: AWS Systems Manager",
}

DEFAULT_PROMPTS: list[str] = list(DEFAULT_FACT_CARDS.keys())


@dataclass
class BurstConfig:
    model: str = "openai/gpt-oss-20b"
    base_url: str = "http://127.0.0.1:8001"
    api_key: str = "EMPTY"
    max_pairs: int = 8
    max_minutes: float = 10.0
    max_calls: int = 32
    max_spend: float = 1.0
    cost_per_call: float = 0.01
    agent_id: str = "kilo"
    capability: str = "goal:execute"
    output_dir: str = "data/evals/burst"


@dataclass
class BurstBudget:
    """Elastic-cash stub: hard ceiling of calls and spend per burst."""

    max_calls: int
    max_spend: float
    cost_per_call: float
    calls: int = 0
    spend: float = 0.0

    def can_call(self) -> bool:
        return self.calls < self.max_calls and (self.spend + self.cost_per_call) <= self.max_spend

    def charge(self) -> bool:
        if not self.can_call():
            return False
        self.calls += 1
        self.spend = round(self.spend + self.cost_per_call, 6)
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_calls": self.max_calls,
            "max_spend": self.max_spend,
            "calls": self.calls,
            "spend": self.spend,
            "cost_per_call": self.cost_per_call,
        }


@dataclass
class BurstReport:
    burst_id: str
    admitted: bool
    reason: str
    agent_id: str
    model: str
    governance_token_id: str
    pairs: int = 0
    calls_used: int = 0
    grounded_count: int = 0
    ungrounded_count: int = 0
    reasoning_captured: int = 0
    groundness_score: float = 0.0
    bind_failure_rate: float = 0.0
    duration_seconds: float = 0.0
    budget: dict[str, Any] = field(default_factory=dict)
    output_path: str = ""
    started_at: str = ""
    ended_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    def to_markdown(self) -> str:
        lines = [
            f"# THINK Burst Report — {self.burst_id}",
            "",
            f"- Admitted: **{self.admitted}** ({self.reason})",
            f"- Agent: `{self.agent_id}`  Model: `{self.model}`",
            f"- Governance token: `{self.governance_token_id}`",
            f"- Contrast pairs: **{self.pairs}**  Calls: {self.calls_used}",
            f"- Grounded: {self.grounded_count}  Ungrounded: {self.ungrounded_count}",
            f"- Reasoning captured: {self.reasoning_captured}",
            f"- Groundedness score: **{self.groundness_score:.3f}**",
            f"- Disruptor bind-failure rate: **{self.bind_failure_rate:.3f}**",
            f"- Duration: {self.duration_seconds:.2f}s",
            f"- Budget: {self.budget}",
            f"- Output: `{self.output_path}`",
            "",
        ]
        return "\n".join(lines)


def synthetic_model(question: str, fact_card: str | None) -> NormalizedCompletion:
    """Deterministic offline stand-in: grounded reasoning with a fact card."""
    if fact_card:
        return NormalizedCompletion(
            content=f"Answer (grounded): {fact_card.split(': ', 1)[-1]}",
            reasoning=f"Using {fact_card.split(':', 1)[0]} to answer.",
            finish_reason="stop",
            usage={"total_tokens": 20},
        )
    return NormalizedCompletion(
        content="Answer (ungrounded): plausible but unverified.",
        reasoning="No evidence available; guessing.",
        finish_reason="stop",
        usage={"total_tokens": 18},
    )


def _governance_gate() -> tuple[GovernanceTokenService, IdentityLedger, AdmissionGate]:
    tokens = GovernanceTokenService(signing_key="burst-key")
    identities = IdentityLedger()
    gate = AdmissionGate(tokens, identities)
    return tokens, identities, gate


class LiveVLLMClient:
    """Loopback OpenAI-compatible client. Never used in unit tests."""

    def __init__(self, config: BurstConfig) -> None:
        self._config = config
        self._normalizer = ReasoningNormalizer()

    def complete(self, question: str, fact_card: str | None) -> NormalizedCompletion:
        import http.client
        from urllib.parse import urlparse

        parsed = urlparse(self._config.base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8001
        system = "Answer using only the provided fact card." if fact_card else "Answer without evidence."
        content = f"{system}\n{fact_card or ''}\nQ: {question}"
        body = json.dumps(
            {
                "model": self._config.model,
                "messages": [{"role": "user", "content": content}],
                "stream": False,
            }
        )
        conn = http.client.HTTPConnection(host, port, timeout=60)
        conn._http_vsn = 10
        conn._http_vsn_str = "HTTP/1.0"
        conn.request(
            "POST",
            "/v1/chat/completions",
            body=body,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
        )
        response = conn.getresponse()
        payload = json.loads(response.read().decode())
        conn.close()
        return self._normalizer.parse_response(payload)


class BurstRunner:
    """Executes one paid window as a bounded, auditable contrast-pair burst."""

    def __init__(
        self,
        config: BurstConfig | None = None,
        model_fn: Callable[[str, str | None], NormalizedCompletion] | None = None,
        gate: AdmissionGate | None = None,
        token_value: str = "",
        now_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or BurstConfig()
        self._model = model_fn or synthetic_model
        self._gate = gate
        self._token_value = token_value
        self._now = now_fn
        self._traces = ThinkTraceCapture()

    def run(self, prompts: list[str] | None = None, fact_cards: dict[str, str] | None = None) -> BurstReport:
        prompts = prompts or DEFAULT_PROMPTS
        fact_cards = fact_cards or DEFAULT_FACT_CARDS
        burst_id = f"burst_{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc).isoformat()
        start = self._now()

        admitted, reason, token_id = self._admit()
        budget = BurstBudget(
            max_calls=self.config.max_calls,
            max_spend=self.config.max_spend,
            cost_per_call=self.config.cost_per_call,
        )
        report = BurstReport(
            burst_id=burst_id,
            admitted=admitted,
            reason=reason,
            agent_id=self.config.agent_id,
            model=self.config.model,
            governance_token_id=token_id,
            started_at=started_at,
            budget=budget.to_dict(),
        )
        if not admitted:
            report.ended_at = datetime.now(timezone.utc).isoformat()
            return report

        records: list[dict[str, Any]] = []
        pairs = 0
        completed = True
        pair_cost = 2 * self.config.cost_per_call
        for question in prompts:
            if pairs >= self.config.max_pairs:
                break
            if (self._now() - start) > self.config.max_minutes * 60:
                report.reason = "time_budget_exhausted"
                completed = False
                break
            if (budget.calls + 2 > budget.max_calls) or (budget.spend + pair_cost > budget.max_spend):
                report.reason = "cash_budget_exhausted"
                completed = False
                break

            fact_card = fact_cards.get(question)
            pair_id = f"pair_{uuid.uuid4().hex[:10]}"
            for variant, card in (("grounded", fact_card), ("ungrounded", None)):
                budget.charge()
                completion = self._model(question, card)
                trace = capture_completion(
                    self._traces,
                    self.config.agent_id,
                    completion,
                    evidence_refs=[card.split(":", 1)[0]] if card else None,
                    tags=["mesh" if card else "disruptor"],
                )
                records.append(self._record(burst_id, pair_id, variant, question, trace, token_id))
                if trace.grounded:
                    report.grounded_count += 1
                else:
                    report.ungrounded_count += 1
                if completion.had_reasoning:
                    report.reasoning_captured += 1
            pairs += 1

        if completed:
            report.reason = "completed"
        report.pairs = pairs
        report.calls_used = budget.calls
        report.budget = budget.to_dict()
        total_variants = report.grounded_count + report.ungrounded_count
        report.groundness_score = report.grounded_count / max(1, total_variants)
        report.bind_failure_rate = 1.0 if report.ungrounded_count else 0.0
        report.ended_at = datetime.now(timezone.utc).isoformat()
        report.duration_seconds = round(self._now() - start, 4)
        report.output_path = self._write_jsonl(burst_id, records)
        return report

    def _admit(self) -> tuple[bool, str, str]:
        if self._gate is None:
            return True, "offline_mode", "offline"
        decision = self._gate.authorize(self._token_value, self.config.agent_id, self.config.capability)
        token_id = self._token_value[:24] if self._token_value else "none"
        return decision.allowed, decision.reason, token_id

    def _record(
        self,
        burst_id: str,
        pair_id: str,
        variant: str,
        question: str,
        trace: ThinkTrace,
        token_id: str,
    ) -> dict[str, Any]:
        record = dict(trace.__dict__)
        record.update(
            {
                "burst_id": burst_id,
                "pair_id": pair_id,
                "variant": variant,
                "question": question,
                "model": self.config.model,
                "governance_token_id": token_id,
            }
        )
        return record

    def _write_jsonl(self, burst_id: str, records: list[dict[str, Any]]) -> str:
        target = Path(self.config.output_dir)
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"think_burst_{burst_id}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, default=str) + "\n")
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="THINK burst runner")
    parser.add_argument("--live", action="store_true", help="call loopback vLLM (requires GPU window)")
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--minutes", type=float, default=10.0)
    parser.add_argument("--max-calls", type=int, default=32)
    parser.add_argument("--budget", type=float, default=1.0)
    parser.add_argument("--out", default="data/evals/burst")
    args = parser.parse_args(argv)

    config = BurstConfig(
        max_pairs=args.pairs,
        max_minutes=args.minutes,
        max_calls=args.max_calls,
        max_spend=args.budget,
        output_dir=args.out,
    )
    if args.live:
        tokens, identities, gate = _governance_gate()
        principal = identities.register(agent_id=config.agent_id, capabilities=[config.capability])
        token = tokens.issue(
            TokenRequest(agent_id=principal.agent_id, capabilities=[config.capability], ttl_seconds=3600.0)
        )
        runner = BurstRunner(
            config=config,
            model_fn=LiveVLLMClient(config).complete,
            gate=gate,
            token_value=token.token_value,
        )
    else:
        runner = BurstRunner(config=config)
    report = runner.run()
    print(report.to_markdown())
    return 0 if report.admitted else 1


if __name__ == "__main__":
    sys.exit(main())