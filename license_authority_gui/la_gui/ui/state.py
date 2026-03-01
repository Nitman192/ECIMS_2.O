"""In-memory session state for unlocked secrets and shared app services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from la_gui.core.audit_log import AuditLogger
from la_gui.core.settings_service import AppSettings
from la_gui.core.storage_paths import StoragePaths


@dataclass(slots=True)
class SessionState:
    """Runtime state for the desktop operator session."""

    storage_paths: StoragePaths
    audit_logger: AuditLogger
    settings: AppSettings
    app_root: Path
    offline_acknowledged: bool = False
    private_key: RSAPrivateKey | None = None
    public_key: RSAPublicKey | None = None
    public_key_fingerprint: str | None = None
    last_action: str = "Ready"

    @property
    def is_unlocked(self) -> bool:
        """Return whether root key material is available in memory."""
        return self.private_key is not None

    @property
    def root_private_key_path(self) -> Path:
        """Return encrypted root private key path."""
        return self.storage_paths.root_key_path

    @property
    def root_public_key_path(self) -> Path:
        """Return root public key path."""
        return self.storage_paths.root_public_key_path

    def lock(self) -> None:
        """Purge in-memory key material."""
        self.private_key = None
        self.public_key = None
        self.last_action = "Locked"
