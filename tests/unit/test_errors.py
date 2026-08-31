"""Tests for CLI commands and error handling."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from think_box_ai.utils.errors import suggest_command, handle_unknown_command
from think_box_ai.ui.colors import supports_color, verdict_color


class TestErrorHandler(unittest.TestCase):
    def test_suggest_command_close(self):
        result = suggest_command("lst", ["list", "show", "submit"])
        self.assertEqual(result, "list")

    def test_suggest_command_no_match(self):
        result = suggest_command("xyz", ["list", "show"])
        self.assertIsNone(result)

    def test_handle_unknown_command_with_suggestion(self):
        msg = handle_unknown_command("lst", ["list", "show"])
        self.assertIn("Did you mean", msg)
        self.assertIn("list", msg)

    def test_handle_unknown_command_no_suggestion(self):
        msg = handle_unknown_command("xyz", ["list", "show"])
        self.assertIn("Unknown command", msg)


class TestColors(unittest.TestCase):
    def test_verdict_color(self):
        self.assertIn("32", verdict_color("succeeded"))  # green
        self.assertIn("31", verdict_color("blocked"))  # red
        self.assertIn("33", verdict_color("unproven"))  # yellow

    def test_supports_color(self):
        result = supports_color()
        self.assertIsInstance(result, bool)


class TestJobValidation(unittest.TestCase):
    def test_all_templates_valid(self):
        import json
        tmpl_dir = Path("jobs/templates")
        if not tmpl_dir.exists():
            return
        for tmpl in tmpl_dir.glob("template_*.json"):
            job = json.loads(tmpl.read_text())
            self.assertIn("id", job)
            self.assertIn("evaluation", job)
            self.assertIn("cost", job)

    def test_all_jobs_have_cost(self):
        import json
        for state in ["done", "blocked"]:
            state_dir = Path(f"jobs/{state}")
            if not state_dir.exists():
                continue
            for jf in state_dir.glob("job_*.json"):
                job = json.loads(jf.read_text())
                self.assertIn("cost", job, f"{jf.name} missing cost")


if __name__ == "__main__":
    unittest.main()
