"""scripts/setup.py writes a local .env with a fresh API key; the key is never printed (AGENTS.md 0.4)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "setup.py"


def _load():
    spec = importlib.util.spec_from_file_location("thinkbox_setup_script", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestSetupEnvFile(unittest.TestCase):
    def setUp(self) -> None:
        self.setup = _load()
        self.tmp = tempfile.TemporaryDirectory()
        self.env = Path(self.tmp.name) / ".env"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_new_api_key_is_written_but_never_printed(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            created = self.setup.create_env_file(self.env)
        self.assertTrue(created)
        key_line = next(line for line in self.env.read_text().splitlines() if line.startswith("THINKBOX_API_KEY="))
        key = key_line.split("=", 1)[1]
        self.assertTrue(key.startswith("tb_") and len(key) > 20)
        self.assertNotIn(key, out.getvalue())
        self.assertIn(str(self.env), out.getvalue())

    def test_an_existing_env_file_is_left_alone(self) -> None:
        self.env.write_text("KEEP=1\n")
        with contextlib.redirect_stdout(io.StringIO()):
            created = self.setup.create_env_file(self.env)
        self.assertFalse(created)
        self.assertEqual(self.env.read_text(), "KEEP=1\n")


if __name__ == "__main__":
    unittest.main()
