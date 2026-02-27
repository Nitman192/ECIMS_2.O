from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path


class TestPhase5StartupEncryption(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi.testclient import TestClient  # noqa: F401
            from app.security import storage_crypto as _x  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"startup encryption test deps unavailable: {exc}") from exc

    def tearDown(self) -> None:
        for k in [
            "ECIMS_DB_PATH",
            "ECIMS_LICENSE_PATH",
            "ECIMS_LICENSE_PUBLIC_KEY_PATH",
            "ECIMS_DATA_KEY_B64",
            "ECIMS_DATA_KEY_PATH",
            "ECIMS_DATA_ENCRYPTION_ENABLED",
        ]:
            os.environ.pop(k, None)
        from app.core.config import get_settings

        get_settings.cache_clear()

    def test_fail_closed_when_required_and_key_missing(self) -> None:
        from fastapi.testclient import TestClient
        from app.core.config import get_settings
        from app import main as main_module

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(tmp / "missing-license.ecims")
            os.environ["ECIMS_DATA_ENCRYPTION_ENABLED"] = "true"
            os.environ["ECIMS_DATA_KEY_PATH"] = str(tmp / "no-keyring.json")
            get_settings.cache_clear()
            importlib.reload(main_module)

            with self.assertRaises(RuntimeError):
                with TestClient(main_module.app):
                    pass


if __name__ == "__main__":
    unittest.main()
