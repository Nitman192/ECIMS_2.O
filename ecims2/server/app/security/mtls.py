from __future__ import annotations

import os


def is_mtls_enabled() -> bool:
    return os.getenv("ECIMS_MTLS_ENABLED", "false").lower() == "true"


def validate_client_certificate_subject(subject: tuple[tuple[tuple[str, str], ...], ...], expected_cn: str) -> bool:
    """Validate peer cert subject tuple from ssl.getpeercert()['subject']."""
    for rdn in subject:
        for field, value in rdn:
            if field == "commonName" and value == expected_cn:
                return True
    return False
