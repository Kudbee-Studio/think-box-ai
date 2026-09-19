"""Unit tests for thinkbox/agent/orchestration_client — Orchestration Service client."""

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

MOCK_ORCHESTRATION_PB2_MODULE = types.ModuleType("orchestration_pb2")
MOCK_ORCHESTRATION_PB2_MODULE.CapacityRequest = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.CapacityResponse = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.ReleaseRequest = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.ResourceProfile = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.PlacementConstraints = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.ServiceQuery = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.ServiceEndpoint = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.ServiceDiscoveryResponse = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.ConfigWatchRequest = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.ConfigValue = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.SecretSpec = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.SecretInjectionSpec = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.SecretHandle = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.SecretInjectionResponse = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.SecretRotationEvent = MagicMock
MOCK_ORCHESTRATION_PB2_MODULE.Empty = MagicMock(return_value=MagicMock())

MOCK_ORCHESTRATION_PB2_MODULE.CapacityRequest.Priority = MagicMock()
MOCK_ORCHESTRATION_PB2_MODULE.CapacityRequest.Priority.NORMAL = 1
MOCK_ORCHESTRATION_PB2_MODULE.CapacityRequest.Priority.HIGH = 2
MOCK_ORCHESTRATION_PB2_MODULE.CapacityRequest.Priority.LOW = 0
MOCK_ORCHESTRATION_PB2_MODULE.CapacityRequest.Priority.CRITICAL = 3
MOCK_ORCHESTRATION_PB2_MODULE.CapacityRequest.Priority.Value = MagicMock(return_value=1)
MOCK_ORCHESTRATION_PB2_MODULE.SecretSpec.Format = MagicMock()
MOCK_ORCHESTRATION_PB2_MODULE.SecretSpec.Format.ENV = 0
MOCK_ORCHESTRATION_PB2_MODULE.SecretSpec.Format.FILE = 1
MOCK_ORCHESTRATION_PB2_MODULE.SecretSpec.Format.MEMORY = 2
MOCK_ORCHESTRATION_PB2_MODULE.SecretSpec.Format.Value = MagicMock(return_value=0)
MOCK_ORCHESTRATION_PB2_MODULE.SecretInjectionSpec.InjectionMethod = MagicMock()
MOCK_ORCHESTRATION_PB2_MODULE.SecretInjectionSpec.InjectionMethod.ENV_FILE = 0
MOCK_ORCHESTRATION_PB2_MODULE.SecretInjectionSpec.InjectionMethod.MEMORY = 1
MOCK_ORCHESTRATION_PB2_MODULE.SecretInjectionSpec.InjectionMethod.VOLUME = 2
MOCK_ORCHESTRATION_PB2_MODULE.SecretInjectionSpec.InjectionMethod.Value = MagicMock(return_value=0)
MOCK_ORCHESTRATION_PB2_MODULE.SecretInjectionSpec.InjectionMethod.Value = MagicMock(return_value=0)

MOCK_ORCHESTRATION_PB2_GRPC_MODULE = types.ModuleType("orchestration_pb2_grpc")
MOCK_ORCHESTRATION_PB2_GRPC_MODULE.OrchestrationServiceStub = MagicMock(
    return_value=MagicMock()
)


def _inject_mock_modules():
    sys.modules["grpc"] = MOCK_GRPC_MODULE
    sys.modules["google.protobuf"] = MOCK_GOOGLE_PROTOBUF_MODULE
    sys.modules["google.protobuf.empty_pb2"] = MOCK_EMPTY_PB2_MODULE
    sys.modules["thinkbox.agent.protocol"] = types.ModuleType(
        "thinkbox.agent.protocol"
    )
    sys.modules["thinkbox.agent.protocol.orchestration_pb2"] = (
        MOCK_ORCHESTRATION_PB2_MODULE
    )
    sys.modules["thinkbox.agent.protocol.orchestration_pb2_grpc"] = (
        MOCK_ORCHESTRATION_PB2_GRPC_MODULE
    )
    sys.modules["thinkbox.agent.protocol"].orchestration_pb2 = (
        MOCK_ORCHESTRATION_PB2_MODULE
    )
    sys.modules["thinkbox.agent.protocol"].orchestration_pb2_grpc = (
        MOCK_ORCHESTRATION_PB2_GRPC_MODULE
    )


def _remove_mock_modules():
    for mod in [
        "grpc",
        "google.protobuf",
        "google.protobuf.empty_pb2",
        "thinkbox.agent.protocol",
        "thinkbox.agent.protocol.orchestration_pb2",
        "thinkbox.agent.protocol.orchestration_pb2_grpc",
    ]:
        if mod in sys.modules:
            del sys.modules[mod]


