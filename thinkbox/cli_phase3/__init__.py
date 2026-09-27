"""KUDBEECLI Phase 3 toolkit — hermetic CLI deepen after Phase 2 (PR #180).

Caps at TEST_VERIFIED; no live provider calls from this package.
"""

from thinkbox.cli_phase3.config import CliPhase3Config, load_phase3_config_from_env
from thinkbox.cli_phase3.errors import CliPhase3Error
from thinkbox.cli_phase3.exit_codes import CLI_PHASE3_EXIT_CONTRACT
from thinkbox.cli_phase3.formatters import OutputFormat, emit_formatted
from thinkbox.cli_phase3.negotiation import CLI_PHASE3_VERSION, negotiate_phase3
from thinkbox.cli_phase3.profile import CliProfile, resolve_active_profile

__all__ = (
    "CLI_PHASE3_EXIT_CONTRACT",
    "CLI_PHASE3_VERSION",
    "CliPhase3Config",
    "CliPhase3Error",
    "CliProfile",
    "OutputFormat",
    "emit_formatted",
    "load_phase3_config_from_env",
    "negotiate_phase3",
    "resolve_active_profile",
)
