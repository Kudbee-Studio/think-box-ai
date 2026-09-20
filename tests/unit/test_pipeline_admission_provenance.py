from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_admission_provenance import collect_admission_provenance, provenance_summary


class TestAdmissionProvenance(unittest.TestCase):
    def test_collects_denial_and_queue(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        store.append_lifecycle(
            run_id="r",
            pr_number=501,
            branch="b",
            from_state="BLOCKED",
            to_state="BLOCKED",
            action="admission_denied",
            result="blocked",
            evidence={"admission_reason": "capability_not_granted"},
        )
        store.append_lifecycle(
            run_id="r",
            pr_number=501,
            branch="b",
            from_state="READY_FOR_CLOSE",
            to_state="READY_FOR_CLOSE",
            action="founder_merge_requested",
            result="queued",
            evidence={"github_merge": False},
        )
        events = collect_admission_provenance(store, pr_number=501)
        self.assertEqual(len(events), 2)
        summary = provenance_summary(events)
        self.assertEqual(summary["merge_requests_queued"], 1)
        self.assertEqual(summary["denials"], 1)


if __name__ == "__main__":
    unittest.main()
