"""Dynamic Token Whip Protocol for ThinkBox AI.

Implements a soft-cap token management system with deterministic syntax
expansion and leader escalation for high-quality task completion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from thinkbox.session import get_current_session, sync_session
from backend.audit_storage import record_audit

STANDARD_TOKEN_ALLOWANCE = 500
MAX_TOKEN_CEILING = 600
WHIP_EXTENSION = 75
COMPLETION_DENSITY_THRESHOLD = 0.9

TOKEN_CHAR_RATIO = 4


class WhipDecision(str, Enum):
    AUTO_GRANTED = "AUTO_GRANTED"
    LEADER_APPROVED = "LEADER_APPROVED"
    DENIED_TRUNCATED = "DENIED_TRUNCATED"
    WITHIN_BUDGET = "WITHIN_BUDGET"


class WhipEvaluationState(str, Enum):
    PENDING = "PENDING"
    SYNTAX_CHECK = "SYNTAX_CHECK"
    LEADER_ESCALATION = "LEADER_ESCALATION"
    COMPLETED = "COMPLETED"


@dataclass
class WhipReceipt:
    task_id: str
    original_tokens: int
    final_tokens: int
    decision: WhipDecision
    state: WhipEvaluationState
    extension_granted: int = 0
    reason: str = ""
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "original_tokens": self.original_tokens,
            "final_tokens": self.final_tokens,
            "decision": self.decision.value,
            "state": self.state.value,
            "extension_granted": self.extension_granted,
            "reason": self.reason,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


def estimate_tokens(text: str) -> int:
    return len(text) // TOKEN_CHAR_RATIO + 1


def has_unclosed_brackets(text: str) -> bool:
    stack = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {")", "]", "}"}

    in_string = False
    string_char = None
    i = 0
    while i < len(text):
        ch = text[i]

        if in_string:
            if ch == string_char and (i == 0 or text[i - 1] != "\\"):
                in_string = False
            i += 1
            continue

        if ch in ("'", '"', "`"):
            in_string = True
            string_char = ch
            i += 1
            continue

        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in closing:
            if not stack or stack[-1] != ch:
                return True
            stack.pop()

        i += 1

    return len(stack) > 0


def has_incomplete_diff_hunk(text: str) -> bool:
    lines = text.split("\n")
    in_hunk = False

    for line in lines:
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            in_hunk = True
        elif line.startswith("@@") and in_hunk:
            hunk_match = re.match(r"@@ -\d+(,\d+)? \+\d+(,\d+)? @@", line)
            if not hunk_match:
                return True
            in_hunk = False

    if in_hunk:
        return True

    if re.search(r"@@ -\d+(,\d+)? \+\d+(,\d+)? @@", text):
        last_hunk = text.rfind("@@")
        remaining = text[last_hunk:]
        if remaining.strip().endswith("@@"):
            return True

    return False


def has_unclosed_code_block(text: str) -> bool:
    code_fence_count = text.count("```")
    if code_fence_count % 2 != 0:
        return True

    indent_stack = []
    for line in text.split("\n"):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        indent = len(line) - len(stripped)

        if indent_stack and indent < indent_stack[-1]:
            while indent_stack and indent < indent_stack[-1]:
                indent_stack.pop()

        if stripped.endswith(":"):
            indent_stack.append(indent + 4)

    return False


def calculate_completion_density(text: str) -> float:
    lines = [l for l in text.strip().split("\n") if l.strip()]
    if not lines:
        return 0.0

    complete_lines = 0
    for line in lines:
        stripped = line.strip()
        if stripped.endswith(("}", ")", "]", ";", ":", ",", ".", "pass", "return", "break", "continue")):
            complete_lines += 1
        elif stripped.startswith(("def ", "class ", "import ", "from ", "if ", "for ", "while ")):
            complete_lines += 1
        elif "=" in stripped and not stripped.endswith("="):
            complete_lines += 1
        elif stripped.startswith(("#", "//", "/*", "*")):
            complete_lines += 1

    return complete_lines / len(lines)


class TokenWhipProtocol:
    def __init__(
        self,
        standard_allowance: int = STANDARD_TOKEN_ALLOWANCE,
        max_ceiling: int = MAX_TOKEN_CEILING,
        extension: int = WHIP_EXTENSION,
        completion_threshold: float = COMPLETION_DENSITY_THRESHOLD,
    ):
        self.standard_allowance = standard_allowance
        self.max_ceiling = max_ceiling
        self.extension = extension
        self.completion_threshold = completion_threshold
        self._receipts: list[WhipReceipt] = []

    @property
    def receipts(self) -> list[WhipReceipt]:
        return self._receipts.copy()

    def evaluate(self, task_id: str, output: str) -> tuple[str, WhipReceipt]:
        token_count = estimate_tokens(output)
        session = get_current_session()
        session_id = session.session_id if session else ""

        if token_count <= self.standard_allowance:
            receipt = WhipReceipt(
                task_id=task_id,
                original_tokens=token_count,
                final_tokens=token_count,
                decision=WhipDecision.WITHIN_BUDGET,
                state=WhipEvaluationState.COMPLETED,
                reason="Output within standard 500-token allowance",
                session_id=session_id,
            )
            self._receipts.append(receipt)
            return output, receipt

        if token_count > self.max_ceiling:
            truncated = output[: self.max_ceiling * TOKEN_CHAR_RATIO]
            receipt = WhipReceipt(
                task_id=task_id,
                original_tokens=token_count,
                final_tokens=estimate_tokens(truncated),
                decision=WhipDecision.DENIED_TRUNCATED,
                state=WhipEvaluationState.COMPLETED,
                reason=f"Output exceeds {self.max_ceiling}-token ceiling, truncated",
                session_id=session_id,
            )
            self._receipts.append(receipt)
            return truncated, receipt

        syntax_issue = self._check_syntax_issues(output)
        if syntax_issue:
            extension = min(self.extension, self.max_ceiling - token_count)
            extended_output = output[: (token_count + extension) * TOKEN_CHAR_RATIO]
            receipt = WhipReceipt(
                task_id=task_id,
                original_tokens=token_count,
                final_tokens=estimate_tokens(extended_output),
                decision=WhipDecision.AUTO_GRANTED,
                state=WhipEvaluationState.COMPLETED,
                extension_granted=extension,
                reason=f"Syntax extension granted: {syntax_issue}",
                session_id=session_id,
                metadata={"syntax_issue": syntax_issue},
            )
            self._receipts.append(receipt)
            return extended_output, receipt

        density = calculate_completion_density(output)
        if density >= self.completion_threshold:
            receipt = WhipReceipt(
                task_id=task_id,
                original_tokens=token_count,
                final_tokens=token_count,
                decision=WhipDecision.LEADER_APPROVED,
                state=WhipEvaluationState.COMPLETED,
                reason=f"Leader approved: {density:.1%} completion density",
                session_id=session_id,
                metadata={"completion_density": density},
            )
            self._receipts.append(receipt)
            return output, receipt

        receipt = WhipReceipt(
            task_id=task_id,
            original_tokens=token_count,
            final_tokens=self.standard_allowance,
            decision=WhipDecision.DENIED_TRUNCATED,
            state=WhipEvaluationState.COMPLETED,
            reason=f"Leader rejected: {density:.1%} completion density below {self.completion_threshold:.0%} threshold",
            session_id=session_id,
            metadata={"completion_density": density},
        )
        self._receipts.append(receipt)
        return output[: self.standard_allowance * TOKEN_CHAR_RATIO], receipt

    def _check_syntax_issues(self, output: str) -> str | None:
        if has_unclosed_brackets(output):
            return "unclosed bracket detected"
        if has_incomplete_diff_hunk(output):
            return "incomplete diff hunk"
        if has_unclosed_code_block(output):
            return "unclosed code block"
        return None

    def record_to_audit(self, receipt: WhipReceipt) -> None:
        record_audit(
            action="whip_evaluation",
            actor="TokenWhipProtocol",
            outcome=receipt.decision.value,
            metadata=receipt.to_dict(),
            session_id=receipt.session_id,
        )
