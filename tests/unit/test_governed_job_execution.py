"""Unit tests for explicit substrate governed job execution routing."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from thinkbox.execution_adapter import ENV_TOKEN, ENV_URL, UpstashBoxExecutionAdapter, _sha256_bytes
from thinkbox.governed_job_execution import (
    SUBSTRATE_LOCAL,
    SUBSTRATE_UPSTASH_BOX,
    GovernedJobExecutionError,
    execute_governed_job_command,
    normalize_execution_substrate,
    select_execution_adapter,
)
from thinkbox.local_execution_adapter import LOCAL_PROVIDER, LocalExecutionAdapter
from thinkbox.repository import Repository


def _make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(path),
        check=True,
    )
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "initial"], cwd=str(path), check=True)


class _BoxHandler(BaseHTTPRequestHandler):
    artifact_content = '{"proof":"ok"}'
    artifact_hash = _sha256_bytes(artifact_content.encode("utf-8"))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length)
        body = json.dumps(
            {
                "exit_code": 0,
                "hostname": "box",
                "os": "linux",
                "output": self.artifact_content,
                "artifact_name": "governed_exec.json",
                "artifact_content": self.artifact_content,
                "artifact_hash": self.artifact_hash,
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args: object) -> None:
        return


class TestGovernedJobExecutionRouting(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._repo_path = Path(self._tmp.name) / "repo"
        self._repo_path.mkdir()
        _make_git_repo(self._repo_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_local_substrate_selects_local_adapter(self) -> None:
        adapter, provider = select_execution_adapter(SUBSTRATE_LOCAL, Repository(self._repo_path))
        self.assertEqual(provider, LOCAL_PROVIDER)
        self.assertIsInstance(adapter, LocalExecutionAdapter)

    def test_local_governed_run_produces_receipt_and_checkpoint(self) -> None:
        result = execute_governed_job_command(
            substrate=SUBSTRATE_LOCAL,
            job_id="gov_local_1",
            command="echo THINKBOX_GOVERNED_LOCAL_PROOF",
            repo=Repository(self._repo_path),
        )
        self.assertEqual(result.adapter_provider, LOCAL_PROVIDER)
        self.assertEqual(result.verdict, "COMPLETED")
        self.assertTrue(result.receipt.verified)
        self.assertTrue(result.receipt.checkpoint_id)
        self.assertTrue(Path(result.receipt.artifact_path).exists())
        self.assertFalse(result.public_proof["live_verified"])

    def test_upstash_substrate_without_config_fails_not_local(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(GovernedJobExecutionError) as ctx:
                select_execution_adapter(SUBSTRATE_UPSTASH_BOX, Repository(self._repo_path))
        self.assertEqual(ctx.exception.code, "remote_not_configured")

    def test_upstash_substrate_uses_remote_adapter_when_configured(self) -> None:
        server = HTTPServer(("127.0.0.1", 0), _BoxHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            with mock.patch.dict(os.environ, {ENV_URL: url, ENV_TOKEN: "token"}, clear=True):
                adapter, provider = select_execution_adapter(
                    SUBSTRATE_UPSTASH_BOX,
                    Repository(self._repo_path),
                )
                self.assertIsInstance(adapter, UpstashBoxExecutionAdapter)
                self.assertEqual(provider, "upstash_box")
                result = execute_governed_job_command(
                    substrate=SUBSTRATE_UPSTASH_BOX,
                    job_id="gov_upstash_1",
                    command="echo remote",
                    repo=Repository(self._repo_path),
                )
                self.assertEqual(result.adapter_provider, "upstash_box")
                self.assertEqual(result.verdict, "COMPLETED")
        finally:
            server.shutdown()
            server.server_close()

    def test_unknown_substrate_fails_clearly(self) -> None:
        with self.assertRaises(GovernedJobExecutionError):
            normalize_execution_substrate("kubernetes")


if __name__ == "__main__":
    unittest.main()
