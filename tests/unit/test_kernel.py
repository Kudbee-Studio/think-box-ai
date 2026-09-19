"""Unit tests for AgentKernel — OrchestrationClient lifecycle wiring."""

import asyncio
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import logging

logger = logging.getLogger(__name__)

MOCK_GRPC_MODULE = types.ModuleType("grpc")
MOCK_GRPC_MODULE.aio = MagicMock()
MOCK_GRPC_MODULE.aio.insecure_channel = MagicMock(return_value=MagicMock())
MOCK_GRPC_MODULE.aio.Channel = MagicMock()
MOCK_GRPC_MODULE.util = MagicMock()
MOCK_GRPC_MODULE.experimental = MagicMock()

MOCK_EMPTY_PB2_MODULE = types.ModuleType("google.protobuf.empty_pb2")
MOCK_EMPTY_PB2_MODULE.Empty = MagicMock(return_value=MagicMock())
MOCK_GOOGLE_PROTOBUF_MODULE = types.ModuleType("google.protobuf")
MOCK_GOOGLE_PROTOBUF_MODULE.empty_pb2 = MOCK_EMPTY_PB2_MODULE

_ALL_PROTO_MODULES = [
    "scheduler_pb2", "scheduler_pb2_grpc",
    "governance_pb2", "governance_pb2_grpc",
    "orchestration_pb2", "orchestration_pb2_grpc",
    "health_pb2", "health_pb2_grpc",
    "cnc_pb2", "cnc_pb2_grpc",
    "agent_to_agent_pb2", "agent_to_agent_pb2_grpc",
]


def _make_proto_module(name):
    return MagicMock()


_MODULES_TO_CLEAN = [
    "grpc",
    "google.protobuf",
    "google.protobuf.empty_pb2",
    "thinkbox.agent.protocol",
    "thinkbox.agent.orchestration_client",
]
for proto_name in _ALL_PROTO_MODULES:
    _MODULES_TO_CLEAN.append(
        f"thinkbox.agent.protocol.{proto_name}"
    )


def _inject_mock_modules():
    sys.modules["grpc"] = MOCK_GRPC_MODULE
    sys.modules["google.protobuf"] = MOCK_GOOGLE_PROTOBUF_MODULE
    sys.modules["google.protobuf.empty_pb2"] = MOCK_EMPTY_PB2_MODULE

    protocol_pkg = types.ModuleType("thinkbox.agent.protocol")
    sys.modules["thinkbox.agent.protocol"] = protocol_pkg
    for proto_name in _ALL_PROTO_MODULES:
        full_name = f"thinkbox.agent.protocol.{proto_name}"
        mod = _make_proto_module(proto_name)
        sys.modules[full_name] = mod
        setattr(protocol_pkg, proto_name, mod)


def _remove_mock_modules():
    for mod in _MODULES_TO_CLEAN:
        if mod in sys.modules:
            del sys.modules[mod]
    for proto_name in _ALL_PROTO_MODULES:
        full_name = f"thinkbox.agent.protocol.{proto_name}"
        if full_name in sys.modules:
            del sys.modules[full_name]


def _remove_kernel_modules():
    for mod in _IMPORTED_KERNEL_MODULES:
        if mod in sys.modules:
            del sys.modules[mod]


_LOOP = None


def _ensure_event_loop():
    global _LOOP
    if _LOOP is None or _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LOOP)
    return _LOOP


def _make_mock_te():
    mock = MagicMock()
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.flush = AsyncMock()
    mock.emit_lifecycle_event = AsyncMock(return_value=None)
    return mock


def _make_mock_sched():
    mock = MagicMock()
    mock.connect = AsyncMock()
    mock.close = AsyncMock()
    return mock


def _make_mock_gov():
    mock = MagicMock()
    mock.connect = AsyncMock()
    mock.close = AsyncMock()
    mock.request_token = AsyncMock()
    return mock


