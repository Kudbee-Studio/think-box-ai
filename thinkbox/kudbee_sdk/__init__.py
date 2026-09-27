"""Kudbee SDK — developer surface for the kudbEE web app (PR #177).

Hermetic Python client helpers, config, and lifecycle utilities. Caps at
TEST_VERIFIED until founder-run live proof exists elsewhere in KILO spine.
"""

from thinkbox.kudbee_sdk.cli_mirror import CLI_MIRROR_COMMANDS, list_cli_mirrors
from thinkbox.kudbee_sdk.config import KudbeeSdkConfig, load_config_from_env
from thinkbox.kudbee_sdk.errors import KudbeeSdkError
from thinkbox.kudbee_sdk.http_client import KudbeeHttpClient
from thinkbox.kudbee_sdk.negotiation import SDK_API_VERSION, SDK_VERSION, negotiate
from thinkbox.kudbee_sdk.receipt_bind import ReceiptBindProof, bind_receipt_hermetic

__all__ = (
    "CLI_MIRROR_COMMANDS",
    "KudbeeHttpClient",
    "KudbeeSdkConfig",
    "KudbeeSdkError",
    "ReceiptBindProof",
    "SDK_API_VERSION",
    "SDK_VERSION",
    "bind_receipt_hermetic",
    "list_cli_mirrors",
    "load_config_from_env",
    "negotiate",
)
