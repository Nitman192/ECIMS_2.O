"""Pure-Python wizard step status evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from la_gui.core.settings_service import AppSettings
from la_gui.core.storage_paths import StoragePaths


@dataclass(slots=True)
class WizardSnapshot:
    offline_ack: bool
    unlocked: bool
    root_key_present: bool
    root_public_present: bool
    license_present: bool
    mtls_ca_present: bool
    data_key_present: bool


@dataclass(slots=True)
class StepStatus:
    key: str
    label: str
    status: str
    details: str
    enabled: bool


def build_snapshot(storage_paths: StoragePaths, unlocked: bool, offline_ack: bool) -> WizardSnapshot:
    return WizardSnapshot(
        offline_ack=offline_ack,
        unlocked=unlocked,
        root_key_present=storage_paths.root_key_path.exists(),
        root_public_present=storage_paths.root_public_key_path.exists(),
        license_present=_latest(storage_paths.exports_dir, "license_*.json") is not None,
        mtls_ca_present=storage_paths.mtls_ca_cert_path.exists(),
        data_key_present=(storage_paths.exports_dir / "data_key_bundle.json").exists(),
    )


def evaluate_steps(snapshot: WizardSnapshot, settings: AppSettings) -> list[StepStatus]:
    steps = [
        StepStatus("offline", "Offline acknowledgement", "OK" if (not settings.require_offline_ack or snapshot.offline_ack) else "Missing", "config/offline_ack.json", True),
        StepStatus("root", "Root Key Generate/Unlock", "OK" if snapshot.unlocked else ("Locked" if snapshot.root_key_present else "Missing"), "keys/la_root_key_encrypted.pem", True),
        StepStatus("license", "Create License", "OK" if snapshot.license_present else "Needs Input", "exports/license_*.json", snapshot.unlocked),
    ]
    if settings.show_advanced_mode:
        steps.extend(
            [
                StepStatus("mtls_ca", "Generate mTLS CA (optional)", "OK" if snapshot.mtls_ca_present else "Missing", "keys/mtls_ca_cert.pem", True),
                StepStatus("mtls_sign", "Sign Agent CSR (optional)", "Needs Input", "exports/agent_cert_*.pem", snapshot.mtls_ca_present),
                StepStatus("data_key", "Generate/Rotate Data Key (optional)", "OK" if snapshot.data_key_present else "Missing", "exports/data_key_bundle.json", True),
            ]
        )

    steps.extend(
        [
            StepStatus("bundle", "Export Activation Bundle", "Needs Input", "exports/activation_bundle_*.zip", snapshot.license_present and snapshot.root_public_present),
            StepStatus("audit", "Verify Audit Chain", "Needs Input", "logs/audit_log.jsonl", True),
        ]
    )
    return steps


def _latest(directory: Path, pattern: str) -> Path | None:
    items = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    return items[-1] if items else None
