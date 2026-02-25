from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID


def main() -> None:
    parser = argparse.ArgumentParser(description="Sign an agent CSR for ECIMS mTLS")
    parser.add_argument("--ca-key", required=True)
    parser.add_argument("--ca-cert", required=True)
    parser.add_argument("--csr", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--out-cert", required=True)
    args = parser.parse_args()

    ca_key = serialization.load_pem_private_key(Path(args.ca_key).read_bytes(), password=None)
    ca_cert = x509.load_pem_x509_certificate(Path(args.ca_cert).read_bytes())
    csr = x509.load_pem_x509_csr(Path(args.csr).read_bytes())

    cn = csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    csr_agent = cn[0].value if cn else ""
    if csr_agent != args.agent_id:
        raise ValueError(f"CSR CN ({csr_agent}) does not match requested agent_id ({args.agent_id})")

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_cert.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=args.days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=True,
                                     content_commitment=False, key_cert_sign=False, crl_sign=False,
                                     data_encipherment=False, key_agreement=False,
                                     encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(f"urn:ecims:agent:{args.agent_id}")]), critical=False)
        .sign(private_key=ca_key, algorithm=hashes.SHA256())
    )

    Path(args.out_cert).write_bytes(cert.public_bytes(serialization.Encoding.PEM))


if __name__ == "__main__":
    main()
