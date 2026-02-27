from __future__ import annotations

import argparse
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate agent private key + CSR for offline mTLS provisioning")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--out-dir", default=".")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, args.agent_id)]))
        .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(f"urn:ecims:agent:{args.agent_id}")]), critical=False)
        .sign(key, hashes.SHA256())
    )

    (out_dir / f"agent_{args.agent_id}.key").write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    (out_dir / f"agent_{args.agent_id}.csr").write_bytes(csr.public_bytes(serialization.Encoding.PEM))


if __name__ == "__main__":
    main()
