"""Receipt-chain deepen tests (PR #182)."""

from __future__ import annotations

import unittest

from thinkbox.receipt_chain_deepen import HermeticReceiptChain, append_receipt
from thinkbox.receipt_chain_deepen.cassette import replay_cassette
from thinkbox.receipt_chain_deepen.compaction import compact_chain_stub
from thinkbox.receipt_chain_deepen.config import load_config_from_env
from thinkbox.receipt_chain_deepen.cursor_pagination import pagination_roundtrip
from thinkbox.receipt_chain_deepen.dry_run import dry_run_chain_page
from thinkbox.receipt_chain_deepen.errors import ReceiptChainDeepenError
from thinkbox.receipt_chain_deepen.fixtures import load_fixture
from thinkbox.receipt_chain_deepen.fork_detect import detect_fork_stub
from thinkbox.receipt_chain_deepen.integrate import integration_summary, run_feature_demo
from thinkbox.receipt_chain_deepen.negotiation import compatible_with_server, negotiate
from thinkbox.receipt_chain_deepen.redact_export import export_chain_redacted
from thinkbox.receipt_chain_deepen.replay import replay_actions
from thinkbox.receipt_chain_deepen.secrets import scan_text_for_secrets
from thinkbox.receipt_chain_deepen.verify import verify_hermetic_chain, verify_store_chain_if_available


class TestReceiptChainDeepen(unittest.TestCase):
    def test_config_fail_closed(self) -> None:
        with self.assertRaises(ReceiptChainDeepenError):
            load_config_from_env({"RECEIPT_CHAIN_DEEPEN_DRY_RUN": "false"})
        cfg = load_config_from_env({"RECEIPT_CHAIN_DEEPEN_DRY_RUN": "true"})
        self.assertTrue(cfg.dry_run)

    def test_append_verify_roundtrip(self) -> None:
        chain = HermeticReceiptChain()
        append_receipt(chain, "r-1", "admit")
        append_receipt(chain, "r-2", "audit")
        result = verify_hermetic_chain(chain)
        self.assertTrue(result["valid"])
        self.assertFalse(result["live_api_called"])

    def test_redact_export_and_secrets(self) -> None:
        row = {"receipt_id": "r", "reason": "Bearer secret-token", "metadata": {}}
        exported = export_chain_redacted([row])
        self.assertTrue(exported["redacted"])
        hits = scan_text_for_secrets("sk-abcdefghijklmnop")
        self.assertTrue(hits)

    def test_cassette_fixture_replay(self) -> None:
        tape = replay_cassette("chain_append_flow.json")
        self.assertEqual(tape["step_count"], 3)
        doc = load_fixture("sample_chain_page.json")
        self.assertEqual(len(doc["receipts"]), 2)
        page = dry_run_chain_page(limit=5)
        self.assertTrue(page["dry_run"])

    def test_fork_compaction_pagination(self) -> None:
        fork = detect_fork_stub("a", "b")
        self.assertTrue(fork.fork_detected)
        chain = HermeticReceiptChain()
        for i in range(10):
            append_receipt(chain, f"r-{i}", "noop")
        compacted = compact_chain_stub(list(chain.entries()), keep_tail=3)
        self.assertTrue(compacted["compacted"])
        self.assertTrue(pagination_roundtrip(4)["ok"])

    def test_integrate_and_store_bridge(self) -> None:
        caps = negotiate(("append", "verify"), ("verify", "export"))
        self.assertEqual(caps.capabilities, ("verify",))
        self.assertTrue(compatible_with_server(1))
        demo = run_feature_demo("verify")
        self.assertTrue(demo["valid"])
        summary = integration_summary()
        self.assertFalse(summary["live_api_called"])
        store_verify = verify_store_chain_if_available()
        self.assertTrue(store_verify["valid"])

    def test_replay_actions(self) -> None:
        out = replay_actions([{"receipt_id": "r-a", "action": "x"}])
        self.assertTrue(out["verification"]["valid"])


if __name__ == "__main__":
    unittest.main()
