"""Process-local memo for hermetic gate evaluations (PR #169 nesting guard).

One evaluate per gate_id + environ fingerprint per process unless cleared.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TypeVar

_T = TypeVar("_T")

_MEMO: dict[tuple[str, str], object] = {}


def environ_fingerprint(environ: Mapping[str, str]) -> str:
    """Stable fingerprint for hermetic gate cache keys."""
    return repr(tuple(sorted(environ.items())))


def memoized_hermetic_check(
    gate_id: str,
    environ: Mapping[str, str],
    evaluate: Callable[[], _T],
) -> _T:
    """Return cached hermetic result for gate_id + environ fingerprint."""
    key = (gate_id, environ_fingerprint(environ))
    cached = _MEMO.get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    result = evaluate()
    _MEMO[key] = result
    return result


def clear_hermetic_gate_memo() -> None:
    """Clear memo (tests only)."""
    _MEMO.clear()
