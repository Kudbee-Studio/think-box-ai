"""Evaluate each KILO gate once per outermost call.

A gate verdict is a pure read of the repository files and the environment, and each gate is layered on the gates
before it: ``evaluate_X`` runs its prior gates, and ``X_contract_summary`` runs them again. Without sharing, one
``spine_contract_summary()`` executed 376,591 gate functions for 176 distinct ones (``evaluate_env_matrix`` alone
54,426 times) and took about 200 s.

``@evaluated_once`` memoizes a gate function for the duration of the **outermost decorated call only**. The cache is
private to that call and thread, so nothing survives into a later call: a test that patches a module, edits a file or
changes ``os.environ`` between two calls sees fresh evaluations, exactly as before. The key is the function, its
arguments and the whole environment (some helpers read ``os.environ`` directly instead of the ``environ`` argument).
Arguments that cannot be keyed are evaluated directly. Results are copied on the way out, so a caller that edits a
returned dict or list cannot change what later callers in the same call receive.
"""

from __future__ import annotations

import copy
import functools
import os
import threading
from collections.abc import Callable, Mapping
from enum import Enum
from pathlib import PurePath
from typing import Any, TypeVar

__all__ = ("evaluated_once",)

F = TypeVar("F", bound=Callable[..., Any])

_scope = threading.local()


def _key(value: object) -> object:
    """A hashable stand-in for ``value``; ``TypeError`` when there is none."""
    if value is None or isinstance(value, (str, int, float, bool, bytes, Enum, PurePath)):
        return value
    if isinstance(value, Mapping):
        return ("map", tuple(sorted((str(k), _key(v)) for k, v in value.items())))
    if isinstance(value, (list, tuple)):
        return ("seq", tuple(_key(v) for v in value))
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted((_key(v) for v in value), key=repr)))
    raise TypeError(f"unkeyable argument: {type(value).__name__}")


def evaluated_once(fn: F) -> F:
    """Memoize ``fn`` inside the outermost ``@evaluated_once`` call (see the module docstring)."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        cache: dict[object, Any] | None = getattr(_scope, "cache", None)
        owner = cache is None
        if cache is None:
            cache = _scope.cache = {}
        try:
            try:
                key = (fn.__module__, fn.__qualname__, _key(args), _key(kwargs), tuple(sorted(os.environ.items())))
            except TypeError:
                return fn(*args, **kwargs)
            if key in cache:
                return copy.deepcopy(cache[key])
            result = fn(*args, **kwargs)
            try:
                cache[key] = copy.deepcopy(result)
            except (TypeError, copy.Error):
                return result  # a result that cannot be copied is never shared
            return result
        finally:
            if owner:
                _scope.cache = None

    return wrapper  # type: ignore[return-value]
