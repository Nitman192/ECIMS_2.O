from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass
class USBDevice:
    device_id: str
    vid: str
    pid: str
    serial: str | None = None
    bus: str | None = None
    location_paths: str | None = None
    vendor_name: str | None = None
    product_name: str | None = None
    pnp_device_id: str | None = None


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
        script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$items = Get-CimInstance Win32_DiskDrive |
    Where-Object { $_.InterfaceType -eq 'USB' } |
    ForEach-Object {
        $pnp = [string]$_.PNPDeviceID
        if (-not $pnp) { return }

        $vid = ''
        $pid = ''
        if ($pnp -match 'VID_([0-9A-Fa-f]{4})') { $vid = $Matches[1].ToLowerInvariant() }
        if ($pnp -match 'PID_([0-9A-Fa-f]{4})') { $pid = $Matches[1].ToLowerInvariant() }

        $serial = ''
        $parts = $pnp -split '\\'
        if ($parts.Length -gt 0) { $serial = $parts[$parts.Length - 1] }

        $locationInfo = ''
        try {
            $locationInfoProp = Get-PnpDeviceProperty -InstanceId $pnp -KeyName 'DEVPKEY_Device_LocationInfo'
            if ($locationInfoProp -and $locationInfoProp.Data) {
                $locationInfo = [string]$locationInfoProp.Data
            }
        } catch {}

        $locationPaths = ''
        try {
            $locationPathsProp = Get-PnpDeviceProperty -InstanceId $pnp -KeyName 'DEVPKEY_Device_LocationPaths'
            if ($locationPathsProp -and $locationPathsProp.Data) {
                if ($locationPathsProp.Data -is [array]) {
                    $locationPaths = ($locationPathsProp.Data -join ';')
                } else {
                    $locationPaths = [string]$locationPathsProp.Data
                }
            }
        } catch {}

        [PSCustomObject]@{
            device_id = ('usb://' + $pnp)
            vid = $vid
            pid = $pid
            serial = $serial
            bus = $locationInfo
            location_paths = $locationPaths
            vendor_name = [string]$_.Manufacturer
            product_name = [string]$_.Model
            pnp_device_id = $pnp
        }
    }

if ($null -eq $items) {
    '[]'
} else {
    $items | ConvertTo-Json -Compress -Depth 4
}
"""
        rows = self._run_powershell_json(script)
        devices: list[USBDevice] = []
        for row in rows:
            pnp_device_id = str(row.get("pnp_device_id") or "").strip()
            if not pnp_device_id:
                continue
            vid = str(row.get("vid") or "").strip().lower() or "unknown"
            pid = str(row.get("pid") or "").strip().lower() or "unknown"
            device_id = str(row.get("device_id") or f"usb://{pnp_device_id}").strip()
            if not device_id:
                continue
            devices.append(
                USBDevice(
                    device_id=device_id,
                    vid=vid,
                    pid=pid,
                    serial=self._clean_optional(row.get("serial")),
                    bus=self._clean_optional(row.get("bus")),
                    location_paths=self._clean_optional(row.get("location_paths")),
                    vendor_name=self._clean_optional(row.get("vendor_name")),
                    product_name=self._clean_optional(row.get("product_name")),
                    pnp_device_id=pnp_device_id,
                )
            )
        return devices

    def block_device(self, device: USBDevice) -> bool:
        state = _load_state()
        if "prior_start" not in state:
            state["prior_start"] = self._read_start_value()
        blocked_instances = self._blocked_instances(state)

        instance_ok = False
        if device.pnp_device_id:
            instance_ok = self._disable_device_instance(device.pnp_device_id)
            if instance_ok:
                blocked_instances.add(device.pnp_device_id)

        # Keep legacy fallback enabled so new USBSTOR mount attempts are denied globally.
        service_ok = self._set_start_value(4)

        if instance_ok or service_ok:
            state["blocked"] = True
            state["blocked_instances"] = sorted(blocked_instances)
            _save_state(state)
        return instance_ok or service_ok

    def unblock_device(self, device: USBDevice, duration_minutes: int | None = None) -> bool:
        state = _load_state()
        blocked_instances = self._blocked_instances(state)
        if device.pnp_device_id:
            blocked_instances.add(device.pnp_device_id)

        instances_ok = True
        for instance_id in sorted(blocked_instances):
            if not self._enable_device_instance(instance_id):
                instances_ok = False

        prior = int(state.get("prior_start", 3))
        service_ok = self._set_start_value(prior)
        if instances_ok and service_ok:
            state["blocked"] = False
            state["blocked_instances"] = []
            _save_state(state)
        return instances_ok and service_ok

    def reconcile_state(self, mode: str) -> None:
        state = _load_state()
        blocked = bool(state.get("blocked", False) or self._blocked_instances(state))
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

    @staticmethod
    def _run_powershell_json(script: str) -> list[dict[str, Any]]:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return []
        stdout = (proc.stdout or "").strip()
        if not stdout:
            return []
        try:
            payload = json.loads(stdout)
        except Exception:
            return []
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    @staticmethod
    def _clean_optional(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _blocked_instances(state: dict[str, Any]) -> set[str]:
        raw = state.get("blocked_instances")
        if not isinstance(raw, list):
            return set()
        return {str(item).strip() for item in raw if str(item).strip()}

    @staticmethod
    def _run_pnputil(command: str, instance_id: str) -> bool:
        proc = subprocess.run(
            ["pnputil", command, instance_id],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode == 0

    @staticmethod
    def _run_pnp_powershell(*, disable: bool, instance_id: str) -> bool:
        escaped = instance_id.replace("'", "''")
        action = "Disable-PnpDevice" if disable else "Enable-PnpDevice"
        script = f"{action} -InstanceId '{escaped}' -Confirm:$false -ErrorAction Stop"
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode == 0

    def _disable_device_instance(self, instance_id: str) -> bool:
        if self._run_pnputil("/disable-device", instance_id):
            return True
        return self._run_pnp_powershell(disable=True, instance_id=instance_id)

    def _enable_device_instance(self, instance_id: str) -> bool:
        if self._run_pnputil("/enable-device", instance_id):
            return True
        return self._run_pnp_powershell(disable=False, instance_id=instance_id)


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
