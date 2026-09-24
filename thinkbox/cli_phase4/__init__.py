"""KUDBEECLI Phase 4 toolkit — hermetic CLI deepen after Phase 2 (PR #196).

Caps at TEST_VERIFIED; no live provider calls from this package.
"""

from thinkbox.cli_phase4.config import CliPhase4Config, load_phase4_config_from_env
from thinkbox.cli_phase4.errors import CliPhase4Error
from thinkbox.cli_phase4.exit_codes import CLI_PHASE4_EXIT_CONTRACT
from thinkbox.cli_phase4.formatters import OutputFormat, emit_formatted
from thinkbox.cli_phase4.negotiation import CLI_PHASE4_VERSION, negotiate_phase4
from thinkbox.cli_phase4.profile import CliProfile, resolve_active_profile

__all__ = (
    "CLI_PHASE4_EXIT_CONTRACT",
    "CLI_PHASE4_VERSION",
    "CliPhase4Config",
    "CliPhase4Error",
    "CliProfile",
    "OutputFormat",
    "emit_formatted",
    "load_phase4_config_from_env",
    "negotiate_phase4",
    "resolve_active_profile",
)