_imported_client = False
_IMPORTED_CLASS = None
_LOOP = None


def _loop_future():
    loop = _ensure_event_loop()
    return loop.create_future()


def _ensure_event_loop():
    global _LOOP
    if _LOOP is None or _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LOOP)
    return _LOOP


def _ensure_client_imported():
    global _imported_client, _IMPORTED_CLASS
    _ensure_event_loop()
    if not _imported_client:
        _inject_mock_modules()
        from thinkbox.agent.orchestration_client import (
            OrchestrationClient as _OC,
        )
        _imported_client = True
        _IMPORTED_CLASS = _OC
    return _IMPORTED_CLASS


class TestOrchestrationClientInit(unittest.TestCase):
    def test_creation(self):
        OrchestrationClient = _ensure_client_imported()
        client = OrchestrationClient(
            endpoint="localhost:50053",
            agent_id="agent_1",
            tenant_id="tenant_1",
        )
        self.assertEqual(client.endpoint, "localhost:50053")
        self.assertEqual(client.agent_id, "agent_1")
        self.assertEqual(client.tenant_id, "tenant_1")
        self.assertFalse(client.connected)
        self.assertIsNone(client._channel)
        self.assertIsNone(client._stub)

    def test_default_state(self):
        OrchestrationClient = _ensure_client_imported()
        client = OrchestrationClient("localhost:50053", "a", "t")
        self.assertEqual(client._config_cache, {})
        self.assertEqual(client._config_version, 0)
        self.assertIsNone(client._watch_config_task)
        self.assertIsNone(client._watch_secret_task)


class TestOrchestrationClientConnect(unittest.TestCase):
    def setUp(self):
        OrchestrationClient = _ensure_client_imported()
        self.client = OrchestrationClient(
            endpoint="localhost:50053",
            agent_id="agent_1",
            tenant_id="tenant_1",
        )

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_connect_success(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._channel = MagicMock()
        self.client._channel.channel_ready = AsyncMock(
            return_value=_loop_future()
        )
        self.client._channel.channel_ready.return_value.set_result(None)
        self.client._stub = MagicMock()

        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.client.connect())
        loop.close()

        self.assertTrue(self.client.connected)
        self.assertIsNotNone(self.client._channel)
        self.assertIsNotNone(self.client._stub)

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_connect_timeout(self, mock_wait_for):
        mock_wait_for.side_effect = asyncio.TimeoutError()

        loop = asyncio.new_event_loop()
        with self.assertRaises(asyncio.TimeoutError):
            loop.run_until_complete(self.client.connect())
        loop.close()

        self.assertFalse(self.client.connected)

    def test_connect_runtime_error_no_grpc(self):
        from thinkbox.agent import orchestration_client as oc_mod
        original_grpc = oc_mod.grpc
        oc_mod.grpc = None
        try:
            loop = asyncio.new_event_loop()
            with self.assertRaises(RuntimeError):
                loop.run_until_complete(self.client.connect())
            loop.close()
        finally:
            oc_mod.grpc = original_grpc

    def test_connect_not_called(self):
        self.assertFalse(self.client.connected)


class TestOrchestrationClientClose(unittest.TestCase):
    def setUp(self):
        OrchestrationClient = _ensure_client_imported()
        self.client = OrchestrationClient(
            endpoint="localhost:50053",
            agent_id="agent_1",
            tenant_id="tenant_1",
        )

    def test_close_with_tasks(self):
        self.client._connected = True
        cfg_mock = MagicMock()
        sec_mock = MagicMock()
        ch_mock = MagicMock()
        ch_mock.close = AsyncMock(return_value=None)
        self.client._watch_config_task = cfg_mock
        self.client._watch_secret_task = sec_mock
        self.client._channel = ch_mock

        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.client.close())
        loop.close()

        self.assertFalse(self.client.connected)
        cfg_mock.cancel.assert_called_once()
        sec_mock.cancel.assert_called_once()
        ch_mock.close.assert_awaited_once()

    def test_close_no_channel(self):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.client.close())
        loop.close()
        self.assertFalse(self.client.connected)


