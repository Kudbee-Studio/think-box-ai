"""Backend remote-execution policy + admission token-capability enforcement (pure / hermetic)."""

from __future__ import annotations

import unittest

from thinkbox.admission import AdmissionGate
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.governed_job_execution import (
    GovernedJobExecutionError,
    execute_governed_job_command,
)
from thinkbox.identity import IdentityLedger
from thinkbox.remote_exec_policy import (
    ALLOWED_READONLY_COMMANDS,
    POLICY_ID,
    command_fingerprint,
    evaluate,
    policy_metadata,
)
from thinkbox.remote_exec_policy import (
    CAPABILITY_UPCLOUD_SSH_READONLY as CAP,
)

FORBIDDEN = [
    "hostname; id", "hostname && id", "hostname || id", "hostname | cat", "hostname > /tmp/x", "hostname >> /tmp/x",
    "hostname < /etc/passwd", "$(id)", "`id`", "hostname $(id)", "echo hi", "id", "cat /etc/shadow", "ls /root",
    "rm -rf /", "sudo hostname", "su -c id", "bash -c hostname", "sh -c hostname", "/bin/sh", "python3 -c 'print(1)'",
    "curl http://example.com", "wget http://example.com", "./script.sh", "hostname -I", "uname -r", "df -h", "df -h / ;",
    " hostname", "hostname ", "HOSTNAME", "hostname\n", "hostname\nid", "uptime &", "", "free -m -t",
]


class TestPolicy(unittest.TestCase):
    def test_all_six_allowed_commands(self) -> None:
        self.assertEqual(ALLOWED_READONLY_COMMANDS, {"hostname", "uname -a", "uptime", "whoami", "df -h /", "free -m"})
        for cmd in ALLOWED_READONLY_COMMANDS:
            self.assertTrue(evaluate(capability=CAP, execution_substrate="upcloud-ssh", exec_command=cmd).allowed, cmd)

    def test_forbidden_commands(self) -> None:
        for cmd in FORBIDDEN:
            d = evaluate(capability=CAP, execution_substrate="upcloud-ssh", exec_command=cmd)
            self.assertFalse(d.allowed, repr(cmd))
            self.assertEqual(d.reason, "command_not_allowed")

    def test_capability_bound_to_upcloud_ssh_only(self) -> None:
        for sub in ("local", "upstash-box", "", "UPCLOUD-SSH-X"):
            self.assertEqual(evaluate(capability=CAP, execution_substrate=sub, exec_command="hostname").reason,
                             "capability_substrate_mismatch", sub)

    def test_upcloud_ssh_requires_the_narrow_capability(self) -> None:
        for cap in ("goal:execute", "goal:execute:verified", "", "shell:upcloud-ssh", "shell:upcloud-ssh:readonly "):
            d = evaluate(capability=cap.strip() if cap.endswith(" ") else cap, execution_substrate="upcloud-ssh", exec_command="hostname")
            if cap.strip() == CAP:
                self.assertTrue(d.allowed)
            else:
                self.assertEqual(d.reason, "substrate_requires_capability", cap)

    def test_other_substrates_untouched(self) -> None:
        self.assertTrue(evaluate(capability="goal:execute", execution_substrate="local", exec_command="echo x").allowed)
        self.assertTrue(evaluate(capability="goal:execute", execution_substrate="", exec_command="").allowed)

    def test_metadata_is_non_secret_and_deterministic(self) -> None:
        m = policy_metadata(capability=CAP, execution_substrate="upcloud-ssh", exec_command="hostname")
        self.assertEqual(m["policy_id"], POLICY_ID)
        self.assertEqual(m["command_fingerprint"], command_fingerprint("hostname"))
        self.assertEqual(len(m["command_fingerprint"]), 16)
        self.assertEqual(set(m), {"policy_id", "policy_version", "capability", "execution_substrate", "command_fingerprint"})

    def test_lowest_layer_refuses_forbidden_upcloud_commands_before_any_adapter(self) -> None:
        for cmd in ("hostname; id", "rm -rf /", "echo x"):
            with self.assertRaises(GovernedJobExecutionError) as ctx:
                execute_governed_job_command(substrate="upcloud-ssh", job_id="j", command=cmd)
            self.assertEqual(ctx.exception.code, "command_not_allowed")


class TestAdmissionTokenCapability(unittest.TestCase):
    def setUp(self) -> None:
        self.tokens = GovernanceTokenService(signing_key="k")
        self.ids = IdentityLedger()
        self.gate = AdmissionGate(self.tokens, self.ids)
        self.ids.register(agent_id="a", capabilities=["goal:execute", CAP])

    def _tok(self, caps, agent="a"):
        return self.tokens.issue(TokenRequest(agent_id=agent, capabilities=caps, ttl_seconds=60)).token_value

    def test_scoped_token_cannot_exercise_other_identity_capabilities(self) -> None:
        t = self._tok([CAP])
        self.assertTrue(self.gate.authorize(t, "a", CAP).allowed)
        d = self.gate.authorize(t, "a", "goal:execute")
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "token_capability_not_granted")

    def test_identity_must_also_hold_capability(self) -> None:
        t = self._tok(["goal:execute:verified"])
        self.assertEqual(self.gate.authorize(t, "a", "goal:execute:verified").reason, "capability_not_granted")

    def test_wrong_agent_and_invalid_token(self) -> None:
        t = self._tok([CAP])
        self.assertEqual(self.gate.authorize(t, "b", CAP).reason, "token_agent_mismatch")
        self.assertEqual(self.gate.authorize("forged", "a", CAP).reason, "token_invalid_or_expired")


if __name__ == "__main__":
    unittest.main()
