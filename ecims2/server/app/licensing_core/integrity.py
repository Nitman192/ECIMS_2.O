from __future__ import annotations

import hashlib
from pathlib import Path

# Hash of licensing_core/loader.py (SHA256). Update during release hardening when source changes.
EXPECTED_LOADER_SHA256 = "7a59cd477cbd38c88365683081565e35dc31e91d891d8f7cdf92a53601d8d6ee"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def check_licensing_integrity() -> tuple[bool, str]:
    loader_path = Path(__file__).resolve().parent / "loader.py"
    if not loader_path.exists():
        return False, "TAMPER_DETECTED"

    current_hash = _sha256_file(loader_path)
    if EXPECTED_LOADER_SHA256 == "TO_BE_FILLED":
        # Non-hardened dev mode compatibility.
        return True, "OK"
    if current_hash != EXPECTED_LOADER_SHA256:
        return False, "TAMPER_DETECTED"
    return True, "OK"
