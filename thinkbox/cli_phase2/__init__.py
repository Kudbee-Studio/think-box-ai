"""KUDBEECLI Phase 2 toolkit — hermetic CLI deepen (PR #178).

Caps at TEST_VERIFIED; no live provider calls from this package.
"""

from thinkbox.cli_phase2.config import CliToolkitConfig, load_config_from_env
from thinkbox.cli_phase2.errors import CliToolkitError
from thinkbox.cli_phase2.http_client import CliHttpClient
from thinkbox.cli_phase2.negotiation import CLI_API_VERSION, CLI_PHASE2_VERSION, negotiate
from thinkbox.cli_phase2.receipt_bind import ReceiptBindProof, bind_receipt_hermetic

__all__ = (
    "CliHttpClient",
    "CliToolkitConfig",
    "CliToolkitError",
    "ReceiptBindProof",
    "CLI_API_VERSION",
    "CLI_PHASE2_VERSION",
    "bind_receipt_hermetic",
    "load_config_from_env",
    "negotiate",
)
