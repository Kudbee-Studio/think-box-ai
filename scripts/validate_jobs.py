#!/usr/bin/env python3
"""Validate all job files against schema."""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = REPO_ROOT / "jobs"
SCHEMA_PATH = JOBS_DIR / "schema.json"

REQUIRED = ["id", "intent", "hat", "inputs", "plan", "capabilities", "execution", "artifacts", "evaluation"]
VALID_HATS = ["researcher", "runner", "director", "camera", "jury"]
STATES = ["done", "blocked", "queue", "templates"]


def validate_job(path: Path) -> dict:
    result = {"file": str(path.relative_to(REPO_ROOT)), "pass": True, "errors": [], "warnings": []}
    try:
        job = json.loads(path.read_text())
    except Exception as e:
        result["pass"] = False
        result["errors"].append(f"Invalid JSON: {e}")
        return result

    # Check required fields
    for field in REQUIRED:
        if field not in job:
            result["errors"].append(f"Missing required: {field}")
            result["pass"] = False

    # Check hat enum
    if job.get("hat") not in VALID_HATS:
        result["errors"].append(f"Invalid hat: {job.get('hat')}")
        result["pass"] = False

    # Check evaluation.verdict
    ev = job.get("evaluation", {})
    if "verdict" not in ev:
        result["errors"].append("Missing evaluation.verdict")
        result["pass"] = False
    elif ev.get("verdict") not in ["succeeded", "failed", "unproven", "blocked"]:
        result["errors"].append(f"Invalid verdict: {ev.get('verdict')}")
        result["pass"] = False

    # Check id pattern
    if not job.get("id", "").startswith("job_"):
        result["warnings"].append(f"ID doesn't match pattern: {job.get('id')}")

    return result


def main():
    results = []
    for state in STATES:
        state_dir = JOBS_DIR / state
        if not state_dir.is_dir():
            continue
        for job_file in sorted(state_dir.glob("job_*.json")):
            results.append(validate_job(job_file))

    # Write audit
    audit_lines = ["# Schema Audit", ""]
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        audit_lines.append(f"## {r['file']} — {status}")
        if r["errors"]:
            for e in r["errors"]:
                audit_lines.append(f"- ERROR: {e}")
        if r["warnings"]:
            for w in r["warnings"]:
                audit_lines.append(f"- WARN: {w}")
        audit_lines.append("")

    audit_path = REPO_ROOT / "data" / "findings" / "schema_audit.md"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text("\n".join(audit_lines))

    # Summary
    passed = sum(1 for r in results if r["pass"])
    failed = sum(1 for r in results if not r["pass"])
    print(f"Validated {len(results)} files: {passed} pass, {failed} fail")
    print(f"Audit: {audit_path}")

    return results


if __name__ == "__main__":
    main()
