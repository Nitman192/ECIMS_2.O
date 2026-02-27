from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class Keyring:
    active_kid: str
    keys: dict[str, bytes]


def _keyring_path() -> Path:
    return Path(os.getenv("ECIMS_KEYRING_PATH", "configs/data_keyring.json"))


def _environment() -> str:
    return os.getenv("ECIMS_ENVIRONMENT", "dev").lower()


def _allow_plaintext_fallback() -> bool:
    if _environment() == "prod":
        return False
    return os.getenv("ECIMS_ALLOW_PLAINTEXT_FALLBACK", "true").lower() == "true"


def load_keyring() -> Keyring:
    path = _keyring_path()
    if not path.exists():
        if _allow_plaintext_fallback():
            return Keyring(active_kid="", keys={})
        raise RuntimeError("Keyring not found and plaintext fallback is disabled")

    raw = json.loads(path.read_text(encoding="utf-8"))
    active_kid = str(raw.get("active_kid", ""))
    keys_raw = raw.get("keys", {})
    keys = {kid: base64.b64decode(value) for kid, value in keys_raw.items()}

    if active_kid and active_kid not in keys:
        raise RuntimeError("active_kid is not present in keyring keys")

    return Keyring(active_kid=active_kid, keys=keys)


def encrypt_token(token: str) -> str:
    keyring = load_keyring()
    if not keyring.active_kid:
        if _allow_plaintext_fallback():
            return f"plain:{token}"
        raise RuntimeError("No active key available for token encryption")

    key = keyring.keys[keyring.active_kid]
    if len(key) != 32:
        raise RuntimeError("Active key must be 32 bytes for AES-256-GCM")

    nonce = os.urandom(12)
    cipher = AESGCM(key).encrypt(nonce, token.encode("utf-8"), None)
    payload = base64.b64encode(nonce + cipher).decode("ascii")
    return f"enc:{keyring.active_kid}:{payload}"


def decrypt_token(value: str) -> str:
    if value.startswith("plain:"):
        if not _allow_plaintext_fallback():
            raise RuntimeError("Plaintext token fallback is disabled")
        return value.removeprefix("plain:")

    if not value.startswith("enc:"):
        raise RuntimeError("Unsupported token storage format")

    _, kid, payload = value.split(":", 2)
    keyring = load_keyring()
    key = keyring.keys.get(kid)
    if not key:
        raise RuntimeError(f"No key found for kid={kid}")

    blob = base64.b64decode(payload)
    nonce, cipher = blob[:12], blob[12:]
    plain = AESGCM(key).decrypt(nonce, cipher, None)
    return plain.decode("utf-8")
