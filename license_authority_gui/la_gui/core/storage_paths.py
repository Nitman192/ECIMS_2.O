"""Filesystem path conventions for the offline license authority app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StoragePaths:
    """Resolved directories for persisted artifacts."""

    root: Path

    @property
    def keys_dir(self) -> Path:
        return self.root / "keys"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def exports_dir(self) -> Path:
        return self.root / "exports"

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def root_key_path(self) -> Path:
        return self.keys_dir / "la_root_key_encrypted.pem"

    @property
    def root_public_key_path(self) -> Path:
        return self.keys_dir / "la_root_public.pem"

    @property
    def audit_log_path(self) -> Path:
        return self.logs_dir / "audit_log.jsonl"

    @property
    def mtls_ca_key_path(self) -> Path:
        return self.keys_dir / "mtls_ca_key_encrypted.pem"

    @property
    def mtls_ca_cert_path(self) -> Path:
        return self.keys_dir / "mtls_ca_cert.pem"

    @property
    def latest_data_key_bundle_path(self) -> Path:
        return self.config_dir / "latest_data_key_bundle.json"

    @property
    def activity_log_path(self) -> Path:
        return self.config_dir / "audit_log.jsonl"

    @property
    def activation_registry_path(self) -> Path:
        return self.config_dir / "activation_registry.json"

    def ensure_directories(self) -> None:
        """Create all required directories with parent support."""
        for directory in [self.keys_dir, self.logs_dir, self.exports_dir, self.config_dir]:
            directory.mkdir(parents=True, exist_ok=True)
