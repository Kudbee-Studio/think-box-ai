"""Bootstrap system for THINK BOX AI.

Single entry point for starting the runtime:
  1. Loads configuration from all sources
  2. Sets up logging
  3. Initializes the memory store (SQLite)
  4. Creates memory layer adapters (session, task, organizational)
  5. Creates governance (permission checker, audit log, approval gate)
  6. Optionally creates a provider (if API key is configured)
  7. Optionally registers built-in tools
  8. Returns a RuntimeContext with all initialized components
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.foundation.config import ThinkBoxConfig, load_config
from core.foundation.logging import get_logger, setup_logging
from core.governance.audit import ApprovalGate, ApprovalPolicy, AuditLog, PermissionChecker
from core.memory.org import OrganizationalMemoryAdapter
from core.memory.session import SessionMemoryAdapter
from core.memory.store import MemoryStore
from core.memory.task import TaskMemoryAdapter
from core.providers.base import ModelProvider, ProviderRegistry
from core.tools import file_read, file_write, http_request, memory_query, shell_exec
from core.tools.registry import ToolRegistry

from core.tools.fs import fs_read, fs_write, fs_list
from core.tools.http import http_get
from core.tools.memory import memory_put, memory_get, memory_search, init_memory_db
from core.tools.doginals import doge_tx, doginals_inscription, compare_inscription, parse_drc20, load_fixture

import core.providers.ollama
import core.providers.openai_compat

logger = get_logger(__name__)


@dataclass
class RuntimeContext:
    """Holds all initialized runtime components."""

    config: ThinkBoxConfig
    store: MemoryStore
    session_memory: SessionMemoryAdapter
    org_memory: OrganizationalMemoryAdapter
    provider: ModelProvider | None = None
    tool_registry: ToolRegistry | None = None
    approval_gate: ApprovalGate | None = None
    project_root: Path = field(default_factory=Path.cwd)

    def create_session(self, session_id: str, agent_id: str) -> SessionMemoryAdapter:
        return SessionMemoryAdapter(
            session_id=session_id,
            agent_id=agent_id,
            store=self.store,
        )

    def create_task_memory(self, task_id: str, root_goal_id: str, agent_id: str) -> TaskMemoryAdapter:
        return TaskMemoryAdapter(
            task_id=task_id,
            root_goal_id=root_goal_id,
            agent_id=agent_id,
            store=self.store,
        )


def _ensure_directories(config: ThinkBoxConfig, project_root: Path) -> None:
    Path(config.data_dir).mkdir(parents=True, exist_ok=True)
    Path(config.memory_db_path).parent.mkdir(parents=True, exist_ok=True)
    (project_root / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (project_root / "data" / "findings").mkdir(parents=True, exist_ok=True)
    (project_root / "data" / "fixtures").mkdir(parents=True, exist_ok=True)


def _create_provider(config: ThinkBoxConfig) -> ModelProvider | None:
    provider_name = config.default_provider
    provider_cls = ProviderRegistry.get(provider_name)
    if provider_cls is None:
        logger.warning(
            "Provider not found in registry",
            extra={"provider": provider_name, "available": ProviderRegistry.list_providers()},
        )
        return None

    provider_config: dict[str, Any] = {}

    if provider_name == "ollama":
        provider_config["base_url"] = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        provider_config["model"] = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
        provider_config["timeout"] = int(os.environ.get("OLLAMA_TIMEOUT", "120"))
        logger.info("Ollama provider configured", extra={"model": provider_config["model"], "url": provider_config["base_url"]})
        return provider_cls(provider_config)

    api_key = os.environ.get(f"THINKBOX_{provider_name.upper()}_API_KEY", "")
    if not api_key:
        logger.info(f"No API key configured for {provider_name}")
        return None

    provider_config["api_key"] = api_key
    provider_config.setdefault("model", config.default_model)
    provider_config["base_url"] = os.environ.get(f"THINKBOX_{provider_name.upper()}_BASE_URL", "")
    return provider_cls(provider_config)


def _create_tool_registry(audit_log: AuditLog, project_root: Path) -> ToolRegistry:
    registry = ToolRegistry(audit_log)

    builtin_tools = [file_read, file_write, shell_exec, http_request, memory_query,
                     fs_read, fs_write, fs_list, http_get,
                     memory_put, memory_get, memory_search,
                     doge_tx, doginals_inscription, compare_inscription, parse_drc20, load_fixture]
    for t in builtin_tools:
        if hasattr(t, "_tool_definition"):
            registry.register(t._tool_definition)

    logger.info("Tool registry initialized", extra={"tool_count": len(registry.list_tools()), "tools": [t.name for t in registry.list_tools()]})
    return registry


def bootstrap(
    project_root: Path | str | None = None,
    log_level: str | None = None,
    with_provider: bool = True,
    with_tools: bool = True,
) -> RuntimeContext:
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)

    os.chdir(project_root)

    config = load_config(project_root)
    if log_level is not None:
        config.log_level = log_level

    setup_logging(config.log_level)
    logger.info("THINK BOX AI bootstrapping", extra={
        "project_root": str(project_root),
        "config": {
            "default_provider": config.default_provider,
            "default_model": config.default_model,
            "max_think_box_depth": config.max_think_box_depth,
            "data_dir": config.data_dir,
        },
    })

    _ensure_directories(config, project_root)

    db_path = project_root / config.memory_db_path
    store = MemoryStore(db_path)
    logger.info("Memory store initialized", extra={"db_path": str(db_path)})

    research_db_path = project_root / "data" / "thinkbox.sqlite"
    init_memory_db(research_db_path)
    logger.info("Research memory DB initialized", extra={"db_path": str(research_db_path)})

    session_memory = SessionMemoryAdapter(session_id="bootstrap", agent_id="system", store=store)
    org_memory = OrganizationalMemoryAdapter(store=store)

    permission_checker = PermissionChecker(ApprovalPolicy(config.default_approval_policy))
    audit_log = AuditLog(store)
    approval_gate = ApprovalGate(permission_checker, audit_log)

    provider = _create_provider(config) if with_provider else None
    if provider:
        logger.info("Provider initialized", extra={"provider": config.default_provider, "model": config.default_model})

    tool_registry = _create_tool_registry(audit_log, project_root) if with_tools else None

    logger.info("THINK BOX AI bootstrap complete")
    return RuntimeContext(
        config=config,
        store=store,
        session_memory=session_memory,
        org_memory=org_memory,
        provider=provider,
        tool_registry=tool_registry,
        approval_gate=approval_gate,
        project_root=project_root,
    )


def shutdown(ctx: RuntimeContext) -> None:
    logger.info("THINK BOX AI shutting down")
    ctx.session_memory.flush()
    ctx.store.close()
    logger.info("THINK BOX AI shutdown complete")
