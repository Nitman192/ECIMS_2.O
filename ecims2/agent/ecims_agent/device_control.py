from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from ecims_agent.alarm import trigger_mass_storage_block_alarm
from ecims_agent.api_client import ApiClient
from ecims_agent.device_adapter import USBDevice
from ecims_agent.offline_store import (
    load_event_queue,
    load_tokens,
    load_used_allow_tokens,
    save_event_queue,
    save_tokens,
    save_used_allow_tokens,
)

logger = logging.getLogger(__name__)


def _b64d(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _parse_expiry_utc(raw: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _verify_token_offline(token: str, public_key_path: str) -> dict[str, Any] | None:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _b64d(payload_b64)
        sig = _b64d(sig_b64)
        public_key = serialization.load_pem_public_key(Path(public_key_path).read_bytes())
        public_key.verify(
            sig,
            payload,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        claims = json.loads(payload.decode("utf-8"))
        expires_at = _parse_expiry_utc(str(claims.get("expires_at", "")))
        if not expires_at or datetime.now(timezone.utc) > expires_at:
            return None
        return claims
    except Exception:
        return None


class DeviceControlManager:
    def __init__(
        self,
        *,
        enforcement_mode: str,
        failsafe_offline_minutes: int,
        token_public_key_path: str,
        local_event_queue_retention_hours: int,
        enforcement_grace_seconds: int = 0,
    ):
        self.enforcement_mode = enforcement_mode
        self.failsafe_offline_minutes = failsafe_offline_minutes
        self.token_public_key_path = token_public_key_path
        self.local_event_queue_retention_hours = local_event_queue_retention_hours
        self.last_server_contact_utc = datetime.now(timezone.utc)
        self.temp_allow_expiry: dict[str, datetime] = {}
        self.enforcement_grace_seconds = enforcement_grace_seconds
        self.policy_hash = ""

    def mark_server_contact(self) -> None:
        self.last_server_contact_utc = datetime.now(timezone.utc)

    def _local_failsafe_active(self) -> bool:
        p = Path(__file__).resolve().parents[2] / ".device_failsafe_unlock"
        if not p.exists():
            return False
        try:
            exp = datetime.fromisoformat(p.read_text(encoding="utf-8").strip())
            return datetime.now(timezone.utc) <= exp.astimezone(timezone.utc)
        except Exception:
            return False

    def effective_mode(self) -> str:
        offline_for = datetime.now(timezone.utc) - self.last_server_contact_utc
        if self._local_failsafe_active():
            return "observe"
        if offline_for > timedelta(minutes=self.failsafe_offline_minutes):
            return "observe"
        return self.enforcement_mode

    def build_detection_events(self, device: USBDevice) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        details = {
            "event_id": str(uuid.uuid4()),
            "device_id": device.device_id,
            "vid": device.vid,
            "pid": device.pid,
            "serial": device.serial,
            "bus": device.bus,
            "location_paths": device.location_paths,
            "pnp_device_id": device.pnp_device_id,
            "vendor_name": device.vendor_name,
            "product_name": device.product_name,
            "first_seen_ts": now,
        }
        return [
            self._ev(now, "device.usb.inserted", device.device_id, details),
            self._ev(now, "device.usb.mass_storage_detected", device.device_id, details),
        ]

    def process_commands(self, client: ApiClient, agent_id: int, token: str, adapter, known_devices: dict[str, USBDevice]) -> None:
        commands = client.get_commands(agent_id, token)
        for cmd in commands:
            cmd_id = int(cmd["id"])
            ctype = cmd.get("type", "")
            payload = cmd.get("payload", {})
            device_id = payload.get("device_id")
            device = known_devices.get(device_id) if device_id else None
            try:
                if ctype == "DEVICE_UNBLOCK":
                    tok = payload.get("allow_token")
                    if tok:
                        ok, reason = self.consume_manual_allow_token(agent_id=agent_id, allow_token=str(tok))
                        if not ok:
                            raise RuntimeError(reason)
                        try:
                            client.consume_allow_token(agent_id, token, str(tok))
                            self.mark_server_contact()
                        except Exception:
                            # Local one-time consumption remains authoritative if server unreachable.
                            pass
                    if device:
                        ok = adapter.unblock_device(device, int(payload.get("duration_minutes") or 60))
                    else:
                        ok = adapter.unblock_device(
                            USBDevice(device_id="command-unblock", vid="", pid=""),
                            int(payload.get("duration_minutes") or 60),
                        )
                    result = "command_unblock_applied" if ok else "command_unblock_failed"
                    self._submit_or_queue(
                        client,
                        agent_id,
                        token,
                        [
                            self._device_applied_event(
                                "device.usb.unblock_applied",
                                {
                                    "device_id": device.device_id if device else str(device_id or "command-scope"),
                                    "result": result,
                                    "request_id": payload.get("request_id"),
                                },
                            )
                        ],
                    )
                    client.ack_command(agent_id, token, cmd_id, applied=ok, error=None if ok else "UNBLOCK_FAILED")
                elif ctype == "DEVICE_SET_MODE":
                    self.enforcement_mode = str(payload.get("mode", "observe"))
                    adapter.reconcile_state(self.enforcement_mode)
                    client.ack_command(agent_id, token, cmd_id, applied=True)
                elif ctype == "DEVICE_FORCE_OBSERVE":
                    self.enforcement_mode = "observe"
                    adapter.reconcile_state(self.enforcement_mode)
                    client.ack_command(agent_id, token, cmd_id, applied=True)
                elif ctype == "DEVICE_APPLY_POLICY_HASH":
                    self.policy_hash = str(payload.get("policy_hash", ""))
                    client.ack_command(agent_id, token, cmd_id, applied=True)
                elif ctype == "DEVICE_TEMP_ALLOW":
                    duration = int(payload.get("duration_minutes") or 30)
                    if device_id:
                        self.temp_allow_expiry[device_id] = datetime.now(timezone.utc) + timedelta(minutes=duration)
                    client.ack_command(agent_id, token, cmd_id, applied=True)
                else:
                    client.ack_command(agent_id, token, cmd_id, applied=False, error="UNKNOWN_COMMAND")
            except Exception as exc:  # noqa: BLE001
                client.ack_command(agent_id, token, cmd_id, applied=False, error=str(exc))

    def maybe_block_device(self, client: ApiClient, agent_id: int, token: str, adapter, device: USBDevice) -> None:
        mode = self.effective_mode()
        if mode == "observe":
            self._submit_or_queue(
                client,
                agent_id,
                token,
                [
                    self._device_applied_event(
                        "device.usb.block_applied",
                        {
                            "device_id": device.device_id,
                            "result": "would_block",
                            "enforcement_mode": "observe",
                        },
                    )
                ],
            )
            return

        token_id = self._consume_matching_allow_token(agent_id, device)
        if token_id:
            self._submit_or_queue(
                client,
                agent_id,
                token,
                [
                    self._device_applied_event(
                        "device.usb.unblock_applied",
                        {"device_id": device.device_id, "result": "token_allow_one_time", "token_id": token_id},
                    )
                ],
            )
            return

        if self.enforcement_grace_seconds > 0:
            return
        ok = adapter.block_device(device)
        result = "blocked" if ok else "block_failed"
        self._submit_or_queue(
            client,
            agent_id,
            token,
            [
                self._device_applied_event(
                    "device.usb.block_applied",
                    {
                        "device_id": device.device_id,
                        "result": result,
                        "bus": device.bus,
                        "location_paths": device.location_paths,
                        "pnp_device_id": device.pnp_device_id,
                    },
                )
            ],
        )
        if ok:
            port_label = device.bus or device.location_paths or "detected USB endpoint"
            trigger_mass_storage_block_alarm(
                (
                    "Mass storage device use detected.\n"
                    f"Blocked endpoint: {port_label}\n"
                    "USB mass-storage access is now blocked. Please contact admin."
                )
            )

    def flush_event_queue(self, client: ApiClient, agent_id: int, token: str) -> None:
        q = load_event_queue()
        if not q:
            return
        sent = set()
        for evt in q:
            try:
                client.post_events(agent_id, token, [evt])
                sent.add(evt["details_json"].get("event_id"))
            except Exception:
                break
        remaining = [e for e in q if e["details_json"].get("event_id") not in sent]
        save_event_queue(remaining)

    def consume_manual_allow_token(self, *, agent_id: int, allow_token: str) -> tuple[bool, str]:
        claims = _verify_token_offline(allow_token, self.token_public_key_path)
        if not claims:
            return False, "ALLOW_TOKEN_INVALID_OR_EXPIRED"
        if int(claims.get("agent_id", -1)) != agent_id:
            return False, "ALLOW_TOKEN_AGENT_MISMATCH"

        token_id = self._token_identifier(claims, allow_token)
        used = load_used_allow_tokens()
        if token_id in used:
            return False, "ALLOW_TOKEN_ALREADY_USED"

        used[token_id] = datetime.now(timezone.utc).isoformat()
        save_used_allow_tokens(used)
        return True, "OK"

    def _has_valid_allow_token(self, agent_id: int, device: USBDevice) -> bool:
        return bool(self._consume_matching_allow_token(agent_id, device))

    def _consume_matching_allow_token(self, agent_id: int, device: USBDevice) -> str | None:
        used = load_used_allow_tokens()
        now_iso = datetime.now(timezone.utc).isoformat()
        consumed_token_id: str | None = None
        keep_tokens: list[str] = []
        changed = False

        for token in load_tokens():
            claims = _verify_token_offline(token, self.token_public_key_path)
            if not claims:
                changed = True
                continue
            if int(claims.get("agent_id", -1)) != agent_id:
                keep_tokens.append(token)
                continue

            token_id = self._token_identifier(claims, token)
            if token_id in used:
                changed = True
                continue

            if consumed_token_id is None and self._token_scope_matches_device(claims.get("scope") or {}, device):
                used[token_id] = now_iso
                consumed_token_id = token_id
                changed = True
                continue

            keep_tokens.append(token)

        if changed:
            save_tokens(keep_tokens)
            save_used_allow_tokens(used)
        return consumed_token_id

    @staticmethod
    def _token_scope_matches_device(scope: dict[str, Any], device: USBDevice) -> bool:
        vid = str(scope.get("vid") or "").strip().lower()
        pid = str(scope.get("pid") or "").strip().lower()
        serial = str(scope.get("serial") or "").strip()
        scoped_device_id = str(scope.get("device_id") or "").strip()

        if vid and vid != (device.vid or "").strip().lower():
            return False
        if pid and pid != (device.pid or "").strip().lower():
            return False
        if serial and serial != str(device.serial or "").strip():
            return False
        if scoped_device_id and scoped_device_id != device.device_id:
            return False
        return True

    @staticmethod
    def _token_identifier(claims: dict[str, Any], token: str) -> str:
        token_id = str(claims.get("token_id") or "").strip()
        if token_id:
            return token_id
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return f"fp:{digest}"

    def _submit_or_queue(self, client: ApiClient, agent_id: int, token: str, events: list[dict]) -> None:
        try:
            client.post_events(agent_id, token, events)
            self.mark_server_contact()
        except Exception:
            q = load_event_queue()
            q.extend(events)
            save_event_queue(q)

    def _device_applied_event(self, event_type: str, details: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        details = dict(details)
        details.setdefault("event_id", str(uuid.uuid4()))
        return self._ev(now, event_type, details.get("device_id", "unknown"), details)

    def _ev(self, now: str, event_type: str, device_id: str, details: dict) -> dict:
        return {
            "schema_version": "1.0",
            "ts": now,
            "event_type": event_type,
            "file_path": f"device://{device_id}",
            "sha256": None,
            "file_size_bytes": None,
            "mtime_epoch": None,
            "user": None,
            "process_name": None,
            "host_ip": None,
            "details_json": details,
        }
