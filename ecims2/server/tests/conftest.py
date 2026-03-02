from __future__ import annotations

import pathlib

import pytest

LEGACY_FILES = {
    "test_phase1_smoke.py",
    "test_phase2_controls.py",
    "test_phase3_ai.py",
    "test_phase4_license.py",
    "test_phase61_revocation.py",
}

SECURITY_POSTURE_FILES = {
    "test_phase5_startup_encryption.py",
    "test_phase5_storage_crypto.py",
    "test_phase6_auth_rbac.py",
    "test_phase6_mtls.py",
    "test_phase6_mtls_integration.py",
    "test_phase7_hardening_operability.py",
    "test_phase8_device_enforcement_pilot.py",
    "test_policy_mtls_fields.py",
    "test_observability_and_health.py",
}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "current: release-blocking current behavior tests")
    config.addinivalue_line("markers", "legacy: retained historical behavior tests (non-blocking)")
    config.addinivalue_line("markers", "security_posture: authoritative security posture gate")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        name = pathlib.Path(str(item.fspath)).name
        if name in LEGACY_FILES:
            item.add_marker(pytest.mark.legacy)
        else:
            item.add_marker(pytest.mark.current)
        if name in SECURITY_POSTURE_FILES:
            item.add_marker(pytest.mark.security_posture)
