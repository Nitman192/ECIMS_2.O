from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from enum import Enum

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.db.database import get_db
from app.licensing_core.policy_state import get_policy_state
from app.services.agent_service import AgentService
from app.services.audit_service import AuditService


class MTLSAuditAction(str, Enum):
    MISSING_CERT = "MTLS_MISSING_CERT"
    INVALID_CERT = "MTLS_INVALID_CERT"
    AGENT_MISMATCH = "MTLS_AGENT_MISMATCH"
    AGENT_REVOKED = "MTLS_AGENT_REVOKED"


@dataclass
class MTLSIdentity:
    agent_id: str
    cert_fingerprint_sha256: str


def _audit_block(action: MTLSAuditAction, message: str, metadata: dict[str, str] | None = None) -> None:
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="SYSTEM",
            action=str(action.value),
            target_type="TLS",
            target_id="mtls",
            message=message,
            metadata=metadata or {},
        )


def _extract_agent_id(cert: x509.Certificate) -> str | None:
    cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if cn_attrs and cn_attrs[0].value:
        return cn_attrs[0].value.strip()

    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return None

    for uri in san.get_values_for_type(x509.UniformResourceIdentifier):
        if uri.startswith("urn:ecims:agent:"):
            return uri.split(":")[-1].strip()
    return None


def parse_mtls_identity(cert_der_b64: str) -> MTLSIdentity:
    try:
        cert_der = base64.b64decode(cert_der_b64)
        cert = x509.load_der_x509_certificate(cert_der)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("INVALID_CERT") from exc

    agent_id = _extract_agent_id(cert)
    if not agent_id:
        raise ValueError("MISSING_AGENT_ID")

    fingerprint = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
    return MTLSIdentity(agent_id=agent_id, cert_fingerprint_sha256=fingerprint)


def require_mtls_client_identity(request: Request, claimed_agent_id: int | None = None) -> MTLSIdentity:
    policy_state = get_policy_state()
    policy = policy_state.policy
    settings = get_settings()
    dev_mode = policy_state.reason == "OK_DEV"

    mtls_required = settings.mtls_required and settings.mtls_enabled and policy.mtls_required
    if not mtls_required:
        return MTLSIdentity(agent_id=str(claimed_agent_id or ""), cert_fingerprint_sha256="")

    cert_der_b64 = request.headers.get("x-ecims-client-cert-b64", "").strip()
    if not cert_der_b64:
        if dev_mode and policy.allow_unsigned_dev:
            return MTLSIdentity(agent_id=str(claimed_agent_id or ""), cert_fingerprint_sha256="DEV_BYPASS")
        _audit_block(MTLSAuditAction.MISSING_CERT, "mTLS client certificate is required")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="mTLS client certificate required")

    try:
        identity = parse_mtls_identity(cert_der_b64)
    except ValueError as exc:
        _audit_block(MTLSAuditAction.INVALID_CERT, "Invalid client certificate", {"reason": str(exc)})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid mTLS client certificate") from exc

    if claimed_agent_id is not None and identity.agent_id != str(claimed_agent_id):
        _audit_block(
            MTLSAuditAction.AGENT_MISMATCH,
            "Agent identity mismatch between payload and certificate",
            {"claimed_agent_id": str(claimed_agent_id), "cert_agent_id": identity.agent_id},
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="mTLS agent identity mismatch")

    if claimed_agent_id is not None:
        agent = AgentService.get_agent(claimed_agent_id)
        if not agent:
            _audit_block(
                MTLSAuditAction.AGENT_MISMATCH,
                "Agent id from certificate is not registered",
                {"claimed_agent_id": str(claimed_agent_id)},
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent not registered")
        if agent.get("agent_revoked"):
            _audit_block(
                MTLSAuditAction.AGENT_REVOKED,
                "Revoked agent attempted mTLS-authenticated access",
                {"claimed_agent_id": str(claimed_agent_id)},
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent certificate revoked")

    return identity
