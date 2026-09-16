"""CNC manufacturing commands."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from thinkbox.cnc import (
    CNCJob,
    CNCManufacturingEngine,
    DemoMode,
    ManufacturingMemory,
    Material,
    MachineProfile,
    Operation,
    ProofStore,
    SafetyGateStore,
    TenantStore,
    Tool,
    ValidationResult,
)
from thinkbox.replay import ReplayDriver

from ..ui.colors import bold, cyan, dim, green, red, yellow
from ..utils.output import is_json_mode, output_json

CNC_DIR = Path("data/cnc")
JOBS_DIR = CNC_DIR / "jobs"
PROOF_DIR = CNC_DIR / "proofs"
MEMORY_DIR = CNC_DIR / "memory"
SAFETY_DIR = CNC_DIR / "safety"
TENANT_DIR = CNC_DIR / "tenants"


def _ensure_dirs() -> None:
    CNC_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    SAFETY_DIR.mkdir(parents=True, exist_ok=True)
    TENANT_DIR.mkdir(parents=True, exist_ok=True)


def _load_jobs() -> list[dict]:
    _ensure_dirs()
    jobs = []
    for f in sorted(JOBS_DIR.glob("*.json")):
        try:
            jobs.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, ValueError):
            continue
    return jobs


def _save_job(job_data: dict) -> None:
    _ensure_dirs()
    f = JOBS_DIR / f"{job_data['job_id']}.json"
    f.write_text(json.dumps(job_data, indent=2, default=str))


def _load_memory() -> dict:
    mem_file = MEMORY_DIR / "manufacturing_memory.json"
    if mem_file.exists():
        try:
            return json.loads(mem_file.read_text())
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _save_memory(data: dict) -> None:
    _ensure_dirs()
    mem_file = MEMORY_DIR / "manufacturing_memory.json"
    mem_file.write_text(json.dumps(data, indent=2, default=str))


def _handle_cnc(args) -> None:
    sub = getattr(args, "cnc_command", None)
    if sub == "job":
        _handle_cnc_job(args)
    elif sub == "demo":
        _handle_cnc_demo(args)
    elif sub == "memory":
        _handle_cnc_memory(args)
    elif sub == "proof":
        _handle_cnc_proof(args)
    elif sub == "safety":
        _handle_cnc_safety(args)
    elif sub == "tenant":
        _handle_cnc_tenant(args)
    elif sub == "replay":
        _handle_cnc_replay(args)
    elif sub == "dashboard":
        _handle_cnc_dashboard(args)
    elif sub == "engine":
        _handle_cnc_engine(args)
    else:
        print(red("Unknown CNC subcommand"))


def _handle_cnc_job(args) -> None:
    job_sub = getattr(args, "job_command", None)

    if job_sub == "list":
        jobs = _load_jobs()
        if is_json_mode():
            output_json(jobs)
            return
        if not jobs:
            print(yellow("  No CNC jobs found"))
            return
        print(bold(f"\n  CNC Jobs ({len(jobs)})"))
        print(dim("  " + "─" * 70))
        for j in jobs:
            status = j.get("status", "unknown")
            print(f"  {cyan(j['job_id'][:12])}  {status:10s}  {j.get('part_name', 'N/A')}")

    elif job_sub == "show":
        jobs = _load_jobs()
        job = next((j for j in jobs if j["job_id"].startswith(args.job_id)), None)
        if not job:
            print(red(f"  Job {args.job_id} not found"))
            return
        if is_json_mode():
            output_json(job)
            return
        print(bold(f"\n  Job: {job['job_id']}"))
        print(dim("  " + "─" * 50))
        for k, v in job.items():
            if k == "operations" and isinstance(v, list):
                print(f"  {yellow(k)}: {len(v)} operations")
            elif isinstance(v, (dict, list)):
                print(f"  {yellow(k)}: {json.dumps(v, indent=2)[:200]}")
            else:
                print(f"  {yellow(k)}: {v}")

    elif job_sub == "create":
        _ensure_dirs()
        job_id = f"cnc-{uuid.uuid4().hex[:8]}"
        material = Material(name=args.material or "6061-T6 Aluminum", grade=args.material_grade or "6061-T6", stock_size=args.stock_size or "100x100x10", stock_units=args.stock_units or "mm")
        machine = MachineProfile(name=args.machine or "HAAS VF-2SS", control_system=args.control_system or "Fanuc", spindle_speed_rpm=args.spindle_speed or 8000, travel_x_mm=args.travel_x or 300, travel_y_mm=args.travel_y or 250, travel_z_mm=args.travel_z or 200)
        tool = Tool(name=args.tool or "End Mill 10mm", tool_type=args.tool_type or "end_mill", diameter_mm=args.tool_diameter or 10.0, flute_count=args.flute_count or 2, material="Carbide")
        operation = Operation(operation_id="op-1", operation_type=args.operation_type or "milling", tool=tool, spindle_speed_rpm=args.spindle_speed or 8000, feed_rate_mm_min=args.feed_rate or 200, depth_of_cut_mm=args.depth_of_cut or 2.0, description=args.description or "Roughing pass")
        job = CNCJob(job_id=job_id, part_name=args.part_name or "Untitled Part", part_number=args.part_number or "PN-001", material=material, machine=machine, operations=[operation], customer_id=getattr(args, "customer_id", "default"), priority=getattr(args, "priority", "normal"))
        job_data = job.model_dump()
        _save_job(job_data)
        if is_json_mode():
            output_json(job_data)
        else:
            print(green(f"  Created CNC job: {job_id}"))
            print(f"  Part: {job.part_name}")
            print(f"  Machine: {machine.name}")
            print(f"  Material: {material.name}")

    elif job_sub == "validate":
        jobs = _load_jobs()
        job = next((j for j in jobs if j["job_id"].startswith(args.job_id)), None)
        if not job:
            print(red(f"  Job {args.job_id} not found"))
            return
        engine = CNCManufacturingEngine()
        result = engine.validate_job(job)
        if is_json_mode():
            output_json(result.model_dump())
        else:
            print(bold(f"\n  Validation: {job['job_id']}"))
            print(f"  Valid: {result.is_valid}")
            if result.errors:
                for e in result.errors:
                    print(f"  {red('ERROR')}: {e}")
            if result.warnings:
                for w in result.warnings:
                    print(f"  {yellow('WARN')}: {w}")

    elif job_sub == "approve":
        jobs = _load_jobs()
        job = next((j for j in jobs if j["job_id"].startswith(args.job_id)), None)
        if not job:
            print(red(f"  Job {args.job_id} not found"))
            return
        gate = SafetyGateStore()
        approval = gate.approve(job_id=job["job_id"], approver_id=args.approver or "operator", reason=args.reason or "Approved for production")
        if is_json_mode():
            output_json(approval.model_dump())
        else:
            print(green(f"  Approved job {job['job_id']}"))
            print(f"  Approved by: {approval.approver_id}")
            print(f"  Reason: {approval.reason}")

    elif job_sub == "execute":
        jobs = _load_jobs()
        job = next((j for j in jobs if j["job_id"].startswith(args.job_id)), None)
        if not job:
            print(red(f"  Job {args.job_id} not found"))
            return
        engine = CNCManufacturingEngine()
        result = engine.execute_job(job)
        if is_json_mode():
            output_json(result)
        else:
            print(bold(f"\n  Execution: {job['job_id']}"))
            print(f"  Status: {result.get('status', 'unknown')}")

    else:
        print(red("Unknown CNC job subcommand. Use: list, show, create, validate, approve, execute"))


def _handle_cnc_demo(args) -> None:
    demo = DemoMode()
    result = demo.run()
    if is_json_mode():
        output_json(result.model_dump())
    else:
        print(bold("\n  CNC Manufacturing Demo"))
        print(dim("  " + "─" * 50))
        print(f"  Job: {result.job.part_name}")
        print(f"  Status: {result.status}")
        print(f"  Duration: {result.duration_seconds:.1f}s")
        print(f"  Evidence Labels: {', '.join(result.evidence_labels)}")
        print(f"  ROI: ${result.roi_stats.total_savings_avoided:,.0f}/year")


def _handle_cnc_memory(args) -> None:
    mem_sub = getattr(args, "memory_command", None)
    memory = ManufacturingMemory()

    if mem_sub == "store":
        memory.store_knowledge(knowledge_type=args.type or "lesson", content=args.content or "", source_job_id=args.job_id or "", confidence=args.confidence or 0.8)
        _save_memory(memory.to_dict())
        print(green(f"  Stored knowledge: {args.type}"))

    elif mem_sub == "recall":
        results = memory.recall(args.query or "")
        if is_json_mode():
            output_json([r.model_dump() for r in results])
        else:
            print(bold(f"\n  Recall: {args.query}"))
            for r in results:
                print(f"  {cyan(r.knowledge_type)}: {r.content[:80]}...")

    elif mem_sub == "list":
        data = _load_memory()
        if is_json_mode():
            output_json(data)
        else:
            print(bold("\n  Manufacturing Memory"))
            for k, v in data.items():
                print(f"  {yellow(k)}: {str(v)[:80]}")

    else:
        print(red("Unknown CNC memory subcommand. Use: store, recall, list"))


def _handle_cnc_proof(args) -> None:
    proof_sub = getattr(args, "proof_command", None)
    store = ProofStore()

    if proof_sub == "list":
        proofs = _load_jobs()  # use jobs as proof data
        if is_json_mode():
            output_json(proofs)
        else:
            print(bold(f"\n  Proof Packages ({len(proofs)})"))
            for p in proofs:
                print(f"  {cyan(p['job_id'][:12])}  {p.get('part_name', 'N/A')}")

    elif proof_sub == "show":
        jobs = _load_jobs()
        proof = next((p for p in jobs if p["job_id"].startswith(args.proof_id)), None)
        if not proof:
            print(red(f"  Proof {args.proof_id} not found"))
            return
        if is_json_mode():
            output_json(proof)
        else:
            print(bold(f"\n  Proof: {proof['job_id']}"))

    else:
        print(red("Unknown CNC proof subcommand. Use: list, show"))


def _handle_cnc_safety(args) -> None:
    safety_sub = getattr(args, "safety_command", None)
    store = SafetyGateStore()

    if safety_sub == "list":
        gates = store.list_gates()
        if is_json_mode():
            output_json([g.model_dump() for g in gates])
        else:
            print(bold(f"\n  Safety Gates ({len(gates)})"))
            for g in gates:
                print(f"  {cyan(g.gate_id[:12])}  {g.status.value}  {g.job_id}")

    elif safety_sub == "check":
        jobs = _load_jobs()
        job = next((j for j in jobs if j["job_id"].startswith(args.job_id)), None)
        if not job:
            print(red(f"  Job {args.job_id} not found"))
            return
        gate = SafetyGate(job_id=job["job_id"], requires_approval=True)
        safe = gate.check_safety()
        if is_json_mode():
            output_json(safe.model_dump())
        else:
            print(bold(f"\n  Safety Check: {job['job_id']}"))
            print(f"  Safe: {safe.is_safe}")

    elif safety_sub == "emergency":
        store.emergency_stop(args.job_id or "all")
        print(yellow("  Emergency stop activated"))

    else:
        print(red("Unknown CNC safety subcommand. Use: list, check, emergency"))


def _handle_cnc_tenant(args) -> None:
    tenant_sub = getattr(args, "tenant_command", None)
    store = TenantStore()

    if tenant_sub == "list":
        tenants = store.list_tenants()
        if is_json_mode():
            output_json([t.model_dump() for t in tenants])
        else:
            print(bold(f"\n  Tenants ({len(tenants)})"))
            for t in tenants:
                print(f"  {cyan(t.tenant_id[:12])}  {t.name}")

    elif tenant_sub == "create":
        tenant = store.create_tenant(name=args.name, domain=args.domain or "", plan=args.plan or "professional", max_jobs=args.max_jobs or 100)
        if is_json_mode():
            output_json(tenant.model_dump())
        else:
            print(green(f"  Created tenant: {tenant.tenant_id}"))

    elif tenant_sub == "access":
        tenant = store.get_tenant(args.tenant_id)
        if not tenant:
            print(red(f"  Tenant {args.tenant_id} not found"))
            return
        if is_json_mode():
            output_json(tenant.model_dump())
        else:
            print(bold(f"\n  Tenant: {tenant.name}"))
            print(f"  Plan: {tenant.plan}")
            print(f"  Max Jobs: {tenant.max_jobs}")

    else:
        print(red("Unknown CNC tenant subcommand. Use: list, create, access"))


def _handle_cnc_replay(args) -> None:
    replay_sub = getattr(args, "replay_command", None)
    driver = ReplayDriver()

    if replay_sub == "list":
        jobs = _load_jobs()
        if is_json_mode():
            output_json(jobs)
        else:
            print(bold(f"\n  Replayable Jobs ({len(jobs)})"))
            for j in jobs:
                print(f"  {cyan(j['job_id'][:12])}  {j.get('part_name', 'N/A')}")

    elif replay_sub == "run":
        jobs = _load_jobs()
        job = next((j for j in jobs if j["job_id"].startswith(args.job_id)), None)
        if not job:
            print(red(f"  Job {args.job_id} not found"))
            return
        result = driver.run(job)
        if is_json_mode():
            output_json(result.model_dump())
        else:
            print(bold(f"\n  Replay: {job['job_id']}"))
            print(f"  Status: {result.status}")
            print(f"  Matches: {result.matches}")

    else:
        print(red("Unknown CNC replay subcommand. Use: list, run"))


def _handle_cnc_dashboard(args) -> None:
    from thinkbox.cnc import ROIDashboard
    dashboard = ROIDashboard()
    stats = dashboard.compute_stats()
    if is_json_mode():
        output_json(stats.model_dump())
    else:
        print(bold("\n  CNC ROI Dashboard"))
        print(dim("  " + "─" * 50))
        print(f"  Programming Hours Avoided: {stats.programming_hours_avoided}")
        print(f"  Total Savings: ${stats.total_savings_avoided:,.0f}/year")


def _handle_cnc_engine(args) -> None:
    engine_sub = getattr(args, "engine_command", None)
    engine = CNCManufacturingEngine()

    if engine_sub == "status":
        stats = engine.get_stats()
        if is_json_mode():
            output_json(stats)
        else:
            print(bold("\n  CNC Engine Status"))
            for k, v in stats.items():
                print(f"  {yellow(k)}: {v}")

    elif engine_sub == "validate":
        jobs = _load_jobs()
        if not jobs:
            print(red("  No jobs to validate"))
            return
        for job_data in jobs:
            result = engine.validate_job(job_data)
            print(f"  {job_data['job_id']}: valid={result.is_valid}, errors={len(result.errors)}")

    else:
        print(red("Unknown CNC engine subcommand. Use: status, validate"))


def register_cnc(subparsers) -> None:
    cnc_p = subparsers.add_parser("cnc", help="CNC manufacturing commands")
    cnc_sub = cnc_p.add_subparsers(dest="cnc_command")

    job_p = cnc_sub.add_parser("job", help="CNC job management")
    job_sub = job_p.add_subparsers(dest="job_command")
    job_sub.add_parser("list", help="List CNC jobs")
    job_show = job_sub.add_parser("show", help="Show job details")
    job_show.add_argument("job_id")
    job_create = job_sub.add_parser("create", help="Create a CNC job")
    job_create.add_argument("--part-name", default="Untitled Part")
    job_create.add_argument("--part-number", default="PN-001")
    job_create.add_argument("--material", default="6061-T6 Aluminum")
    job_create.add_argument("--material-grade", default="6061-T6")
    job_create.add_argument("--stock-size", default="100x100x10")
    job_create.add_argument("--stock-units", default="mm")
    job_create.add_argument("--machine", default="HAAS VF-2SS")
    job_create.add_argument("--control-system", default="Fanuc")
    job_create.add_argument("--spindle-speed", type=int, default=8000)
    job_create.add_argument("--travel-x", type=int, default=300)
    job_create.add_argument("--travel-y", type=int, default=250)
    job_create.add_argument("--travel-z", type=int, default=200)
    job_create.add_argument("--tool", default="End Mill 10mm")
    job_create.add_argument("--tool-type", default="end_mill")
    job_create.add_argument("--tool-diameter", type=float, default=10.0)
    job_create.add_argument("--flute-count", type=int, default=2)
    job_create.add_argument("--operation-type", default="milling")
    job_create.add_argument("--feed-rate", type=int, default=200)
    job_create.add_argument("--depth-of-cut", type=float, default=2.0)
    job_create.add_argument("--description", default="Roughing pass")
    job_create.add_argument("--customer-id", default="default")
    job_create.add_argument("--priority", default="normal")
    job_validate = job_sub.add_parser("validate", help="Validate a job")
    job_validate.add_argument("job_id")
    job_approve = job_sub.add_parser("approve", help="Approve a job")
    job_approve.add_argument("job_id")
    job_approve.add_argument("--approver", default="operator")
    job_approve.add_argument("--reason", default="Approved for production")
    job_execute = job_sub.add_parser("execute", help="Execute a job")
    job_execute.add_argument("job_id")

    cnc_sub.add_parser("demo", help="Run CNC manufacturing demo")

    mem_p = cnc_sub.add_parser("memory", help="Manufacturing memory")
    mem_sub = mem_p.add_subparsers(dest="memory_command")
    mem_store = mem_sub.add_parser("store", help="Store knowledge")
    mem_store.add_argument("--type", default="lesson")
    mem_store.add_argument("--content", default="")
    mem_store.add_argument("--job-id", default="")
    mem_store.add_argument("--confidence", type=float, default=0.8)
    mem_recall = mem_sub.add_parser("recall", help="Recall knowledge")
    mem_recall.add_argument("query", nargs="?")
    mem_list = mem_sub.add_parser("list", help="List memory")

    proof_p = cnc_sub.add_parser("proof", help="Proof packages")
    proof_sub = proof_p.add_subparsers(dest="proof_command")
    proof_sub.add_parser("list", help="List proofs")
    proof_show = proof_sub.add_parser("show", help="Show proof")
    proof_show.add_argument("proof_id")

    safety_p = cnc_sub.add_parser("safety", help="Safety gates")
    safety_sub = safety_p.add_subparsers(dest="safety_command")
    safety_sub.add_parser("list", help="List safety gates")
    safety_check = safety_sub.add_parser("check", help="Check safety")
    safety_check.add_argument("job_id")
    safety_emergency = safety_sub.add_parser("emergency", help="Emergency stop")
    safety_emergency.add_argument("job_id", nargs="?")

    tenant_p = cnc_sub.add_parser("tenant", help="Tenant management")
    tenant_sub = tenant_p.add_subparsers(dest="tenant_command")
    tenant_sub.add_parser("list", help="List tenants")
    tenant_create = tenant_sub.add_parser("create", help="Create tenant")
    tenant_create.add_argument("--name", required=True)
    tenant_create.add_argument("--domain", default="")
    tenant_create.add_argument("--plan", default="professional")
    tenant_create.add_argument("--max-jobs", type=int, default=100)
    tenant_access = tenant_sub.add_parser("access", help="View tenant")
    tenant_access.add_argument("tenant_id")

    replay_p = cnc_sub.add_parser("replay", help="Replay jobs")
    replay_sub = replay_p.add_subparsers(dest="replay_command")
    replay_sub.add_parser("list", help="List replayable jobs")
    replay_run = replay_sub.add_parser("run", help="Run replay")
    replay_run.add_argument("job_id")

    cnc_sub.add_parser("dashboard", help="Show ROI dashboard")

    engine_p = cnc_sub.add_parser("engine", help="CNC engine")
    engine_sub = engine_p.add_subparsers(dest="engine_command")
    engine_sub.add_parser("status", help="Engine status")
    engine_validate = engine_sub.add_parser("validate", help="Validate all jobs")
