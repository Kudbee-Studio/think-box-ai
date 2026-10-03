"""Hermetic tests for the redacting live-proof bundle builder.

No network, no real worker: every fixture is a temp directory with hand-built
artifact/receipt/checkpoint JSON that mirrors a real governed ``upcloud-ssh`` run.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from thinkbox.execution_adapter import _sha256_file
from thinkbox.live_proof_bundle import (
    LiveProofBundleError,
    build_live_proof_bundle,
    default_evidence_dir,
    scan_for_secrets,
    write_live_proof_bundle,
)

WORKER_IP = "209.50.51.174"
RECORDED_AT = "2026-10-03T12:00:00+00:00"


def _artifact_payload(**overrides: object) -> dict:
    payload = {
        "provider": "upcloud-ssh",
        "execution_id": "exec_test0001",
        "job_id": "engine_test0001",
        "exit_code": 0,
        "timed_out": False,
        "intent_fingerprint": "7063dece7cccf374",
        "command_argv_preview": ["hostname"],
        "remote_host": WORKER_IP,
        "remote_user": "root",
        "elapsed_s": 1.2,
        "stdout": "kudbee-hermes-worker-02\n",
        "stderr": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
    }
    payload.update(overrides)
    return payload


class _Fixture:
    def __init__(self, tmp: Path, payload: dict | None = None) -> None:
        self.dir = tmp
        self.artifact_path = tmp / "exec_test0001-governed_exec.json"
        self.payload = payload or _artifact_payload()
        self.artifact_path.write_text(json.dumps(self.payload, sort_keys=True), encoding="utf-8")
        self.artifact_hash = _sha256_file(self.artifact_path)

    def receipt(self, **overrides: object) -> dict:
        receipt = {
            "job_id": "engine_test0001",
            "execution_id": "exec_test0001",
            "provider": "upcloud-ssh",
            "status": "COMPLETED",
            "verified": True,
            "exit_code": 0,
            "start_time": "2026-10-03T11:59:58+00:00",
            "end_time": "2026-10-03T12:00:00+00:00",
            "artifact_name": "governed_exec.json",
            "artifact_hash": self.artifact_hash,
            "artifact_path": "/home/x/.thinkbox/artifacts/exec_test0001-governed_exec.json",
            "checkpoint_id": "chk_test0001",
            "receipt_path": "/home/x/.thinkbox/checkpoints/chk_test0001.json",
            "error": "",
            "provenance": ["discover_upcloud_ssh", "execute_ssh", "checkpoint_created", "hash_verified"],
        }
        receipt.update(overrides)
        return receipt

    @staticmethod
    def checkpoint() -> dict:
        return {
            "checkpoint_id": "chk_test0001",
            "git_branch": "feat/pr340-p3-live-proof-bundle",
            "head": "abc1234",
            "path": "/workspace/secret/absolute/path",
            "metadata": {
                "receipt_id": "exec_test0001",
                "artifact_path": "/home/x/.thinkbox/artifacts/exec_test0001-governed_exec.json",
                "artifact_hash": "deadbeef",
            },
        }


class TestSecretScan(unittest.TestCase):
    def test_clean_text_has_no_hits(self) -> None:
        self.assertEqual(scan_for_secrets("hostname\nkudbee-hermes-worker-02"), [])

    def test_private_key_block_detected(self) -> None:
        self.assertIn("private_key_block", scan_for_secrets("-----BEGIN OPENSSH PRIVATE KEY-----"))

    def test_bearer_token_detected(self) -> None:
        self.assertIn("bearer_token", scan_for_secrets("Authorization: Bearer abcdef0123456789xyz"))

    def test_ssh_key_path_detected(self) -> None:
        self.assertIn("ssh_key_path", scan_for_secrets("using ~/.ssh/kilo-upcloud"))


class TestBuildBundle(unittest.TestCase):
    def test_valid_run_produces_verified_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(Path(tmp))
            result = build_live_proof_bundle(
                fixture.artifact_path,
                fixture.receipt(),
                fixture.checkpoint(),
                recorded_at=RECORDED_AT,
            )
            self.assertEqual(result.execution_id, "exec_test0001")
            self.assertTrue(result.bundle["live_verified"])
            self.assertEqual(result.bundle["artifact_sha256"], fixture.artifact_hash)
            self.assertEqual(result.bundle["artifact"]["stdout"], "kudbee-hermes-worker-02\n")
            self.assertTrue(result.bundle["artifact"]["remote_host_known"])
            self.assertEqual(result.warnings, ())

    def test_absolute_paths_never_survive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(Path(tmp))
            result = build_live_proof_bundle(
                fixture.artifact_path,
                fixture.receipt(),
                fixture.checkpoint(),
                recorded_at=RECORDED_AT,
            )
            serialized = json.dumps(result.bundle)
            self.assertNotIn("/workspace/secret/absolute/path", serialized)
            self.assertNotIn(".thinkbox/artifacts", serialized)
            self.assertNotIn("remote_user", result.bundle["artifact"])
            self.assertNotIn("path", result.bundle["checkpoint"]["metadata_keys"])

    def test_unknown_artifact_fields_are_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = _artifact_payload(internal_note="should not survive", api_token="leaky")
            fixture = _Fixture(Path(tmp), payload=payload)
            result = build_live_proof_bundle(
                fixture.artifact_path,
                fixture.receipt(),
                None,
                recorded_at=RECORDED_AT,
            )
            serialized = json.dumps(result.bundle)
            self.assertNotIn("should not survive", serialized)
            self.assertNotIn("leaky", serialized)

    def test_unknown_remote_host_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = _artifact_payload(remote_host="10.0.0.5")
            fixture = _Fixture(Path(tmp), payload=payload)
            result = build_live_proof_bundle(
                fixture.artifact_path,
                fixture.receipt(),
                None,
                recorded_at=RECORDED_AT,
            )
            self.assertFalse(result.bundle["artifact"]["remote_host_known"])
            self.assertEqual(result.bundle["artifact"]["remote_host"], "<redacted-host>")

    def test_missing_checkpoint_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(Path(tmp))
            result = build_live_proof_bundle(
                fixture.artifact_path,
                fixture.receipt(),
                None,
                recorded_at=RECORDED_AT,
            )
            self.assertIn("checkpoint_missing", result.warnings)


class TestFailClosed(unittest.TestCase):
    def test_hash_mismatch_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(Path(tmp))
            with self.assertRaises(LiveProofBundleError) as ctx:
                build_live_proof_bundle(
                    fixture.artifact_path,
                    fixture.receipt(artifact_hash="0" * 64),
                    None,
                    recorded_at=RECORDED_AT,
                )
            self.assertIn("hash mismatch", str(ctx.exception))

    def test_non_completed_status_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(Path(tmp))
            with self.assertRaises(LiveProofBundleError):
                build_live_proof_bundle(
                    fixture.artifact_path,
                    fixture.receipt(status="TIMEOUT"),
                    None,
                    recorded_at=RECORDED_AT,
                )

    def test_unverified_receipt_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(Path(tmp))
            with self.assertRaises(LiveProofBundleError):
                build_live_proof_bundle(
                    fixture.artifact_path,
                    fixture.receipt(verified=False),
                    None,
                    recorded_at=RECORDED_AT,
                )

    def test_wrong_provider_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(Path(tmp), payload=_artifact_payload(provider="local"))
            with self.assertRaises(LiveProofBundleError):
                build_live_proof_bundle(
                    fixture.artifact_path,
                    fixture.receipt(),
                    None,
                    recorded_at=RECORDED_AT,
                )

    def test_secret_in_stdout_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = _artifact_payload(stdout="-----BEGIN OPENSSH PRIVATE KEY-----\n")
            fixture = _Fixture(Path(tmp), payload=payload)
            with self.assertRaises(LiveProofBundleError) as ctx:
                build_live_proof_bundle(
                    fixture.artifact_path,
                    fixture.receipt(),
                    None,
                    recorded_at=RECORDED_AT,
                )
            self.assertIn("secret", str(ctx.exception))

    def test_missing_artifact_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(Path(tmp))
            with self.assertRaises(LiveProofBundleError):
                build_live_proof_bundle(
                    Path(tmp) / "nope.json",
                    fixture.receipt(),
                    None,
                    recorded_at=RECORDED_AT,
                )


class TestWriteBundle(unittest.TestCase):
    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(Path(tmp))
            result = build_live_proof_bundle(
                fixture.artifact_path,
                fixture.receipt(),
                fixture.checkpoint(),
                recorded_at=RECORDED_AT,
            )
            out = Path(tmp) / "evidence"
            json_path, md_path = write_live_proof_bundle(result, out)
            self.assertTrue(json_path.is_file())
            self.assertTrue(md_path.is_file())
            self.assertEqual(json_path.name, "exec_test0001.json")
            self.assertIn("kudbee-hermes-worker-02", md_path.read_text(encoding="utf-8"))
            reloaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(reloaded["artifact_sha256"], fixture.artifact_hash)

    def test_default_evidence_dir_layout(self) -> None:
        self.assertEqual(
            default_evidence_dir(Path("/repo")),
            Path("/repo/docs/evidence/live-proof"),
        )


if __name__ == "__main__":
    unittest.main()
