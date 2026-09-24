"""Hermetic receipt-chain deepen toolkit (PR #182)."""

from thinkbox.receipt_chain_deepen.append import HermeticReceiptChain, append_receipt
from thinkbox.receipt_chain_deepen.deepen_status_report import receipt_chain_deepen_status_report
from thinkbox.receipt_chain_deepen.errors import ReceiptChainDeepenError
from thinkbox.receipt_chain_deepen.negotiation import RECEIPT_CHAIN_DEEPEN_VERSION

__all__ = (
    "HermeticReceiptChain",
    "ReceiptChainDeepenError",
    "RECEIPT_CHAIN_DEEPEN_VERSION",
    "append_receipt",
    "receipt_chain_deepen_status_report",
)
