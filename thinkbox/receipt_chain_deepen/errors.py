"""Structured errors for receipt-chain deepen (PR #182 F02)."""

from __future__ import annotations


class ReceiptChainDeepenError(Exception):
    """Fail-closed receipt-chain deepen error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
