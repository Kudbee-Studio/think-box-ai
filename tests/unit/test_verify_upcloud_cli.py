"""Hermetic tests for scripts/verify_upcloud_cli.py (subprocess mocked; no network, no upctl needed)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_upcloud_cli.py"
FAKE_TOKEN = "ucat_FAKE_TOKEN_FOR_TESTS_0000"


def _load():
    spec = importlib.util.spec_from_file_location("verify_upcloud_cli", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cp(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["upctl"], returncode=returncode, stdout=stdout, stderr=stderr)


class TestVerifyUpcloudCli(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _load()

    def _run(self, side_effect, environ=None):
        buf = io.StringIO()
        with patch.object(self.mod.subprocess, "run", side_effect=side_effect) as run, contextlib.redirect_stdout(buf):
            code = self.mod.verify_upctl(environ if environ is not None else {})
        return code, buf.getvalue(), run

    def test_uses_official_version_subcommand(self) -> None:
        code, _, run = self._run([_cp(0, "Upctl v3.36.0"), _cp(0, "Username: kudbeex")])
        self.assertEqual(code, 0)
        self.assertEqual(run.call_args_list[0].args[0], ["upctl", "version"])

    def test_not_installed_returns_1(self) -> None:
        code, out, _ = self._run(FileNotFoundError("upctl"))
        self.assertEqual(code, 1)
        self.assertIn("not found", out)

    def test_version_nonzero_returns_1(self) -> None:
        code, _, _ = self._run([_cp(2)])
        self.assertEqual(code, 1)

    def test_authenticated_without_legacy_config_file(self) -> None:
        # Regression: the old script required ~/.upcloud/config, a path upctl never uses,
        # so it failed every correctly configured install.
        with tempfile.TemporaryDirectory() as empty_home, patch.dict("os.environ", {"HOME": empty_home}):
            code, out, _ = self._run([_cp(0, "Upctl v3.36.0"), _cp(0, "Username: kudbeex\nCredits: 1")])
        self.assertEqual(code, 0)
        self.assertIn("authenticated", out)
        self.assertIn("Username: kudbeex", out)

    def test_auth_failure_returns_2(self) -> None:
        code, out, _ = self._run([_cp(0, "Upctl v3.36.0"), _cp(1, stderr="Authentication failed")])
        self.assertEqual(code, 2)
        self.assertIn("failed", out)

    def test_repo_token_mapped_to_upcloud_token_and_never_printed(self) -> None:
        code, out, run = self._run(
            [_cp(0, "Upctl v3.36.0"), _cp(0, "Username: kudbeex")],
            environ={"THINKBOX_UPCLOUD_API_TOKEN": FAKE_TOKEN},
        )
        self.assertEqual(code, 0)
        passed_env = run.call_args_list[1].kwargs["env"]
        self.assertEqual(passed_env["UPCLOUD_TOKEN"], FAKE_TOKEN)
        self.assertNotIn(FAKE_TOKEN, out)
        self.assertIn("mapped to UPCLOUD_TOKEN", out)

    def test_explicit_upcloud_token_not_overridden(self) -> None:
        env = self.mod.upctl_env({"UPCLOUD_TOKEN": "explicit", "THINKBOX_UPCLOUD_API_TOKEN": "repo"})
        self.assertEqual(env["UPCLOUD_TOKEN"], "explicit")

    def test_no_token_leaves_upctl_to_config_or_keyring(self) -> None:
        env = self.mod.upctl_env({})
        self.assertNotIn("UPCLOUD_TOKEN", env)

    def test_install_instructions_are_official_not_pip(self) -> None:
        text = self.mod.INSTALL_INSTRUCTIONS
        self.assertNotRegex(text, r"(?m)^\s*(python3 -m )?pip install")
        self.assertIn("brew tap UpCloudLtd/tap", text)
        self.assertIn("_amd64.deb", text)
        self.assertIn("go install github.com/UpCloudLtd/upcloud-cli/v3/...@latest", text)
        self.assertIn("upctl account login --with-token", text)

    def test_install_flag_prints_instructions_only_on_failure(self) -> None:
        buf = io.StringIO()
        with patch.object(self.mod.subprocess, "run", side_effect=FileNotFoundError("upctl")), contextlib.redirect_stdout(buf):
            self.assertEqual(self.mod.main(["--install"]), 1)
        self.assertIn("brew tap UpCloudLtd/tap", buf.getvalue())

        buf = io.StringIO()
        with patch.object(self.mod.subprocess, "run", side_effect=[_cp(0, "v"), _cp(0, "Username: x")]), \
                patch.dict("os.environ", {}, clear=False), contextlib.redirect_stdout(buf):
            self.assertEqual(self.mod.main(["--install"]), 0)
        self.assertNotIn("brew tap", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
