"""A failed model call must never be reported as model output or success."""

from __future__ import annotations

import asyncio
import io
import json
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from thinkbox.model_client import (
    INCEPTION_BASE_URL,
    INCEPTION_MIN_MAX_TOKENS,
    AsyncModelClient,
    ModelCallError,
    ModelConfig,
)


def _resp(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__.return_value = resp
    return resp


def _http_error(code: int, body: str = "boom") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(body.encode()))


class TestModelConfigFromEnv(unittest.TestCase):
    def test_defaults_to_ollama(self):
        cfg = ModelConfig.from_env({})
        self.assertEqual(cfg.api_type, "ollama")
        self.assertEqual(cfg.base_url, "http://localhost:11434")

    def test_ollama_host_without_scheme(self):
        cfg = ModelConfig.from_env({"OLLAMA_HOST": "127.0.0.1:11434"})
        self.assertEqual(cfg.base_url, "http://127.0.0.1:11434")

    def test_openai_compat_reads_key_and_url(self):
        cfg = ModelConfig.from_env({
            "THINKBOX_DEFAULT_PROVIDER": "openai_compat",
            "THINKBOX_OPENAI_COMPAT_BASE_URL": "https://api.groq.com/openai/v1",
            "THINKBOX_OPENAI_COMPAT_API_KEY": "gsk_x",
            "THINKBOX_DEFAULT_MODEL": "llama-3.1-8b-instant",
        })
        self.assertEqual(cfg.api_type, "openai_compat")
        self.assertEqual(cfg.api_key, "gsk_x")
        self.assertEqual(cfg.chat_completions_url(), "https://api.groq.com/openai/v1/chat/completions")

    def test_inception_preset(self):
        cfg = ModelConfig.from_env({"THINKBOX_DEFAULT_PROVIDER": "inception", "INCEPTION_API_KEY": "k"})
        self.assertEqual(cfg.base_url, INCEPTION_BASE_URL)
        self.assertEqual(cfg.model, "mercury-2")
        self.assertEqual(cfg.max_tokens, INCEPTION_MIN_MAX_TOKENS)
        self.assertEqual(cfg.chat_completions_url(), "https://api.inceptionlabs.ai/v1/chat/completions")

    def test_overrides_win_and_none_ignored(self):
        cfg = ModelConfig.from_env({}, model="qwen2.5:1.5b", base_url=None)
        self.assertEqual(cfg.model, "qwen2.5:1.5b")
        self.assertEqual(cfg.base_url, "http://localhost:11434")

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            ModelConfig.from_env({"THINKBOX_DEFAULT_PROVIDER": "nope"})

    def test_api_key_not_in_repr(self):
        self.assertNotIn("secret", repr(ModelConfig(api_key="secret")))

    def test_base_url_without_v1_gets_v1(self):
        self.assertEqual(ModelConfig(base_url="http://vllm:8000").chat_completions_url(),
                         "http://vllm:8000/v1/chat/completions")


