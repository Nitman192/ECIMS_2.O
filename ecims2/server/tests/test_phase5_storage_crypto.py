from __future__ import annotations

import base64
import json
import os
import tempfile
import unittest
from pathlib import Path


class TestPhase5StorageCrypto(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from app.security import storage_crypto as _mod  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"storage crypto deps unavailable: {exc}") from exc

    def tearDown(self) -> None:
        for k in ["ECIMS_DATA_KEY_B64", "ECIMS_DATA_KEY_ID", "ECIMS_DATA_KEY_PATH", "ECIMS_DB_PATH"]:
            os.environ.pop(k, None)
        from app.core.config import get_settings

        get_settings.cache_clear()

    def test_roundtrip_per_purpose(self) -> None:
        from app.security.storage_crypto import decrypt_bytes, encrypt_bytes

        os.environ["ECIMS_DATA_KEY_B64"] = base64.b64encode(b"a" * 32).decode("ascii")
        os.environ["ECIMS_DATA_KEY_ID"] = "k1"

        plain = b"hello-ecims"
        encrypted = encrypt_bytes("audit_export", plain)
        self.assertNotEqual(plain, encrypted)
        self.assertEqual(decrypt_bytes("audit_export", encrypted), plain)

    def test_wrong_key_fails_decrypt(self) -> None:
        from app.security.storage_crypto import decrypt_bytes, encrypt_bytes

        os.environ["ECIMS_DATA_KEY_B64"] = base64.b64encode(b"a" * 32).decode("ascii")
        os.environ["ECIMS_DATA_KEY_ID"] = "k1"
        encrypted = encrypt_bytes("archive_export", b"payload")

        os.environ["ECIMS_DATA_KEY_B64"] = base64.b64encode(b"b" * 32).decode("ascii")
        with self.assertRaises(ValueError):
            decrypt_bytes("archive_export", encrypted)

    def test_key_rotation_old_decrypt_new_encrypt(self) -> None:
        from app.core.config import get_settings
        from app.security.storage_crypto import decrypt_bytes, encrypt_bytes

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "keyring.json"
            keyring = {
                "active_key_id": "k1",
                "keys": {
                    "k1": base64.b64encode(b"a" * 32).decode("ascii"),
                    "k2": base64.b64encode(b"b" * 32).decode("ascii"),
                },
            }
            p.write_text(json.dumps(keyring), encoding="utf-8")
            os.environ["ECIMS_DATA_KEY_PATH"] = str(p)
            os.environ.pop("ECIMS_DATA_KEY_B64", None)
            get_settings.cache_clear()

            old_blob = encrypt_bytes("ai_artifact", b"v1")

            keyring["active_key_id"] = "k2"
            p.write_text(json.dumps(keyring), encoding="utf-8")
            get_settings.cache_clear()

            self.assertEqual(decrypt_bytes("ai_artifact", old_blob), b"v1")
            new_blob = encrypt_bytes("ai_artifact", b"v2")
            self.assertEqual(decrypt_bytes("ai_artifact", new_blob), b"v2")


if __name__ == "__main__":
    unittest.main()
