from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception as _exc:  # noqa: BLE001
    AESGCM = None  # type: ignore[assignment]
    HKDF = None  # type: ignore[assignment]
    hashes = None  # type: ignore[assignment]
    _CRYPTO_IMPORT_ERR = _exc
else:
    _CRYPTO_IMPORT_ERR = None

from app.core.config import get_settings
from app.licensing_core.policy_state import get_policy_state

MAGIC = b"ECIMSENC"
VERSION = 1


@dataclass
class Keyring:
    active_key_id: str
    keys: dict[str, bytes]


@dataclass
class CryptoStatus:
    encryption_enabled: bool
    active_key_id: str | None
    keyring_count: int
    reason: str


def _require_crypto() -> None:
    if _CRYPTO_IMPORT_ERR is not None:
        raise RuntimeError(f"cryptography dependency unavailable: {_CRYPTO_IMPORT_ERR}")


def _decode_key(b64_value: str) -> bytes:
    raw = base64.b64decode(b64_value)
    if len(raw) != 32:
        raise ValueError("Data key must be exactly 32 bytes for AES-256-GCM")
    return raw


def _keyring_from_env() -> Keyring | None:
    settings = get_settings()
    data_key = os.getenv(settings.data_key_env)
    if not data_key:
        return None
    key_id = os.getenv("ECIMS_DATA_KEY_ID", "env-key")
    return Keyring(active_key_id=key_id, keys={key_id: _decode_key(data_key)})


def _keyring_from_file(path: Path) -> Keyring:
    body = json.loads(path.read_text(encoding="utf-8"))
    active = str(body.get("active_key_id", "")).strip()
    keys_obj = body.get("keys", {})
    if not active or not isinstance(keys_obj, dict):
        raise ValueError("Invalid keyring file format")
    keys: dict[str, bytes] = {}
    for key_id, key_b64 in keys_obj.items():
        keys[str(key_id)] = _decode_key(str(key_b64))
    if active not in keys:
        raise ValueError("active_key_id not present in keys")
    return Keyring(active_key_id=active, keys=keys)


def _resolve_keyring_path() -> Path:
    settings = get_settings()
    p = Path(settings.data_key_path)
    if p.is_absolute():
        return p
    root = Path(__file__).resolve().parents[3]
    return root / p


def load_keyring() -> Keyring:
    env_ring = _keyring_from_env()
    if env_ring is not None:
        return env_ring

    p = _resolve_keyring_path()
    if not p.exists():
        raise FileNotFoundError(f"Data keyring not found: {p}")
    return _keyring_from_file(p)


def _derive_purpose_key(master_key: bytes, purpose: str) -> bytes:
    _require_crypto()
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=f"ecims:{purpose}".encode("utf-8"))
    return hkdf.derive(master_key)


def _active_encryption_required() -> bool:
    settings = get_settings()
    _ = get_policy_state()  # ensure policy state is initialized for consistent startup ordering
    return settings.data_encryption_enabled


def get_crypto_status() -> CryptoStatus:
    required = _active_encryption_required()
    try:
        keyring = load_keyring()
        _require_crypto()
    except Exception as exc:  # noqa: BLE001
        if required:
            return CryptoStatus(False, None, 0, f"DATA_KEY_MISSING:{exc}")
        return CryptoStatus(False, None, 0, f"DISABLED_OR_MISSING_KEY:{exc}")

    return CryptoStatus(True, keyring.active_key_id, len(keyring.keys), "OK")


def _aad(purpose: str, key_id: str) -> bytes:
    return f"{purpose}:{key_id}".encode("utf-8")


def encrypt_bytes(purpose: str, plaintext: bytes) -> bytes:
    keyring = load_keyring()
    key_id = keyring.active_key_id
    mdk = keyring.keys[key_id]
    dkey = _derive_purpose_key(mdk, purpose)
    nonce = os.urandom(12)
    ct_tag = AESGCM(dkey).encrypt(nonce, plaintext, _aad(purpose, key_id))

    header = {
        "version": VERSION,
        "purpose": purpose,
        "key_id": key_id,
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    return MAGIC + len(header_bytes).to_bytes(2, "big") + header_bytes + nonce + ct_tag


def decrypt_bytes(purpose: str, encrypted_bytes: bytes) -> bytes:
    if not encrypted_bytes.startswith(MAGIC):
        raise ValueError("PLAINTEXT_INPUT")
    header_len = int.from_bytes(encrypted_bytes[len(MAGIC):len(MAGIC) + 2], "big")
    cursor = len(MAGIC) + 2
    header = json.loads(encrypted_bytes[cursor:cursor + header_len].decode("utf-8"))
    cursor += header_len
    nonce = encrypted_bytes[cursor:cursor + 12]
    ct_tag = encrypted_bytes[cursor + 12:]

    key_id = str(header.get("key_id", ""))
    hdr_purpose = str(header.get("purpose", ""))
    if hdr_purpose != purpose:
        raise ValueError("PURPOSE_MISMATCH")

    keyring = load_keyring()
    if key_id not in keyring.keys:
        raise ValueError("UNKNOWN_KEY_ID")
    dkey = _derive_purpose_key(keyring.keys[key_id], purpose)
    try:
        return AESGCM(dkey).decrypt(nonce, ct_tag, _aad(purpose, key_id))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("DECRYPT_FAILED") from exc


def encrypt_file(purpose: str, src_path: str | Path, dst_path: str | Path) -> None:
    src = Path(src_path)
    dst = Path(dst_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(encrypt_bytes(purpose, src.read_bytes()))


def decrypt_file(purpose: str, src_path: str | Path, dst_path: str | Path | None = None) -> bytes:
    src = Path(src_path)
    plain = decrypt_bytes(purpose, src.read_bytes())
    if dst_path is not None:
        dst = Path(dst_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(plain)
    return plain


def maybe_decrypt_legacy(purpose: str, blob: bytes) -> tuple[bytes, bool]:
    try:
        return decrypt_bytes(purpose, blob), True
    except ValueError as exc:
        if str(exc) == "PLAINTEXT_INPUT":
            return blob, False
        raise