class TestOrchestrationClientCapacity(unittest.TestCase):
    def setUp(self):
        OrchestrationClient = _ensure_client_imported()
        self.client = OrchestrationClient(
            endpoint="localhost:50053",
            agent_id="agent_1",
            tenant_id="tenant_1",
        )

    def test_request_capacity_not_connected(self):
        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            self.client.request_capacity(
                {"cpu_cores": 2.0, "memory_mb": 1024},
                priority="HIGH",
            )
        )
        loop.close()

        self.assertFalse(response.granted)
        self.assertEqual(response.reason, "Orchestration service unavailable")

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_request_capacity_success(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()
        self.client._stub.RequestCapacity = AsyncMock(
            return_value=MagicMock(
                request_id="req_1",
                granted=True,
                allocation_id="alloc_1",
            )
        )

        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            self.client.request_capacity(
                {"cpu_cores": 2.0, "memory_mb": 1024},
                duration_hint_seconds=1800,
                priority="HIGH",
                placement_constraints={"zone": "us-east-1"},
                required_capabilities=["gpu"],
            )
        )
        loop.close()

        self.assertTrue(response.granted)
        self.assertEqual(response.allocation_id, "alloc_1")

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_request_capacity_error(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()
        self.client._stub.RequestCapacity = AsyncMock(
            side_effect=Exception("timeout")
        )

        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            self.client.request_capacity({"cpu_cores": 1.0})
        )
        loop.close()

        self.assertFalse(response.granted)
        self.assertIn("timeout", response.reason)

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_release_capacity_success(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()
        self.client._stub.ReleaseCapacity = AsyncMock(
            return_value=MagicMock()
        )

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            self.client.release_capacity("alloc_1", reason="TASK_COMPLETE")
        )
        loop.close()

        self.assertTrue(result)

    def test_release_capacity_not_connected(self):
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(self.client.release_capacity("alloc_1"))
        loop.close()
        self.assertFalse(result)


class TestOrchestrationClientDiscovery(unittest.TestCase):
    def setUp(self):
        OrchestrationClient = _ensure_client_imported()
        self.client = OrchestrationClient(
            endpoint="localhost:50053",
            agent_id="agent_1",
            tenant_id="tenant_1",
        )

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_discover_services_success(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()
        self.client._stub.DiscoverServices = AsyncMock(
            return_value=MagicMock(
                endpoints=[
                    MagicMock(
                        service_name="compute",
                        endpoint="compute:8080",
                        protocol="grpc",
                        health="HEALTHY",
                    ),
                    MagicMock(
                        service_name="storage",
                        endpoint="storage:9090",
                        protocol="http",
                        health="HEALTHY",
                    ),
                ],
                ttl_seconds=60,
            )
        )

        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            self.client.discover_services(
                "compute", namespace="default", tags={"env": "prod"}
            )
        )
        loop.close()

        self.assertEqual(len(response.endpoints), 2)
        self.assertEqual(response.endpoints[0].service_name, "compute")
        self.assertEqual(response.endpoints[1].service_name, "storage")
        self.assertEqual(response.ttl_seconds, 60)

    def test_discover_services_not_connected(self):
        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            self.client.discover_services("compute")
        )
        loop.close()

        self.assertEqual(len(response.endpoints), 0)

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_discover_services_error(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()
        self.client._stub.DiscoverServices = AsyncMock(
            side_effect=Exception("discovery failed")
        )

        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            self.client.discover_services("compute")
        )
        loop.close()

        self.assertEqual(len(response.endpoints), 0)
        self.assertIn("discovery failed", response.reason)


