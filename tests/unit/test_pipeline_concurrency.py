"""Concurrency tests: multiple PR rollups without cross-talk."""

from __future__ import annotations

import threading
import unittest

from thinkbox.pipeline_dashboard import PipelineDashboardAggregator, build_hermetic_pipeline_dashboard


class TestPipelineConcurrency(unittest.TestCase):
    def test_three_prs_aggregate_without_cross_talk(self) -> None:
        aggregator, _, _, proof_key = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        errors: list[str] = []

        def writer(pr: int) -> None:
            try:
                for i in range(5):
                    store.append_lifecycle(
                        run_id=f"run_{pr}",
                        pr_number=pr,
                        branch=f"branch-{pr}",
                        from_state="A",
                        to_state="B",
                        action="act",
                        result="success",
                        evidence={"idx": i, "pr": pr},
                    )
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(str(exc))

        threads = [threading.Thread(target=writer, args=(p,)) for p in (801, 802, 803)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

        summaries = {s["pr_number"]: s for s in aggregator.list_summaries()}
        self.assertEqual(summaries[801]["branch"], "branch-801")
        self.assertEqual(summaries[802]["branch"], "branch-802")
        self.assertEqual(summaries[803]["branch"], "branch-803")
        self.assertNotEqual(summaries[801]["branch"], summaries[802]["branch"])
        _ = proof_key


if __name__ == "__main__":
    unittest.main()
