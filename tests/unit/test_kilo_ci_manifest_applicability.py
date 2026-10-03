"""The KILO CI manifest applies when CI runs Python, and says so when it does not.

PR #308 removed the Python unit-and-integration job and its KILO steps from .github/workflows/test.yml, leaving the
web job. The manifest (PR #172, delegated to by PR #151) still demanded six Python steps, so the whole gate chain from
PR #151 on failed on a requirement that no longer describes the CI. The requirement now applies only to a workflow that
runs Python, so it returns on its own when a Python job comes back; the rest of the manifest (no redundant verify
scripts, no default --e2e) always applies.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from thinkbox import kilo_post_season_harden as psh
from thinkbox import kilo_pr172_ci_spine_trust as pr172

ROOT = Path(__file__).resolve().parents[2]

WEB_ONLY = """\
name: test
jobs:
  web-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm install
      - run: npm run typecheck
      - run: npm test
"""

PYTHON_JOB_WITHOUT_THE_KILO_STEPS = WEB_ONLY + """\
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
      - run: pip install -e .
      - run: python3 -m unittest discover
"""

PYTHON_JOB_WITH_THE_KILO_STEPS = "\n".join(
    [WEB_ONLY, "  unit:", "    steps:", "      - uses: actions/setup-python@v5"]
    + [f"      - run: {snippet}" for snippet in pr172.REQUIRED_CI_SNIPPETS]
)


class TestCiManifestApplicability(unittest.TestCase):
    def test_a_workflow_that_runs_python_must_carry_every_required_step(self) -> None:
        ok, violations = pr172.validate_pr172_ci_workflow_manifest(PYTHON_JOB_WITHOUT_THE_KILO_STEPS)
        self.assertFalse(ok)
        missing = {v.message for v in violations if v.code == "ci_workflow_missing_snippet"}
        self.assertIn("CI workflow must reference verify_kilo_spine.py", missing)
        self.assertIn("CI workflow must reference scan_doc_secrets.py", missing)

    def test_a_python_job_with_all_the_steps_passes(self) -> None:
        ok, violations = pr172.validate_pr172_ci_workflow_manifest(PYTHON_JOB_WITH_THE_KILO_STEPS)
        self.assertTrue(ok, msg=violations)

    def test_a_web_only_workflow_has_no_python_steps_to_check(self) -> None:
        ok, violations = pr172.validate_pr172_ci_workflow_manifest(WEB_ONLY)
        self.assertTrue(ok, msg=violations)
        self.assertFalse(pr172.ci_runs_python(WEB_ONLY))
        self.assertTrue(pr172.ci_runs_python(PYTHON_JOB_WITHOUT_THE_KILO_STEPS))

    def test_the_rest_of_the_manifest_always_applies(self) -> None:
        for text, code in (
            (WEB_ONLY + "      - run: python3 scripts/verify_kilo_spine.py --e2e\n", "ci_workflow_e2e_default_forbidden"),
            (WEB_ONLY + "      - run: bash x/verify_kilo_api_ops_harden.py\n", "ci_workflow_redundant_verify_script"),
        ):
            ok, violations = pr172.validate_pr172_ci_workflow_manifest(text)
            self.assertFalse(ok)
            self.assertIn(code, {v.code for v in violations})

    def test_the_summary_says_when_the_requirement_does_not_apply(self) -> None:
        web = pr172.ci_spine_trust_contract_summary(WEB_ONLY)
        self.assertTrue(web["hermetic_operator_ok"])
        self.assertFalse(web["ci_runs_python"])
        python = pr172.ci_spine_trust_contract_summary(PYTHON_JOB_WITHOUT_THE_KILO_STEPS)
        self.assertFalse(python["hermetic_operator_ok"])
        self.assertTrue(python["ci_runs_python"])

    def test_post_season_harden_delegates_to_the_same_rule(self) -> None:
        self.assertTrue(psh.validate_ci_workflow_manifest(WEB_ONLY)[0])
        self.assertFalse(psh.validate_ci_workflow_manifest(PYTHON_JOB_WITHOUT_THE_KILO_STEPS)[0])

    def test_the_repository_workflow_and_the_gate_chain(self) -> None:
        text = (ROOT / pr172.CI_WORKFLOW_REL).read_text(encoding="utf-8")
        self.assertTrue(pr172.validate_pr172_ci_workflow_manifest(text)[0])
        result = psh.hermetic_post_season_harden_operator_check()
        self.assertTrue(result.ok, msg=result.violations)
        self.assertEqual(result.evidence.ci_manifest_applies, pr172.ci_runs_python(text))

    def test_post_season_summary_reports_applicability(self) -> None:
        summary = psh.post_season_harden_contract_summary()
        self.assertIn("ci_manifest_applies", summary)


if __name__ == "__main__":
    unittest.main()
