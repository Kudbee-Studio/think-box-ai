"""Mutation testing: does a test suite catch deliberately injected bugs?

Independent verification & validation (IV&V) practice: a passing suite only
proves the code agrees with the tests. Mutation testing measures the tests
themselves. Each mutant is a copy of the module with exactly one small,
realistic bug (a boundary comparison, an arithmetic or boolean operator, a
negation, a flipped boolean constant). The suite "kills" a mutant if at least
one test fails; a surviving mutant is either an untested behavior or an
equivalent mutant (one that cannot change observable behavior). Survivors are
reported with their source line so a human can tell which.

Standard library only. Each mutant runs in its own subprocess, so a mutant
that crashes or loops forever cannot affect the harness or other mutants.
"""

from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_COMPARE_SWAPS: dict[type, type] = {
    ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Lt: ast.LtE, ast.LtE: ast.Lt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}
_BINOP_SWAPS: dict[type, type] = {
    ast.Add: ast.Sub, ast.Sub: ast.Add,
    ast.Mult: ast.Div, ast.Div: ast.Mult,
}
_BOOLOP_SWAPS: dict[type, type] = {ast.And: ast.Or, ast.Or: ast.And}

_SYMBOLS: dict[type, str] = {
    ast.Gt: ">", ast.GtE: ">=", ast.Lt: "<", ast.LtE: "<=", ast.Eq: "==",
    ast.NotEq: "!=", ast.Is: "is", ast.IsNot: "is not", ast.In: "in",
    ast.NotIn: "not in", ast.Add: "+", ast.Sub: "-", ast.Mult: "*",
    ast.Div: "/", ast.And: "and", ast.Or: "or",
}

# Runs inside the subprocess: installs the mutated source under the real
# module name before the test module imports it, then runs the tests.
_RUNNER = r"""
import importlib, os, sys, types, unittest
name, src_path, tests = sys.argv[1], sys.argv[2], sys.argv[3]
pkg, _, leaf = name.rpartition(".")
if pkg:
    importlib.import_module(pkg)
mod = types.ModuleType(name)
mod.__file__ = src_path
mod.__package__ = pkg
sys.modules[name] = mod
if pkg:
    setattr(sys.modules[pkg], leaf, mod)
with open(src_path, encoding="utf-8") as fh:
    exec(compile(fh.read(), src_path, "exec"), mod.__dict__)
suite = unittest.defaultTestLoader.loadTestsFromName(tests)
with open(os.devnull, "w") as sink:
    result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
sys.exit(0 if result.wasSuccessful() and result.testsRun > 0 else 1)
"""


class MutationCampaignError(RuntimeError):
    """The campaign cannot produce a meaningful score (e.g. red baseline)."""


@dataclass(frozen=True)
class Mutant:
    """One single-point change to a module's source."""

    mutant_id: str
    lineno: int
    col: int
    kind: str
    original: str
    replacement: str


