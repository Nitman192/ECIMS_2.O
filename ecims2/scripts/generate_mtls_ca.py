#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def generate_mtls_materials(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ca_key = output_dir / "ca.key.pem"
    ca_cert = output_dir / "ca.cert.pem"
    server_key = output_dir / "server.key.pem"
    server_csr = output_dir / "server.csr.pem"
    server_cert = output_dir / "server.cert.pem"

    subprocess.run(["openssl", "genrsa", "-out", str(ca_key), "4096"], check=True)
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-new",
            "-nodes",
            "-key",
            str(ca_key),
            "-sha256",
            "-days",
            "3650",
            "-subj",
            "/CN=ECIMS-MTLS-CA",
            "-out",
            str(ca_cert),
        ],
        check=True,
    )

    subprocess.run(["openssl", "genrsa", "-out", str(server_key), "2048"], check=True)
    subprocess.run(
        [
            "openssl",
            "req",
            "-new",
            "-key",
            str(server_key),
            "-subj",
            "/CN=ecims-server",
            "-out",
            str(server_csr),
        ],
        check=True,
    )
    subprocess.run(
        [
            "openssl",
            "x509",
            "-req",
            "-in",
            str(server_csr),
            "-CA",
            str(ca_cert),
            "-CAkey",
            str(ca_key),
            "-CAcreateserial",
            "-out",
            str(server_cert),
            "-days",
            "365",
            "-sha256",
        ],
        check=True,
    )


def main() -> None:
    out = Path(os.getenv("ECIMS_MTLS_OUT_DIR", "configs/mtls"))
    generate_mtls_materials(out)
    print(f"generated mTLS materials in {out}")


if __name__ == "__main__":
    main()
