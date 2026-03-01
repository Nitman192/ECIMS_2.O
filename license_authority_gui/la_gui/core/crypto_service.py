"""Cryptographic primitives for key management and signing."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey


@dataclass(slots=True)
class KeyPairArtifacts:
    """Result object produced when generating a root keypair."""

    encrypted_private_pem: bytes
    public_pem: bytes
    public_key_fingerprint: str


class CryptoService:
    """Centralized cryptographic operations for the offline authority tool."""

    @staticmethod
    def generate_root_keypair(passphrase: str) -> KeyPairArtifacts:
        """Generate an RSA-4096 keypair and encrypt the private PEM with passphrase."""
        if not passphrase:
            raise ValueError("Passphrase is required for root key encryption.")

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        encrypted_private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(passphrase.encode("utf-8")),
        )
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return KeyPairArtifacts(
            encrypted_private_pem=encrypted_private_pem,
            public_pem=public_pem,
            public_key_fingerprint=CryptoService.public_key_fingerprint(public_pem),
        )

    @staticmethod
    def load_encrypted_private_key(private_pem: bytes, passphrase: str) -> RSAPrivateKey:
        """Load an encrypted RSA private key from PEM bytes."""
        key = serialization.load_pem_private_key(private_pem, password=passphrase.encode("utf-8"))
        if not isinstance(key, RSAPrivateKey):
            raise TypeError("Loaded key is not an RSA private key.")
        return key

    @staticmethod
    def load_public_key(public_pem: bytes) -> RSAPublicKey:
        """Load a PEM public key."""
        key = serialization.load_pem_public_key(public_pem)
        if not isinstance(key, RSAPublicKey):
            raise TypeError("Loaded key is not an RSA public key.")
        return key

    @staticmethod
    def sign_bytes(private_key: RSAPrivateKey, payload: bytes) -> str:
        """Sign payload bytes with RSA-PSS SHA-256 and return base64 signature."""
        signature = private_key.sign(
            payload,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("ascii")

    @staticmethod
    def verify_signature(public_key: RSAPublicKey, payload: bytes, signature_b64: str) -> bool:
        """Verify an RSA-PSS signature; return False when invalid."""
        signature = base64.b64decode(signature_b64.encode("ascii"))
        try:
            public_key.verify(
                signature,
                payload,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            return True
        except InvalidSignature:
            return False

    @staticmethod
    def sha256_hex(payload: bytes) -> str:
        """Calculate SHA-256 hex digest."""
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def public_key_fingerprint(public_pem: bytes) -> str:
        """Return SHA-256 fingerprint for public key bytes."""
        return hashlib.sha256(public_pem).hexdigest()
