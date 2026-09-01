"""Unit tests for Phase 5 components: autoscaler, pruner, git_engine."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class TestAutoscaler(unittest.TestCase):
    def test_default_config(self):
        from thinkbox.autoscaler import DynamicAutoscaler, ScalerConfig
        scaler = DynamicAutoscaler()
        self.assertEqual(scaler.current_workers, 16)
        self.assertEqual(scaler.config.min_workers, 4)
        self.assertEqual(scaler.config.max_workers, 512)

    def test_custom_config(self):
        from thinkbox.autoscaler import DynamicAutoscaler, ScalerConfig
        config = ScalerConfig(min_workers=2, max_workers=100, default_workers=8)
        scaler = DynamicAutoscaler(config)
        self.assertEqual(scaler.current_workers, 8)

    def test_scale_down(self):
        from thinkbox.autoscaler import DynamicAutoscaler, ScalerConfig
        scaler = DynamicAutoscaler()
        scaler._current_workers = 100
        scaler._metrics.cpu_percent = 95.0
        new_target = scaler._compute_target_workers()
        self.assertLess(new_target, 100)

    def test_scale_up(self):
        from thinkbox.autoscaler import DynamicAutoscaler, ScalerConfig
        scaler = DynamicAutoscaler()
        scaler._current_workers = 16
        scaler._metrics.cpu_percent = 10.0
        scaler._metrics.memory_percent = 20.0
        scaler._metrics.gpu_vram_used_percent = 10.0
        new_target = scaler._compute_target_workers()
        self.assertGreater(new_target, 16)

    def test_bounds_enforced(self):
        from thinkbox.autoscaler import DynamicAutoscaler, ScalerConfig
        config = ScalerConfig(min_workers=4, max_workers=100)
        scaler = DynamicAutoscaler(config)
        scaler._current_workers = 5
        scaler._metrics.gpu_vram_used_percent = 95.0
        new_target = scaler._compute_target_workers()
        self.assertGreaterEqual(new_target, 4)

    def test_pause_resume(self):
        import asyncio
        from thinkbox.autoscaler import DynamicAutoscaler
        scaler = DynamicAutoscaler()

        async def test():
            self.assertFalse(scaler.is_paused)
            scaler._pause_event.clear()
            self.assertTrue(scaler.is_paused)
            scaler._pause_event.set()
            self.assertFalse(scaler.is_paused)

        asyncio.run(test())


class TestContextPruner(unittest.TestCase):
    def test_estimate_tokens(self):
        from thinkbox.pruner import ContextPruner
        pruner = ContextPruner()
        tokens = pruner.estimate_tokens("hello world")
        self.assertGreater(tokens, 0)

    def test_prune_python_removes_comments(self):
        from thinkbox.pruner import ContextPruner
        pruner = ContextPruner()
        source = "# This is a comment\nimport os\n\nprint('hello')\n"
        result = pruner.prune_python(source)
        self.assertNotIn("# This is a comment", result.content)
        self.assertIn("print('hello')", result.content)

    def test_prune_python_removes_imports(self):
        from thinkbox.pruner import ContextPruner
        pruner = ContextPruner()
        source = "import os\nimport sys\n\nprint('hello')\n"
        result = pruner.prune_python(source)
        self.assertNotIn("import os", result.content)
        self.assertIn("print('hello')", result.content)

    def test_prune_python_removes_docstrings(self):
        from thinkbox.pruner import ContextPruner
        pruner = ContextPruner()
        source = '\"\"\"This is a docstring.\"\"\"\n\nprint(\'hello\')\n'
        result = pruner.prune_python(source)
        self.assertNotIn("docstring", result.content)
        self.assertIn("print('hello')", result.content)

    def test_prune_to_budget(self):
        from thinkbox.pruner import ContextPruner
        pruner = ContextPruner(max_tokens=10)
        source = "x = 1\ny = 2\nz = 3\n" * 100
        result = pruner.prune_to_budget(source)
        self.assertLessEqual(pruner.estimate_tokens(result), 10)

    def test_chunk_payload(self):
        from thinkbox.pruner import ContextPruner
        pruner = ContextPruner(max_tokens=10)
        source = "x" * 1000
        chunks = pruner.chunk_payload(source, overlap=10)
        self.assertGreater(len(chunks), 1)

    def test_within_budget(self):
        from thinkbox.pruner import ContextPruner
        pruner = ContextPruner(max_tokens=500)
        source = "print('hello')\n"
        result = pruner.prune_python(source)
        self.assertTrue(result.within_budget)

    def test_prune_javascript(self):
        from thinkbox.pruner import ContextPruner
        pruner = ContextPruner()
        source = "// comment\nconst x = 1;\n/* block */\nconsole.log(x);\n"
        result = pruner.prune_javascript(source)
        self.assertNotIn("// comment", result.content)
        self.assertIn("console.log(x)", result.content)


class TestGitEngine(unittest.TestCase):
    def test_default_config(self):
        from thinkbox.git_engine import GitEngine, GitConfig
        engine = GitEngine(repo_path=".")
        self.assertEqual(engine.config.author_name, "ThinkBox AI")

    def test_sign_message(self):
        from thinkbox.git_engine import GitEngine
        engine = GitEngine(repo_path=".")
        sig1 = engine._sign_message("test message")
        sig2 = engine._sign_message("test message")
        self.assertEqual(sig1, sig2)
        self.assertEqual(len(sig1), 16)

    def test_generate_commit_message(self):
        from thinkbox.git_engine import GitEngine
        engine = GitEngine(repo_path=".")
        message = engine.generate_commit_message(
            task_id="abc123",
            execution_time_ms=1500.0,
            tokens_used=300,
            exit_code=0,
            summary="Test complete",
        )
        self.assertIn("abc123", message)
        self.assertIn("1500.0ms", message)
        self.assertIn("Signed:", message)

    def test_commit_skips_on_nonzero_exit(self):
        from thinkbox.git_engine import GitEngine
        engine = GitEngine(repo_path=".")
        result = engine.commit_speculative_result(
            task_id="abc123",
            execution_time_ms=1000.0,
            tokens_used=200,
            exit_code=1,
        )
        self.assertIsNone(result)

    def test_git_config_custom(self):
        from thinkbox.git_engine import GitConfig
        config = GitConfig(author_name="Test", author_email="test@test.com")
        self.assertEqual(config.author_name, "Test")
        self.assertEqual(config.author_email, "test@test.com")


if __name__ == "__main__":
    unittest.main()
