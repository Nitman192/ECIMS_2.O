from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import rsa

from la_gui.core.activation_service import ActivationService
from la_gui.core.canonical_json import canonicalize_json
from la_gui.core.storage_paths import StoragePaths


def _b64u(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def test_parse_request_and_generate_verification_id() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    request_payload = {
        "token_type": "ECIMS_ACTIVATION_REQUEST_V1",
        "installation_id": "INS-TEST-001",
        "challenge": "abc123",
        "license_id": "LIC-TEST-001",
        "machine_fingerprint": "f" * 64,
        "license_expiry_date": (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat(),
        "customer_name": "Test Org",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
    }
    request_code = _b64u(canonicalize_json(request_payload))
    parsed = ActivationService.parse_request_code(request_code)
    token, claims = ActivationService.create_verification_id(
        request_payload=parsed,
        private_key=private_key,
        validity_days=10,
    )
    assert token.count(".") == 1
    assert claims["installation_id"] == "INS-TEST-001"
    assert claims["license_id"] == "LIC-TEST-001"
    assert claims["token_type"] == "ECIMS_SERVER_ACTIVATION_V1"


def test_registry_upsert_and_expiry_alert(tmp_path: Path) -> None:
    storage = StoragePaths(root=tmp_path)
    storage.ensure_directories()
    request_payload = {
        "installation_id": "INS-REG-001",
        "license_id": "LIC-REG-001",
        "machine_fingerprint": "a" * 64,
        "license_expiry_date": (datetime.now(timezone.utc).date() + timedelta(days=5)).isoformat(),
        "customer_name": "Customer A",
    }
    claims = {
        "verification_id": "VER-REG-001",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }
    entry = ActivationService.upsert_registry_entry(
        storage_paths=storage,
        request_payload=request_payload,
        verification_claims=claims,
    )
    assert entry["installation_id"] == "INS-REG-001"
    registry = ActivationService.load_registry(storage)
    assert isinstance(registry.get("clients"), list)
    assert len(registry["clients"]) == 1

    expiring = ActivationService.expiring_entries(storage, within_days=7)
    assert len(expiring) == 1
    assert expiring[0]["installation_id"] == "INS-REG-001"
