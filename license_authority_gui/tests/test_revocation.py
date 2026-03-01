"""Tests for revocation bundle signing and verification."""

from __future__ import annotations

from dataclasses import asdict

from la_gui.core.crypto_service import CryptoService
from la_gui.core.models import RevocationBundle
from la_gui.core.revocation_service import RevocationService


def test_revocation_bundle_signature_verifies() -> None:
    artifacts = CryptoService.generate_root_keypair("strong-pass")
    private_key = CryptoService.load_encrypted_private_key(artifacts.encrypted_private_pem, "strong-pass")
    public_key = CryptoService.load_public_key(artifacts.public_pem)

    bundle = RevocationService.create_bundle(["L1", "L2", "L1"], private_key)
    assert bundle.revoked_serials == ["L1", "L2"]
    assert RevocationService.verify_bundle(bundle, public_key)


def test_revocation_bundle_tamper_detected() -> None:
    artifacts = CryptoService.generate_root_keypair("strong-pass")
    private_key = CryptoService.load_encrypted_private_key(artifacts.encrypted_private_pem, "strong-pass")
    public_key = CryptoService.load_public_key(artifacts.public_pem)

    bundle = RevocationService.create_bundle(["L1"], private_key)
    tampered = asdict(bundle)
    tampered["revoked_serials"] = ["L1", "L9"]

    assert not RevocationService.verify_bundle(RevocationBundle(**tampered), public_key)
