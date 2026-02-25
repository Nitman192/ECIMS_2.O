from __future__ import annotations

import argparse
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12


def main() -> None:
    parser = argparse.ArgumentParser(description="Package agent cert+key as PFX")
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    cert = x509.load_pem_x509_certificate(Path(args.cert).read_bytes())
    key = serialization.load_pem_private_key(Path(args.key).read_bytes(), password=None)
    blob = pkcs12.serialize_key_and_certificates(
        name=b"ecims-agent",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(args.password.encode("utf-8")),
    )
    Path(args.out).write_bytes(blob)


if __name__ == "__main__":
    main()
