from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import uuid


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.strip().lower() if ch.isalnum() or ch in "-_:")


def _run_wmic(args: list[str]) -> str:
    try:
        out = subprocess.check_output(["wmic", *args], stderr=subprocess.DEVNULL, text=True, timeout=5)
    except Exception:
        return ""
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if len(lines) >= 2:
        return _normalize(lines[1])
    return ""


def compute_machine_fingerprint() -> str:
    parts: list[str] = []
    if platform.system().lower().startswith("win"):
        parts.extend(
            [
                _run_wmic(["cpu", "get", "ProcessorId"]),
                _run_wmic(["bios", "get", "serialnumber"]),
                _run_wmic(["csproduct", "get", "uuid"]),
            ]
        )

    parts.append(_normalize(hex(uuid.getnode())[2:]))
    parts.append(_normalize(platform.node()))
    parts.append(_normalize(os.environ.get("COMPUTERNAME", "")))

    material = "|".join([p for p in parts if p]) or "fallback-ecims"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
