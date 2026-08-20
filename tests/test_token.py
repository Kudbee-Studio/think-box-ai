"""Tests for the Think Token core logic."""

import pytest
from think_box_ai.token import ThinkToken, SYMBOL, NAME, DECIMALS, TOTAL_SUPPLY


def test_constants():
    assert SYMBOL == "THNK"
    assert NAME == "Think Token"
    assert DECIMALS == 18
    assert TOTAL_SUPPLY == 1_000_000_000


def test_initial_balance():
    account = ThinkToken("0xABC", balance=500)
    assert account.balance == 500


def test_transfer_success():
    sender = ThinkToken("0xSENDER", balance=1000)
    receiver = ThinkToken("0xRECEIVER", balance=0)
    sender.transfer(receiver, 400)
    assert sender.balance == 600
    assert receiver.balance == 400


def test_transfer_insufficient_balance():
    sender = ThinkToken("0xSENDER", balance=100)
    receiver = ThinkToken("0xRECEIVER", balance=0)
    with pytest.raises(ValueError, match="Insufficient balance"):
        sender.transfer(receiver, 200)


def test_transfer_non_positive_amount():
    sender = ThinkToken("0xSENDER", balance=100)
    receiver = ThinkToken("0xRECEIVER", balance=0)
    with pytest.raises(ValueError, match="positive"):
        sender.transfer(receiver, 0)


def test_repr():
    account = ThinkToken("0xABC", balance=42)
    assert "0xABC" in repr(account)
    assert "42" in repr(account)
