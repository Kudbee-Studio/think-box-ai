"""Think Token core logic."""

from __future__ import annotations

SYMBOL = "THNK"
NAME = "Think Token"
DECIMALS = 18
TOTAL_SUPPLY = 1_000_000_000  # 1 billion tokens


class ThinkToken:
    """Represents a Think Token balance for an account."""

    def __init__(self, address: str, balance: int = 0) -> None:
        if not isinstance(balance, int) or isinstance(balance, bool):
            raise TypeError("Balance must be an integer.")
        if balance < 0:
            raise ValueError("Balance must be non-negative.")
        self.address = address
        self._balance = balance

    @property
    def balance(self) -> int:
        return self._balance

    def transfer(self, recipient: "ThinkToken", amount: int) -> None:
        """Transfer *amount* tokens to *recipient*."""
        if amount <= 0:
            raise ValueError("Transfer amount must be positive.")
        if amount > self._balance:
            raise ValueError("Insufficient balance.")
        self._balance -= amount
        recipient._balance += amount

    def __repr__(self) -> str:
        return f"ThinkToken(address={self.address!r}, balance={self._balance})"
