"""Tests for Think Box CLI commands."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

JOBS_DIR = Path(__file__).resolve().parent.parent / "jobs"


class TestJobSchema(unittest.TestCase):
    """Test job schema validation."""

    def test_all_jobs_have_required_fields(self):
        required = ["id", "intent", "hat", "inputs", "plan", "capabilities", "execution", "artifacts", "evaluation"]
        for state in ["done", "blocked", "queue", "templates"]:
            state_dir = JOBS_DIR / state
            if not state_dir.is_dir():
                continue
            for jf in state_dir.glob("job_*.json"):
                job = json.loads(jf.read_text())
                for field in required:
                    self.assertIn(field, job, f"{jf.name} missing {field}")

    def test_all_jobs_have_valid_hat(self):
        valid_hats = ["researcher", "runner", "director", "camera", "jury"]
        for state in ["done", "blocked", "queue"]:
            state_dir = JOBS_DIR / state
            if not state_dir.is_dir():
                continue
            for jf in state_dir.glob("job_*.json"):
                job = json.loads(jf.read_text())
                self.assertIn(job.get("hat"), valid_hats, f"{jf.name} invalid hat")

    def test_all_jobs_have_valid_verdict(self):
        valid = ["succeeded", "failed", "unproven", "blocked"]
        for state in ["done", "blocked", "queue"]:
            state_dir = JOBS_DIR / state
            if not state_dir.is_dir():
                continue
            for jf in state_dir.glob("job_*.json"):
                job = json.loads(jf.read_text())
                verdict = job.get("evaluation", {}).get("verdict")
                self.assertIn(verdict, valid, f"{jf.name} invalid verdict")

    def test_all_jobs_have_cost(self):
        for state in ["done", "blocked"]:
            state_dir = JOBS_DIR / state
            if not state_dir.is_dir():
                continue
            for jf in state_dir.glob("job_*.json"):
                job = json.loads(jf.read_text())
                self.assertIn("cost", job, f"{jf.name} missing cost")


class TestCLI(unittest.TestCase):
    """Test CLI commands."""

    def test_job_list_imports(self):
        from think_box_ai.commands import job
        self.assertTrue(hasattr(job, "list_jobs"))
        self.assertTrue(hasattr(job, "show_job"))
        self.assertTrue(hasattr(job, "submit_job"))

    def test_findings_imports(self):
        from think_box_ai.commands import findings
        self.assertTrue(hasattr(findings, "list_findings"))
        self.assertTrue(hasattr(findings, "show_finding"))

    def test_config_imports(self):
        from think_box_ai.commands import config
        self.assertTrue(hasattr(config, "show_config"))
        self.assertTrue(hasattr(config, "set_config"))


if __name__ == "__main__":
    unittest.main()
