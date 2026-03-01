"""Tests for mTLS CA generation and CSR signing."""

from __future__ import annotations

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from la_gui.core.mtls_service import MTLSService
from la_gui.core.storage_paths import StoragePaths


def test_generate_ca_sign_csr_and_export_chain(tmp_path) -> None:
    paths = StoragePaths(root=tmp_path)
    paths.ensure_directories()

    MTLSService.generate_ca(paths, "ca-pass")
    assert paths.mtls_ca_key_path.exists()
    assert paths.mtls_ca_cert_path.exists()

    agent_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "agent-1")]))
        .sign(agent_key, hashes.SHA256())
    )
    csr_path = tmp_path / "agent.csr.pem"
    csr_path.write_bytes(csr.public_bytes(serialization.Encoding.PEM))

    signed = MTLSService.sign_agent_csr(paths, "ca-pass", csr_path, validity_days=90)
    assert signed.output_path.exists()

    chain_path = MTLSService.export_chain(paths)
    assert chain_path.exists()
    assert (paths.exports_dir / "mtls_ca_cert.pem").exists()
