"""Tests for license signing and verification logic."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from la_gui.core.crypto_service import CryptoService
from la_gui.core.license_service import LicenseService
from la_gui.core.models import LicensePayload, SignedLicense


def test_license_sign_and_verify_roundtrip() -> None:
    artifacts = CryptoService.generate_root_keypair("strong-pass")
    private_key = CryptoService.load_encrypted_private_key(artifacts.encrypted_private_pem, "strong-pass")
    public_key = CryptoService.load_public_key(artifacts.public_pem)

    issued = datetime.now(timezone.utc)
    payload = LicensePayload(
        serial="LIC-001",
        customer="Acme Corp",
        issued_at=issued.isoformat(),
        expires_at=(issued + timedelta(days=30)).isoformat(),
        max_agents=25,
        server_id="srv-a",
        features={"tier": "enterprise"},
        public_key_fingerprint=artifacts.public_key_fingerprint,
    )

    signed = LicenseService.sign_license(payload, private_key)
    assert LicenseService.verify_license_signature(signed, public_key)


def test_license_verification_fails_when_payload_tampered() -> None:
    artifacts = CryptoService.generate_root_keypair("strong-pass")
    private_key = CryptoService.load_encrypted_private_key(artifacts.encrypted_private_pem, "strong-pass")
    public_key = CryptoService.load_public_key(artifacts.public_pem)

    issued = datetime.now(timezone.utc)
    payload = LicensePayload(
        serial="LIC-002",
        customer="Beta Org",
        issued_at=issued.isoformat(),
        expires_at=(issued + timedelta(days=30)).isoformat(),
        max_agents=5,
        public_key_fingerprint=artifacts.public_key_fingerprint,
    )

    signed = LicenseService.sign_license(payload, private_key)
    tampered_dict = asdict(signed)
    tampered_dict["max_agents"] = 999
    tampered = SignedLicense(**tampered_dict)

    assert not LicenseService.verify_license_signature(tampered, public_key)
