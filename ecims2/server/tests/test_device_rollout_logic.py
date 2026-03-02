from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.licensing_core.policy import DeviceEnforcementRollout, PolicyLoadResult, SecurityPolicy
from app.licensing_core.policy_state import set_policy_state
from app.services.device_control_state_service import DeviceControlStateService
from app.services.device_policy_service import DevicePolicyService


class TestDeviceRolloutLogic(unittest.TestCase):

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        os.environ["ECIMS_DB_PATH"] = str(Path(self._td.name) / "db.sqlite")
        from app.core.config import get_settings
        from app.db.database import init_db

        get_settings.cache_clear()
        init_db()
        from app.db.database import get_db

        with get_db() as conn:
            conn.execute("INSERT INTO agents(name, hostname, token, registered_at, last_seen, status) VALUES('a1','h1','t',datetime('now'),datetime('now'),'ONLINE')")

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("ECIMS_DB_PATH", None)
        from app.core.config import get_settings

        get_settings.cache_clear()
    def _policy(self, rollout: DeviceEnforcementRollout, *, kill=False):
        return SecurityPolicy(
            mode="STRICT",
            allow_key_override=False,
            grace_days=0,
            status_redaction_level=1,
            allow_unsigned_dev=False,
            mtls_required=True,
            pinning_required=True,
            allow_tls12=False,
            allow_plain_https=False,
            mass_storage_default_action="block_on_insert",
            usb_allowlist=[],
            temporary_allow_duration_minutes=10,
            escalation_threshold=3,
            device_enforcement_mode="enforce",
            mass_storage_offline_behavior="block",
            allow_token_required_for_unblock=True,
            allow_token_max_duration_minutes=240,
            local_event_queue_retention_hours=24,
            token_public_key_path="x",
            device_enforcement_rollout=rollout,
            device_kill_switch=kill,
            per_agent_override_allowed=True,
            enforcement_grace_seconds=0,
        )

    def test_kill_switch_allows(self):
        set_policy_state(PolicyLoadResult(policy=self._policy(DeviceEnforcementRollout(), kill=True), source="signed", reason="OK"))
        d = DevicePolicyService.evaluate_usb_mass_storage(vid="a", pid="b", serial=None, agent_id=1)
        self.assertEqual(d.reason, "KILL_SWITCH")

    def test_percent_rollout_deterministic(self):
        p = self._policy(DeviceEnforcementRollout(strategy="percent", percent=0))
        set_policy_state(PolicyLoadResult(policy=p, source="signed", reason="OK"))
        d = DevicePolicyService.evaluate_usb_mass_storage(vid="a", pid="b", serial=None, agent_id=1)
        self.assertEqual(d.reason, "ROLLOUT_OBSERVE")

    def test_state_kill_switch_overrides(self):
        p = self._policy(DeviceEnforcementRollout(strategy="all", percent=100))
        set_policy_state(PolicyLoadResult(policy=p, source="signed", reason="OK"))
        DeviceControlStateService.set_kill_switch(True)
        d = DevicePolicyService.evaluate_usb_mass_storage(vid="a", pid="b", serial=None, agent_id=1)
        self.assertEqual(d.reason, "KILL_SWITCH")
        DeviceControlStateService.set_kill_switch(False)


if __name__ == "__main__":
    unittest.main()
