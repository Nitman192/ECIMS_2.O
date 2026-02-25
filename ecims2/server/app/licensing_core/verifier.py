from __future__ import annotations

import base64
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

EMBEDDED_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvKcM9c+Gm1YwoKJ2s9+P
3ixmxCvUwC1IiY0FvLULeN0iQatObbJ4KBk/y+KEDW8GhGv66zaAvtgvQgifla7a
FB8rLKOfWfgVO/qRsYlrv7RH2PGKGHN7TCWGC21lAd5otHdfUBKq5q1kNXtmHedl
RL5Cym09RKMbt/iuBfBbDIj9WilESNT10+ltXbvJT4ipqIq+DtySXcg9LeahcKqr
c13klW/PXvj/hQwL6fOu2W8gGNMcd+iB4U+JR3fc/venWGmXq3vy5YpeCKCSIVTG
ck6os3if8DZawnH/MYnCvhbnhpnYfxwOew8egVaowJHapXZZ0ZxaKtVOSvKpGr+o
bwIDAQAB
-----END PUBLIC KEY-----
"""


def _load_public_key_from_pem(pem_bytes: bytes):
    return serialization.load_pem_public_key(pem_bytes)


def load_public_key(public_key_path: str | None = None):
    if public_key_path:
        path = Path(public_key_path)
        if path.exists():
            return _load_public_key_from_pem(path.read_bytes())
    return _load_public_key_from_pem(EMBEDDED_PUBLIC_KEY_PEM.encode("utf-8"))


def verify_signature(payload_bytes: bytes, signature_b64: str, public_key_path: str | None = None) -> tuple[bool, str]:
    try:
        public_key = load_public_key(public_key_path)
        signature = base64.b64decode(signature_b64)
    except FileNotFoundError:
        return False, "NO_PUBLIC_KEY"
    except (ValueError, TypeError):
        return False, "INVALID_SIGNATURE_ENCODING"

    try:
        public_key.verify(
            signature,
            payload_bytes,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return True, "OK"
    except InvalidSignature:
        pass
    except Exception:
        return False, "INVALID_SIGNATURE"

    try:
        public_key.verify(signature, payload_bytes, padding.PKCS1v15(), hashes.SHA256())
        return True, "OK"
    except InvalidSignature:
        return False, "INVALID_SIGNATURE"
    except Exception:
        return False, "INVALID_SIGNATURE"
