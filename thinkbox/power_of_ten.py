"""JPL "Power of 10" audit, adapted to Python, with a no-new-violations ratchet.

Holzmann's ten rules (JPL, 2006) were written for safety-critical C. Four
translate directly to Python and are enforced here; the rest are mapped
honestly in RULE_MAP instead of being claimed.

  P1  simple control flow   -> no direct recursion
  P2  bounded loops         -> no `while True:` without a break/return/raise
  P4  short functions       -> no function longer than 60 lines
  P7  check every result    -> no silently swallowed broad exceptions, no bare `except:`

Existing violations are recorded in a baseline. The ratchet fails on any
violation not in the baseline, so the count can only go down.
"""

from __future__ import annotations

import ast
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MAX_FUNCTION_LINES = 60
BROAD_EXCEPTIONS = frozenset({"Exception", "BaseException"})

RULE_MAP: dict[str, str] = {
    "1": "Simple control flow (no goto/setjmp/recursion) -> P1: no direct recursion. "
         "Mutual recursion is not detected.",
    "2": "Fixed upper bound on loops -> P2: `while True:` must contain a break, return or raise.",
    "3": "No dynamic allocation after init -> N/A (Python manages memory).",
    "4": "Functions fit on one page -> P4: at most 60 lines, docstring included.",
    "5": "Two assertions per function -> N/A (asserts are stripped under -O; this repo "
         "raises typed errors instead).",
    "6": "Smallest possible data scope -> N/A (not statically decidable here).",
    "7": "Check return values and parameters -> P7: no silently swallowed broad exceptions, "
         "no bare `except:` (AGENTS.md 2.5).",
    "8": "Limited preprocessor use -> N/A.",
    "9": "Restricted pointer use -> N/A.",
    "10": "All warnings on, static analyzers clean -> covered by ruff/mypy/bandit in CI.",
}


@dataclass(frozen=True)
class Finding:
    """One rule violation at one location."""

    rule: str
    path: str
    qualname: str
    lineno: int
    detail: str

    @property
    def key(self) -> str:
        """Line-independent identity, so unrelated edits don't reshuffle the baseline."""
        return f"{self.rule}|{self.path}|{self.qualname}"


def _exits_loop(loop: ast.While) -> bool:
    """True if the loop body contains a break that belongs to this loop, or
    any return/raise outside nested function or class definitions."""
    stack: list[tuple[ast.AST, bool]] = [(n, True) for n in loop.body]
    while stack:
        node, own_loop = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Break) and own_loop:
            return True
        if isinstance(node, (ast.Return, ast.Raise)):
            return True
        nested = isinstance(node, (ast.For, ast.AsyncFor, ast.While))
        for child in ast.iter_child_nodes(node):
            stack.append((child, own_loop and not nested))
    return False


def _is_constant_true(test: ast.AST) -> bool:
    return isinstance(test, ast.Constant) and bool(test.value) and not isinstance(test.value, str)


def _silent(body: list[ast.stmt]) -> bool:
    """A handler body that does nothing: pass, continue, or `...`."""
    return all(
        isinstance(s, (ast.Pass, ast.Continue))
        or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and s.value.value is Ellipsis)
        for s in body
    )


def _names(node: ast.AST | None) -> set[str]:
    """Exception class names in an except clause; iterative so this module passes its own P1."""
    names: set[str] = set()
    stack = [node] if node is not None else []
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Tuple):
            stack.extend(n.elts)
        elif isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
    return names


class _Auditor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.scope: list[str] = []
        self.findings: list[Finding] = []

    def _add(self, rule: str, node: ast.AST, detail: str) -> None:
        qual = ".".join(self.scope) or "<module>"
        self.findings.append(Finding(rule, self.path, qual, getattr(node, "lineno", 0), detail))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        if length > MAX_FUNCTION_LINES:
            self._add("P4", node, f"{length} lines (max {MAX_FUNCTION_LINES})")
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                f = sub.func
                direct = isinstance(f, ast.Name) and f.id == node.name
                method = (
                    isinstance(f, ast.Attribute) and f.attr == node.name
                    and isinstance(f.value, ast.Name) and f.value.id in {"self", "cls"}
                )
                if direct or method:
                    self._add("P1", sub, f"{node.name} calls itself")
                    break
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_While(self, node: ast.While) -> None:
        if _is_constant_true(node.test) and not _exits_loop(node):
            self._add("P2", node, "while True with no break/return/raise")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self._add("P7", node, "bare except: (also catches KeyboardInterrupt/SystemExit)")
        elif _silent(node.body) and _names(node.type) & BROAD_EXCEPTIONS:
            self._add("P7", node, f"except {', '.join(sorted(_names(node.type)))}: silently swallowed")
        self.generic_visit(node)


def audit_source(source: str, path: str) -> list[Finding]:
    """Audit one file's source. A file that does not parse is itself a finding."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [Finding("PARSE", path, "<module>", exc.lineno or 0, f"does not parse: {exc.msg}")]
    auditor = _Auditor(path)
    auditor.visit(tree)
    return auditor.findings


def audit_tree(root: Path, packages: Iterable[str]) -> list[Finding]:
    """Audit every .py file under ``root/<package>`` for each package."""
    findings: list[Finding] = []
    for package in packages:
        for file in sorted((root / package).rglob("*.py")):
            if "__pycache__" in file.parts:
                continue
            rel = file.relative_to(root).as_posix()
            findings.extend(audit_source(file.read_text(encoding="utf-8", errors="replace"), rel))
    return findings


def baseline_from(findings: list[Finding]) -> dict[str, int]:
    """Counts per line-independent key."""
    return dict(sorted(Counter(f.key for f in findings).items()))


def ratchet(findings: list[Finding], baseline: dict[str, int]) -> dict[str, Any]:
    """Compare against the baseline. ``new`` must be empty to pass.

    ``new`` lists findings beyond the baseline count for their key;
    ``fixed`` lists baseline keys whose count went down (update the baseline
    to lock the improvement in).
    """
    current = Counter(f.key for f in findings)
    new: list[dict[str, Any]] = []
    seen: Counter[str] = Counter()
    for f in findings:
        seen[f.key] += 1
        if seen[f.key] > baseline.get(f.key, 0):
            new.append(asdict(f))
    fixed = {k: v - current.get(k, 0) for k, v in baseline.items() if current.get(k, 0) < v}
    return {"passed": not new, "new": new, "fixed": fixed}


def summarize(findings: list[Finding]) -> dict[str, Any]:
    """Totals per rule and the files with the most findings."""
    by_rule = Counter(f.rule for f in findings)
    by_file = Counter(f.path for f in findings)
    return {
        "total": len(findings),
        "by_rule": dict(sorted(by_rule.items())),
        "top_files": by_file.most_common(10),
        "rule_map": RULE_MAP,
    }


def load_baseline(path: Path) -> dict[str, int]:
    """Read a baseline written by ``write_baseline``."""
    return json.loads(path.read_text(encoding="utf-8"))["counts"]


def write_baseline(path: Path, findings: list[Finding]) -> None:
    """Write the baseline with its per-rule summary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summarize(findings), "counts": baseline_from(findings)}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
