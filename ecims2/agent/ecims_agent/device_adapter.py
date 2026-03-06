from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class USBDevice:
    device_id: str
    vid: str
    pid: str
    serial: str | None = None
    bus: str | None = None
    vendor_name: str | None = None
    product_name: str | None = None


class DeviceEnforcementAdapter(Protocol):
    def detect_mass_storage(self) -> list[USBDevice]: ...

    def block_device(self, device: USBDevice) -> bool: ...

    def unblock_device(self, device: USBDevice, duration_minutes: int | None = None) -> bool: ...

    def reconcile_state(self, mode: str) -> None: ...


_STATE = Path(__file__).resolve().parents[2] / ".device_adapter_state.json"


def set_device_state_file(path: str | Path) -> None:
    global _STATE
    _STATE = Path(path)
    _STATE.parent.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict:
    if not _STATE.exists():
        return {}
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _STATE.write_text(json.dumps(state), encoding="utf-8")


class LinuxDeviceAdapter:
    def detect_mass_storage(self) -> list[USBDevice]:
        return []

    def block_device(self, device: USBDevice) -> bool:
        return True

    def unblock_device(self, device: USBDevice, duration_minutes: int | None = None) -> bool:
        return True

    def reconcile_state(self, mode: str) -> None:
        return


class WindowsDeviceAdapter:
    USBSTOR_KEY = r"HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR"

    def detect_mass_storage(self) -> list[USBDevice]:
        return []

    def block_device(self, device: USBDevice) -> bool:
        state = _load_state()
        if "prior_start" not in state:
            state["prior_start"] = self._read_start_value()
        ok = self._set_start_value(4)
        if ok:
            state["blocked"] = True
            _save_state(state)
        return ok

    def unblock_device(self, device: USBDevice, duration_minutes: int | None = None) -> bool:
        state = _load_state()
        prior = int(state.get("prior_start", 3))
        ok = self._set_start_value(prior)
        if ok:
            state["blocked"] = False
            _save_state(state)
        return ok

    def reconcile_state(self, mode: str) -> None:
        state = _load_state()
        blocked = bool(state.get("blocked", False))
        if mode == "observe" and blocked:
            self.unblock_device(USBDevice(device_id="reconcile", vid="", pid=""))
        if mode == "enforce" and not blocked:
            self.block_device(USBDevice(device_id="reconcile", vid="", pid=""))

    def _read_start_value(self) -> int:
        cmd = ["reg", "query", self.USBSTOR_KEY, "/v", "Start"]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            return 3
        for line in proc.stdout.splitlines():
            if "Start" in line:
                parts = line.split()
                val = parts[-1]
                try:
                    return int(val, 16)
                except Exception:
                    return 3
        return 3

    def _set_start_value(self, value: int) -> bool:
        cmd = ["reg", "add", self.USBSTOR_KEY, "/v", "Start", "/t", "REG_DWORD", "/d", str(value), "/f"]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return proc.returncode == 0


class StubDeviceAdapter:
    def detect_mass_storage(self) -> list[USBDevice]:
        return []

    def block_device(self, device: USBDevice) -> bool:
        return True

    def unblock_device(self, device: USBDevice, duration_minutes: int | None = None) -> bool:
        return True

    def reconcile_state(self, mode: str) -> None:
        return


def select_adapter() -> DeviceEnforcementAdapter:
    os_name = platform.system().lower()
    if os_name == "linux":
        return LinuxDeviceAdapter()
    if os_name == "windows":
        return WindowsDeviceAdapter()
    return StubDeviceAdapter()
