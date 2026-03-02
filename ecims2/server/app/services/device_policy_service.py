from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.db.database import get_db
from app.licensing_core.policy import USBAllowlistEntry
from app.licensing_core.policy_state import get_policy_state
from app.services.device_control_state_service import DeviceControlStateService


@dataclass
class DeviceDecision:
    action: str
    reason: str
    temporary_allow_minutes: int | None = None


class DevicePolicyService:
    @staticmethod
    def evaluate_usb_mass_storage(*, vid: str, pid: str, serial: str | None, prior_blocks: int = 0, agent_id: int | None = None) -> DeviceDecision:
        state = get_policy_state()
        policy = state.policy

        if policy.device_kill_switch or DeviceControlStateService.get_kill_switch():
            return DeviceDecision(action="ALLOW", reason="KILL_SWITCH")

        if agent_id is not None and not DevicePolicyService._is_agent_enforcing(agent_id):
            return DeviceDecision(action="ALLOW", reason="ROLLOUT_OBSERVE")

        normalized_vid = vid.strip().lower()
        normalized_pid = pid.strip().lower()
        normalized_serial = serial.strip() if serial else None

        if DevicePolicyService._matches_allowlist(policy.usb_allowlist, normalized_vid, normalized_pid, normalized_serial):
            return DeviceDecision(action="ALLOW", reason="ALLOWLIST_MATCH")

        if policy.mass_storage_default_action == "allow":
            return DeviceDecision(action="ALLOW", reason="DEFAULT_ALLOW")

        if prior_blocks >= policy.escalation_threshold:
            return DeviceDecision(action="TEMP_ALLOW", reason="ESCALATION_THRESHOLD_REACHED", temporary_allow_minutes=policy.temporary_allow_duration_minutes)

        return DeviceDecision(action="BLOCK", reason="DEFAULT_BLOCK_ON_INSERT")

    @staticmethod
    def _is_agent_enforcing(agent_id: int) -> bool:
        policy = get_policy_state().policy
        with get_db() as conn:
            row = conn.execute("SELECT device_mode_override, device_tags FROM agents WHERE id = ?", (agent_id,)).fetchone()
            if not row:
                return False
            override = (row["device_mode_override"] or "").strip().lower()
            if policy.per_agent_override_allowed and override in {"observe", "enforce"}:
                return override == "enforce"

            rollout = policy.device_enforcement_rollout
            if rollout.strategy == "all":
                return True
            if rollout.strategy == "allowlist_agents":
                return agent_id in set(rollout.allowlist_agents)
            if rollout.strategy == "percent":
                bucket = int(hashlib.sha256(f"agent:{agent_id}".encode()).hexdigest(), 16) % 100
                return bucket < rollout.percent
            if rollout.strategy == "tags":
                tags = {x.strip() for x in str(row["device_tags"] or "").split(",") if x.strip()}
                return bool(tags.intersection(set(rollout.tags)))
            return False

    @staticmethod
    def rollout_counters() -> dict[str, int]:
        kill = DeviceControlStateService.get_kill_switch() or get_policy_state().policy.device_kill_switch
        with get_db() as conn:
            rows = conn.execute("SELECT id FROM agents").fetchall()
        eligible = len(rows)
        enforcing = sum(1 for r in rows if DevicePolicyService._is_agent_enforcing(int(r["id"])))
        observing = eligible - enforcing
        return {"eligible": eligible, "enforcing": enforcing, "observing": observing, "killed": eligible if kill else 0}

    @staticmethod
    def _matches_allowlist(allowlist: list[USBAllowlistEntry], vid: str, pid: str, serial: str | None) -> bool:
        for entry in allowlist:
            if entry.vid != vid or entry.pid != pid:
                continue
            if entry.serial and entry.serial != (serial or ""):
                continue
            return True
        return False
