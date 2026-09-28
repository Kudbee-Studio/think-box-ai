"""Hermetic unit tests for SSHCloudExecutionProvider — subprocess is mocked;
no network I/O in this file. See tests/integration/test_upcloud_live.py-style
gating for the real live proof (run separately, not part of this suite)."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from thinkbox.cloud_execution.errors import CloudExecutionError
from thinkbox.cloud_execution.job import ExecutionJob
from thinkbox.cloud_execution.providers.ssh_remote import (
    SSHCloudExecutionProvider,
    SSHWorkerConfig,
)
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding


def _limits() -> ResourceLimits:
    return ResourceLimits(cpu_cores=1, memory_mb=256, wall_clock_timeout_s=5, max_concurrency=1)


def _ws() -> WorkspaceBinding:
    return WorkspaceBinding(workspace_id="ws1", worktree_path="/tmp/ws1")


def _config() -> SSHWorkerConfig:
    return SSHWorkerConfig(host="203.0.113.10", username="root", private_key_path="/fake/id_rsa")


class TestSSHConfig(unittest.TestCase):
    def test_missing_host_rejected(self) -> None:
        with self.assertRaises(CloudExecutionError):
            SSHWorkerConfig(host="").validate()

    def test_missing_username_rejected(self) -> None:
        with self.assertRaises(CloudExecutionError):
            SSHWorkerConfig(host="1.2.3.4", username="").validate()


class TestSSHProviderRun(unittest.TestCase):
    def test_missing_command_rejected(self) -> None:
        provider = SSHCloudExecutionProvider(_config())
        job = ExecutionJob(intent="x")  # no metadata["command"]
        with self.assertRaises(CloudExecutionError):
            provider.run(job, _limits(), _ws())

    @patch("thinkbox.cloud_execution.providers.ssh_remote.subprocess.run")
    def test_success(self, mock_run) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ssh"], returncode=0, stdout="kudbee-hermes-worker-02\n", stderr=""
        )
        provider = SSHCloudExecutionProvider(_config())
        job = ExecutionJob(intent="hostname", metadata={"command": "hostname"})
        result = provider.run(job, _limits(), _ws())

        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.summary, "kudbee-hermes-worker-02")
        self.assertEqual(result.metadata["stdout"], "kudbee-hermes-worker-02")
        self.assertIn("ssh-stdout://", result.artifact_refs[0])
        # private key path never leaks into metadata
        self.assertNotIn("/fake/id_rsa", str(result.metadata))

    @patch("thinkbox.cloud_execution.providers.ssh_remote.subprocess.run")
    def test_nonzero_exit(self, mock_run) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ssh"], returncode=127, stdout="", stderr="command not found"
        )
        provider = SSHCloudExecutionProvider(_config())
        job = ExecutionJob(intent="bad", metadata={"command": "nope"})
        result = provider.run(job, _limits(), _ws())

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 127)
        self.assertEqual(result.summary, "command not found")
        self.assertEqual(result.artifact_refs, [])

    @patch("thinkbox.cloud_execution.providers.ssh_remote.subprocess.run")
    def test_timeout(self, mock_run) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=5, output="", stderr="")
        provider = SSHCloudExecutionProvider(_config())
        job = ExecutionJob(intent="slow", metadata={"command": "sleep 100"})
        result = provider.run(job, _limits(), _ws())

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 124)
        self.assertIn("timeout", result.summary)

    @patch("thinkbox.cloud_execution.providers.ssh_remote.subprocess.run")
    def test_connection_failure_ssh_binary_missing(self, mock_run) -> None:
        mock_run.side_effect = FileNotFoundError("no such file: ssh")
        provider = SSHCloudExecutionProvider(_config())
        job = ExecutionJob(intent="x", metadata={"command": "hostname"})
        with self.assertRaises(CloudExecutionError):
            provider.run(job, _limits(), _ws())

    @patch("thinkbox.cloud_execution.providers.ssh_remote.subprocess.run")
    def test_unavailable_provider_fails_closed(self, mock_run) -> None:
        provider = SSHCloudExecutionProvider(_config())
        provider.set_available(False)
        job = ExecutionJob(intent="x", metadata={"command": "hostname"})
        with self.assertRaises(CloudExecutionError):
            provider.run(job, _limits(), _ws())
        mock_run.assert_not_called()

    @patch("thinkbox.cloud_execution.providers.ssh_remote.subprocess.run")
    def test_stdout_stderr_captured_separately(self, mock_run) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ssh"], returncode=0, stdout="out-line\n", stderr="warn-line\n"
        )
        provider = SSHCloudExecutionProvider(_config())
        job = ExecutionJob(intent="x", metadata={"command": "hostname"})
        result = provider.run(job, _limits(), _ws())

        self.assertEqual(result.metadata["stdout"], "out-line")
        self.assertEqual(result.metadata["stderr"], "warn-line")

    def test_build_receipt_reused_unchanged(self) -> None:
        """The provider must not redefine build_receipt — it inherits the base
        class's existing honest receipt construction (verification_class stays
        TEST_VERIFIED at the substrate layer; live_api_called defaults False
        unless the caller sets it)."""
        self.assertNotIn("build_receipt", SSHCloudExecutionProvider.__dict__)


if __name__ == "__main__":
    unittest.main()
