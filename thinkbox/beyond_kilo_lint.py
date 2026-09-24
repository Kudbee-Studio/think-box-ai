"""Beyond-KILO lint primitives: ruff, mypy, bandit (PR #170, hermetic).

Scoped to gate modules so the readiness lane stays honest without rewriting history.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from thinkbox.kilo_hermetic_subprocess import run_bounded_command
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "BEYOND_KILO_LINT_LABEL",
    "BEYOND_KILO_LINT_VERSION",
    "LINT_SCOPE_REL_PATHS",
    "LintToolResult",
    "LintViolation",
    "beyond_kilo_lint_contract_snippet",
    "detect_lint_tool",
    "execute_beyond_kilo_lint_suite",
    "lint_execution_enabled",
    "lint_tools_required",
    "pyproject_lint_sections_present",
    "validate_lint_scope_paths",
)

BEYOND_KILO_LINT_LABEL = "beyond-kilo-lint-readiness"
BEYOND_KILO_LINT_VERSION = "2"

# PR #174 wave 1: spine + hermetic helpers (25 modules). Manifest:
# data/kilo_beyond_kilo_lint/wave1_scope.json
LINT_SCOPE_REL_PATHS: tuple[str, ...] = (
    "thinkbox/beyond_kilo_lint.py",
    "thinkbox/kilo_beyond_kilo_lint.py",
    "thinkbox/kilo_hermetic_subprocess.py",
    "thinkbox/kilo_hermetic_gate_memo.py",
    "thinkbox/kilo_live_proof_readiness.py",
    "thinkbox/kilo_env_matrix.py",
    "thinkbox/kilo_substrate_checklist.py",
    "thinkbox/kilo_governance_evidence.py",
    "thinkbox/kilo_mercury_hermetic.py",
    "thinkbox/kilo_swarm_instrumentation.py",
    "thinkbox/kilo_proof_schema.py",
    "thinkbox/kilo_dashboard_slots.py",
    "thinkbox/kilo_live_proof_exec.py",
    "thinkbox/kilo_post_season_harden.py",
    "thinkbox/kilo_live_smoke_evidence.py",
    "thinkbox/kilo_live_smoke_operator.py",
    "thinkbox/kilo_control_plane_api.py",
    "thinkbox/kilo_receipt_chain_etag.py",
    "thinkbox/kilo_governance_evidence_live_proof_readiness.py",
    "thinkbox/kilo_control_plane_e2e_deepen.py",
    "thinkbox/kilo_end_link_deepen.py",
    "thinkbox/kilo_api_ops_harden.py",
    "thinkbox/kilo_pr172_ci_spine_trust.py",
    "thinkbox/kilo_pr173_chronicle_honesty.py",
    "thinkbox/kilo_pr174_lint_scope_wave1.py",
)

_LINT_TIMEOUT_SECONDS = 120
_TRUTHY = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class LintViolation:
    code: str
    message: str
    tool: str | None = None


@dataclass(frozen=True)
class LintToolResult:
    tool: str
    ok: bool
    skipped: bool
    returncode: int
    detail: str


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY


def lint_tools_required(environ: Mapping[str, str]) -> bool:
    """Fail closed on missing linters when CI or explicit operator ack is set."""
    if _is_truthy(environ.get("CI")):
        return True
    if _is_truthy(environ.get("KILO_BEYOND_KILO_LINT_REQUIRE_TOOLS")):
        return True
    return False


def lint_execution_enabled(environ: Mapping[str, str]) -> bool:
    """Run ruff/mypy/bandit subprocesses (verify script / explicit operator only)."""
    if _is_truthy(environ.get("KILO_BEYOND_KILO_LINT_EXECUTE")):
        return True
    return False


def detect_lint_tool(name: str) -> str | None:
    """Resolve a lint CLI on PATH (no network)."""
    return shutil.which(name)


def validate_lint_scope_paths(repo_root: Path | None = None) -> list[LintViolation]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[LintViolation] = []
    for rel in LINT_SCOPE_REL_PATHS:
        if not (root / rel).is_file():
            violations.append(
                LintViolation(code="scope_missing", message=rel, tool="scope"),
            )
    return violations


def pyproject_lint_sections_present(repo_root: Path | None = None) -> tuple[bool, list[str]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    path = root / "pyproject.toml"
    missing: list[str] = []
    if not path.is_file():
        return False, ["pyproject.toml"]
    text = path.read_text(encoding="utf-8")
    for marker in ("[tool.ruff]", "[tool.mypy]", "[tool.bandit]"):
        if marker not in text:
            missing.append(marker)
    return len(missing) == 0, missing


def beyond_kilo_lint_contract_snippet() -> dict[str, object]:
    return {
        "label": BEYOND_KILO_LINT_LABEL,
        "version": BEYOND_KILO_LINT_VERSION,
        "scope_paths": list(LINT_SCOPE_REL_PATHS),
        "tools": ("ruff", "mypy", "bandit"),
        "four_state_max": "TEST_VERIFIED",
        "live_verified": False,
        "live_api_called": False,
    }


def _scope_args(repo_root: Path) -> list[str]:
    return [str(repo_root / rel) for rel in LINT_SCOPE_REL_PATHS]


def _redact_lint_output(text: str, max_len: int = 400) -> str:
    trimmed = text.strip().replace("\r\n", "\n")
    if len(trimmed) <= max_len:
        return trimmed
    return trimmed[: max_len - 3] + "..."


def _run_tool(
    cmd: Sequence[str],
    *,
    repo_root: Path,
    tool: str,
) -> LintToolResult:
    result = run_bounded_command(cmd, cwd=repo_root, timeout_seconds=_LINT_TIMEOUT_SECONDS)
    ok = result.returncode == 0 and not result.timed_out
    detail_parts = []
    if result.timed_out:
        detail_parts.append("timed_out")
    if result.stdout:
        detail_parts.append(_redact_lint_output(result.stdout))
    if result.stderr:
        detail_parts.append(_redact_lint_output(result.stderr))
    detail = "; ".join(detail_parts) if detail_parts else "ok"
    return LintToolResult(
        tool=tool,
        ok=ok,
        skipped=False,
        returncode=result.returncode,
        detail=detail,
    )


def _ruff_check(repo_root: Path) -> LintToolResult:
    exe = detect_lint_tool("ruff")
    if exe is None:
        return LintToolResult(tool="ruff", ok=False, skipped=True, returncode=127, detail="missing")
    paths = _scope_args(repo_root)
    check = _run_tool([exe, "check", *paths], repo_root=repo_root, tool="ruff")
    if not check.ok:
        return check
    fmt = _run_tool(
        [exe, "format", "--check", *paths],
        repo_root=repo_root,
        tool="ruff-format",
    )
    return LintToolResult(
        tool="ruff",
        ok=fmt.ok,
        skipped=False,
        returncode=fmt.returncode,
        detail=fmt.detail if not fmt.ok else check.detail,
    )


def _mypy_check(repo_root: Path) -> LintToolResult:
    exe = detect_lint_tool("mypy")
    if exe is None:
        return LintToolResult(tool="mypy", ok=False, skipped=True, returncode=127, detail="missing")
    paths = _scope_args(repo_root)
    return _run_tool(
        [exe, "--follow-imports=skip", *paths],
        repo_root=repo_root,
        tool="mypy",
    )


def _bandit_check(repo_root: Path) -> LintToolResult:
    exe = detect_lint_tool("bandit")
    if exe is None:
        return LintToolResult(
            tool="bandit",
            ok=False,
            skipped=True,
            returncode=127,
            detail="missing",
        )
    paths = _scope_args(repo_root)
    config = repo_root / "pyproject.toml"
    cmd = [exe, "-q", "-r", *paths, "-c", str(config)]
    return _run_tool(cmd, repo_root=repo_root, tool="bandit")


def execute_beyond_kilo_lint_suite(
    environ: Mapping[str, str],
    repo_root: Path | None = None,
) -> tuple[list[LintToolResult], list[LintViolation]]:
    """Run scoped linters when execution is enabled; otherwise return empty runs."""
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[LintViolation] = []
    results: list[LintToolResult] = []

    if not lint_execution_enabled(environ):
        return results, violations

    require = lint_tools_required(environ)
    for runner in (_ruff_check, _mypy_check, _bandit_check):
        tool_result = runner(root)
        results.append(tool_result)
        if tool_result.skipped:
            if require:
                violations.append(
                    LintViolation(
                        code="tool_missing",
                        message=tool_result.tool,
                        tool=tool_result.tool,
                    ),
                )
            continue
        if not tool_result.ok:
            violations.append(
                LintViolation(
                    code="tool_failed",
                    message=tool_result.detail,
                    tool=tool_result.tool,
                ),
            )

    return results, violations


def lint_results_to_json(results: Sequence[LintToolResult]) -> list[dict[str, object]]:
    return [
        {
            "tool": r.tool,
            "ok": r.ok,
            "skipped": r.skipped,
            "returncode": r.returncode,
            "detail": r.detail,
        }
        for r in results
    ]


if __name__ == "__main__":  # pragma: no cover
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["KILO_BEYOND_KILO_LINT_EXECUTE"] = "1"
    runs, viols = execute_beyond_kilo_lint_suite(env)
    print(json.dumps({"results": lint_results_to_json(runs), "violations": len(viols)}, indent=2))
    sys.exit(0 if not viols else 1)
