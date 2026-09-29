"""Hermetic tests for the ``upcloud-ssh`` governed substrate (no network; SSH provider faked)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest import mock

from thinkbox.cloud_execution.errors import CloudExecutionError
from thinkbox.cloud_execution.provider import ProviderRunResult
from thinkbox.governed_job_execution import (
    SUBSTRATE_UPCLOUD_SSH,
    GovernedJobExecutionError,
    execute_governed_job_command,
    select_execution_adapter,
)
from thinkbox.lifecycle_harden import (
    LifecycleError,
    reject_remote_local_fallback,
    validate_substrate,
)
from thinkbox.repository import Repository
from thinkbox.upcloud_ssh_execution_adapter import (
    UPCLOUD_SSH_PROVIDER,
    UpCloudSSHExecutionAdapter,
    UpCloudSSHExecutionConfig,
)


def _make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "initial"], cwd=str(path), check=True)


class _FakeSSH:
    """Stands in for SSHCloudExecutionProvider; records the config and job it was given."""

    instances: ClassVar[list[_FakeSSH]] = []

    def __init__(self, config, result=None, raises=None) -> None:
        self.config = config
        self._result = result
        self._raises = raises
        self.jobs = []
        _FakeSSH.instances.append(self)

    def run(self, job, limits, workspace):
        self.jobs.append((job, limits, workspace))
        if self._raises:
            raise self._raises
        return self._result


def _factory(result=None, raises=None):
    return lambda cfg: _FakeSSH(cfg, result=result, raises=raises)


def _ok(stdout="kudbee-hermes-worker-02", exit_code=0, summary=None, stderr=""):
    return ProviderRunResult(
        success=exit_code == 0,
        exit_code=exit_code,
        summary=summary if summary is not None else (stdout if exit_code == 0 else stderr),
        metadata={"stdout": stdout, "stderr": stderr, "elapsed_s": 0.5},
    )


class _RepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.repo_path = root / "repo"
        self.repo_path.mkdir()
        _make_git_repo(self.repo_path)
        self.repo = Repository(self.repo_path)
        self.key = root / "id_test"
        self.key.write_text("not-a-real-key")
        self.cfg = UpCloudSSHExecutionConfig(host="203.0.113.10", username="root", private_key_path=str(self.key))
        _FakeSSH.instances.clear()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def adapter(self, **kw):
        return UpCloudSSHExecutionAdapter(repo=self.repo, config=self.cfg, **kw)


class TestConfig(_RepoCase):
    def test_from_env_reads_existing_upcloudconfig_vars(self) -> None:
        cfg = UpCloudSSHExecutionConfig.from_env(
            {"UPCLOUD_SERVER_IP": "209.50.51.174", "UPCLOUD_SSH_KEY_PATH": str(self.key)}
        )
        self.assertEqual((cfg.host, cfg.username, cfg.private_key_path), ("209.50.51.174", "root", str(self.key)))
        self.assertTrue(cfg.is_complete())

    def test_incomplete_without_ip_or_existing_key(self) -> None:
        self.assertFalse(UpCloudSSHExecutionConfig.from_env({"UPCLOUD_SSH_KEY_PATH": str(self.key)}).is_complete())
        self.assertFalse(
            UpCloudSSHExecutionConfig.from_env(
                {"UPCLOUD_SERVER_IP": "1.2.3.4", "UPCLOUD_SSH_KEY_PATH": "/nonexistent/key"}
            ).is_complete()
        )


class TestAdapterExecute(_RepoCase):
    def test_success_writes_verified_artifact_and_checkpoint(self) -> None:
        receipt = self.adapter(provider_factory=_factory(_ok())).execute("job_ok", command="hostname")
        self.assertEqual(receipt.status, "COMPLETED")
        self.assertEqual(receipt.provider, UPCLOUD_SSH_PROVIDER)
        self.assertEqual(receipt.exit_code, 0)
        self.assertTrue(receipt.verified)
        self.assertTrue(receipt.checkpoint_id)
        artifact = json.loads(Path(receipt.artifact_path).read_text())
        self.assertEqual(artifact["stdout"], "kudbee-hermes-worker-02")
        self.assertEqual(artifact["remote_host"], "203.0.113.10")
        self.assertNotIn(str(self.key), json.dumps(artifact))
        # the SSH provider got the configured worker and the command via job.metadata
        fake = _FakeSSH.instances[0]
        self.assertEqual((fake.config.host, fake.config.username, fake.config.private_key_path),
                         ("203.0.113.10", "root", str(self.key)))
        self.assertEqual(fake.jobs[0][0].metadata["command"], "hostname")

    def test_remote_nonzero_exit_is_exit_failed_without_checkpoint(self) -> None:
        receipt = self.adapter(provider_factory=_factory(_ok(stdout="", exit_code=2, stderr="boom"))).execute(
            "job_fail", command="false"
        )
        self.assertEqual(receipt.status, "EXIT_FAILED")
        self.assertEqual(receipt.exit_code, 2)
        self.assertFalse(receipt.checkpoint_id)

    def test_ssh_transport_error_255_is_ssh_failed(self) -> None:
        res = _ok(stdout="", exit_code=255, stderr="root@203.0.113.10: Permission denied (publickey).")
        receipt = self.adapter(provider_factory=_factory(res)).execute("job_auth", command="hostname")
        self.assertEqual(receipt.status, "SSH_FAILED")
        self.assertIn("Permission denied", receipt.error)
        self.assertFalse(receipt.checkpoint_id)

    def test_timeout(self) -> None:
        res = _ok(stdout="", exit_code=124, summary="ssh timeout after 30.00s: 'sleep 99'")
        receipt = self.adapter(provider_factory=_factory(res)).execute("job_slow", command="sleep 99")
        self.assertEqual(receipt.status, "TIMEOUT")

    def test_provider_error_is_ssh_failed(self) -> None:
        err = CloudExecutionError(error_type="ProviderRunFailed", context={"reason": "ssh binary not found"})
        receipt = self.adapter(provider_factory=_factory(raises=err)).execute("job_err", command="hostname")
        self.assertEqual(receipt.status, "SSH_FAILED")
        self.assertEqual(receipt.error, "ProviderRunFailed")

    def test_empty_command_fails_closed_without_ssh(self) -> None:
        receipt = self.adapter(provider_factory=_factory(_ok())).execute("job_empty", command="  ")
        self.assertEqual(receipt.status, "INVALID_COMMAND")
        self.assertEqual(_FakeSSH.instances, [])

    def test_not_configured_fails_closed_without_ssh(self) -> None:
        adapter = UpCloudSSHExecutionAdapter(
            repo=self.repo, config=UpCloudSSHExecutionConfig(), provider_factory=_factory(_ok())
        )
        receipt = adapter.execute("job_nc", command="hostname")
        self.assertEqual(receipt.status, "NOT_CONFIGURED")
        self.assertEqual(_FakeSSH.instances, [])


class TestGovernedRouting(_RepoCase):
    def test_unconfigured_upcloud_ssh_raises_never_falls_back_to_local(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(GovernedJobExecutionError) as ctx:
            select_execution_adapter(SUBSTRATE_UPCLOUD_SSH, self.repo)
        self.assertEqual(ctx.exception.code, "remote_not_configured")

    def test_configured_upcloud_ssh_routes_and_marks_live_api_called(self) -> None:
        env = {"UPCLOUD_SERVER_IP": "203.0.113.10", "UPCLOUD_SSH_KEY_PATH": str(self.key)}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch(
            "thinkbox.upcloud_ssh_execution_adapter.SSHCloudExecutionProvider",
            side_effect=lambda cfg: _FakeSSH(cfg, result=_ok()),
        ):
            result = execute_governed_job_command(
                substrate="UpCloud-SSH", job_id="job_routed", command="hostname", repo=self.repo
            )
        self.assertEqual(result.substrate, SUBSTRATE_UPCLOUD_SSH)
        self.assertEqual(result.adapter_provider, UPCLOUD_SSH_PROVIDER)
        self.assertEqual(result.receipt.status, "COMPLETED")
        self.assertTrue(result.public_proof["live_api_called"])
        self.assertFalse(result.public_proof["live_verified"])


class TestLifecycleHarden(unittest.TestCase):
    def test_upcloud_ssh_is_an_allowed_substrate(self) -> None:
        self.assertEqual(validate_substrate(" UPCLOUD-SSH "), SUBSTRATE_UPCLOUD_SSH)

    def test_upcloud_ssh_cannot_record_local_provider(self) -> None:
        with self.assertRaises(LifecycleError):
            reject_remote_local_fallback(SUBSTRATE_UPCLOUD_SSH, "local")
        reject_remote_local_fallback(SUBSTRATE_UPCLOUD_SSH, UPCLOUD_SSH_PROVIDER)


if __name__ == "__main__":
    unittest.main()
