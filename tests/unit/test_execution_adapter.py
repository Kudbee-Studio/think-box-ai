"""Unit tests for thinkbox/execution_adapter.py and CLI execute."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import unittest.mock
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from thinkbox.execution_adapter import (
    ENV_TOKEN,
    ENV_URL,
    UpstashBoxConfig,
    UpstashBoxExecutionAdapter,
    _sha256_bytes,
    _sha256_file,
)
from thinkbox.repository import Repository

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHONPATH = str(REPO_ROOT)


def _make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "initial"], cwd=str(path), check=True)


def _run_cli(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "thinkbox.repository_cli", *args],
        cwd=str(cwd),
        env={**os.environ, "PYTHONPATH": PYTHONPATH, **(env or {})},
        capture_output=True,
        text=True,
        timeout=30,
    )


class _BoxHandler(BaseHTTPRequestHandler):
    artifact_content = '{"hostname":"box","os":"linux"}'
    artifact_hash = _sha256_bytes(artifact_content.encode("utf-8"))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length)
        body = json.dumps({
            "exit_code": 0,
            "hostname": "box",
            "os": "linux",
            "output": self.artifact_content,
            "artifact_name": "artifact.json",
            "artifact_content": self.artifact_content,
            "artifact_hash": self.artifact_hash,
        })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args) -> None:
        pass


class TestExecutionAdapter(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._repo = Path(self._tmp.name) / "repo"
        self._repo.mkdir()
        _make_git_repo(self._repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_config_loads_from_env(self):
        with unittest.mock.patch.dict(
            os.environ,
            {ENV_URL: "https://box.example.com", ENV_TOKEN: "token"},
            clear=True,
        ):
            config = UpstashBoxConfig.load_from_env()
        self.assertEqual(config.url, "https://box.example.com")
        self.assertEqual(config.token, "token")
        self.assertEqual(config.box_id, "box")
        self.assertTrue(config.is_configured)

    def test_config_unconfigured_when_missing(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            config = UpstashBoxConfig.load_from_env()
        self.assertFalse(config.is_configured)

    def test_discover_env_names_only(self):
        adapter = UpstashBoxExecutionAdapter(repo=Repository(self._repo))
        inventory = adapter.discover_env()
        self.assertIn(ENV_URL, inventory)
        self.assertIn(ENV_TOKEN, inventory)
        self.assertFalse(any(isinstance(v, str) and v for v in inventory.values()))

    def test_fail_closed_when_unconfigured(self):
        adapter = UpstashBoxExecutionAdapter(repo=Repository(self._repo))
        receipt = adapter.execute(job_id="job_unconfigured", command="echo hi")
        self.assertEqual(receipt.status, "NOT_CONFIGURED")
        self.assertFalse(receipt.verified)
        self.assertFalse(receipt.artifact_path)
        self.assertIn("fail_closed_no_config", receipt.provenance)
        self.assertFalse(adapter.is_configured())

    def test_verify_helper(self):
        p = Path(self._tmp.name) / "file"
        p.write_text("hello")
        receipt = type("R", (), {"artifact_path": str(p), "artifact_hash": _sha256_file(p)})()
        self.assertTrue(UpstashBoxExecutionAdapter(repo=Repository(self._repo)).verify(receipt))

    def test_live_path_with_local_stub(self):
        server = HTTPServer(("127.0.0.1", 0), _BoxHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            with unittest.mock.patch.dict(
                os.environ,
                {ENV_URL: url, ENV_TOKEN: "token"},
                clear=True,
            ):
                adapter = UpstashBoxExecutionAdapter(repo=Repository(self._repo))
                receipt = adapter.execute(
                    job_id="job_live",
                    command="echo hello",
                    artifact_name="artifact.json",
                )
            self.assertEqual(receipt.status, "COMPLETED")
            self.assertTrue(receipt.verified)
            self.assertEqual(receipt.exit_code, 0)
            self.assertTrue(receipt.artifact_path)
            self.assertTrue(Path(receipt.artifact_path).exists())
            self.assertEqual(receipt.artifact_hash, _sha256_file(Path(receipt.artifact_path)))
            self.assertTrue(receipt.checkpoint_id)
            self.assertTrue(receipt.receipt_path)
            self.assertIn("hash_verified", receipt.provenance)
            self.assertIn("checkpoint_created", receipt.provenance)
            self.assertTrue(adapter.verify(receipt))
        finally:
            server.shutdown()
            server.server_close()


class TestCLIExecute(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._repo = Path(self._tmp.name) / "repo"
        self._repo.mkdir()
        _make_git_repo(self._repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_cli_execute_fail_closed(self):
        result = _run_cli(
            ["job", "execute", "--job-id", "job_cli", "--exec-command", "echo hi"],
            self._repo,
            env={},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: NOT_CONFIGURED", result.stdout)
        self.assertNotIn("echo hi", result.stdout)
        self.assertIn("remote execution is unavailable", result.stdout)
        checkpoint_dir = self._repo / ".thinkbox" / "checkpoints"
        self.assertTrue(checkpoint_dir.exists())
        self.assertEqual(list(checkpoint_dir.glob("*.json")), [])

    def test_cli_execute_live_with_stub(self):
        server = HTTPServer(("127.0.0.1", 0), _BoxHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            result = _run_cli(
                ["job", "execute", "--job-id", "job_cli_live", "--exec-command", "echo hi"],
                self._repo,
                env={ENV_URL: url, ENV_TOKEN: "token"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("status: COMPLETED", result.stdout)
            self.assertIn("verified: True", result.stdout)
            self.assertIn("checkpoint_id:", result.stdout)
            self.assertIn("receipt_path:", result.stdout)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
