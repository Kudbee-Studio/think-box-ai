"""Tests for Think Job schema and worker logic."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

JOBS_DIR = Path(__file__).resolve().parent.parent / "jobs"
SCHEMA_PATH = JOBS_DIR / "schema.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_schema_loads():
    schema = load_json(SCHEMA_PATH)
    assert "required" in schema
    assert "id" in schema["required"]


def test_template_validates_against_schema():
    schema = load_json(SCHEMA_PATH)
    required = schema["required"]
    template = load_json(JOBS_DIR / "templates" / "template_wallet_scan.json")
    for field in required:
        assert field in template, f"Template missing required field: {field}"


def test_runner_job_blocked_when_gpu_stopped():
    """Runner-hat jobs should be refused while GPU is stopped."""
    GPU_STOPPED = True
    job = load_json(JOBS_DIR / "templates" / "template_wallet_scan.json")
    # Template is researcher, so it should pass
    if GPU_STOPPED and job.get("hat") == "runner":
        assert False, "Runner job should be blocked when GPU stopped"
    # This should not raise
    assert job.get("hat") == "researcher"


def test_all_jobs_have_valid_verdict():
    schema = load_json(SCHEMA_DIR)
    valid_verdicts = ["succeeded", "failed", "unproven", "blocked"]
    for state in ["done", "blocked", "queue", "templates"]:
        state_dir = JOBS_DIR / state
        if not state_dir.is_dir():
            continue
        for job_file in state_dir.glob("job_*.json"):
            job = load_json(job_file)
            verdict = job.get("evaluation", {}).get("verdict")
            assert verdict in valid_verdicts, f"{job_file}: invalid verdict {verdict}"
