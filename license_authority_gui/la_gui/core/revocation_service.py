"""Revocation bundle creation and signature verification."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from la_gui.core.canonical_json import canonicalize_json
from la_gui.core.crypto_service import CryptoService
from la_gui.core.models import RevocationBundle


class RevocationService:
    """Service for CRL-like signed revocation bundles."""

    @staticmethod
    def create_bundle(revoked_serials: list[str], private_key: Any) -> RevocationBundle:
        """Create a signed revocation bundle."""
        deduped = sorted(set(serial.strip() for serial in revoked_serials if serial.strip()))
        issued_at = datetime.now(timezone.utc).isoformat()
        payload = {"issued_at": issued_at, "revoked_serials": deduped}
        signature = CryptoService.sign_bytes(private_key, canonicalize_json(payload))
        return RevocationBundle(issued_at=issued_at, revoked_serials=deduped, signature=signature)

    @staticmethod
    def verify_bundle(bundle: RevocationBundle, public_key: Any) -> bool:
        """Verify revocation bundle signature."""
        payload = asdict(bundle)
        signature = payload.pop("signature")
        return CryptoService.verify_signature(public_key, canonicalize_json(payload), signature)
