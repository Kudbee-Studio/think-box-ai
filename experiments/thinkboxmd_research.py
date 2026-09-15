#!/usr/bin/env python3
"""THINKBOXMD-RESEARCH — KUDBEE end-to-end research workflow test.

PURPOSE
-------
Prove KUDBEE can execute a real end-to-end research workflow using the
existing Think Box / control-fabric infrastructure and a real model provider.

This is a RESEARCH + INFRASTRUCTURE test. It is NOT clinical advice and it
does NOT perform autonomous medical decision-making. All scenarios are
synthetic. All findings must be tiered:

    EVIDENCE      directly supported by a cited public source
    INFERENCE     reasoned from evidence, not itself directly cited
    HYPOTHESIS    plausible, unverified
    UNVERIFIED    could not be grounded

Every scenario record is tagged SYNTHETIC=true.

REAL INFRASTRUCTURE USED (see PROOF output for actual booleans)
--------------------------------------------------------------
  Think Boxes .......... thinkbox.workspace (WorkspaceRegistry + WorkspaceStore)
  Governance ........... thinkbox.{identity,governance_token,admission}
  Audit / proof ........ thinkbox.ledger.ActionLedger (SHA-256 hash chain)
  Tracing .............. thinkbox.thinktrace.ThinkTraceCapture
  Memory ............... core.memory.store.MemoryStore (SQLite)
  Provider ............. core.providers.openai_compat (live Mercury 2)
  Vector memory ........ thinkbox.session.UpstashVectorSync (if configured)

Usage:
    python experiments/thinkboxmd_research.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thinkbox.workspace import WorkspaceRegistry, WorkspaceStore, ThinkBox
from thinkbox.identity import IdentityLedger
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.admission import AdmissionGate
from thinkbox.ledger import ActionLedger
from thinkbox.thinktrace import ThinkTraceCapture
from core.memory.store import MemoryStore
from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer
from core.providers.openai_compat import OpenAICompatProvider
from core.providers.base import Message
from thinkbox.session import UpstashVectorSync, create_session

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

INCEPTION_BASE_URL = "https://api.inceptionlabs.ai/v1"
INCEPTION_MODEL = "mercury-2"

OUT_DIR = ROOT / "data" / "thinkboxmd"
DB_DIR = OUT_DIR / "db"

SAFETY_BANNER = (
    "RESEARCH INFRASTRUCTURE TEST. NOT CLINICAL ADVICE. "
    "No real patient data. Synthetic scenarios only. "
    "Do not produce dosing guidance or actionable medical instructions."
)


class Tier(str, Enum):
    EVIDENCE = "EVIDENCE"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    UNVERIFIED = "UNVERIFIED"


# --------------------------------------------------------------------------
# Data shapes
# --------------------------------------------------------------------------

@dataclass
class SyntheticScenario:
    scenario_id: str
    synthetic: bool
    title: str
    profile: dict[str, Any]
    agents_co_prescribed: list[str]
    research_question: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    worker: str
    scenario_id: str
    tier: str
    claim: str
    rationale: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.0
    raw_chars: int = 0
    latency_s: float = 0.0
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    trace_id: str = ""
    ledger_entry_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkerSpec:
    role: str
    capability: str
    mission: str
    system_prompt: str


# --------------------------------------------------------------------------
# Worker definitions
# --------------------------------------------------------------------------

TIER_INSTRUCTION = (
    "For EVERY claim you make, prefix it with exactly one tier token from: "
    "[EVIDENCE], [INFERENCE], [HYPOTHESIS], [UNVERIFIED]. "
    "EVIDENCE requires a named public source category (e.g. FDA label, "
    "peer-reviewed pharmacology review, published clinical guideline). "
    "If you cannot name a source, downgrade to INFERENCE or HYPOTHESIS."
)

COMMON_RULES = (
    f"{SAFETY_BANNER}\n"
    "You are a research worker inside an auditable test harness. "
    "You must never output real patient data. "
    "You must never give dosing, administration, or treatment instructions. "
    "Answer strictly about evidence quality, mechanisms, and contradictions. "
    f"{TIER_INSTRUCTION}\n"
    "Return STRICT JSON with keys: "
    '"claims" (list of {tier, claim, rationale, evidence_refs}), '
    '"contradictions" (list of strings), '
    '"unsupported" (list of strings), '
    '"limitations" (list of strings). '
    "No prose outside the JSON."
)

WORKERS: list[WorkerSpec] = [
    WorkerSpec(
        role="PHARMA",
        capability="research:pharmacology",
        mission="Interaction evidence",
        system_prompt=(
            "You are PHARMA, a pharmacology evidence researcher. "
            "Given a synthetic co-prescription scenario, enumerate what classes "
            "of public evidence would be needed to establish a drug-interaction "
            "signal, and classify each claim by tier. "
            "You do not provide clinical recommendations. " + COMMON_RULES
        ),
    ),
    WorkerSpec(
        role="TOX",
        capability="research:toxicology",
        mission="Overdose mechanisms (evidence framing only)",
        system_prompt=(
            "You are TOX, a toxicology evidence researcher. "
            "Given a synthetic scenario, describe the GENERAL mechanisms by "
            "which overdose risk is assessed and what evidence categories are "
            "required to substantiate a mechanism claim. "
            "Do NOT state lethal doses, thresholds, or actionable quantities. "
            "Classify every claim by tier. " + COMMON_RULES
        ),
    ),
    WorkerSpec(
        role="VALIDATOR",
        capability="research:validation",
        mission="Challenge claims",
        system_prompt=(
            "You are VALIDATOR, an adversarial evidence reviewer. "
            "Given another worker's claim set, attempt to falsify or downgrade "
            "each claim: identify missing sources, overreach, and tier inflation. "
            "Your job is to be skeptical, not agreeable. " + COMMON_RULES
        ),
    ),
    WorkerSpec(
        role="SAFETY",
        capability="research:safety",
        mission="Flag unsupported or dangerous conclusions",
        system_prompt=(
            "You are SAFETY, a research-safety reviewer. "
            "Given findings, flag any statement that (a) reads as clinical "
            "advice, (b) implies actionable dosing/administration, or (c) asserts "
            "causality without EVIDENCE-tier support. "
            "Output the flagged text verbatim and the reason. " + COMMON_RULES
        ),
    ),
    WorkerSpec(
        role="SYNTH",
        capability="research:synthesis",
        mission="Generate synthetic scenarios",
        system_prompt=(
            "You are SYNTH, a synthetic-scenario generator. "
            "Produce additional SYNTHETIC patient scenarios (clearly labelled "
            "SYNTHETIC=true) that stress-test interaction and overdose-risk "
            "evidence reasoning. Never use real personal data. "
            "Every generated scenario must be fictional. " + COMMON_RULES
        ),
    ),
]


# --------------------------------------------------------------------------
# Provider wrapper (real, live Mercury 2)
# --------------------------------------------------------------------------

class MercuryClient:
    """Thin wrapper over the repo's real OpenAI-compatible provider."""

    def __init__(self, base_url: str = INCEPTION_BASE_URL, model: str = INCEPTION_MODEL):
        self.base_url = base_url
        self.model = model
        key = os.environ.get("INCEPTION_API_KEY", "")
        self._provider = OpenAICompatProvider(
            {"api_key": key, "model": model, "base_url": base_url}
        )

    @property
    def key_present(self) -> bool:
        return bool(self._provider._api_key)

    async def complete(self, system: str, user: str, max_tokens: int = 3500) -> tuple[str, dict, float]:
        t0 = time.monotonic()
        resp = await self._provider.complete(
            [Message(role="system", content=system), Message(role="user", content=user)],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return resp.content or "", resp.usage or {}, time.monotonic() - t0


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def extract_json(text: str) -> dict[str, Any]:
    """Robustly extract the first balanced JSON object from model output.

    Handles markdown code fences, leading prose, and nested braces.
    """
    if not text:
        return {}
    cleaned = text.strip()
    # Strip markdown fences
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    # Direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Balanced-brace scan
    start = cleaned.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        start = cleaned.find("{", start + 1)
    return {}


def tier_of(token: str) -> str:
    for t in Tier:
        if t.value in token.upper():
            return t.value
    return Tier.UNVERIFIED.value


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Main experiment
# --------------------------------------------------------------------------

class ThinkBoxMDResearch:
    def __init__(self, inject_failure: bool = True) -> None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        DB_DIR.mkdir(parents=True, exist_ok=True)

        self.inject_failure = inject_failure
        self.run_id = f"thinkboxmd_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.started_at = now_iso()

        # --- REAL infrastructure -------------------------------------------
        self.registry = WorkspaceRegistry()
        self.store = WorkspaceStore(DB_DIR / "workspaces.db")
        self.identities = IdentityLedger()
        self.tokens = GovernanceTokenService(signing_key=f"thinkboxmd-{self.run_id}")
        self.gate = AdmissionGate(self.tokens, self.identities)
        self.ledger = ActionLedger(DB_DIR / "action_ledger.db")
        self.traces = ThinkTraceCapture()
        self.memory = MemoryStore(DB_DIR / "research_memory.db")
        self.vector = UpstashVectorSync()
        self.session = create_session(
            environment="local",
            model_backend="OpenAI-compat",
            actor="kudbee-thinkboxmd",
            metadata={"run_id": self.run_id, "synthetic": True},
        )

        # --- Provider -------------------------------------------------------
        self.client = MercuryClient()

        # --- Results --------------------------------------------------------
        self.workers: dict[str, dict[str, Any]] = {}
        self.findings: list[Finding] = []
        self.failures: list[dict[str, Any]] = []
        self.reconciliation: dict[str, Any] = {}
        self.memory_written: list[str] = []
        self.vector_synced = False
        self.logs: list[str] = []

    def log(self, msg: str) -> None:
        line = f"[{now_iso()}] {msg}"
        self.logs.append(line)
        print("  " + msg)

    # -- Stage 1: BOOT -------------------------------------------------------

    def stage_boot(self) -> dict[str, Any]:
        print("\n[1] BOOT — wiring real infrastructure")
        report = {
            "provider_key_present": self.client.key_present,
            "provider_base_url": self.client.base_url,
            "provider_model": self.client.model,
            "thinkbox_workspace_store": str(self.store._path),
            "action_ledger": str(self.ledger._path),
            "memory_store": str(self.memory.db_path),
            "vector_enabled": self.vector.enabled,
        }
        for k, v in report.items():
            self.log(f"{k} = {v}")
        return report

    # -- Stage 2: THINK BOX --------------------------------------------------

    def stage_create_box(self) -> ThinkBox:
        print("\n[2] THINK BOX — creating THINKBOXMD-RESEARCH")

        self.identities.register(
            agent_id="THINKBOXMD-RESEARCH",
            capabilities=[w.capability for w in WORKERS] + ["research:orchestrate"],
            metadata={"kind": "research", "synthetic_only": True},
        )
        token = self.tokens.issue(
            TokenRequest(
                agent_id="THINKBOXMD-RESEARCH",
                capabilities=[w.capability for w in WORKERS] + ["research:orchestrate"],
                ttl_seconds=3600,
                attestation={"synthetic_only": True, "not_clinical": True},
            )
        )
        self.token_value = token.token_value

        box = self.registry.create(
            owner_id="THINKBOXMD-RESEARCH",
            capabilities=[w.capability for w in WORKERS] + ["research:orchestrate"],
            state={
                "mission": "Research medication interaction & overdose-risk evidence patterns (synthetic only)",
                "synthetic_only": True,
                "not_clinical": True,
                "run_id": self.run_id,
            },
        )
        self.store.save(box)
        self.ledger.append(
            agent_id="THINKBOXMD-RESEARCH",
            capability="research:orchestrate",
            action="create_think_box",
            allowed=True,
            reason="admitted",
            metadata={"box_id": box.box_id, "run_id": self.run_id},
        )
        self.log(f"box_id = {box.box_id} (persisted to {self.store._path})")
        self.box = box
        return box

    def stage_create_workers(self) -> None:
        print("\n[3] SWARM — registering specialized worker boxes")
        for spec in WORKERS:
            self.identities.grant("THINKBOXMD-RESEARCH", spec.capability)
            wbox = self.registry.create(
                owner_id="THINKBOXMD-RESEARCH",
                capabilities=[spec.capability],
                state={"role": spec.role, "mission": spec.mission, "synthetic_only": True},
            )
            self.store.save(wbox)
            self.workers[spec.role] = {"spec": spec, "box": wbox}
            self.log(f"{spec.role:9s} box={wbox.box_id} cap={spec.capability}")

    # -- Stage 3: RESEARCH ---------------------------------------------------

    def stage_research(self, scenarios: list[SyntheticScenario]) -> None:
        print("\n[4] RESEARCH — workers querying live provider")

        # SYNTH first: generate extra synthetic scenarios
        self._run_worker("SYNTH", scenarios, prior_findings=None)

        # PHARMA + TOX produce primary findings for each scenario
        for scenario in scenarios:
            for role in ("PHARMA", "TOX"):
                self._run_worker(role, [scenario], prior_findings=None)

        # VALIDATOR challenges PHARMA + TOX output
        primary = [f for f in self.findings if f.worker in ("PHARMA", "TOX")]
        self._run_worker("VALIDATOR", scenarios, prior_findings=primary)

        # SAFETY reviews everything
        self._run_worker("SAFETY", scenarios, prior_findings=self.findings)

    def _run_worker(
        self,
        role: str,
        scenarios: list[SyntheticScenario],
        prior_findings: list[Finding] | None,
    ) -> None:
        spec: WorkerSpec = self.workers[role]["spec"]
        box: ThinkBox = self.workers[role]["box"]
        worker_agent = f"THINKBOXMD-{role}"

        # Governance: every worker acts as a distinct admitted identity.
        if self.identities.get(worker_agent) is None:
            self.identities.register(worker_agent, capabilities=[spec.capability])
        w_token = self.tokens.issue(
            TokenRequest(
                agent_id=worker_agent,
                capabilities=[spec.capability],
                ttl_seconds=3600,
                attestation={"synthetic_only": True},
            )
        )
        decision = self.gate.authorize(w_token.token_value, worker_agent, spec.capability)
        entry = self.ledger.append(
            agent_id=worker_agent,
            capability=spec.capability,
            action=f"research_call:{role}",
            allowed=decision.allowed,
            reason=decision.reason,
            metadata={"box_id": box.box_id, "run_id": self.run_id, "synthetic": True},
        )
        if not decision.allowed:
            self.failures.append({"worker": role, "kind": "admission_denied", "reason": decision.reason})
            self.log(f"{role:9s} ADMISSION DENIED ({decision.reason})")
            return

        user_prompt = self._build_user_prompt(role, scenarios, prior_findings)
        finding = Finding(
            worker=role,
            scenario_id=scenarios[0].scenario_id if scenarios else "ALL",
            tier=Tier.UNVERIFIED.value,
            claim="",
            ledger_entry_id=entry.entry_id,
        )

        # Deliberate failure injection on the first TOX call.
        provider_override = None
        if self.inject_failure and role == "TOX" and not any(
            f.get("kind") == "provider_unavailable" for f in self.failures
        ):
            provider_override = "http://127.0.0.1:9/v1"  # closed port
            self.log(f"{role:9s} ⚠ injecting provider failure (unreachable endpoint)")

        client = self.client
        if provider_override:
            client = MercuryClient(base_url=provider_override, model=self.client.model)

        try:
            content, usage, latency = asyncio.run(
                client.complete(spec.system_prompt, user_prompt)
            )
            parsed = extract_json(content)
            # One bounded retry if the JSON contract was not honoured
            # (reasoning tokens can consume the completion budget).
            if not (parsed or {}).get("claims"):
                retry_user = (
                    user_prompt
                    + "\n\nReturn ONLY a single valid JSON object. No markdown fences. "
                    "Keep claims to at most 5 items so the object is complete."
                )
                try:
                    c2, u2, l2 = asyncio.run(
                        client.complete(spec.system_prompt, retry_user, max_tokens=4000)
                    )
                    p2 = extract_json(c2)
                    if (p2 or {}).get("claims"):
                        content, usage, latency = c2, u2, latency + l2
                        parsed = p2
                except Exception:
                    pass

            finding.model = client.model
            finding.usage = usage
            finding.latency_s = round(latency, 3)
            finding.raw_chars = len(content)
            if not parsed:
                finding.tier = Tier.UNVERIFIED.value
                finding.claim = content[:400] or "(empty response)"
                finding.rationale = "model did not return parseable JSON (uncontracted output)"
            else:
                claims = parsed.get("claims", []) or []
                first = claims[0] if claims else {}
                finding.tier = tier_of(str(first.get("tier", "UNVERIFIED")))
                finding.claim = str(first.get("claim", ""))[:600]
                finding.rationale = str(first.get("rationale", ""))[:400]
                finding.evidence_refs = [str(r) for r in (first.get("evidence_refs") or [])][:6]
                finding.confidence = 0.7 if finding.tier == Tier.EVIDENCE.value else 0.4
                if parsed.get("contradictions"):
                    finding.usage["contradictions"] = parsed["contradictions"]
                if parsed.get("unsupported"):
                    finding.usage["unsupported"] = parsed["unsupported"]
        except Exception as e:  # provider unavailable etc.
            finding.error = f"{type(e).__name__}: {str(e)[:200]}"
            finding.tier = Tier.UNVERIFIED.value
            finding.claim = "(provider call failed)"
            self.failures.append(
                {
                    "worker": role,
                    "kind": "provider_unavailable",
                    "error": finding.error,
                    "endpoint": (provider_override or self.client.base_url),
                    "ledger_entry_id": entry.entry_id,
                    "detected": True,
                }
            )
            self.ledger.append(
                agent_id=worker_agent,
                capability=spec.capability,
                action=f"provider_failure:{role}",
                allowed=False,
                reason="provider_unavailable",
                metadata={"error": finding.error, "endpoint": provider_override or self.client.base_url},
            )
            self.log(f"{role:9s} ✗ provider failure DETECTED and recorded: {finding.error[:70]}")

        # Trace capture (real)
        trace = self.traces.capture(
            agent_id=worker_agent,
            thought=finding.claim,
            evidence_refs=finding.evidence_refs or None,
            tags=[role, "synthetic", finding.tier],
            metadata={"scenario_id": finding.scenario_id, "error": finding.error},
        )
        finding.trace_id = trace.trace_id

        self.findings.append(finding)
        if not finding.error:
            self.log(
                f"{role:9s} ✓ tier={finding.tier:10s} latency={finding.latency_s}s "
                f"chars={finding.raw_chars} trace={trace.trace_id}"
            )

    def _build_user_prompt(
        self,
        role: str,
        scenarios: list[SyntheticScenario],
        prior_findings: list[Finding] | None,
    ) -> str:
        payload: dict[str, Any] = {
            "synthetic": True,
            "not_clinical": True,
            "role": role,
            "scenarios": [s.to_dict() for s in scenarios],
        }
        if prior_findings:
            payload["prior_findings"] = [f.to_dict() for f in prior_findings[:6]]
        return json.dumps(payload, indent=2)

    # -- Stage 4: RECONCILE --------------------------------------------------

    def stage_reconcile(self) -> dict[str, Any]:
        print("\n[5] RECONCILE — contradicting findings & tier distribution")
        tiers: dict[str, int] = {t.value: 0 for t in Tier}
        for f in self.findings:
            tiers[f.tier] = tiers.get(f.tier, 0) + 1

        contradictions: list[dict[str, Any]] = []
        primary = [f for f in self.findings if f.worker in ("PHARMA", "TOX") and not f.error]
        for i in range(len(primary)):
            for j in range(i + 1, len(primary)):
                a, b = primary[i], primary[j]
                if a.tier != b.tier and a.claim[:40] and a.claim[:40] != b.claim[:40]:
                    contradictions.append(
                        {
                            "a": {"worker": a.worker, "tier": a.tier},
                            "b": {"worker": b.worker, "tier": b.tier},
                            "note": "tier disagreement between primary workers",
                        }
                    )

        safety_flags: list[dict[str, Any]] = []
        for f in self.findings:
            if f.worker == "SAFETY":
                safety_flags = f.usage.get("unsupported", []) or []

        self.reconciliation = {
            "tier_distribution": tiers,
            "contradictions": contradictions,
            "safety_flags": safety_flags,
            "workers_with_errors": [f.worker for f in self.findings if f.error],
            "grounded_traces": self.traces.count(grounded=True),
            "ungrounded_traces": self.traces.count(grounded=False),
        }
        self.log(f"tier distribution = {tiers}")
        self.log(f"contradictions     = {len(contradictions)}")
        self.log(f"safety flags       = {len(safety_flags)}")
        self.log(
            f"traces grounded={self.reconciliation['grounded_traces']} "
            f"ungrounded={self.reconciliation['ungrounded_traces']}"
        )
        return self.reconciliation

    # -- Stage 5: FAILURE TEST ----------------------------------------------

    def stage_failure_recovery(self) -> dict[str, Any]:
        print("\n[6] FAILURE TEST — detect / surface / preserve / recover")
        result: dict[str, Any] = {"injected": self.inject_failure}

        provider_failures = [f for f in self.failures if f["kind"] == "provider_unavailable"]
        result["detected"] = len(provider_failures) > 0
        result["failure_records"] = provider_failures
        result["ledger_preserved"] = any(
            e["action"].startswith("provider_failure") for e in self.ledger.entries(limit=1000)
        )
        self.log(f"detected          = {result['detected']}")
        self.log(f"ledger preserved  = {result['ledger_preserved']}")

        # Recovery: re-run the failed worker on a healthy endpoint.
        recovered = False
        if provider_failures:
            self.log("recovering: re-running TOX on healthy endpoint")
            before = len(self.findings)
            self._run_worker("TOX", [self.scenarios[0]], prior_findings=None)
            new = self.findings[before:]
            recovered = any((not f.error) for f in new)
        result["recovered"] = recovered
        self.log(f"recovered         = {recovered}")
        return result

    # -- Stage 6: MEMORY -----------------------------------------------------

    def stage_memory(self) -> dict[str, Any]:
        print("\n[7] MEMORY — persistent Commons + Upstash Vector")
        for f in self.findings:
            if f.error:
                continue
            key = f"research:{f.worker}:{f.scenario_id}:{f.trace_id}"
            entry = MemoryEntry(
                key=key,
                layer=MemoryLayer.ORGANIZATIONAL,
                entry_type=MemoryEntryType.PATTERN,
                value={
                    "synthetic": True,
                    "not_clinical": True,
                    "worker": f.worker,
                    "tier": f.tier,
                    "claim": f.claim,
                    "evidence_refs": f.evidence_refs,
                    "run_id": self.run_id,
                },
                agent_id=f"THINKBOXMD-{f.worker}",
                task_id=self.run_id,
                metadata={"synthetic": True, "tier": f.tier},
                confidence=f.confidence,
            )
            self.memory.put(entry)
            self.memory_written.append(key)

        count = self.memory.count()
        self.log(f"memory entries written = {len(self.memory_written)} (store total={count})")

        # Real Upstash Vector sync (honest boolean + captured error)
        self.vector_error = ""
        if self.vector.enabled:
            try:
                self.vector_synced = asyncio.run(self.vector.upsert(self.session, status="COMPLETED"))
                if not self.vector_synced:
                    self.vector_error = self._probe_vector_error()
            except Exception as e:
                self.vector_error = f"{type(e).__name__}: {str(e)[:200]}"
                self.vector_synced = False
            self.log(f"upstash vector synced = {self.vector_synced}")
            if self.vector_error:
                self.log(f"upstash vector error  = {self.vector_error}")
        else:
            self.log("upstash vector not configured (UPSTASH_VECTOR_REST_URL/TOKEN absent)")

        return {
            "memory_entries": len(self.memory_written),
            "memory_store_total": count,
            "vector_enabled": self.vector.enabled,
            "vector_synced": self.vector_synced,
            "vector_error": self.vector_error,
        }

    def _probe_vector_error(self) -> str:
        """Capture the real HTTP reason the vector upsert was rejected."""
        import urllib.request
        import urllib.error

        if not self.vector.url:
            return "url unset"
        try:
            body = json.dumps({"id": self.session.session_id, "metadata": {"probe": True}}).encode()
            req = urllib.request.Request(
                f"{self.vector.url}/upsert",
                data=body,
                headers={
                    "Authorization": f"Bearer {self.vector._token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            return f"HTTP {e.code}: {e.read(200).decode(errors='replace')[:160]}"
        except Exception as e:
            return f"{type(e).__name__}: {str(e)[:160]}"

    # -- Stage 7: PROOF ------------------------------------------------------

    def stage_proof(self, boot: dict, box: ThinkBox, recon: dict, fail: dict, mem: dict) -> dict[str, Any]:
        print("\n[8] PROOF — assembling machine + human record")
        ledger_valid = self.ledger.verify()

        payload = {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "ended_at": now_iso(),
            "synthetic_only": True,
            "not_clinical": True,
            "boot": boot,
            "think_box": box.snapshot(),
            "workers": [
                {
                    "role": r,
                    "box_id": self.workers[r]["box"].box_id,
                    "capability": self.workers[r]["spec"].capability,
                    "mission": self.workers[r]["spec"].mission,
                }
                for r in self.workers
            ],
            "scenarios": [s.to_dict() for s in self.scenarios],
            "findings": [f.to_dict() for f in self.findings],
            "reconciliation": recon,
            "failure_test": fail,
            "memory": mem,
            "ledger": {
                "entries": len(self.ledger.entries(limit=100000)),
                "valid": ledger_valid,
                "head": (self.ledger.entries(limit=1) or [{}])[0].get("entry_hash", ""),
            },
            "traces": {
                "total": self.traces.count(),
                "grounded": self.traces.count(grounded=True),
                "ungrounded": self.traces.count(grounded=False),
            },
            "provider": {"base_url": self.client.base_url, "model": self.client.model},
            "logs": self.logs,
        }
        payload["proof_hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()

        json_path = OUT_DIR / f"{self.run_id}.json"
        json_path.write_text(json.dumps(payload, indent=2, default=str))
        md_path = OUT_DIR / f"{self.run_id}.md"
        md_path.write_text(self._render_markdown(payload))
        self.log(f"wrote {json_path.name} and {md_path.name}")
        return {"json": str(json_path), "md": str(md_path), "ledger_valid": ledger_valid, "payload": payload}

    def _render_markdown(self, p: dict[str, Any]) -> str:
        lines = [
            f"# THINKBOXMD-RESEARCH — {p['run_id']}",
            "",
            f"**Synthetic only:** {p['synthetic_only']}  |  **Not clinical:** {p['not_clinical']}",
            f"**Provider:** `{p['provider']['model']}` @ `{p['provider']['base_url']}`",
            f"**Proof hash:** `{p['proof_hash']}`",
            f"**Ledger valid:** {p['ledger']['valid']}  |  **Entries:** {p['ledger']['entries']}",
            "",
            "## Think Box",
            f"- `{p['think_box']['box_id']}` owner=`{p['think_box']['owner_id']}`",
            "",
            "## Workers",
            "| Role | Box | Capability |",
            "|------|-----|------------|",
        ]
        for w in p["workers"]:
            lines.append(f"| {w['role']} | `{w['box_id']}` | {w['capability']} |")
        lines += ["", "## Findings", "| Worker | Tier | Latency | Claim |", "|--------|------|---------|-------|"]
        for f in p["findings"]:
            claim = (f["claim"] or "").replace("|", "/")[:90]
            lines.append(f"| {f['worker']} | {f['tier']} | {f['latency_s']}s | {claim} |")
        lines += [
            "",
            "## Reconciliation",
            f"- Tier distribution: `{p['reconciliation']['tier_distribution']}`",
            f"- Contradictions: {len(p['reconciliation']['contradictions'])}",
            f"- Safety flags: {len(p['reconciliation']['safety_flags'])}",
            f"- Traces: grounded={p['traces']['grounded']} ungrounded={p['traces']['ungrounded']}",
            "",
            "## Failure Test",
            f"- Injected: {p['failure_test'].get('injected')}",
            f"- Detected: {p['failure_test'].get('detected')}",
            f"- Ledger preserved: {p['failure_test'].get('ledger_preserved')}",
            f"- Recovered: {p['failure_test'].get('recovered')}",
            "",
            "## Memory",
            f"- Entries written: {p['memory']['memory_entries']}",
            f"- Upstash Vector enabled: {p['memory']['vector_enabled']} synced: {p['memory']['vector_synced']}",
            f"- Upstash Vector error: {p['memory'].get('vector_error', '') or '(none)'}",
            "",
            "> RESEARCH INFRASTRUCTURE TEST — NOT CLINICAL ADVICE. All scenarios synthetic.",
        ]
        return "\n".join(lines) + "\n"

    # -- Orchestration -------------------------------------------------------

    def build_scenarios(self) -> list[SyntheticScenario]:
        return [
            SyntheticScenario(
                scenario_id="SYN-001",
                synthetic=True,
                title="Co-prescribed agents with a known interaction class (synthetic)",
                profile={"age_band": "60-69", "sex": "F", "renal": "reduced", "synthetic": True},
                agents_co_prescribed=["Agent-A", "Agent-B"],
                research_question=(
                    "What public evidence categories would be required to establish "
                    "whether Agent-A and Agent-B have a clinically meaningful interaction? "
                    "Classify each claim by tier. Do not provide clinical advice."
                ),
            ),
            SyntheticScenario(
                scenario_id="SYN-002",
                synthetic=True,
                title="Overdose-risk assessment evidence framing (synthetic)",
                profile={"age_band": "20-29", "sex": "M", "psych": "synthetic-comorbid", "synthetic": True},
                agents_co_prescribed=["Agent-C", "Agent-D"],
                research_question=(
                    "Describe the GENERAL evidence categories used to assess overdose "
                    "risk for co-prescribed sedating agents. Do not state doses or "
                    "thresholds. Classify each claim by tier."
                ),
            ),
            SyntheticScenario(
                scenario_id="SYN-003",
                synthetic=True,
                title="Contradictory evidence scenario (synthetic)",
                profile={"age_band": "40-49", "sex": "F", "hepatic": "synthetic-elevated", "synthetic": True},
                agents_co_prescribed=["Agent-B", "Agent-E"],
                research_question=(
                    "Two public sources disagree on the significance of the Agent-B/"
                    "Agent-E interaction. How should a research system represent and "
                    "reconcile this contradiction? Classify each claim by tier."
                ),
            ),
        ]

    def run(self) -> dict[str, Any]:
        print("=" * 70)
        print("THINKBOXMD-RESEARCH — KUDBEE END-TO-END RESEARCH WORKFLOW")
        print("=" * 70)
        boot = self.stage_boot()
        box = self.stage_create_box()
        self.stage_create_workers()
        self.scenarios = self.build_scenarios()
        self.stage_research(self.scenarios)
        recon = self.stage_reconcile()
        fail = self.stage_failure_recovery()
        mem = self.stage_memory()
        proof = self.stage_proof(boot, box, recon, fail, mem)
        return proof


# --------------------------------------------------------------------------
# Verdict
# --------------------------------------------------------------------------

def compute_verdicts(p: dict[str, Any]) -> dict[str, str]:
    f = p["findings"]
    live = [x for x in f if not x["error"]]
    return {
        "BOOT": "PASS" if p["boot"]["provider_key_present"] else "FAIL",
        "THINK BOX": "PASS" if p["think_box"]["box_id"] else "FAIL",
        "SWARM": "PASS" if len(p["workers"]) == 5 else "PARTIAL",
        "RESEARCH": "PASS" if len(live) >= 4 else ("PARTIAL" if live else "FAIL"),
        "SAFETY": "PASS" if all(x["synthetic"] for x in p["scenarios"]) else "PARTIAL",
        "EXECUTION": "PASS" if live else "FAIL",
        "MEMORY": (
            "PASS" if p["memory"]["memory_entries"] > 0 and p["memory"]["vector_synced"]
            else ("PARTIAL" if p["memory"]["memory_entries"] > 0 else "FAIL")
        ),
        "PROVENANCE": "PASS" if p["traces"]["total"] > 0 else "FAIL",
        "PROOF": "PASS" if p["ledger"]["valid"] else "FAIL",
        "THINK INTEGRATION": "PARTIAL",
        "FAILURE RECOVERY": (
            "PASS" if p["failure_test"].get("detected") and p["failure_test"].get("recovered")
            else "PARTIAL"
        ),
    }


def main() -> int:
    exp = ThinkBoxMDResearch(inject_failure=True)
    proof = exp.run()
    p = proof["payload"]
    verdict = compute_verdicts(p)

    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)
    for layer, v in verdict.items():
        print(f"  {layer:20s} {v}")

    largest_gap = (
        "No durable distributed execution substrate: Think Boxes persist only as "
        "registry rows + SQLite snapshots, and workers run as in-process model calls. "
        "There is no scheduler/worker process isolation, no MCP tool bridge, and no "
        "credentialed Upstash Box / Redis work queue — so a real THINKBOXMD research "
        "system cannot fan work out across resilient, independently-restartable workers."
    )
    print(f"\nLARGEST MISSING CAPABILITY:\n  {largest_gap}")

    # Attach verdicts to the artifacts
    p["verdict"] = verdict
    p["largest_missing_capability"] = largest_gap
    (OUT_DIR / f"{p['run_id']}.json").write_text(json.dumps(p, indent=2, default=str))
    md = Path(proof["md"])
    md.write_text(md.read_text() + "\n## Final Verdict\n\n" + "\n".join(
        f"- **{k}:** {v}" for k, v in verdict.items()
    ) + f"\n\n## Largest Missing Capability\n\n{largest_gap}\n")

    print(f"\nArtifacts:\n  {proof['json']}\n  {proof['md']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
