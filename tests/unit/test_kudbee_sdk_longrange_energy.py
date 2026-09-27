"""Kudbee SDK long-range + energy loops deepen tests (PR #193)."""

from __future__ import annotations

import unittest

from thinkbox.kudbee_sdk_longrange_energy import (
    DEFAULT_CLIENT_CAPABILITIES,
    EnergyLoopMesh,
    KudbeeSdkLrEnergyClient,
    TwinFederationStub,
    load_config_from_env,
    negotiate,
)
from thinkbox.kudbee_sdk_longrange_energy.cassette import list_cassette_names, replay_cassette
from thinkbox.kudbee_sdk_longrange_energy.conservation_ledger import ConservationLedger
from thinkbox.kudbee_sdk_longrange_energy.errors import SdkLrEnergyError
from thinkbox.kudbee_sdk_longrange_energy.fixtures import fixture_exists, load_fixture
from thinkbox.kudbee_sdk_longrange_energy.integrate import integration_summary, run_feature_demo
from thinkbox.kudbee_sdk_longrange_energy.negotiation import compatible_with_server
from thinkbox.kudbee_sdk_longrange_energy.health import ReadinessTier, classify_readiness
from thinkbox.kudbee_sdk_longrange_energy.hop_scheduler import Page, decode_cursor, encode_cursor, filter_items, iter_pages
from thinkbox.kudbee_sdk_longrange_energy.sdk_status_report import route_catalog_lr_energy, run_hermetic_sdk_lr_energy_demo
from thinkbox.kudbee_sdk_longrange_energy.secrets import scan_text_for_secrets
from thinkbox.kudbee_sdk_longrange_energy.long_range_session_bind import SessionBridgeLrEnergy
from thinkbox.kudbee_sdk_longrange_energy.energy_task_budget import TaskBridgeLrEnergy
from thinkbox.kudbee_sdk_longrange_energy.webhook_signature import parse_signature_header, sign_payload, verify_signature


class TestKudbeeSdkLongrangeEnergyDeepen(unittest.TestCase):
    def test_config_fail_closed(self) -> None:
        with self.assertRaises(SdkLrEnergyError):
            load_config_from_env({"KUDBEE_SDK_LR_ENERGY_BASE_URL": "ftp://bad"})
        cfg = load_config_from_env({"KUDBEE_SDK_LR_ENERGY_DRY_RUN": "true"})
        self.assertTrue(cfg.dry_run)

    def test_negotiation_v5(self) -> None:
        caps = negotiate(
            ("sessions", "long_range_link", "energy_loop_mesh"),
            ("webhooks", "long_range_link", "conservation_ledger"),
        )
        self.assertEqual(caps.capabilities, ("long_range_link",))
        self.assertTrue(compatible_with_server(5))
        self.assertFalse(compatible_with_server(99))

    def test_pagination_and_client(self) -> None:
        page = Page(items=(1, 2), next_cursor=None)
        filtered = filter_items(page, lambda x: x > 1)
        self.assertEqual(filtered.items, (2,))
        collected = iter_pages(lambda c: Page(items=((c or "a",)), next_cursor="b" if c is None else None), max_pages=2)
        self.assertEqual(collected, ("a", "b"))
        client = KudbeeSdkLrEnergyClient.from_env()
        health = client.health()
        self.assertTrue(health["ready"])
        self.assertFalse(health["live_api_called"])
        caps = client.capabilities()
        self.assertIn("energy_loop_mesh", caps["capabilities"])

    def test_webhook_cassette_bridges(self) -> None:
        sig = sign_payload(b"secret", b"{}")
        result = verify_signature(b"secret", b"{}", sig, dry_run=True)
        self.assertTrue(result.valid)
        tape = replay_cassette("long_range_energy_flow.json")
        self.assertEqual(tape["step_count"], 3)
        session = SessionBridgeLrEnergy.open("s-lr")
        session.link_twin("twin-1")
        self.assertTrue(session.summary()["twin_linked"])
        task = TaskBridgeLrEnergy.create("t-lr", "demo")
        out = task.run_hermetic()
        self.assertEqual(out["status"], "completed")

    def test_fixtures_integrate_demo(self) -> None:
        doc = load_fixture("health_ok.json")
        self.assertTrue(doc.get("ready"))
        demo = run_hermetic_sdk_lr_energy_demo()
        self.assertFalse(demo["live_api_called"])
        routes = route_catalog_lr_energy()
        self.assertIn("/api/sdk/v4/longrange-energy/capabilities", routes["routes"])
        summary = integration_summary()
        self.assertFalse(summary["live_api_called"])
        feat = run_feature_demo("occupancy")
        self.assertIn("cells", feat)

    def test_energy_mesh_and_ledger(self) -> None:
        mesh = EnergyLoopMesh("m-1")
        loop = mesh.attach_loop("l-1", capacity=20.0)
        loop.deposit(5.0)
        mesh.attach_link("link-1")
        snap = mesh.snapshot()
        self.assertEqual(snap["loop_count"], 1)
        self.assertTrue(snap["all_conserved"])
        ledger = ConservationLedger()
        ledger.record("l-1", 5.0, conserved=True)
        self.assertTrue(ledger.verify_chain())

    def test_secret_scan_and_deepen_helpers(self) -> None:
        scan = scan_text_for_secrets("export const x = 1;")
        self.assertTrue(scan.clean)
        cursor = encode_cursor({"hop": 2})
        self.assertEqual(decode_cursor(cursor)["hop"], 2)
        self.assertIn("long_range_link", DEFAULT_CLIENT_CAPABILITIES)
        self.assertTrue(fixture_exists("health_ok.json"))
        self.assertIn("long_range_energy_flow.json", list_cassette_names())
        algo, _ = parse_signature_header(sign_payload(b"s", b"{}"))
        self.assertEqual(algo, "sha256")
        client = KudbeeSdkLrEnergyClient.from_env()
        fed = client.twin_federation()
        self.assertEqual(fed["peer_count"], 0)
        self.assertEqual(classify_readiness(True, "dry-run-lr-energy"), ReadinessTier.READY)
        session = SessionBridgeLrEnergy.open("s-tag")
        session.set_tag("env", "hermetic")
        self.assertEqual(session.tags["env"], "hermetic")
        task = TaskBridgeLrEnergy.create("t-cancel", "x")
        cancelled = task.cancel_hermetic()
        self.assertEqual(cancelled["status"], "failed")
        mesh = TwinFederationStub()
        mesh.register_peer("t1", "s1")
        self.assertEqual(mesh.federation_snapshot()["peer_count"], 1)
        feat = run_feature_demo("twin_federation")
        self.assertEqual(feat["peer_count"], 1)


if __name__ == "__main__":
    unittest.main()
