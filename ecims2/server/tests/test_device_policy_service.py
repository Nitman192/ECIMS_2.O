from __future__ import annotations

import unittest

from app.licensing_core.policy import SecurityPolicy, USBAllowlistEntry
from app.licensing_core.policy_state import set_policy_state
from app.services.device_policy_service import DevicePolicyService


class TestDevicePolicyService(unittest.TestCase):
    def _set_policy(
        self,
        *,
        default_action: str = "block_on_insert",
        allowlist: list[USBAllowlistEntry] | None = None,
        temp_minutes: int = 45,
        escalation_threshold: int = 3,
    ) -> None:
        policy = SecurityPolicy(
            mode="STRICT",
            allow_key_override=False,
            grace_days=0,
            status_redaction_level=1,
            allow_unsigned_dev=False,
            mtls_required=True,
            pinning_required=True,
            allow_tls12=False,
            allow_plain_https=False,
            mass_storage_default_action=default_action,
            usb_allowlist=allowlist or [],
            temporary_allow_duration_minutes=temp_minutes,
            escalation_threshold=escalation_threshold,
        )
        from app.licensing_core.policy import PolicyLoadResult

        set_policy_state(PolicyLoadResult(policy=policy, source="signed", reason="OK"))

    def test_allowlist_match_allows(self) -> None:
        self._set_policy(allowlist=[USBAllowlistEntry(vid="abcd", pid="1234", serial=None)])
        decision = DevicePolicyService.evaluate_usb_mass_storage(vid="ABCD", pid="1234", serial="anything")
        self.assertEqual(decision.action, "ALLOW")
        self.assertEqual(decision.reason, "ALLOWLIST_MATCH")

    def test_default_allow_policy(self) -> None:
        self._set_policy(default_action="allow")
        decision = DevicePolicyService.evaluate_usb_mass_storage(vid="ffff", pid="eeee", serial=None)
        self.assertEqual(decision.action, "ALLOW")
        self.assertEqual(decision.reason, "DEFAULT_ALLOW")

    def test_default_block_without_escalation(self) -> None:
        self._set_policy(default_action="block_on_insert", escalation_threshold=3)
        decision = DevicePolicyService.evaluate_usb_mass_storage(vid="ffff", pid="eeee", serial=None, prior_blocks=1)
        self.assertEqual(decision.action, "BLOCK")

    def test_escalation_returns_temp_allow(self) -> None:
        self._set_policy(default_action="block_on_insert", escalation_threshold=2, temp_minutes=30)
        decision = DevicePolicyService.evaluate_usb_mass_storage(vid="ffff", pid="eeee", serial=None, prior_blocks=2)
        self.assertEqual(decision.action, "TEMP_ALLOW")
        self.assertEqual(decision.temporary_allow_minutes, 30)


if __name__ == "__main__":
    unittest.main()
