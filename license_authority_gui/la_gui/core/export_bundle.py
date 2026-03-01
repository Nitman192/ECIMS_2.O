"""Secure activation bundle ZIP export and manifest verification."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from la_gui.core.crypto_service import CryptoService


_ALLOWED_NAMES = {
    "license.json",
    "la_public_key.pem",
    "mtls_ca_cert.pem",
    "mtls_chain.pem",
    "revocation.json",
    "data_key_bundle.json",
}


class ExportBundleService:
    """Creates and verifies activation export bundles with hash manifest."""

    @staticmethod
    def create_activation_bundle(output_zip_path: Path, files_to_include: list[Path]) -> Path:
        """Create a bundle with manifest of file hashes and manifest hash."""
        if output_zip_path.suffix.lower() != ".zip":
            raise ValueError("Activation bundle output must be a .zip file")

        normalized: list[tuple[str, bytes]] = []
        seen_names: set[str] = set()

        for source in files_to_include:
            if not source.exists() or not source.is_file():
                continue
            safe_name = ExportBundleService._safe_name_for_path(source)
            if safe_name in seen_names:
                continue
            seen_names.add(safe_name)
            normalized.append((safe_name, source.read_bytes()))

        required = {"license.json", "la_public_key.pem"}
        present = {name for name, _ in normalized}
        missing = required - present
        if missing:
            raise ValueError(f"Missing required activation files: {sorted(missing)}")

        files_manifest = [
            {
                "name": name,
                "sha256": CryptoService.sha256_hex(content),
            }
            for name, content in normalized
        ]

        manifest_core = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": files_manifest,
        }
        manifest_sha256 = CryptoService.sha256_hex(
            json.dumps(manifest_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        manifest = {**manifest_core, "manifest_sha256": manifest_sha256}

        output_zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
            for name, content in normalized:
                archive.writestr(name, content)

        return output_zip_path

    @staticmethod
    def verify_manifest(zip_path: Path) -> tuple[bool, dict[str, Any]]:
        """Verify manifest hash and listed file hashes inside zip bundle."""
        if not zip_path.exists():
            return False, {"error": "zip does not exist"}

        with zipfile.ZipFile(zip_path, "r") as archive:
            members = set(archive.namelist())
            if "manifest.json" not in members:
                return False, {"error": "manifest.json missing"}

            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            files = manifest.get("files", [])
            manifest_core = {
                "created_at": manifest.get("created_at"),
                "files": files,
            }
            expected_manifest_hash = CryptoService.sha256_hex(
                json.dumps(manifest_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
            if expected_manifest_hash != manifest.get("manifest_sha256"):
                return False, {"error": "manifest hash mismatch", "expected": expected_manifest_hash}

            mismatches: list[dict[str, str]] = []
            missing: list[str] = []
            for item in files:
                name = str(item.get("name", ""))
                expected = str(item.get("sha256", ""))
                if name not in members:
                    missing.append(name)
                    continue
                actual = CryptoService.sha256_hex(archive.read(name))
                if actual != expected:
                    mismatches.append({"name": name, "expected": expected, "actual": actual})

            ok = not missing and not mismatches
            return ok, {
                "missing": missing,
                "mismatches": mismatches,
                "manifest_sha256": manifest.get("manifest_sha256"),
                "file_count": len(files),
            }

    @staticmethod
    def _safe_name_for_path(path: Path) -> str:
        """Map arbitrary source path into allowed archive filename set."""
        name = path.name
        if name in _ALLOWED_NAMES:
            return name

        lower = name.lower()
        if lower.startswith("license_") and lower.endswith(".json"):
            return "license.json"
        if lower.startswith("revocation_") and lower.endswith(".json"):
            return "revocation.json"
        if lower.startswith("data_key_bundle") and lower.endswith(".json"):
            return "data_key_bundle.json"

        raise ValueError(f"Unsupported export artifact name: {name}")
