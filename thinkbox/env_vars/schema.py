"""Typed env field schema (PR #200)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
class EnvValueKind(str, Enum):
    STRING = "string"
    BOOL = "bool"
    INT = "int"
    URL = "url"


@dataclass(frozen=True)
class EnvField:
    """One environment variable in the THINK BOX schema."""

    key: str
    kind: EnvValueKind
    required: bool = False
    sensitive: bool = False
    description: str = ""
    pattern: re.Pattern[str] | None = None
    default: str | None = None
