"""mTLS CA generation and agent CSR signing services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from la_gui.core.storage_paths import StoragePaths


@dataclass(slots=True)
class MTLSSigningResult:
    """Result for a signed agent certificate."""

    certificate_pem: bytes
    output_path: Path


class MTLSService:
    """Core mTLS workflows for offline CA and CSR signing."""

    @staticmethod
    def generate_ca(storage_paths: StoragePaths, passphrase: str) -> tuple[Path, Path]:
        """Generate encrypted CA private key and self-signed CA certificate."""
        if not passphrase:
            raise ValueError("CA passphrase is required")

        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ECIMS 2.0 License Authority"),
                x509.NameAttribute(NameOID.COMMON_NAME, "ECIMS Offline mTLS Root CA"),
            ]
        )
        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                key_cert_sign=True,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ), critical=True)
            .sign(private_key=ca_key, algorithm=hashes.SHA256())
        )

        key_path = storage_paths.keys_dir / "mtls_ca_key_encrypted.pem"
        cert_path = storage_paths.keys_dir / "mtls_ca_cert.pem"

        key_bytes = ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(passphrase.encode("utf-8")),
        )
        cert_bytes = cert.public_bytes(serialization.Encoding.PEM)

        key_path.write_bytes(key_bytes)
        cert_path.write_bytes(cert_bytes)

        return key_path, cert_path

    @staticmethod
    def sign_agent_csr(
        storage_paths: StoragePaths,
        ca_passphrase: str,
        csr_pem_path: Path,
        validity_days: int = 365,
    ) -> MTLSSigningResult:
        """Sign an agent CSR with the offline CA key."""
        if validity_days <= 0:
            raise ValueError("validity_days must be positive")

        ca_key = MTLSService._load_ca_key(storage_paths, ca_passphrase)
        ca_cert = x509.load_pem_x509_certificate(storage_paths.mtls_ca_cert_path.read_bytes())
        csr = x509.load_pem_x509_csr(csr_pem_path.read_bytes())

        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(csr.subject)
            .issuer_name(ca_cert.subject)
            .public_key(csr.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=validity_days))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
            .sign(private_key=ca_key, algorithm=hashes.SHA256())
        )

        output_path = storage_paths.exports_dir / f"agent_cert_{csr_pem_path.stem}.pem"
        output_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        return MTLSSigningResult(certificate_pem=output_path.read_bytes(), output_path=output_path)

    @staticmethod
    def export_chain(storage_paths: StoragePaths, output_name: str = "mtls_chain.pem") -> Path:
        """Export mTLS chain (currently CA cert only) into exports directory."""
        if not storage_paths.mtls_ca_cert_path.exists():
            raise ValueError("CA certificate not found. Generate CA first.")

        chain_path = storage_paths.exports_dir / output_name
        chain_path.write_bytes(storage_paths.mtls_ca_cert_path.read_bytes())

        export_ca_cert_path = storage_paths.exports_dir / "mtls_ca_cert.pem"
        export_ca_cert_path.write_bytes(storage_paths.mtls_ca_cert_path.read_bytes())
        return chain_path

    @staticmethod
    def _load_ca_key(storage_paths: StoragePaths, passphrase: str) -> RSAPrivateKey:
        if not storage_paths.mtls_ca_key_path.exists() or not storage_paths.mtls_ca_cert_path.exists():
            raise ValueError("CA key/cert not found. Generate CA first.")
        key = serialization.load_pem_private_key(
            storage_paths.mtls_ca_key_path.read_bytes(),
            password=passphrase.encode("utf-8"),
        )
        if not isinstance(key, RSAPrivateKey):
            raise TypeError("Loaded CA key is not RSA")
        return key
