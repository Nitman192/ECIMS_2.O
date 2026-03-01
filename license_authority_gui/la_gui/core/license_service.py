"""License payload validation, signing, and verification."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from la_gui.core.canonical_json import canonicalize_json
from la_gui.core.crypto_service import CryptoService
from la_gui.core.models import LicensePayload, SignedLicense


class LicenseValidationError(ValueError):
    """Raised when user-supplied license fields fail strict validation."""


class LicenseService:
    """Service that creates and verifies signed license files."""

    @staticmethod
    def validate_payload(payload: LicensePayload) -> None:
        """Apply strict field validation before signing."""
        if not payload.serial.strip():
            raise LicenseValidationError("serial is required")
        if not payload.customer.strip():
            raise LicenseValidationError("customer is required")
        if payload.max_agents <= 0:
            raise LicenseValidationError("max_agents must be positive")
        if not payload.public_key_fingerprint.strip():
            raise LicenseValidationError("public_key_fingerprint is required")

        now = datetime.now(timezone.utc)
        expiry = datetime.fromisoformat(payload.expires_at)
        issued = datetime.fromisoformat(payload.issued_at)

        if expiry <= now:
            raise LicenseValidationError("expires_at must be in the future")
        if issued > now:
            raise LicenseValidationError("issued_at cannot be in the future")
        if expiry <= issued:
            raise LicenseValidationError("expires_at must be after issued_at")

    @staticmethod
    def payload_to_sign_dict(payload: LicensePayload) -> dict[str, Any]:
        """Convert payload to deterministic dictionary for signing."""
        as_map = asdict(payload)
        if not as_map.get("features"):
            as_map["features"] = {}
        return as_map

    @staticmethod
    def sign_license(payload: LicensePayload, private_key: Any) -> SignedLicense:
        """Validate and sign a license payload with RSA-PSS SHA-256."""
        LicenseService.validate_payload(payload)
        signable_payload = LicenseService.payload_to_sign_dict(payload)
        canonical_payload = canonicalize_json(signable_payload)
        signature = CryptoService.sign_bytes(private_key=private_key, payload=canonical_payload)
        payload_hash = CryptoService.sha256_hex(canonical_payload)

        return SignedLicense(
            **signable_payload,
            signature=signature,
            signed_payload_hash=payload_hash,
        )

    @staticmethod
    def signed_license_to_signable_payload(signed_license: SignedLicense) -> dict[str, Any]:
        """Extract signed payload fields (without signature fields) for verification."""
        full = asdict(signed_license)
        full.pop("signature")
        full.pop("signed_payload_hash")
        return full

    @staticmethod
    def verify_license_signature(signed_license: SignedLicense, public_key: Any) -> bool:
        """Verify signature and payload hash integrity."""
        payload = LicenseService.signed_license_to_signable_payload(signed_license)
        canonical_payload = canonicalize_json(payload)
        if CryptoService.sha256_hex(canonical_payload) != signed_license.signed_payload_hash:
            return False
        return CryptoService.verify_signature(
            public_key=public_key,
            payload=canonical_payload,
            signature_b64=signed_license.signature,
        )
