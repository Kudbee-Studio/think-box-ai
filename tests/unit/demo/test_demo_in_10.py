"""Tests: demo_in_10_control_plane.sh + data/proofs/ gitignore."""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path


class TestDemoIn10ControlPlane(unittest.TestCase):
    def test_script_exists(self) -> None:
        path = Path("scripts/demo_in_10_control_plane.sh")
        self.assertTrue(path.exists(), f"{path} not found")
        self.assertTrue(os.access(str(path), os.X_OK), f"{path} not executable")

    def test_script_has_key_steps(self) -> None:
        content = Path("scripts/demo_in_10_control_plane.sh").read_text()
        for keyword in ["burst", "harvest", "proof", "verify", "mock"]:
            self.assertIn(keyword, content, f"Missing keyword: {keyword}")

    def test_gitignore_has_proofs(self) -> None:
        gitignore = Path(".gitignore").read_text()
        self.assertIn("data/proofs/", gitignore, "data/proofs/ not in .gitignore")

    def test_no_gpu_usage(self) -> None:
        content = Path("scripts/demo_in_10_control_plane.sh").read_text()
        self.assertNotIn("nvidia-smi", content, "Script should not use GPU")
        self.assertNotIn("CUDA_VISIBLE_DEVICES", content, "Script should not use CUDA")
        self.assertNotIn("/dev/nvidia", content, "Script should not access GPU devices")
