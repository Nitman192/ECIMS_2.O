from __future__ import annotations

import ssl
from pathlib import Path

from app.core.config import Settings
from app.licensing_core.policy import SecurityPolicy


def build_server_ssl_context(settings: Settings, policy: SecurityPolicy) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=str(Path(settings.server_cert_path)), keyfile=str(Path(settings.server_key_path)))
    context.load_verify_locations(cafile=str(Path(settings.client_ca_cert_path)))
    context.verify_mode = ssl.CERT_REQUIRED if policy.mtls_required and settings.mtls_required else ssl.CERT_OPTIONAL

    if policy.allow_tls12 or settings.tls_min_version == "1.2":
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    else:
        context.minimum_version = ssl.TLSVersion.TLSv1_3
    return context
