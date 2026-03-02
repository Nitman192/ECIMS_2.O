from __future__ import annotations

import importlib
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


def _load_client() -> TestClient:
    from app import main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_corrupt_policy_fails_startup_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        bad_policy = tmp / "bad.policy.json"
        bad_policy.write_text("{not-json", encoding="utf-8")

        monkeypatch.setenv("ECIMS_ENVIRONMENT", "prod")
        monkeypatch.setenv("ECIMS_JWT_SECRET", "x" * 32)
        monkeypatch.setenv("ECIMS_BOOTSTRAP_ADMIN_TOKEN", "bootstrap-token")
        monkeypatch.setenv("ECIMS_BOOTSTRAP_ADMIN_USERNAME", "admin-prod")
        monkeypatch.setenv("ECIMS_BOOTSTRAP_ADMIN_PASSWORD", "StrongPassw0rd!")
        monkeypatch.setenv("ECIMS_SECURITY_POLICY_PATH", str(bad_policy))
        monkeypatch.setenv("ECIMS_SECURITY_POLICY_SIG_PATH", str(tmp / "missing.sig"))
        monkeypatch.setenv("ECIMS_DEVICE_ALLOW_TOKEN_PRIVATE_KEY_PATH", str(tmp / "missing-private.pem"))
        get_settings.cache_clear()

        with pytest.raises(RuntimeError):
            with _load_client():
                pass


def test_kill_switch_enabled_returns_enabled_state(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("ECIMS_DB_PATH", str(Path(td) / "db.sqlite"))
        monkeypatch.setenv("ECIMS_ENVIRONMENT", "dev")
        get_settings.cache_clear()

        with _load_client() as client:
            login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            set_ks = client.post(
                "/api/v1/admin/device/kill-switch",
                headers=headers,
                json={"enabled": True, "reason": "recovery-drill"},
            )
            assert set_ks.status_code == 200
            rollout = client.get("/api/v1/admin/device/rollout/status", headers=headers)
            assert rollout.status_code == 200
            assert rollout.json()["kill_switch"] is True
