"""scripts/verify_upcloud_credentials.py promises 'No credentials printed to stdout' (and AGENTS.md 0.4)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_upcloud_credentials.py"
_TOKEN = "ucat_HEADPART" + "x" * 30 + "TAIL"


def _load():
    spec = importlib.util.spec_from_file_location("verify_upcloud_credentials_script", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestVerifyUpcloudNoTokenOutput(unittest.TestCase):
    def test_no_part_of_the_token_is_printed(self) -> None:
        script = _load()
        out = io.StringIO()
        with patch.dict(os.environ, {"THINKBOX_UPCLOUD_API_TOKEN": _TOKEN}, clear=False), \
                patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline in tests")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            script.verify_upcloud_credentials()
        text = out.getvalue()
        self.assertIn("Token loaded", text)
        for fragment in ("ucat_HEA", "HEADPART", "TAIL", _TOKEN[:8], _TOKEN[-4:]):
            self.assertNotIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
