from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    private_path = Path("private_key.pem")
    public_path = Path("public_key.pem")

    if private_path.exists() and public_path.exists():
        print("Keys already exist; skipping generation.")
        return

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path.write_bytes(private_bytes)
    public_path.write_bytes(public_bytes)
    print("Generated private_key.pem and public_key.pem")
    print("Copy public_key.pem to ecims2/server/app/license/public_key.pem")


if __name__ == "__main__":
    main()
