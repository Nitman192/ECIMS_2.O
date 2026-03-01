"""Data key bundle generation and rotation services."""

from __future__ import annotations

import base64
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from la_gui.core.crypto_service import CryptoService
from la_gui.core.storage_paths import StoragePaths


@dataclass(slots=True)
class DataKeyBundle:
    """Data key bundle payload for server at-rest encryption workflow."""

    bundle_id: str
    created_at: str
    key_id: str
    algorithm: str
    key_material_b64: str
    key_material_sha256: str
    previous_key_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "key_material_b64": self.key_material_b64,
            "key_material_sha256": self.key_material_sha256,
            "previous_key_id": self.previous_key_id,
        }


class DataKeyService:
    """Generates and rotates data key bundles."""

    ALGORITHM = "AES-256"

    @staticmethod
    def generate_data_key_bundle(storage_paths: StoragePaths) -> DataKeyBundle:
        """Generate and persist latest data key bundle in config and exports."""
        raw_key = secrets.token_bytes(32)
        key_b64 = base64.b64encode(raw_key).decode("ascii")
        bundle = DataKeyBundle(
            bundle_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            key_id=str(uuid.uuid4()),
            algorithm=DataKeyService.ALGORITHM,
            key_material_b64=key_b64,
            key_material_sha256=CryptoService.sha256_hex(raw_key),
        )
        DataKeyService._save_latest(storage_paths, bundle)
        DataKeyService.export_bundle(storage_paths, bundle)
        return bundle

    @staticmethod
    def rotate_data_key_bundle(storage_paths: StoragePaths, previous_bundle: DataKeyBundle | None = None) -> DataKeyBundle:
        """Rotate to a new data key bundle and reference the previous key id."""
        prior = previous_bundle or DataKeyService.load_latest_bundle(storage_paths)
        rotated = DataKeyService.generate_data_key_bundle(storage_paths)
        rotated.previous_key_id = prior.key_id if prior else None
        DataKeyService._save_latest(storage_paths, rotated)
        DataKeyService.export_bundle(storage_paths, rotated)
        return rotated

    @staticmethod
    def export_bundle(storage_paths: StoragePaths, bundle: DataKeyBundle) -> Path:
        """Export data key bundle JSON into exports directory."""
        path = storage_paths.exports_dir / "data_key_bundle.json"
        path.write_text(json.dumps(bundle.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    @staticmethod
    def load_latest_bundle(storage_paths: StoragePaths) -> DataKeyBundle | None:
        """Load latest bundle from config if available."""
        if not storage_paths.latest_data_key_bundle_path.exists():
            return None
        raw = json.loads(storage_paths.latest_data_key_bundle_path.read_text(encoding="utf-8"))
        return DataKeyBundle(**raw)

    @staticmethod
    def _save_latest(storage_paths: StoragePaths, bundle: DataKeyBundle) -> None:
        storage_paths.latest_data_key_bundle_path.write_text(
            json.dumps(bundle.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
