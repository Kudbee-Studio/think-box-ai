"""KUDBEE Control Fabric — Harvest replay.

Reads burst / think-trace jsonl, reconstructs grounded-vs-disruptor contrast
pairs, and scores them with the deterministic grounding scorer. Harvest
once on the GPU; re-score forever offline. Optionally bridges the pairs
through the Verifier.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.disruptor import DisruptorResult
from thinkbox.grounding import GroundingScorer


@dataclass
class HarvestMetrics:
    records: int = 0
    pairs: int = 0
    grounded_variants: int = 0
    ungrounded_variants: int = 0
    reasoning_coverage: float = 0.0
    groundedness_score: float = 0.0
    bind_failure_rate: float = 0.0
    mean_grounding_score: float = 0.0
    verifier_overall: float | None = None
    verifier_verdict: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class HarvestReport:
    sources: list[str]
    timestamp: str
    metrics: HarvestMetrics
    pairs_detail: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": self.sources,
            "timestamp": self.timestamp,
            "metrics": self.metrics.to_dict(),
            "pairs_detail": self.pairs_detail,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def to_markdown(self) -> str:
        m = self.metrics
        lines = [
            f"# Harvest Replay Report",
            "",
            f"**Timestamp:** {self.timestamp}",
            f"**Sources:** {', '.join(self.sources) if self.sources else '(none)'}",
            "",
            "## Metrics",
            "",
            f"- Records: {m.records}  |  Contrast pairs: {m.pairs}",
            f"- Grounded variants: {m.grounded_variants}  |  Ungrounded variants: {m.ungrounded_variants}",
            f"- Reasoning coverage: **{m.reasoning_coverage:.3f}**",
            f"- Groundedness score (grounded variants): **{m.groundedness_score:.3f}**",
            f"- Bind-failure rate (ungrounded correctly unbound): **{m.bind_failure_rate:.3f}**",
            f"- Mean grounding score: **{m.mean_grounding_score:.3f}**",
        ]
        if m.verifier_overall is not None:
            lines.append(f"- Verifier overall: **{m.verifier_overall:.3f}** ({m.verifier_verdict})")
        lines += [
            "",
            "> Honest note: bind-failure is measured by the deterministic grounding",
            "> scorer against the recorded evidence text — not an adversary outcome.",
            "",
        ]
        return "\n".join(lines)


class HarvestReplay:
    def __init__(self, threshold: float = 0.5) -> None:
        self._scorer = GroundingScorer(threshold=threshold)
        self._threshold = threshold

    def load(self, paths: list[str | Path]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in paths:
            for line in Path(path).read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def replay_dir(self, directory: str | Path = "data/evals/burst") -> HarvestReport:
        paths = sorted(Path(directory).glob("*.jsonl"))
        return self.analyze(self.load(paths), sources=[str(p) for p in paths])

    def analyze(
        self,
        records: list[dict[str, Any]],
        sources: list[str] | None = None,
        verify: bool = False,
        ctx: dict[str, Any] | None = None,
    ) -> HarvestReport:
        pairs: dict[str, dict[str, dict[str, Any]]] = {}
        for record in records:
            pair_id = record.get("pair_id")
            if not pair_id:
                continue
            pairs.setdefault(pair_id, {})[str(record.get("variant", "unknown"))] = record

        scores: list[float] = []
        grounded_scores: list[float] = []
        ungrounded_bound_correctly = 0
        ungrounded_total = 0
        reasoning_count = 0
        detail: list[dict[str, Any]] = []
        verifier_results: list[DisruptorResult] = []

        for pair_id, variants in pairs.items():
            pair_scores: dict[str, float] = {}
            for variant, record in variants.items():
                claim = str(record.get("thought", ""))
                evidence = record.get("evidence_text") or " ".join(record.get("evidence_refs") or [])
                reasoning = str((record.get("metadata") or {}).get("reasoning", ""))
                grounding = self._scorer.score(claim, evidence, reasoning)
                scores.append(grounding.score)
                pair_scores[variant] = grounding.score
                if reasoning:
                    reasoning_count += 1
                if variant == "grounded":
                    grounded_scores.append(grounding.score)
                    verifier_results.append(
                        DisruptorResult(
                            name=f"harvest_{pair_id}_grounded",
                            category="grounding",
                            description="harvested grounded variant",
                            outcome={"score": grounding.score},
                            passed=grounding.is_grounded(self._threshold),
                        )
                    )
                elif variant == "ungrounded":
                    ungrounded_total += 1
                    correctly_unbound = not grounding.is_grounded(self._threshold)
                    if correctly_unbound:
                        ungrounded_bound_correctly += 1
                    verifier_results.append(
                        DisruptorResult(
                            name=f"harvest_{pair_id}_ungrounded",
                            category="grounding",
                            description="harvested disruptor twin",
                            outcome={"score": grounding.score},
                            passed=correctly_unbound,
                        )
                    )
            detail.append({"pair_id": pair_id, "scores": pair_scores})

        metrics = HarvestMetrics(
            records=len(records),
            pairs=len(pairs),
            grounded_variants=len(grounded_scores),
            ungrounded_variants=ungrounded_total,
            reasoning_coverage=round(reasoning_count / len(records), 4) if records else 0.0,
            groundedness_score=round(sum(grounded_scores) / len(grounded_scores), 4) if grounded_scores else 0.0,
            bind_failure_rate=round(ungrounded_bound_correctly / ungrounded_total, 4) if ungrounded_total else 0.0,
            mean_grounding_score=round(sum(scores) / len(scores), 4) if scores else 0.0,
        )

        if verify and verifier_results:
            from thinkbox.verifier import Verifier, build_eval_fabric

            report = Verifier().evaluate(verifier_results, ctx or build_eval_fabric())
            metrics.verifier_overall = report.metrics.overall_score
            metrics.verifier_verdict = report.metrics.verdict

        return HarvestReport(
            sources=sources or [],
            timestamp=datetime.now(timezone.utc).isoformat(),
            metrics=metrics,
            pairs_detail=detail,
        )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="THINK harvest replay")
    parser.add_argument("--dir", default="data/evals/burst", help="directory with burst jsonl files")
    parser.add_argument("--verify", action="store_true", help="run verifier on pairs")
    args = parser.parse_args(argv)

    replay = HarvestReplay()
    report = replay.replay_dir(args.dir)
    print(report.to_markdown())

    if args.verify:
        report_verify = replay.analyze(replay.load(args.dir), sources=[str(args.dir)], verify=True)
        print("\n--- With Verifier ---")
        print(report_verify.to_markdown())

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())