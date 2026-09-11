"""Tests for the Think Token core logic."""

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
    try:
        sender.transfer(receiver, 200)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Insufficient balance" in str(e)


def test_transfer_non_positive_amount():
    sender = ThinkToken("0xSENDER", balance=100)
    receiver = ThinkToken("0xRECEIVER", balance=0)
    try:
        sender.transfer(receiver, 0)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "amount must be positive" in str(e)


def test_repr():
    account = ThinkToken("0xABC", balance=42)
    repr_str = repr(account)
    assert "0xABC" in repr_str
    assert "42" in repr_str


if __name__ == "__main__":
    test_constants()
    test_initial_balance()
    test_transfer_success()
    test_transfer_insufficient_balance()
    test_transfer_non_positive_amount()
    test_repr()
    print("All token tests passed!")
