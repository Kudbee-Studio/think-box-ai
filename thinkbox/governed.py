"""KUDBEE Control Fabric — GovernedEngine wrapper.

Interposes the admission gate and action ledger before any side-effect
execution that the base engine performs. Denied requests are recorded in
the ledger and surfaced as FAILED events instead of executing.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.admission import AdmissionGate, AdmissionDecision
from thinkbox.engine import ThinkBoxEngine, TaskState
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.ledger import ActionLedger

EXECUTION_STATUSES = (
    "FIRST_TRY_SUCCESS",
    "RECOVERED_SUCCESS",
    "FAILED_AFTER_RETRY",
    "BUDGET_EXHAUSTED",
    "UNVERIFIED",
)


@dataclass
class GovernedEngineConfig:
    engine: ThinkBoxEngine
    token_service: GovernanceTokenService | None = None
    identity_ledger: IdentityLedger | None = None
    ledger_path: str = ":memory:"


class GovernedEngine:
    """Admission-gated facade around the base ThinkBoxEngine."""

    def __init__(self, config: GovernedEngineConfig) -> None:
        self._base = config.engine
        self._tokens = config.token_service or GovernanceTokenService()
        self._identities = config.identity_ledger or IdentityLedger()
        self._ledger = ActionLedger(config.ledger_path)
        self._gate = AdmissionGate(self._tokens, self._identities)

    def register_agent(self, agent_id: str, capabilities: list[str]) -> str:
        """Register identity and mint a governance token in one step."""
        self._identities.register(agent_id=agent_id, capabilities=capabilities)
        token = self._tokens.issue(TokenRequest(agent_id=agent_id, capabilities=capabilities, ttl_seconds=3600.0))
        return token.token_value

    def authorize(self, token_value: str, agent_id: str, capability: str, action: str, metadata: dict[str, Any] | None = None) -> AdmissionDecision:
        decision = self._gate.authorize(token_value, agent_id, capability, metadata)
        self._ledger.append(
            agent_id=agent_id,
            capability=capability,
            action=action,
            allowed=decision.allowed,
            reason=decision.reason,
            metadata=metadata,
        )
        return decision

    async def execute_goal(self, goal: str, token_value: str = "", agent_id: str = "", capability: str = "goal:execute") -> dict[str, Any]:
        if token_value:
            decision = self.authorize(token_value, agent_id, capability, "execute_goal")
            if not decision.allowed:
                self._base.emit("root", TaskState.FAILED, f"Governance denied: {decision.reason}")
                return {"governed": False, "reason": decision.reason, "events": len(self._base.events)}
        summary = await self._base.execute_goal(goal)
        summary["governed"] = True
        return summary

    @property
    def ledger(self) -> ActionLedger:
        return self._ledger

    @property
    def gate(self) -> AdmissionGate:
        return self._gate

    async def execute_verified_task(
        self,
        task_id: str,
        prompt: str,
        verify,
        reprompt,
        complete_async,
        session=None,
        agent_id: str = "",
        experiment_id: str = "",
        session_id: str = "",
        latency_s: float = 0.0,
        tokens: Any = 0,
    ) -> dict[str, Any]:
        """Standard verified-execution wrapper around VerifiedRetrySession.

        Smallest safe integration point: every verified Think Job task runs
        here instead of calling the provider directly. Reuses
        VerifiedRetrySession/VerifiedCallResult/BudgetExhausted/RetryTrace
        without duplicating their logic. Behavior without verification is
        untouched — callers that pass verify=None get the legacy single
        attempt with status UNVERIFIED.

        Every attempt records session/job/experiment ids, taxonomy, attempt
        number, latency, usage and outcome into the ledger metadata, and the
        returned dict carries execution_status in
        FIRST_TRY_SUCCESS / RECOVERED_SUCCESS / FAILED_AFTER_RETRY /
        BUDGET_EXHAUSTED / UNVERIFIED for dashboard telemetry.

        tokens may be an int or a zero-arg callable resolved at ledger-append
        time (live runners accumulate usage across attempts).
        """
        from thinkbox.pop_arena import BudgetExhausted, VerifiedRetrySession

        t0 = time.monotonic()
        if session is None:
            session = VerifiedRetrySession()
        if verify is None:
            await complete_async(prompt)
            status = "UNVERIFIED"
            self._ledger.append(
                agent_id=agent_id or task_id,
                capability="model:complete",
                action=f"verified_task:{task_id}",
                allowed=True,
                reason=status,
                metadata={
                    "session_id": session_id,
                    "job_id": task_id,
                    "experiment_id": experiment_id,
                    "taxonomy": "",
                    "attempt": 1,
                    "latency_s": round(time.monotonic() - t0, 3),
                    "tokens": _resolve_tokens(tokens),
                    "outcome": status,
                },
            )
            return {
                "task_id": task_id,
                "execution_status": status,
                "valid": True,
                "taxonomy": "",
                "attempts": 1,
                "retries_used": 0,
                "converted": False,
                "latency_s": round(time.monotonic() - t0, 3),
                "tokens": _resolve_tokens(tokens),
            }
        try:
            result = await session.run_async(task_id, prompt, complete_async, verify, reprompt)
        except BudgetExhausted:
            self._ledger.append(
                agent_id=agent_id or task_id,
                capability="model:complete",
                action=f"verified_task:{task_id}",
                allowed=False,
                reason="BUDGET_EXHAUSTED",
                metadata={
                    "session_id": session_id,
                    "job_id": task_id,
                    "experiment_id": experiment_id,
                    "taxonomy": "",
                    "attempt": session.calls_spent + 1,
                    "latency_s": round(time.monotonic() - t0, 3),
                    "tokens": _resolve_tokens(tokens),
                    "outcome": "BUDGET_EXHAUSTED",
                },
            )
            return {
                "task_id": task_id,
                "execution_status": "BUDGET_EXHAUSTED",
                "valid": False,
                "taxonomy": "",
                "attempts": result_attempts(session),
                "retries_used": session.retries_fired,
                "converted": False,
                "latency_s": round(time.monotonic() - t0, 3),
                "tokens": _resolve_tokens(tokens),
            }
        if result.valid and result.attempts == 1:
            status = "FIRST_TRY_SUCCESS"
        elif result.valid:
            status = "RECOVERED_SUCCESS"
        else:
            status = "FAILED_AFTER_RETRY"
        self._ledger.append(
            agent_id=agent_id or task_id,
            capability="model:complete",
            action=f"verified_task:{task_id}",
            allowed=result.valid,
            reason=status,
            metadata={
                "session_id": session_id,
                "job_id": task_id,
                "experiment_id": experiment_id,
                "taxonomy": result.trace.first_taxonomy,
                "final_taxonomy": result.trace.final_taxonomy,
                "attempt": result.attempts,
                "latency_s": latency_s or round(time.monotonic() - t0, 3),
                "tokens": _resolve_tokens(tokens),
                "outcome": status,
            },
        )
        return {
            "task_id": task_id,
            "execution_status": status,
            "valid": result.valid,
            "taxonomy": result.trace.first_taxonomy,
            "final_taxonomy": result.trace.final_taxonomy,
            "attempts": result.attempts,
            "retries_used": result.retries_used,
            "converted": result.converted,
            "latency_s": latency_s or round(time.monotonic() - t0, 3),
            "tokens": _resolve_tokens(tokens),
            "trace": result.trace.to_dict(),
        }

    async def execute_verified_goal(
        self,
        goal: str,
        subtasks: list[dict[str, Any]],
        complete_async,
        token_value: str = "",
        agent_id: str = "",
        capability: str = "goal:execute",
        max_calls: int = 0,
        max_retries: int | None = None,
        session: Any = None,
        manager: Any = None,
        emit_dashboard: bool = False,
        persist_profile: dict[str, Any] | None = None,
        goal_experiment_id: str | None = None,
        session_id_override: str | None = None,
    ) -> dict[str, Any]:
        """DAG-level verified execution through the REAL engine lifecycle.

        Builds a TaskGraph from subtask specs (each: description, family,
        spec, optional depends_on list of subtask indexes), assigns every
        task a stable task/session/experiment identifier, injects a runner
        that delegates each eligible task to the canonical
        execute_verified_task primitive (shared bounded VerifiedRetrySession
        across the whole DAG), executes via ThinkBoxEngine.execute_goal,
        aggregates child outcomes without hiding failures/recoveries, and
        persists telemetry through the existing ExperimentManager /
        ActionLedger / proof-artifact architecture.

        This is NOT a second execution wrapper: retry/verification logic
        lives only in VerifiedRetrySession; per-task governance lives only in
        execute_verified_task. This method wires them into the DAG lifecycle.
        """
        from thinkbox.decomposer import TaskGraph, TaskNode
        from thinkbox.pop_arena import (
            VerifiedRetryConfig, VerifiedRetrySession,
            extract_json, retry_prompt_for, verify_v2,
        )

        if token_value:
            decision = self.authorize(token_value, agent_id, capability, "execute_verified_goal")
            if not decision.allowed:
                self._base.emit("root", TaskState.FAILED, f"Governance denied: {decision.reason}")
                return {"governed": False, "reason": decision.reason, "events": len(self._base.events)}

        now = datetime.now(timezone.utc)
        session_id = session_id_override or f"tb_sess_{now.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:4]}"
        goal_experiment_id = goal_experiment_id or f"tb_exp_{now.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

        cfg_kwargs: dict[str, Any] = {"max_calls": max_calls}
        if max_retries is not None:
            cfg_kwargs["max_retries"] = max_retries
        if session is None:
            session = VerifiedRetrySession(VerifiedRetryConfig(**cfg_kwargs))

        nodes: list[TaskNode] = []
        for i, st in enumerate(subtasks):
            ts = datetime.now(timezone.utc)
            node = TaskNode(
                id=f"dagtask_{ts.strftime('%Y%m%d%H%M%S')}_{i:02d}_{uuid.uuid4().hex[:6]}",
                description=st["description"],
                dependencies=[nodes[d].id for d in st.get("depends_on", []) if d < i],
                metadata={
                    "verification": {"family": st["family"], "spec": st["spec"]},
                    "experiment_id": f"tb_exp_{ts.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
                    "session_id": session_id,
                    "family": st["family"],
                    "variant": st.get("variant", ""),
                },
            )
            nodes.append(node)
        graph = TaskGraph(root_id=nodes[0].id, tasks={n.id: n for n in nodes})

        task_outputs: dict[str, dict[str, Any]] = {}
        tokens_by_task: dict[str, int] = {}

        async def _counting_complete(task_id: str):
            async def _complete(prompt: str) -> str:
                out = await complete_async(prompt)
                if isinstance(out, tuple):
                    text, usage = out[0], (out[1] or {})
                else:
                    text, usage = out, {}
                if isinstance(usage, dict):
                    tokens_by_task[task_id] = tokens_by_task.get(task_id, 0) + int(usage.get("total_tokens") or 0)
                return text
            return _complete

        async def _runner(task_id: str, prompt: str, verification: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
            family = verification["family"]
            spec = verification["spec"]
            verify = lambda text: verify_v2(family, extract_json(text), spec)  # noqa: E731
            reprompt = lambda taxonomy: retry_prompt_for(family, taxonomy, spec)  # noqa: E731
            complete = await _counting_complete(task_id)
            res = await self.execute_verified_task(
                task_id=task_id,
                prompt=prompt,
                verify=verify,
                reprompt=reprompt,
                complete_async=complete,
                session=session,
                agent_id=agent_id or task_id,
                experiment_id=context.get("experiment_id", ""),
                session_id=context.get("session_id", session_id),
                tokens=lambda: tokens_by_task.get(task_id, 0),
            )
            task_outputs[task_id] = res
            return res

        previous_runner = self._base._verified_task_runner
        self._base.set_verified_task_runner(_runner)
        try:
            summary = await self._base.execute_goal(goal, graph=graph)
        finally:
            self._base.set_verified_task_runner(previous_runner)

        verified = summary.get("verified", {})
        summary["governed"] = True
        summary["session_id"] = session_id
        summary["goal_experiment_id"] = goal_experiment_id
        summary["task_experiment_ids"] = {n.id: n.metadata["experiment_id"] for n in nodes}
        summary["calls_spent"] = session.calls_spent
        summary["budget_remaining"] = session.budget_remaining
        summary["budget_config"] = session.config.to_dict()

        self._ledger.append(
            agent_id=agent_id or "governed-engine",
            capability=capability,
            action="execute_verified_goal",
            allowed=True,
            reason="DAG_COMPLETE",
            metadata={
                "session_id": session_id,
                "job_id": goal_experiment_id,
                "experiment_id": goal_experiment_id,
                "tasks": len(nodes),
                "first_try_successes": verified.get("first_try_successes", 0),
                "recovered_successes": verified.get("recovered_successes", 0),
                "failures": verified.get("failures", 0),
                "budget_exhausted": verified.get("budget_exhausted", 0),
                "retries": verified.get("retries", 0),
                "verification_rate": verified.get("verification_rate", 0.0),
                "calls_spent": session.calls_spent,
            },
        )

        if manager is not None:
            self._persist_verified_goal(
                manager=manager,
                goal=goal,
                session_id=session_id,
                goal_experiment_id=goal_experiment_id,
                nodes=nodes,
                summary=summary,
                task_outputs=task_outputs,
                tokens_by_task=tokens_by_task,
                persist_profile=persist_profile,
            )

        if emit_dashboard:
            try:
                from thinkbox.dashboard_state import (
                    get_dashboard_state, DashboardCategory, DashboardEvent,
                )
                await get_dashboard_state().emit(
                    DashboardCategory.THINK_JOBS,
                    DashboardEvent.JOB_COMPLETED,
                    {
                        "job_id": goal_experiment_id,
                        "session_id": session_id,
                        "kind": "verified_goal_dag",
                        "tasks": verified.get("tasks", 0),
                        "first_try_successes": verified.get("first_try_successes", 0),
                        "recovered_successes": verified.get("recovered_successes", 0),
                        "failures": verified.get("failures", 0),
                        "budget_exhausted": verified.get("budget_exhausted", 0),
                        "retries": verified.get("retries", 0),
                        "verification_rate": verified.get("verification_rate", 0.0),
                        "calls_spent": session.calls_spent,
                    },
                    source="GovernedEngine.execute_verified_goal",
                    evidence_label="verified",
                )
            except Exception:
                pass

        return summary

    def _persist_verified_goal(
        self,
        manager: Any,
        goal: str,
        session_id: str,
        goal_experiment_id: str,
        nodes: list,
        summary: dict[str, Any],
        task_outputs: dict[str, dict[str, Any]],
        tokens_by_task: dict[str, int],
        persist_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist DAG telemetry via the existing ExperimentManager architecture."""
        import hashlib
        import json as _json
        from datetime import datetime as _dt

        from thinkbox.experiment import AgentSessionRecord, ExperimentRecord, ParameterProvenance

        profile = persist_profile or {}
        four_state = profile.get("four_state", "LIVE_VERIFIED")
        execution_mode = profile.get("execution_mode", "live")
        persist_agent = profile.get("agent_id_field", "governed-engine")
        model_name = profile.get("model", "mercury-2")
        provider_name = profile.get("provider", "openai_compat")
        evidence_label = profile.get("evidence_label", "verified")
        verified = summary.get("verified", {})
        now_iso = _dt.now(timezone.utc).isoformat()

        manager.db.save_session(AgentSessionRecord(
            session_id=session_id,
            agent_id=persist_agent,
            started_at=now_iso,
            ended_at=now_iso,
            last_completed_action="execute_verified_goal",
            current_state="COMPLETE",
            four_state=four_state,
            metadata={"goal": goal[:200], "goal_experiment_id": goal_experiment_id},
        ))

        goal_rec = ExperimentRecord(
            experiment_id=goal_experiment_id,
            session_id=session_id,
            agent_id=persist_agent,
            timestamp=now_iso,
            intent=f"verified-goal-dag: {goal[:150]}",
            hypothesis="eligible DAG tasks pass through the governed verified-execution primitive with bounded retries",
            execution_mode=execution_mode,
            status="completed",
            four_state=four_state,
            confidence=1.0,
        )
        manager.db.save_experiment(goal_rec)
        for name, value in (
            ("scope", "dag"),
            ("dag_tasks", str(len(nodes))),
            ("first_try_successes", str(verified.get("first_try_successes", 0))),
            ("recovered_successes", str(verified.get("recovered_successes", 0))),
            ("failures", str(verified.get("failures", 0))),
            ("budget_exhausted", str(verified.get("budget_exhausted", 0))),
            ("retries", str(verified.get("retries", 0))),
            ("verification_rate", str(verified.get("verification_rate", 0.0))),
            ("calls_spent", str(summary.get("calls_spent", 0))),
        ):
            manager.db.save_parameter(goal_experiment_id, ParameterProvenance(
                name=name, value=value, source="measured", confidence=1.0, session_id=session_id,
            ))

        artifacts_dir = manager.artifacts_dir
        proof_tasks = []
        for node in nodes:
            exp_id = node.metadata["experiment_id"]
            out = task_outputs.get(node.id, {})
            rec = ExperimentRecord(
                experiment_id=exp_id,
                session_id=session_id,
                agent_id=persist_agent,
                timestamp=now_iso,
                intent=node.metadata.get("family", "") + (f":{node.metadata['variant']}" if node.metadata.get("variant") else ""),
                hypothesis=node.description[:200],
                execution_mode=execution_mode,
                status="completed" if out.get("valid") else "failed",
                four_state=four_state if out.get("valid") else four_state,
                confidence=1.0 if out.get("valid") else 0.0,
            )
            manager.db.save_experiment(rec)
            for name, value in (
                ("scope", "dag_task"),
                ("dag_goal_experiment", goal_experiment_id),
                ("task_id", node.id),
                ("family", node.metadata.get("family", "")),
                ("variant", node.metadata.get("variant", "")),
                ("execution_status", out.get("execution_status", "")),
                ("model", model_name),
                ("provider", provider_name),
            ):
                manager.db.save_parameter(exp_id, ParameterProvenance(
                    name=name, value=str(value), source="measured", confidence=1.0, session_id=session_id,
                ))
            outcome = {
                "property_valid": bool(out.get("valid")),
                "execution_status": out.get("execution_status", ""),
                "taxonomy": out.get("taxonomy", ""),
                "final_taxonomy": out.get("final_taxonomy", ""),
                "attempts": out.get("attempts"),
                "retries_used": out.get("retries_used"),
                "converted": out.get("converted"),
                "latency_s": out.get("latency_s"),
                "tokens": tokens_by_task.get(node.id, 0),
                "trace": out.get("trace", {}),
            }
            manager.db.save_outcome(
                exp_id, outcome,
                1.0 if out.get("valid") else 0.0,
                four_state,
            )
            artifact_payload = {
                "experiment_id": exp_id,
                "session_id": session_id,
                "goal_experiment_id": goal_experiment_id,
                "task_id": node.id,
                "description": node.description,
                "dependencies": node.dependencies,
                "family": node.metadata.get("family", ""),
                "variant": node.metadata.get("variant", ""),
                "telemetry": outcome,
                "timestamp": now_iso,
            }
            art_path = artifacts_dir / f"dagpath_{node.metadata.get('family','task')}_{node.metadata.get('variant','')}_{exp_id}.json"
            art_path.write_text(_json.dumps(artifact_payload, indent=2, sort_keys=True))
            art_hash = hashlib.sha256(art_path.read_bytes()).hexdigest()
            manager.db.save_artifact(exp_id, f"art_dag_{exp_id[-8:]}", "dag_task_artifact",
                                     str(art_path), art_hash, {"task_id": node.id})
            proof_tasks.append({
                "task_id": node.id,
                "experiment_id": exp_id,
                "artifact": str(art_path),
                "artifact_sha256": art_hash,
                **{k: outcome[k] for k in ("execution_status", "taxonomy", "final_taxonomy",
                                           "attempts", "retries_used", "converted", "latency_s")},
                "tokens": outcome["tokens"],
            })

        proof = {
            "phase": "dag-verified-execution",
            "timestamp": now_iso,
            "session_id": session_id,
            "goal_experiment_id": goal_experiment_id,
            "goal": goal[:200],
            "integration_point": "ThinkBoxEngine.execute_goal._execute_task -> GovernedEngine.execute_verified_task -> VerifiedRetrySession.run_async",
            "dag": {
                "tasks": len(nodes),
                "layers": "see dependencies per task",
                **{k: verified.get(k) for k in ("first_try_successes", "recovered_successes",
                                                "failures", "budget_exhausted", "retries",
                                                "verification_rate")},
                "calls_spent": summary.get("calls_spent", 0),
                "budget_config": summary.get("budget_config", {}),
            },
            "tasks": proof_tasks,
            "ledger_entries": "one per task via execute_verified_task + one goal-level entry",
            "no_claims": [
                "no model intelligence improvement claimed",
                "no GPU", "no UpCloud compute", "no SSH",
            ],
        }
        proof_bytes = _json.dumps(proof, indent=2, sort_keys=True).encode()
        proof_hash = hashlib.sha256(proof_bytes).hexdigest()
        proof["proof_sha256"] = proof_hash
        proof_path = artifacts_dir / f"dagpath_proof_{goal_experiment_id}.json"
        proof_path.write_text(_json.dumps(proof, indent=2, sort_keys=True))
        manager.db.save_artifact(goal_experiment_id, f"art_dagproof_{proof_hash[:8]}", "dag_proof",
                                 str(proof_path), proof_hash, {"tasks": len(nodes)})
        manager.db.save_proof(goal_experiment_id, {
            "proof_id": proof_path.stem,
            "evidence_label": evidence_label,
            "hash": proof_hash,
        })
        summary["proof_artifact"] = str(proof_path)
        summary["proof_sha256"] = proof_hash
        return proof


def _resolve_tokens(tokens: Any) -> int:
    if callable(tokens):
        try:
            return int(tokens() or 0)
        except Exception:
            return 0
    try:
        return int(tokens or 0)
    except (TypeError, ValueError):
        return 0


def result_attempts(session) -> int:
    """Attempts so far on a session (calls spent; 0 when budget blocked first call)."""
    return session.calls_spent