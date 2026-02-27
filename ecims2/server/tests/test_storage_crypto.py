from __future__ import annotations

import base64
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

if importlib.util.find_spec("cryptography") is not None:
    from app.security.storage_crypto import decrypt_token, encrypt_token
else:
    decrypt_token = encrypt_token = None


@unittest.skipIf(encrypt_token is None, "cryptography is not installed")
class TestStorageCrypto(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            keyring = Path(temp_dir) / "data_keyring.json"
            keyring.write_text(
                json.dumps(
                    {
                        "active_kid": "k1",
                        "keys": {"k1": base64.b64encode(b"a" * 32).decode("ascii")},
                    }
                ),
                encoding="utf-8",
            )
            os.environ["ECIMS_KEYRING_PATH"] = str(keyring)
            os.environ["ECIMS_ENVIRONMENT"] = "dev"
            encrypted = encrypt_token("token-123")
            self.assertTrue(encrypted.startswith("enc:k1:"))
            self.assertEqual(decrypt_token(encrypted), "token-123")
            os.environ.pop("ECIMS_KEYRING_PATH", None)
            os.environ.pop("ECIMS_ENVIRONMENT", None)

    def test_plaintext_fallback_forbidden_in_prod(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["ECIMS_KEYRING_PATH"] = str(Path(temp_dir) / "missing.json")
            os.environ["ECIMS_ENVIRONMENT"] = "prod"
            with self.assertRaises(RuntimeError):
                encrypt_token("token-123")
            with self.assertRaises(RuntimeError):
                decrypt_token("plain:token-123")
            os.environ.pop("ECIMS_KEYRING_PATH", None)
            os.environ.pop("ECIMS_ENVIRONMENT", None)


if __name__ == "__main__":
    unittest.main()
