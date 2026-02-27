from __future__ import annotations

import ssl
from pathlib import Path


def create_server_ssl_context(
    certfile: str,
    keyfile: str,
    cafile: str | None = None,
    require_client_cert: bool = False,
) -> ssl.SSLContext:
    cert_path = Path(certfile)
    key_path = Path(keyfile)
    if not cert_path.exists() or not key_path.exists():
        raise FileNotFoundError("TLS certfile/keyfile not found")

    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

    if cafile:
        ca_path = Path(cafile)
        if not ca_path.exists():
            raise FileNotFoundError("TLS cafile not found")
        context.load_verify_locations(cafile=str(ca_path))

    context.verify_mode = ssl.CERT_REQUIRED if require_client_cert else ssl.CERT_OPTIONAL
    context.check_hostname = False
    return context
