"""Unit tests for the ThinkBox Session Tracking Engine."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if "fastapi" not in sys.modules:
    sys.modules["fastapi"] = MagicMock()
    sys.modules["fastapi.middleware"] = MagicMock()
    sys.modules["fastapi.middleware.cors"] = MagicMock()
    sys.modules["starlette"] = MagicMock()
    sys.modules["starlette.middleware"] = MagicMock()
    sys.modules["starlette.middleware.base"] = MagicMock()
    sys.modules["pydantic"] = MagicMock()


class TestSessionIDGeneration(unittest.TestCase):
    def test_session_id_format(self):
        from thinkbox.session import generate_session_id
        session_id = generate_session_id()
        self.assertTrue(session_id.startswith("tb_sess_"))
        self.assertGreater(len(session_id), 20)

    def test_session_id_uniqueness(self):
        from thinkbox.session import generate_session_id
        ids = {generate_session_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_session_id_timestamp(self):
        from thinkbox.session import generate_session_id
        from datetime import datetime, timezone
        before = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        session_id = generate_session_id()
        after = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        timestamp_part = session_id.split("_")[2]
        self.assertTrue(before <= timestamp_part <= after)


class TestSessionContext(unittest.TestCase):
    def test_create_session(self):
        from thinkbox.session import create_session, get_current_session
        session = create_session(environment="test", model_backend="Ollama", actor="test-user")
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.environment, "test")
        self.assertEqual(session.model_backend, "Ollama")
        self.assertEqual(session.actor, "test-user")
        self.assertIsNotNone(session.created_at)

    def test_get_current_session(self):
        from thinkbox.session import create_session, get_current_session, clear_session
        clear_session()
        self.assertIsNone(get_current_session())
        create_session(environment="test")
        current = get_current_session()
        self.assertIsNotNone(current)
        self.assertEqual(current.environment, "test")

    def test_clear_session(self):
        from thinkbox.session import create_session, get_current_session, clear_session
        create_session(environment="test")
        self.assertIsNotNone(get_current_session())
        clear_session()
        self.assertIsNone(get_current_session())

    def test_session_to_dict(self):
        from thinkbox.session import SessionContext
        session = SessionContext(
            session_id="tb_sess_test",
            environment="test",
            model_backend="Ollama",
            actor="user",
        )
        d = session.to_dict()
        self.assertEqual(d["session_id"], "tb_sess_test")
        self.assertEqual(d["environment"], "test")
        self.assertEqual(d["model_backend"], "Ollama")
        self.assertEqual(d["actor"], "user")


class TestEnvironmentDetection(unittest.TestCase):
    def test_get_environment_local(self):
        from thinkbox.session import get_environment
        with patch.dict(os.environ, {}, clear=True):
            env = get_environment()
            self.assertEqual(env, "local")

    def test_get_environment_box(self):
        from thinkbox.session import get_environment
        with patch.dict(os.environ, {"UPSTASH_PUBLIC_BOX_URL": "https://test-box-123.preview.box.upstash.com/"}):
            env = get_environment()
            self.assertEqual(env, "test-box-123.preview.box.upstash.com")

    def test_get_model_backend_ollama(self):
        from thinkbox.session import get_model_backend
        with patch.dict(os.environ, {"THINKBOX_DEFAULT_MODEL": "llama3.1:8b"}):
            backend = get_model_backend()
            self.assertEqual(backend, "Ollama")

    def test_get_model_backend_vllm(self):
        from thinkbox.session import get_model_backend
        with patch.dict(os.environ, {"THINKBOX_DEFAULT_MODEL": "vllm/model"}):
            backend = get_model_backend()
            self.assertEqual(backend, "vLLM")

    def test_get_actor(self):
        from thinkbox.session import get_actor
        with patch.dict(os.environ, {"THINKBOX_ACTOR": "test-user"}):
            actor = get_actor()
            self.assertEqual(actor, "test-user")


class TestUpstashVectorSync(unittest.TestCase):
    def test_sync_disabled_without_config(self):
        from thinkbox.session import UpstashVectorSync
        with patch.dict(os.environ, {}, clear=True):
            sync = UpstashVectorSync()
            self.assertFalse(sync.enabled)

    def test_sync_enabled_with_config(self):
        from thinkbox.session import UpstashVectorSync
        with patch.dict(os.environ, {
            "UPSTASH_VECTOR_REST_URL": "https://test.upstash.io",
            "UPSTASH_VECTOR_REST_TOKEN": "test-token",
        }):
            sync = UpstashVectorSync()
            self.assertTrue(sync.enabled)
            self.assertEqual(sync.url, "https://test.upstash.io")


class TestSessionWithAuditStorage(unittest.TestCase):
    def test_record_audit_with_session(self):
        from backend.audit_storage import record_audit, list_audits
        record_audit("test_action", "test_actor", "success", {"key": "value"}, session_id="tb_sess_test123")
        audits = list_audits(session_id="tb_sess_test123")
        self.assertGreater(len(audits), 0)
        self.assertEqual(audits[0]["session_id"], "tb_sess_test123")

    def test_list_sessions(self):
        from backend.audit_storage import record_audit, list_sessions
        record_audit("action1", "actor1", "success", session_id="tb_sess_list_test")
        sessions = list_sessions(limit=10)
        session_ids = [s["session_id"] for s in sessions]
        self.assertIn("tb_sess_list_test", session_ids)


class TestContextVarsPropagation(unittest.TestCase):
    def test_contextvars_isolation(self):
        import contextvars
        from thinkbox.session import SESSION_CONTEXT_VAR, create_session, get_current_session

        clear_token = SESSION_CONTEXT_VAR.set(None)
        self.assertIsNone(SESSION_CONTEXT_VAR.get())

        session = create_session(environment="test-env")
        self.assertEqual(SESSION_CONTEXT_VAR.get().session_id, session.session_id)

        SESSION_CONTEXT_VAR.reset(clear_token)
        self.assertIsNone(SESSION_CONTEXT_VAR.get())


if __name__ == "__main__":
    unittest.main()