class TestOrchestrationClientConfigWatch(unittest.TestCase):
    def setUp(self):
        OrchestrationClient = _ensure_client_imported()
        self.client = OrchestrationClient(
            endpoint="localhost:50053",
            agent_id="agent_1",
            tenant_id="tenant_1",
        )

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_watch_config_not_connected(self, mock_wait_for):
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(
            self._collect_async_gen(self.client.watch_config("key1"))
        )
        loop.close()

        self.assertEqual(results, [])

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_watch_config_success(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()

        async def _gen():
            yield MagicMock(key="key1", value="val1", version=1)
            yield MagicMock(key="key1", value="val2", version=2)

        self.client._stub.WatchConfig = MagicMock(return_value=_gen())

        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(
            self._collect_async_gen(self.client.watch_config("key1"))
        )
        loop.close()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].value, "val1")
        self.assertEqual(results[1].value, "val2")

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_watch_config_error(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()

        async def _gen():
            yield MagicMock(key="key1", value="val1", version=1)
            raise Exception("stream error")

        self.client._stub.WatchConfig = MagicMock(return_value=_gen())

        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(
            self._collect_async_gen(self.client.watch_config("key1"))
        )
        loop.close()

        self.assertEqual(len(results), 1)

    def test_get_config_cache(self):
        self.client._config_cache = {"key1": "val1"}
        self.assertEqual(self.client.get_config_cache(), {"key1": "val1"})

    def test_get_config_version(self):
        self.client._config_version = 42
        self.assertEqual(self.client.get_config_version(), 42)

    def _collect_async_gen(self, gen):
        return self._collect(gen)

    async def _collect(self, gen):
        results = []
        async for item in gen:
            results.append(item)
        return results


class TestOrchestrationClientSecrets(unittest.TestCase):
    def setUp(self):
        OrchestrationClient = _ensure_client_imported()
        self.client = OrchestrationClient(
            endpoint="localhost:50053",
            agent_id="agent_1",
            tenant_id="tenant_1",
        )

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_inject_secrets_success(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()
        self.client._stub.InjectSecrets = AsyncMock(
            return_value=MagicMock(
                handles=[
                    MagicMock(name="db_pass", value="secret1"),
                    MagicMock(name="api_key", value="secret2"),
                ],
            )
        )

        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            self.client.inject_secrets(
                [
                    {"name": "db_pass", "path": "/secret/db"},
                    {"name": "api_key", "path": "/secret/api"},
                ]
            )
        )
        loop.close()

        self.assertEqual(len(response.handles), 2)

    def test_inject_secrets_not_connected(self):
        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            self.client.inject_secrets([{"name": "secret1"}])
        )
        loop.close()

        self.assertEqual(len(response.handles), 0)
        self.assertIn("unavailable", response.reason)

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_inject_secrets_error(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()
        self.client._stub.InjectSecrets = AsyncMock(
            side_effect=Exception("injection failed")
        )

        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            self.client.inject_secrets([{"name": "secret1"}])
        )
        loop.close()

        self.assertEqual(len(response.handles), 0)
        self.assertIn("injection failed", response.reason)

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_watch_secret_rotation_success(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()

        async def _gen():
            yield MagicMock(
                secret_name="db_pass",
                new_version="v2",
                rotated_at="2026-01-01T00:00:00Z",
            )

        self.client._stub.WatchSecretRotation = MagicMock(return_value=_gen())

        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(
            self._collect_async_gen(self.client.watch_secret_rotation())
        )
        loop.close()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].secret_name, "db_pass")

    def test_watch_secret_rotation_not_connected(self):
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(
            self._collect_async_gen(self.client.watch_secret_rotation())
        )
        loop.close()
        self.assertEqual(results, [])

    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_watch_secret_rotation_error(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        self.client._connected = True
        self.client._stub = MagicMock()

        async def _gen():
            yield MagicMock(
                secret_name="db_pass",
                new_version="v2",
                rotated_at="2026-01-01T00:00:00Z",
            )
            raise Exception("stream error")

        self.client._stub.WatchSecretRotation = MagicMock(return_value=_gen())

        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(
            self._collect_async_gen(self.client.watch_secret_rotation())
        )
        loop.close()

        self.assertEqual(len(results), 1)

    def _collect_async_gen(self, gen):
        return self._collect(gen)

    async def _collect(self, gen):
        results = []
        async for item in gen:
            results.append(item)
        return results


class TestOrchestrationClientConnected(unittest.TestCase):
    def test_connected_property(self):
        OrchestrationClient = _ensure_client_imported()
        client = OrchestrationClient("localhost:50053", "a", "t")
        self.assertFalse(client.connected)
        client._connected = True
        self.assertTrue(client.connected)


class TestOrchestrationClientPlacementConstraints(unittest.TestCase):
    @patch("thinkbox.agent.orchestration_client.asyncio.wait_for")
    def test_request_capacity_placement_constraints(self, mock_wait_for):
        mock_wait_for.return_value = _loop_future()
        mock_wait_for.return_value.set_result(None)
        OrchestrationClient = _ensure_client_imported()
        self.client = OrchestrationClient(
            endpoint="localhost:50053",
            agent_id="agent_1",
            tenant_id="tenant_1",
        )
        self.client._connected = True
        self.client._stub = MagicMock()
        self.client._stub.RequestCapacity = AsyncMock(
            return_value=MagicMock(
                request_id="req_1",
                granted=True,
                allocation_id="alloc_1",
            )
        )

        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            self.client.request_capacity(
                {"cpu_cores": 4.0},
                placement_constraints={
                    "zone": "us-east-1a",
                    "region": "us-east-1",
                    "provider": "aws",
                    "require_gpu": True,
                    "gpu_types": ["A100"],
                    "tenancy": "dedicated",
                    "compliance": ["HIPAA"],
                    "data_residency": "us",
                },
            )
        )
        loop.close()

        self.assertTrue(response.granted)


if __name__ == "__main__":
    unittest.main()
