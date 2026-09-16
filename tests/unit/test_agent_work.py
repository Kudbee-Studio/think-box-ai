"""Tests for the agent work-template protocol (`scripts/agent_work.py`)."""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _load_agent_work():
    import sys
    spec = importlib.util.spec_from_file_location("agent_work", ROOT / "scripts" / "agent_work.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # register before exec: dataclasses on 3.10 look the module up in sys.modules
    sys.modules["agent_work"] = mod
    spec.loader.exec_module(mod)
    return mod


aw = _load_agent_work()


class TestTemplateRegistry(unittest.TestCase):
    def test_dashboard_template_registered(self) -> None:
        self.assertIn("dashboard-evolution", aw.TEMPLATES)
        t = aw.TEMPLATES["dashboard-evolution"]
        self.assertEqual(t.domain, "dashboard")
        self.assertTrue(t.baseline, "baseline commands required")
        self.assertTrue(t.verification, "verification commands required")
        self.assertTrue(t.e2e_routes, "e2e routes required")

    def test_every_template_has_a_contract_file(self) -> None:
        for name, t in aw.TEMPLATES.items():
            with self.subTest(template=name):
                self.assertTrue(t.contract_path, f"{name} missing contract_path")
                self.assertTrue((ROOT / t.contract_path).exists(),
                                f"{name}: {t.contract_path} does not exist")

    def test_registry_and_yaml_do_not_drift(self) -> None:
        """The machine registry and the human contract must name the same commands."""
        yaml_text = (ROOT / "docs" / "agent-templates" / "_contract.template.yaml").read_text()
        t = aw.TEMPLATES["dashboard-evolution"]
        for cmd in t.baseline + t.verification:
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, yaml_text, f"{cmd!r} missing from _contract.template.yaml")

    def test_contract_documents_design_rules(self) -> None:
        text = (ROOT / aw.TEMPLATES["dashboard-evolution"].contract_path).read_text()
        for rule in ("files over servers", "mobile-first", "no fake green",
                     "signals are not failures", "unproven stays unproven"):
            with self.subTest(rule=rule):
                self.assertIn(rule, text.lower(), f"contract missing rule: {rule}")


class TestBranchNaming(unittest.TestCase):
    def test_accepts_compliant_names(self) -> None:
        t = aw.TEMPLATES["dashboard-evolution"]
        for name in (
            "agent/dashboard-evolution/kilo-20260916",
            "agent/dashboard-command-center/kilo-20260916",
            "agent/dashboard-evolution/codex-20260101",
        ):
            with self.subTest(branch=name):
                self.assertRegex(name, t.branch_pattern)
                self.assertTrue(any(name.startswith(p) for p in t.accepted_prefixes))

    def test_rejects_non_compliant_names(self) -> None:
        t = aw.TEMPLATES["dashboard-evolution"]
        for name in (
            "main",
            "feature/dashboard",
            "agent/dashboard-evolution",              # no agent/date suffix
            "agent/dashboard-evolution/kilo",         # no date
            "agent/dashboard-evolution/kilo-26-09-16",  # wrong date shape
            "dashboard-evolution/kilo-20260916",      # missing agent/ prefix
        ):
            with self.subTest(branch=name):
                compliant = bool(re.match(t.branch_pattern, name)) and any(
                    name.startswith(p) for p in t.accepted_prefixes
                )
                self.assertFalse(compliant, f"{name} should not be compliant")

    def test_main_is_never_a_valid_work_branch(self) -> None:
        t = aw.TEMPLATES["dashboard-evolution"]
        for name in ("main", "master"):
            self.assertFalse(any(name.startswith(p) for p in t.accepted_prefixes))


class TestDashboardE2E(unittest.TestCase):
    """The protocol's E2E step must actually exercise the dashboard routes."""

    def test_e2e_route_list_matches_dashboard_routes(self) -> None:
        src = (ROOT / "experiments" / "swarm_dashboard.py").read_text()
        t = aw.TEMPLATES["dashboard-evolution"]
        for route in t.e2e_routes:
            with self.subTest(route=route):
                if route == "/healthz":
                    self.assertIn('"/healthz"', src)
                else:
                    self.assertIn(f'"{route}"', src, f"{route} not handled by the dashboard")

    def test_e2e_check_runs_and_reports(self) -> None:
        t = aw.TEMPLATES["dashboard-evolution"]
        ok, lines = aw._dashboard_e2e(t)
        self.assertTrue(ok, "dashboard E2E failed:\n" + "\n".join(lines))
        self.assertEqual(len(lines), len(t.e2e_routes))


if __name__ == "__main__":
    unittest.main()