def _eligible(tree: ast.AST) -> list[tuple[ast.AST, int, str, str, str]]:
    """Every mutation site, in a deterministic order.

    Returns (node, sub_index, kind, original, replacement) tuples. Order is
    ast.walk order, so the same source always yields the same mutant ids.
    """
    sites: list[tuple[ast.AST, int, str, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                swap = _COMPARE_SWAPS.get(type(op))
                if swap:
                    sites.append((node, i, "compare", _SYMBOLS[type(op)], _SYMBOLS[swap]))
        elif isinstance(node, ast.BinOp):
            swap = _BINOP_SWAPS.get(type(node.op))
            if swap:
                sites.append((node, 0, "arithmetic", _SYMBOLS[type(node.op)], _SYMBOLS[swap]))
        elif isinstance(node, ast.BoolOp):
            swap = _BOOLOP_SWAPS.get(type(node.op))
            if swap:
                sites.append((node, 0, "boolean", _SYMBOLS[type(node.op)], _SYMBOLS[swap]))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            sites.append((node, 0, "negation", "not x", "x"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            sites.append((node, 0, "constant", repr(node.value), repr(not node.value)))
    return sites


def enumerate_mutants(source: str) -> list[Mutant]:
    """List every mutant of ``source``. Deterministic for identical input."""
    tree = ast.parse(source)
    return [
        Mutant(f"m{idx:04d}", getattr(n, "lineno", 0), getattr(n, "col_offset", 0), kind, orig, repl)
        for idx, (n, _sub, kind, orig, repl) in enumerate(_eligible(tree))
    ]


class _Unnot(ast.NodeTransformer):
    def __init__(self, target: ast.AST) -> None:
        self.target = target

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        return node.operand if node is self.target else node


def apply_mutant(source: str, mutant: Mutant) -> str:
    """Return ``source`` with exactly ``mutant`` applied."""
    tree = ast.parse(source)
    sites = _eligible(tree)
    index = int(mutant.mutant_id[1:])
    if index >= len(sites):
        raise MutationCampaignError(f"{mutant.mutant_id} does not exist in this source")
    node, sub, kind, _orig, _repl = sites[index]
    if kind == "compare":
        node.ops[sub] = _COMPARE_SWAPS[type(node.ops[sub])]()
    elif kind == "arithmetic":
        node.op = _BINOP_SWAPS[type(node.op)]()
    elif kind == "boolean":
        node.op = _BOOLOP_SWAPS[type(node.op)]()
    elif kind == "negation":
        tree = _Unnot(node).visit(tree)
    elif kind == "constant":
        node.value = not node.value
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _run_suite(module_name: str, source: str, test_module: str, root: Path, timeout: float) -> str:
    """Run ``test_module`` against ``source`` installed as ``module_name``.

    Returns "survived" (all tests passed), "killed", or "timeout".
    """
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(source)
        path = fh.name
    env = {**os.environ, "PYTHONPATH": str(root) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _RUNNER, module_name, path, test_module],
            cwd=str(root), env=env, capture_output=True, timeout=timeout,
        )
        return "survived" if proc.returncode == 0 else "killed"
    except subprocess.TimeoutExpired:
        return "timeout"
    finally:
        os.unlink(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_campaign(
    module_path: Path,
    module_name: str,
    test_module: str,
    root: Path,
    *,
    timeout: float = 60.0,
    workers: int | None = None,
) -> dict[str, Any]:
    """Mutate every site in ``module_path`` and run ``test_module`` per mutant.

    Raises MutationCampaignError if the unmutated module does not pass its
    own tests: a mutation score on a red baseline would be meaningless.
    A mutant that times out (e.g. an injected infinite loop) counts as
    killed, since a real run would be stopped by the same timeout.
    """
    source = module_path.read_text(encoding="utf-8")
    baseline = _run_suite(module_name, source, test_module, root, timeout)
    if baseline != "survived":
        raise MutationCampaignError(
            f"baseline {baseline}: {test_module} does not pass against unmutated {module_name}"
        )
    mutants = enumerate_mutants(source)
    lines = source.splitlines()

    def one(m: Mutant) -> tuple[Mutant, str]:
        return m, _run_suite(module_name, apply_mutant(source, m), test_module, root, timeout)

    with ThreadPoolExecutor(max_workers=workers or os.cpu_count() or 2) as pool:
        outcomes = list(pool.map(one, mutants))

    killed = sum(1 for _, o in outcomes if o == "killed")
    timeouts = sum(1 for _, o in outcomes if o == "timeout")
    survivors = [
        {**asdict(m), "line": lines[m.lineno - 1].strip() if 0 < m.lineno <= len(lines) else ""}
        for m, o in outcomes if o == "survived"
    ]
    total = len(mutants)
    test_file = root / (test_module.replace(".", "/") + ".py")
    return {
        "module": module_name,
        "module_sha256": _sha256(module_path),
        "tests": test_module,
        "tests_sha256": _sha256(test_file) if test_file.is_file() else None,
        "total": total,
        "killed": killed + timeouts,
        "killed_by_timeout": timeouts,
        "survived": len(survivors),
        "score": round((killed + timeouts) / total, 4) if total else None,
        "survivors": survivors,
        "evidence_level": "MEASURED",
        "note": (
            "A survivor is an untested behavior or an equivalent mutant. "
            "Each needs a human verdict; the score alone does not decide."
        ),
    }