def _make_mock_orch(connected=True):
    mock = MagicMock()
    mock.connected = connected
    mock.connect = AsyncMock()
    mock.close = AsyncMock()
    return mock


class TestKernelOrchestrationWiring(unittest.TestCase):
    """Test OrchestrationClient wiring in AgentKernel lifecycle."""

    def setUp(self):
        _inject_mock_modules()
        self.loop = _ensure_event_loop()

    def tearDown(self):
        # Remove orchestration_client so test_orchestration_client
        # can re-import with its own mocks. Keep kernel cached
        # so @patch decorators work on subsequent tests.
        if "thinkbox.agent.orchestration_client" in sys.modules:
            del sys.modules["thinkbox.agent.orchestration_client"]
        _remove_mock_modules()

    def _make_kernel(self):
        from thinkbox.agent.kernel import AgentKernel, AgentConfig

        config = AgentConfig(
            agent_id="test-agent",
            agent_type="TASK_AGENT",
            tenant_id="test-tenant",
            resource_profile={"cpu_cores": 1.0, "memory_mb": 512},
        )
        kernel = AgentKernel(config)
        return kernel

    @patch("thinkbox.agent.kernel.SchedulerClient")
    @patch("thinkbox.agent.kernel.GovernanceClient")
    @patch("thinkbox.agent.kernel.TelemetryEmitter")
    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_initialize_requests_capacity(
        self, MockOC, MockTE, MockGC, MockSC
    ):
        mock_orch = _make_mock_orch()
        mock_orch.request_capacity = AsyncMock(
            return_value=MagicMock(granted=True, allocation_id="alloc_1")
        )
        mock_orch.discover_services = AsyncMock()
        mock_orch.inject_secrets = AsyncMock()
        MockOC.return_value = mock_orch

        mock_sched = _make_mock_sched()
        MockSC.return_value = mock_sched

        mock_gov = _make_mock_gov()
        MockGC.return_value = mock_gov

        mock_te = _make_mock_te()
        MockTE.return_value = mock_te

        kernel = self._make_kernel()
        result = self.loop.run_until_complete(kernel.initialize())

        self.assertTrue(result.success)
        mock_orch.request_capacity.assert_awaited_once()
        mock_orch.discover_services.assert_awaited_once()
        mock_orch.connect.assert_awaited_once()

    @patch("thinkbox.agent.kernel.SchedulerClient")
    @patch("thinkbox.agent.kernel.GovernanceClient")
    @patch("thinkbox.agent.kernel.TelemetryEmitter")
    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_initialize_fails_closed_capacity_denied(
        self, MockOC, MockTE, MockGC, MockSC
    ):
        mock_orch = _make_mock_orch()
        mock_orch.request_capacity = AsyncMock(
            return_value=MagicMock(
                granted=False, reason="insufficient resources"
            )
        )
        MockOC.return_value = mock_orch

        mock_sched = _make_mock_sched()
        MockSC.return_value = mock_sched

        mock_gov = _make_mock_gov()
        MockGC.return_value = mock_gov

        mock_te = _make_mock_te()
        MockTE.return_value = mock_te

        kernel = self._make_kernel()
        result = self.loop.run_until_complete(kernel.initialize())

        self.assertFalse(result.success)
        self.assertIn("Capacity request denied", result.error)
        self.assertIsNone(kernel._orchestration_allocation_id)

    @patch("thinkbox.agent.kernel.SchedulerClient")
    @patch("thinkbox.agent.kernel.GovernanceClient")
    @patch("thinkbox.agent.kernel.TelemetryEmitter")
    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_initialize_fails_closed_secrets_missing(
        self, MockOC, MockTE, MockGC, MockSC
    ):
        mock_orch = _make_mock_orch()
        mock_orch.request_capacity = AsyncMock(
            return_value=MagicMock(granted=True, allocation_id="alloc_1")
        )
        mock_orch.discover_services = AsyncMock()
        mock_orch.inject_secrets = AsyncMock(
            return_value=MagicMock(handles=[])
        )
        MockOC.return_value = mock_orch

        mock_sched = _make_mock_sched()
        MockSC.return_value = mock_sched

        mock_gov = _make_mock_gov()
        MockGC.return_value = mock_gov

        mock_te = _make_mock_te()
        MockTE.return_value = mock_te

        from thinkbox.agent.kernel import AgentKernel, AgentConfig

        config = AgentConfig(
            agent_id="test-agent",
            agent_type="TASK_AGENT",
            tenant_id="test-tenant",
            resource_profile={"cpu_cores": 1.0, "memory_mb": 512},
            metadata={"required_secrets": ["db_pass", "api_key"]},
        )
        kernel = AgentKernel(config)
        result = self.loop.run_until_complete(kernel.initialize())

        self.assertFalse(result.success)
        self.assertIn("Required secrets", result.error)

    @patch("thinkbox.agent.kernel.SchedulerClient")
    @patch("thinkbox.agent.kernel.GovernanceClient")
    @patch("thinkbox.agent.kernel.TelemetryEmitter")
    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_shutdown_releases_capacity(
        self, MockOC, MockTE, MockGC, MockSC
    ):
        mock_orch = _make_mock_orch()
        mock_orch.release_capacity = AsyncMock(return_value=True)
        MockOC.return_value = mock_orch

        mock_sched = _make_mock_sched()
        MockSC.return_value = mock_sched

        mock_gov = _make_mock_gov()
        MockGC.return_value = mock_gov

        mock_te = _make_mock_te()
        MockTE.return_value = mock_te

        kernel = self._make_kernel()
        kernel._orchestration_allocation_id = "alloc_1"

        result = self.loop.run_until_complete(kernel.shutdown())

        self.assertTrue(result.success)
        mock_orch.release_capacity.assert_awaited_once()

    @patch("thinkbox.agent.kernel.SchedulerClient")
    @patch("thinkbox.agent.kernel.GovernanceClient")
    @patch("thinkbox.agent.kernel.TelemetryEmitter")
    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_shutdown_releases_capacity_on_failure(
        self, MockOC, MockTE, MockGC, MockSC
    ):
        mock_orch = _make_mock_orch()
        mock_orch.release_capacity = AsyncMock(return_value=True)
        MockOC.return_value = mock_orch

        mock_sched = _make_mock_sched()
        mock_sched.close = AsyncMock(side_effect=Exception("close failed"))
        MockSC.return_value = mock_sched

        mock_gov = _make_mock_gov()
        MockGC.return_value = mock_gov

        mock_te = _make_mock_te()
        MockTE.return_value = mock_te

        kernel = self._make_kernel()
        kernel._orchestration_allocation_id = "alloc_1"

        result = self.loop.run_until_complete(kernel.shutdown())

        mock_orch.release_capacity.assert_awaited_once()

    @patch("thinkbox.agent.kernel.SchedulerClient")
    @patch("thinkbox.agent.kernel.GovernanceClient")
    @patch("thinkbox.agent.kernel.TelemetryEmitter")
    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_shutdown_does_not_release_if_no_allocation(
        self, MockOC, MockTE, MockGC, MockSC
    ):
        mock_orch = _make_mock_orch()
        mock_orch.release_capacity = AsyncMock(return_value=True)
        MockOC.return_value = mock_orch

        mock_sched = _make_mock_sched()
        MockSC.return_value = mock_sched

        mock_gov = _make_mock_gov()
        MockGC.return_value = mock_gov

        mock_te = _make_mock_te()
        MockTE.return_value = mock_te

        kernel = self._make_kernel()

        result = self.loop.run_until_complete(kernel.shutdown())

        mock_orch.release_capacity.assert_not_called()

    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_inject_required_secrets_success(self, MockOC):
        mock_orch = MagicMock()
        mock_orch.inject_secrets = AsyncMock(
            return_value=MagicMock(
                handles=[
                    types.SimpleNamespace(name="db_pass"),
                    types.SimpleNamespace(name="api_key"),
                ]
            )
        )
        MockOC.return_value = mock_orch

        from thinkbox.agent.kernel import AgentKernel, AgentConfig

        config = AgentConfig(
            agent_id="test",
            agent_type="TASK_AGENT",
            tenant_id="t1",
            metadata={"required_secrets": ["db_pass", "api_key"]},
        )
        kernel = AgentKernel(config)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(kernel._inject_required_secrets())
        loop.close()

        mock_orch.inject_secrets.assert_awaited_once()

    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_inject_required_secrets_fail_closed(self, MockOC):
        mock_orch = MagicMock()
        bad_handles = MagicMock()
        bad_handles.__iter__ = MagicMock(return_value=iter([]))
        mock_orch.inject_secrets = AsyncMock(
            return_value=MagicMock(handles=[])
        )
        MockOC.return_value = mock_orch

        from thinkbox.agent.kernel import AgentKernel, AgentConfig

        config = AgentConfig(
            agent_id="test",
            agent_type="TASK_AGENT",
            tenant_id="t1",
            metadata={"required_secrets": ["db_pass"]},
        )
        kernel = AgentKernel(config)
        loop = asyncio.new_event_loop()
        with self.assertRaises(RuntimeError) as ctx:
            loop.run_until_complete(kernel._inject_required_secrets())
        loop.close()

        self.assertIn("Required secrets", str(ctx.exception))

    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_inject_required_secrets_no_required(self, MockOC):
        mock_orch = MagicMock()
        MockOC.return_value = mock_orch

        from thinkbox.agent.kernel import AgentKernel, AgentConfig

        config = AgentConfig(
            agent_id="test",
            agent_type="TASK_AGENT",
            tenant_id="t1",
        )
        kernel = AgentKernel(config)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(kernel._inject_required_secrets())
        loop.close()

        mock_orch.inject_secrets.assert_not_called()

    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_get_config_returns_cached(self, MockOC):
        mock_orch = MagicMock()
        mock_orch.get_config_cache.return_value = {"key1": "val1"}
        MockOC.return_value = mock_orch

        from thinkbox.agent.kernel import AgentKernel, AgentConfig

        config = AgentConfig(agent_id="test", agent_type="TASK_AGENT")
        kernel = AgentKernel(config)

        result = kernel.get_config("key1")
        self.assertEqual(result, "val1")

    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_get_config_returns_default(self, MockOC):
        mock_orch = MagicMock()
        mock_orch.get_config_cache.return_value = {}
        MockOC.return_value = mock_orch

        from thinkbox.agent.kernel import AgentKernel, AgentConfig

        config = AgentConfig(agent_id="test", agent_type="TASK_AGENT")
        kernel = AgentKernel(config)

        result = kernel.get_config("missing", default="fallback")
        self.assertEqual(result, "fallback")

    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_watch_config_delegates(self, MockOC):
        mock_orch = MagicMock()
        mock_watch = MagicMock()
        mock_orch.watch_config.return_value = mock_watch
        MockOC.return_value = mock_orch

        from thinkbox.agent.kernel import AgentKernel, AgentConfig

        config = AgentConfig(agent_id="test", agent_type="TASK_AGENT")
        kernel = AgentKernel(config)

        kernel.watch_config("test_key")
        mock_orch.watch_config.assert_called_once_with("test_key")

    @patch("thinkbox.agent.kernel.OrchestrationClient")
    def test_orchestration_property_caches(self, MockOC):
        MockOC.return_value = MagicMock()

        from thinkbox.agent.kernel import AgentKernel, AgentConfig

        config = AgentConfig(
            agent_id="test",
            agent_type="TASK_AGENT",
            orchestration_endpoint="localhost:50053",
        )
        kernel = AgentKernel(config)

        first = kernel.orchestration
        second = kernel.orchestration
        self.assertIs(first, second)
        MockOC.assert_called_once()


if __name__ == "__main__":
    unittest.main()