class TestModelClientFailures(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    @patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused"))
    def test_unreachable_raises_non_retryable(self, _):
        with self.assertRaises(ModelCallError) as ctx:
            self._run(AsyncModelClient().generate("hi"))
        self.assertFalse(ctx.exception.retryable)
        self.assertIn("unreachable", str(ctx.exception))

    @patch("urllib.request.urlopen", side_effect=_http_error(500))
    def test_http_500_retryable(self, _):
        cfg = ModelConfig(api_type="openai_compat", base_url="https://x/v1")
        with self.assertRaises(ModelCallError) as ctx:
            self._run(AsyncModelClient(cfg).generate("hi"))
        self.assertTrue(ctx.exception.retryable)

    @patch("urllib.request.urlopen", side_effect=_http_error(401, "bad key"))
    def test_http_401_not_retryable_and_body_surfaced(self, _):
        cfg = ModelConfig(api_type="openai_compat", base_url="https://x/v1")
        with self.assertRaises(ModelCallError) as ctx:
            self._run(AsyncModelClient(cfg).generate("hi"))
        self.assertFalse(ctx.exception.retryable)
        self.assertIn("401", str(ctx.exception))
        self.assertIn("bad key", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_null_content_raises(self, urlopen):
        urlopen.return_value = _resp({"choices": [{"message": {"content": None}, "finish_reason": "length"}]})
        cfg = ModelConfig(api_type="openai_compat", base_url="https://x/v1")
        with self.assertRaises(ModelCallError) as ctx:
            self._run(AsyncModelClient(cfg).generate("hi"))
        self.assertIn("finish_reason=length", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_ollama_error_field_raises(self, urlopen):
        urlopen.return_value = _resp({"error": "model 'x' not found"})
        with self.assertRaises(ModelCallError) as ctx:
            self._run(AsyncModelClient().generate("hi"))
        self.assertIn("not found", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_ollama_empty_response_raises(self, urlopen):
        urlopen.return_value = _resp({"response": "  "})
        with self.assertRaises(ModelCallError):
            self._run(AsyncModelClient().generate("hi"))


class TestModelClientSuccess(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_openai_sends_bearer_and_parses(self, urlopen):
        urlopen.return_value = _resp({"choices": [{"message": {"content": "391"}}]})
        cfg = ModelConfig(api_type="openai_compat", base_url="https://api.inceptionlabs.ai/v1",
                          api_key="k123", model="mercury-2")
        out = asyncio.run(AsyncModelClient(cfg).generate("17*23"))
        self.assertEqual(out, "391")
        req = urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.inceptionlabs.ai/v1/chat/completions")
        self.assertEqual(req.get_header("Authorization"), "Bearer k123")

    @patch("urllib.request.urlopen")
    def test_ollama_options_payload(self, urlopen):
        urlopen.return_value = _resp({"response": "ok"})
        asyncio.run(AsyncModelClient(ModelConfig(model="m")).generate("p", max_tokens=7, temperature=0.5))
        body = json.loads(urlopen.call_args[0][0].data)
        self.assertEqual(body["options"], {"temperature": 0.5, "num_predict": 7})
        self.assertIsNone(urlopen.call_args[0][0].get_header("Authorization"))


class TestSwarmAndEngineHonesty(unittest.TestCase):
    def test_unreachable_model_is_failure_without_speculation(self):
        from thinkbox.swarm import AsyncWorkerPool

        client = MagicMock()

        async def _fail(*a, **k):
            raise ModelCallError("down", provider="ollama", model="m", retryable=False)

        client.generate.side_effect = _fail
        pool = AsyncWorkerPool(client, max_workers=2)
        result = asyncio.run(pool.execute_with_speculation("t1", "p"))
        self.assertIsNone(result.winner)
        self.assertEqual(len(result.attempts), 1)
        self.assertFalse(result.attempts[0].success)
        self.assertEqual(result.attempts[0].error_type, "ModelCallError")
        self.assertEqual(client.generate.call_count, 1)

    def test_retryable_failure_still_speculates(self):
        from thinkbox.swarm import AsyncWorkerPool

        calls = {"n": 0}

        async def _flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ModelCallError("empty", provider="ollama", model="m", retryable=True)
            return "fixed"

        client = MagicMock()
        client.generate.side_effect = _flaky
        result = asyncio.run(AsyncWorkerPool(client).execute_with_speculation("t1", "p"))
        self.assertIsNotNone(result.winner)
        self.assertEqual(result.winner.output, "fixed")

    @patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused"))
    def test_engine_reports_failure_and_task_output(self, _):
        from thinkbox.engine import ThinkBoxEngine

        summary = asyncio.run(ThinkBoxEngine().execute_goal("Compute 17 * 23"))
        self.assertEqual(summary["successful"], 0)
        self.assertEqual(summary["failed"], summary["completed"])
        self.assertTrue(summary["tasks"])
        for task in summary["tasks"]:
            self.assertFalse(task["success"])
            self.assertEqual(task["error_type"], "ModelCallError")

    @patch("urllib.request.urlopen")
    def test_engine_success_carries_model_output(self, urlopen):
        from thinkbox.engine import ThinkBoxEngine

        urlopen.return_value = _resp({"response": '{"answer": 391}'})
        summary = asyncio.run(ThinkBoxEngine().execute_goal("Compute 17 * 23"))
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["tasks"][0]["output"], '{"answer": 391}')


class TestEmbedderDimension(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_wrong_dimension_rejected(self, urlopen):
        from thinkbox.embedder import OpenAICompatEmbedder
        from thinkbox.embedder import EmbeddingError

        urlopen.return_value = _resp({"data": [{"embedding": [0.1] * 768}]})
        with self.assertRaises(EmbeddingError) as ctx:
            OpenAICompatEmbedder(api_key="k", base_url="https://x/v1").embed(["hi"])
        self.assertIn("768", str(ctx.exception))

    @patch.dict("os.environ", {"THINKBOX_DEFAULT_MODEL": "mercury-2"}, clear=False)
    def test_default_embed_model_is_not_chat_model(self):
        import os

        from thinkbox.embedder import OpenAICompatEmbedder

        os.environ.pop("THINKBOX_EMBED_MODEL", None)
        emb = OpenAICompatEmbedder(api_key="k", base_url="https://x/v1")
        self.assertEqual(emb._model, "text-embedding-3-small")


class TestCliRunHonesty(unittest.TestCase):
    def _main(self, argv):
        from thinkbox.cli import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                main(argv)
                code = 0
            except SystemExit as exc:
                code = exc.code
        return code, buf.getvalue()

    @patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused"))
    def test_run_unreachable_exits_fail_and_prints_error(self, _):
        import tempfile

        from thinkbox.cli_inspect import CLI_EXIT_FAIL

        with tempfile.TemporaryDirectory() as d:
            code, out = self._main(["run", "--goal", "hi", "--ledger", f"{d}/l.db", "--no-speculation"])
        self.assertEqual(code, CLI_EXIT_FAIL)
        self.assertIn("FAIL", out)
        self.assertIn("Connection refused", out)
        self.assertIn("ledger verified: True", out)

    @patch("urllib.request.urlopen")
    def test_run_success_prints_output(self, urlopen):
        import tempfile

        from thinkbox.cli_inspect import CLI_EXIT_OK

        urlopen.return_value = _resp({"response": "144"})
        with tempfile.TemporaryDirectory() as d:
            code, out = self._main(["run", "--goal", "12*12", "--ledger", f"{d}/l.db"])
        self.assertEqual(code, CLI_EXIT_OK)
        self.assertIn("output: 144", out)

    @patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused"))
    def test_model_check_fails_honestly(self, _):
        from thinkbox.cli_inspect import CLI_EXIT_FAIL

        code, out = self._main(["model", "check"])
        self.assertEqual(code, CLI_EXIT_FAIL)
        self.assertIn("FAIL", out)


if __name__ == "__main__":
    unittest.main()


class TestLocalProofScript(unittest.TestCase):
    """scripts/prove_think_box_local.py passes only when the model answers correctly."""

    def _load(self):
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "scripts" / "prove_think_box_local.py"
        spec = importlib.util.spec_from_file_location("prove_think_box_local", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _run(self, answer_fn):
        import re
        import tempfile

        async def _gen(self_client, prompt, **kw):
            m = re.search(r"What is (\d+) \* (\d+)", prompt)
            return answer_fn(int(m.group(1)), int(m.group(2))) if m else "OK"

        mod = self._load()
        with tempfile.TemporaryDirectory() as d, patch.object(AsyncModelClient, "generate", _gen):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = mod.main(["--out-dir", d])
            proofs = list(__import__("pathlib").Path(d).glob("local_proof_*.json"))
            data = json.loads(proofs[0].read_text())
        return code, data

    def test_correct_answer_passes_all_checks(self):
        code, data = self._run(lambda a, b: str(a * b))
        self.assertEqual(code, 0)
        self.assertTrue(data["all_passed"])
        self.assertEqual(data["evidence_label"], "verified")
        self.assertEqual(len(data["checks"]), 6)

    def test_wrong_answer_fails(self):
        code, data = self._run(lambda a, b: str(a * b + 1))
        self.assertEqual(code, 1)
        self.assertFalse(data["all_passed"])
        failed = [c["check"] for c in data["checks"] if not c["passed"]]
        self.assertEqual(failed, ["governed_answer"])
