"""Tests for tamper-evident audit logging."""

from __future__ import annotations

import json

from la_gui.core.audit_log import AuditLogger


def test_audit_chain_verification_detects_tampering(tmp_path) -> None:
    log_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path)
    logger.append("root_key_generated", {"fingerprint": "abc"}, actor="operator")
    logger.append("license_signed", {"serial": "LIC-10"}, actor="operator")

    ok, message = logger.verify_chain()
    assert ok, message

    with log_path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()

    item = json.loads(lines[1])
    item["details"]["serial"] = "LIC-TAMPERED"
    lines[1] = json.dumps(item) + "\n"

    with log_path.open("w", encoding="utf-8") as handle:
        handle.writelines(lines)

    ok, message = logger.verify_chain()
    assert not ok
    assert "Invalid entry_hash" in message
